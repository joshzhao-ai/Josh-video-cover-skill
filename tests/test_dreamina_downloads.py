import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import execute_dreamina_manifest as executor


class DreaminaDownloadTests(unittest.TestCase):
    def test_retry_ignores_old_image_and_waits_for_current_submission(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            stale = root / "previous.png"
            Image.new("RGB", (30, 40), "red").save(stale)
            queries = []

            def fake_run(command):
                if command[1] != "query_result":
                    return '{"submit_id":"new-submission"}'
                target = Path(command[command.index("--download_dir") + 1])
                queries.append(target)
                if len(queries) == 1:
                    return '{"gen_status":"querying"}'
                Image.new("RGB", (30, 40), "blue").save(target / "new.png")
                return '{"gen_status":"success"}'

            with patch.object(executor, "run", side_effect=fake_run):
                result = executor.submit_and_download(
                    ["dreamina", "text2image"], root, timeout=2, interval=0
                )

            self.assertEqual(len(queries), 2)
            self.assertEqual(queries[0], queries[1])
            self.assertNotEqual(result.parent, root)
            with Image.open(result) as image:
                self.assertEqual(image.getpixel((0, 0)), (0, 0, 255))
            self.assertTrue(stale.exists())

    def test_failed_submission_does_not_deliver_downloaded_artifact(self):
        with tempfile.TemporaryDirectory() as directory:
            def fake_run(command):
                if command[1] != "query_result":
                    return '{"submit_id":"failed-submission"}'
                target = Path(command[command.index("--download_dir") + 1])
                Image.new("RGB", (30, 40)).save(target / "partial.png")
                return '{"gen_status":"fail"}'

            with patch.object(executor, "run", side_effect=fake_run):
                with self.assertRaisesRegex(RuntimeError, "generation failed"):
                    executor.submit_and_download(
                        ["dreamina", "text2image"], Path(directory), timeout=2, interval=0
                    )

    def test_wrong_ratio_is_rejected_without_modifying_image(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "vertical.png"
            Image.new("RGB", (300, 400)).save(path)
            original = path.read_bytes()
            with self.assertRaisesRegex(RuntimeError, "refusing to crop"):
                executor.validate_ratio(path, "4:3")
            self.assertEqual(path.read_bytes(), original)


if __name__ == "__main__":
    unittest.main()

import json
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

    def test_one_pixel_rounding_is_accepted_without_resizing(self):
        with tempfile.TemporaryDirectory() as directory:
            for ratio, size in (("3:4", (1087, 1448)), ("4:3", (1449, 1086))):
                with self.subTest(ratio=ratio):
                    path = Path(directory) / "rounded.png"
                    Image.new("RGB", size).save(path)
                    original = path.read_bytes()
                    executor.validate_ratio(path, ratio)
                    self.assertEqual(path.read_bytes(), original)
                    with self.assertRaises(RuntimeError):
                        executor.validate_ratio(path, ratio, relative_tolerance=0)

    def test_relative_ratio_tolerance_is_inclusive_and_limited_to_point_two_percent(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "ratio.png"
            Image.new("RGB", (1503, 2000)).save(path)
            executor.validate_ratio(path, "3:4")
            Image.new("RGB", (1504, 2000)).save(path)
            with self.assertRaises(RuntimeError):
                executor.validate_ratio(path, "3:4")
            for tolerance in (-0.001, 0.01, float("nan")):
                with self.subTest(tolerance=tolerance), self.assertRaises(ValueError):
                    executor.validate_ratio(path, "3:4", relative_tolerance=tolerance)

    def test_executor_honors_manifest_tolerance_for_existing_native_image(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            image_path = root / "rounded.png"
            Image.new("RGB", (1087, 1448)).save(image_path)
            manifest_path = root / "manifest.json"
            manifest = {"routes": [{
                "name": "test", "engine": "dreamina", "dreamina_command": ["dreamina", "text2image"],
                "expected_output": str(image_path), "ratio": "3:4",
            }]}
            manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
            with patch.object(sys, "argv", ["executor", "--manifest", str(manifest_path)]), patch.object(executor, "run") as run:
                executor.main()
                run.assert_not_called()
                manifest["review_contract"] = {"aspect_ratio": {"relative_tolerance": 0.0}}
                manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
                with self.assertRaises(RuntimeError):
                    executor.main()
                run.assert_not_called()


if __name__ == "__main__":
    unittest.main()

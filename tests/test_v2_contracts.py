import argparse
import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import codex_showcase_prompt_builder as builder
import cover_workflow_state as workflow


class V2ContractTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.video = self.root / "video.mp4"
        self.video.write_bytes(b"video")
        self.job = self.root / "cover_job.json"
        workflow.command_init(argparse.Namespace(job=str(self.job), video=str(self.video)))

    def tearDown(self):
        self.temp.cleanup()

    def write_analysis(self, has_person=True):
        analysis = {
            "content_summary": "讲清一个 AI 工具能完成什么任务",
            "hook_summary": "展示真实方法和结果",
            "verified_proof": [],
            "cover_promise": "看懂工具的实际价值",
            "proof_chain": ["输入问题", "调用工具", "得到结果"],
            "visual_proof_objects": ["结果成片", "方法文件"],
            "hero_object": "结果成片",
            "evidence_object": "方法文件",
            "content_reference_frames": [],
            "has_real_person": has_person,
            "portrait_frame_quality": "good",
        }
        path = self.root / "analysis.json"
        path.write_text(json.dumps(analysis, ensure_ascii=False), encoding="utf-8")
        workflow.command_record_analysis(argparse.Namespace(job=str(self.job), analysis=str(path)))
        return path

    def choose_copy(self, has_person=True):
        analysis = self.write_analysis(has_person=has_person)
        if has_person:
            workflow.command_choose_person(argparse.Namespace(
                job=str(self.job), mode="no-person", portrait="", pose_reference=""
            ))
        workflow.command_choose_title(argparse.Namespace(
            job=str(self.job), title="AI 工具", hook="到底能做什么", subtitle=""
        ))
        return analysis

    def builder_args(self, analysis, ratio="3:4", engine="image2", out_name="out"):
        return argparse.Namespace(
            analysis=str(analysis),
            job=str(self.job),
            title="",
            hook="",
            subtitle="",
            person_mode="auto",
            portrait="",
            pose_reference="",
            ratio=ratio,
            engine=engine,
            dreamina_model="auto",
            dreamina_mode="recipe-direct",
            dreamina_use_selected_cover=True,
            dreamina_resolution="2k",
            style_profile="none",
            style_reference=[],
            content_reference=[],
            source_cover="",
            source_route="",
            routes=[],
            out=str(self.root / out_name),
        )

    def test_title_cannot_bypass_person_gate(self):
        self.write_analysis(has_person=True)
        with self.assertRaises(SystemExit):
            workflow.command_choose_title(argparse.Namespace(
                job=str(self.job), title="概率实验", hook="真是50%吗", subtitle=""
            ))
        job = workflow.load_job(self.job)
        self.assertEqual(job["phase"], "awaiting_person_choice")

    def test_landscape_requires_selected_vertical(self):
        self.choose_copy(has_person=False)
        with self.assertRaises(SystemExit):
            workflow.command_assert_ready(argparse.Namespace(job=str(self.job), ratio="4:3"))

    def test_three_vertical_routes_are_distinct(self):
        analysis = self.choose_copy(has_person=False)
        args = self.builder_args(analysis)
        builder.build_requests(args)
        manifest = json.loads((Path(args.out) / "cover_requests.json").read_text(encoding="utf-8"))
        routes = manifest["routes"]
        self.assertEqual(len(routes), 3)
        self.assertEqual(len({item["parent_route"] for item in routes}), 3)
        self.assertEqual(len({item["creative_route"]["layout"] for item in routes}), 3)

    def test_dreamina_landscape_uses_selected_cover_by_default(self):
        analysis = self.choose_copy(has_person=False)
        vertical = self.root / "selected.png"
        vertical.write_bytes(b"image")
        workflow.command_register_candidate(argparse.Namespace(
            job=str(self.job), ratio="3:4", route="outcome_editorial",
            image=str(vertical), manifest=""
        ))
        workflow.command_select_vertical(argparse.Namespace(
            job=str(self.job), image="", route="outcome_editorial"
        ))
        original_resolver = builder.resolve_dreamina_model
        builder.resolve_dreamina_model = lambda requested: {
            "cli": "dreamina", "resolved_model": "5.0-pro", "pro_available": True
        }
        try:
            args = self.builder_args(analysis, ratio="4:3", engine="dreamina", out_name="landscape")
            builder.build_requests(args)
        finally:
            builder.resolve_dreamina_model = original_resolver
        manifest = json.loads((Path(args.out) / "cover_requests.json").read_text(encoding="utf-8"))
        self.assertEqual(len(manifest["routes"]), 2)
        for route in manifest["routes"]:
            self.assertIn("selected_vertical_reference", route["reference_roles"])
            self.assertIn(str(vertical.resolve()), route["reference_images"])

    def test_product_interaction_requires_official_asset(self):
        analysis = self.choose_copy(has_person=False)
        args = self.builder_args(analysis)
        args.style_profile = "creator_product_interaction"
        with self.assertRaises(SystemExit):
            builder.build_requests(args)


if __name__ == "__main__":
    unittest.main()

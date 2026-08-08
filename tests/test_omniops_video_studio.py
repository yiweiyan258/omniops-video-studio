import importlib.util
import json
import os
import stat
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
LIBRARY = ROOT / "backend/omniops_video_studio_lib.py"
CLI = ROOT / "backend/omniops-video-studio-cli.py"
DESKTOP_ROOT = ROOT


def load_library():
    spec = importlib.util.spec_from_file_location(
        "omniops_video_studio_lib",
        LIBRARY,
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class VideoStudioBootstrapTests(unittest.TestCase):
    def test_shared_video_studio_library_exists(self):
        self.assertTrue(
            LIBRARY.is_file(),
            "the shared desktop/WeChat video application CLI library is missing",
        )
        spec = importlib.util.spec_from_file_location(
            "omniops_video_studio_lib",
            LIBRARY,
        )
        self.assertIsNotNone(spec)

    def test_shared_library_exposes_application_service_contract(self):
        module = load_library()
        required = (
            "VideoStudioConfig",
            "VideoStudioStore",
            "VideoStudioService",
            "WorkbenchRunner",
            "PolicyViolation",
        )
        missing = [name for name in required if not hasattr(module, name)]
        self.assertEqual([], missing)

    def test_application_cli_entrypoint_exists(self):
        self.assertTrue(
            CLI.is_file(),
            "the packaged desktop/WeChat CLI entrypoint is missing",
        )


class VideoStudioServiceTests(unittest.TestCase):
    def setUp(self):
        self.module = load_library()
        self.temp_dir = tempfile.TemporaryDirectory()
        self.root = Path(self.temp_dir.name)
        self.log_path = self.root / "workbench-invocations.jsonl"
        self.workbench = self.root / "fake-workbench.py"
        self.workbench.write_text(
            """#!/usr/bin/env python3
import json
import sys
from pathlib import Path

log_path = Path(sys.argv[sys.argv.index("--test-log") + 1])
argv = [arg for index, arg in enumerate(sys.argv[1:]) if index not in {
    sys.argv[1:].index("--test-log"),
    sys.argv[1:].index("--test-log") + 1,
}]
with log_path.open("a", encoding="utf-8") as handle:
    handle.write(json.dumps({"argv": argv}, ensure_ascii=False) + "\\n")

command = argv[0]
merchant = argv[argv.index("--merchant-id") + 1] if "--merchant-id" in argv else None
if command == "doctor":
    payload = {"schema": "fake.doctor.v1", "status": "PASS"}
elif command == "start":
    run_dir = log_path.parent / "runs" / ("run-" + merchant)
    workflow = run_dir / "workflow"
    workflow.mkdir(parents=True, exist_ok=True)
    app_state = workflow / "video_creation_app_state.json"
    app_state.write_text(json.dumps({
        "schema": "omniops.video_creation_app_state.v1",
        "status": "ACTIVE",
        "writesExternalSystems": False,
    }), encoding="utf-8")
    payload = {
        "schema": "omniops.video_workbench_start.v1",
        "status": "PASS",
        "merchantId": merchant,
        "runDir": str(run_dir),
        "appStatePath": str(app_state),
        "nextAllowedAction": "REVIEW_CREATIVE_CANDIDATES",
    }
elif command in {"status", "next"}:
    payload = {
        "schema": "omniops.video_workbench_status.v1",
        "status": "PASS",
        "blocked": False,
        "merchantId": merchant,
        "nextAllowedAction": "WAIT_EXPLICIT_PAID_SEEDANCE_AUTHORIZATION",
        "professionalWorkerTeam": {
            "status": "ACTIVE",
            "taskState": "IN_PROGRESS",
            "stageStates": {
                "producer_intake": "PASS",
                "material_evidence": "ACTIVE",
            },
        },
    }
elif command == "acceptance":
    payload = {
        "schema": "omniops.video_workbench_acceptance.v1",
        "status": "PASS",
        "merchantId": merchant,
        "finalVideo": str(log_path.parent / "final.mp4"),
    }
elif command == "run":
    payload = {
        "schema": "omniops.video_workbench_run.v1",
        "status": "PASS",
        "merchantId": merchant,
        "step": argv[argv.index("--step") + 1],
    }
else:
    payload = {"schema": "fake.error.v1", "status": "BLOCKED"}
payload["writesExternalSystems"] = False
print(json.dumps(payload, ensure_ascii=False))
""",
            encoding="utf-8",
        )
        self.workbench.chmod(self.workbench.stat().st_mode | stat.S_IXUSR)
        config = self.module.VideoStudioConfig(
            data_root=self.root / "data",
            workbench_command=(
                sys.executable,
                str(self.workbench),
                "--test-log",
                str(self.log_path),
            ),
            timeout_seconds=10,
        )
        store = self.module.VideoStudioStore(config.database_path)
        store.initialize()
        runner = self.module.WorkbenchRunner(
            config.workbench_command,
            timeout_seconds=config.timeout_seconds,
        )
        self.service = self.module.VideoStudioService(config, store, runner)

    def tearDown(self):
        self.temp_dir.cleanup()

    def submit(self, *, source="desktop", duration_seconds=52):
        return self.service.submit(
            {
                "merchantId": "xiaoyuanli",
                "goal": "胜哥开庭第一集，人物剧情短视频",
                "media": [str(self.root / "front.jpg")],
                "source": source,
                "targetDurationSeconds": duration_seconds,
            }
        )

    def invocations(self):
        return [
            json.loads(line)
            for line in self.log_path.read_text(encoding="utf-8").splitlines()
        ]

    def test_desktop_submit_delegates_to_canonical_workbench_and_persists_job(self):
        result = self.submit()
        self.assertEqual("desktop", result["source"])
        self.assertEqual("xiaoyuanli", result["merchantId"])
        self.assertEqual("platform_independent", result["productionMode"])
        self.assertEqual(52, result["targetDurationSeconds"])
        self.assertEqual([15, 15, 15, 7], [
            unit["durationSeconds"] for unit in result["generationUnitPlan"]["units"]
        ])
        self.assertEqual("PASS", result["workbenchStatus"])
        self.assertEqual("REVIEW_CREATIVE_CANDIDATES", result["nextAllowedAction"])
        self.assertTrue(Path(result["runDir"]).is_dir())
        self.assertFalse(result["writesExternalSystems"])

        invocation = self.invocations()[0]["argv"]
        self.assertEqual("start", invocation[0])
        self.assertIn("--format", invocation)
        self.assertEqual("json", invocation[invocation.index("--format") + 1])
        self.assertIn("--write-report", invocation)
        self.assertNotIn("--platform", invocation)
        compiled_goal = invocation[invocation.index("--goal") + 1]
        self.assertIn("目标成片时长：52秒", compiled_goal)
        self.assertIn("15+15+15+7", compiled_goal)

        request_contract = json.loads(
            (
                Path(result["runDir"])
                / "workflow"
                / "video_studio_request_contract.json"
            ).read_text(encoding="utf-8")
        )
        self.assertEqual(52, request_contract["targetDurationSeconds"])
        self.assertEqual(4, request_contract["generationUnitPlan"]["unitCount"])
        self.assertFalse(request_contract["requiresPlatformOrAccount"])

        listed = self.service.list_jobs()
        self.assertEqual(1, listed["count"])
        self.assertEqual(result["jobId"], listed["jobs"][0]["jobId"])
        self.assertFalse(listed["writesExternalSystems"])

    def test_material_analysis_reports_real_local_assets_without_inventing_business_facts(self):
        image = self.root / "store-front.jpg"
        video = self.root / "dish-closeup.mp4"
        image.write_bytes(b"image-bytes")
        video.write_bytes(b"video-bytes")

        result = self.service.analyze_materials(
            {
                "merchantId": "xiaoyuanli",
                "media": [str(image), str(video)],
            }
        )

        self.assertEqual("omniops.video_studio_material_analysis.v1", result["schema"])
        self.assertEqual("PASS_LOCAL_MATERIAL_INTAKE", result["status"])
        self.assertEqual(2, result["mediaCount"])
        self.assertEqual(["image", "video"], [
            item["kind"] for item in result["assetObservations"]
        ])
        self.assertEqual(["store-front.jpg", "dish-closeup.mp4"], [
            item["name"] for item in result["assetObservations"]
        ])
        self.assertEqual([], result["insight"]["productFeatures"])
        self.assertEqual([], result["insight"]["coreSellingPoints"])
        self.assertEqual([], result["insight"]["targetAudiences"])
        self.assertEqual([], result["insight"]["usageScenarios"])
        self.assertEqual(
            "REQUIRES_PROFESSIONAL_MATERIAL_WORKER",
            result["insight"]["evidenceStatus"],
        )
        self.assertFalse(result["writesExternalSystems"])

    def test_creation_blueprint_compiles_candidates_and_model_bounded_units(self):
        result = self.module.compile_creation_blueprint(
            {
                "goal": "用夜宵场景表现朋友聚餐的真实烟火气",
                "productFeatures": ["现熬牛杂", "夜间营业"],
                "coreSellingPoints": ["真材实料", "适合朋友聚餐"],
                "targetAudiences": ["本地年轻人"],
                "usageScenarios": ["朋友夜宵"],
                "contentType": "同城种草",
                "shootingStyle": "快节奏反转",
                "audioMode": "旁白 + BGM",
                "supplement": "前三秒先展示热气与端锅动作",
                "referenceVideo": "",
                "durationSeconds": 52,
                "candidateCount": 3,
            }
        )

        self.assertEqual("omniops.video_studio_creation_blueprint.v1", result["schema"])
        self.assertEqual("PASS_CREATION_BLUEPRINT", result["status"])
        self.assertEqual(3, len(result["candidates"]))
        self.assertEqual([15, 15, 15, 7], [
            unit["durationSeconds"] for unit in result["generationUnitPlan"]["units"]
        ])
        self.assertEqual(
            ["开场钩子", "场景推进", "核心兑现", "结尾回收"],
            [beat["label"] for beat in result["candidates"][0]["beats"]],
        )
        self.assertTrue(all(candidate["status"] == "DRAFT_FOR_WORKER_REWRITE" for candidate in result["candidates"]))
        self.assertFalse(result["writesExternalSystems"])

    def test_submit_persists_structured_creation_brief_for_professional_workers(self):
        creation_brief = {
            "productFeatures": ["胜哥本人出镜"],
            "coreSellingPoints": ["人物反差"],
            "targetAudiences": ["本地年轻人"],
            "usageScenarios": ["夜宵聚餐"],
            "contentType": "人物剧情",
            "shootingStyle": "电影感叙事",
            "audioMode": "角色对白 + BGM",
            "supplement": "不使用站桩口播",
            "referenceVideo": "",
            "selectedCandidateId": "candidate-01",
        }
        result = self.service.submit(
            {
                "merchantId": "xiaoyuanli",
                "goal": "胜哥人物剧情",
                "media": [],
                "source": "desktop",
                "targetDurationSeconds": 30,
                "creationBrief": creation_brief,
            }
        )

        request_contract = json.loads(
            (
                Path(result["runDir"])
                / "workflow"
                / "video_studio_request_contract.json"
            ).read_text(encoding="utf-8")
        )
        self.assertEqual(creation_brief, request_contract["creationBrief"])
        self.assertEqual(creation_brief, result["creationBrief"])

    def test_weixin_and_desktop_sources_share_the_same_job_store(self):
        desktop = self.submit(source="desktop")
        weixin = self.submit(source="weixin")
        listed = self.service.list_jobs()
        self.assertEqual(2, listed["count"])
        self.assertEqual({"desktop", "weixin"}, {job["source"] for job in listed["jobs"]})
        self.assertNotEqual(desktop["jobId"], weixin["jobId"])

    def test_status_refresh_uses_the_job_run_directory_and_updates_workers(self):
        submitted = self.submit(source="weixin")
        refreshed = self.service.job_status(submitted["jobId"], refresh=True)
        self.assertEqual(
            "WAIT_EXPLICIT_PAID_SEEDANCE_AUTHORIZATION",
            refreshed["nextAllowedAction"],
        )
        self.assertEqual("ACTIVE", refreshed["professionalWorkerTeam"]["status"])
        invocation = self.invocations()[-1]["argv"]
        self.assertEqual("status", invocation[0])
        self.assertEqual(
            submitted["runDir"],
            invocation[invocation.index("--draft-dir") + 1],
        )
        self.assertFalse(refreshed["writesExternalSystems"])

    def test_forbidden_platform_and_account_actions_are_rejected_before_invocation(self):
        submitted = self.submit()
        initial_count = len(self.invocations())
        for action in (
            "publish",
            "upload",
            "comment",
            "like",
            "follow",
            "delete",
            "account-control",
        ):
            with self.subTest(action=action):
                with self.assertRaises(self.module.PolicyViolation):
                    self.service.execute(submitted["jobId"], action, {})
        self.assertEqual(initial_count, len(self.invocations()))

    def test_paid_generation_requires_unique_explicit_authorization(self):
        submitted = self.submit()
        with self.assertRaises(self.module.PolicyViolation):
            self.service.execute(
                submitted["jobId"],
                "run-step",
                {"step": "ai-video-sequential-executor-execute-next"},
            )

        executed = self.service.execute(
            submitted["jobId"],
            "run-step",
            {
                "step": "ai-video-sequential-executor-execute-next",
                "paidAuthorizationId": "paid-auth-001",
            },
        )
        self.assertEqual("PASS", executed["workbenchStatus"])
        self.assertFalse(executed["writesExternalSystems"])
        invocation = self.invocations()[-1]["argv"]
        self.assertEqual(
            "paid-auth-001",
            invocation[invocation.index("--paid-authorization-id") + 1],
        )

        with self.assertRaises(self.module.PolicyViolation):
            self.service.execute(
                submitted["jobId"],
                "run-step",
                {
                    "step": "ai-video-sequential-executor-execute-next",
                    "paidAuthorizationId": "paid-auth-001",
                },
            )

    def test_safe_local_actions_never_need_paid_authorization(self):
        submitted = self.submit()
        result = self.service.execute(
            submitted["jobId"],
            "run-step",
            {"step": "preflight"},
        )
        self.assertEqual("PASS", result["workbenchStatus"])
        invocation = self.invocations()[-1]["argv"]
        self.assertEqual("preflight", invocation[invocation.index("--step") + 1])
        self.assertNotIn("--paid-authorization-id", invocation)

    def test_unknown_merchant_and_source_fail_closed(self):
        base = {
            "merchantId": "unknown-merchant",
            "goal": "test",
            "source": "desktop",
            "targetDurationSeconds": 30,
        }
        with self.assertRaises(self.module.PolicyViolation):
            self.service.submit(base)
        base["merchantId"] = "xiaoyuanli"
        base["source"] = "browser-extension"
        with self.assertRaises(self.module.PolicyViolation):
            self.service.submit(base)

    def test_target_duration_must_be_between_fifteen_and_sixty_seconds(self):
        for duration in (14, 61):
            with self.subTest(duration=duration):
                with self.assertRaises(self.module.PolicyViolation):
                    self.submit(duration_seconds=duration)

    def test_generation_units_cover_duration_without_exceeding_model_limit(self):
        compile_units = self.module.compile_generation_units
        self.assertEqual(
            [15, 15, 15, 7],
            [unit["durationSeconds"] for unit in compile_units(52)["units"]],
        )
        self.assertEqual(
            [15, 15, 15, 15],
            [unit["durationSeconds"] for unit in compile_units(60)["units"]],
        )
        self.assertTrue(
            all(
                unit["durationSeconds"] <= 15
                for unit in compile_units(60)["units"]
            )
        )

    def test_legacy_jobs_without_duration_contract_remain_fifteen_seconds(self):
        submitted = self.submit(duration_seconds=30)
        with self.service.store.connect() as connection:
            connection.execute(
                """
                UPDATE video_jobs
                SET request_json = ?, target_duration_seconds = 30,
                    generation_unit_plan_json = '{}'
                WHERE job_id = ?
                """,
                (
                    json.dumps(
                        {
                            "merchantId": "xiaoyuanli",
                            "platform": "douyin_video",
                            "goal": "legacy fifteen second task",
                            "media": [],
                            "source": "desktop",
                        }
                    ),
                    submitted["jobId"],
                ),
            )

        legacy = self.service.store.get_job(submitted["jobId"])

        self.assertEqual(15, legacy["targetDurationSeconds"])
        self.assertEqual(1, legacy["generationUnitPlan"]["unitCount"])


class VideoStudioCliTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.root = Path(self.temp_dir.name)
        self.workbench = self.root / "fake-cli-workbench.py"
        self.workbench.write_text(
            """#!/usr/bin/env python3
import json
import sys
from pathlib import Path

command = sys.argv[1]
merchant = sys.argv[sys.argv.index("--merchant-id") + 1] if "--merchant-id" in sys.argv else None
if command == "start":
    run_dir = Path(__file__).parent / "runs" / ("run-" + merchant)
    (run_dir / "workflow").mkdir(parents=True, exist_ok=True)
    payload = {
        "status": "PASS",
        "merchantId": merchant,
        "runDir": str(run_dir),
        "appStatePath": str(run_dir / "workflow/video_creation_app_state.json"),
        "nextAllowedAction": "REVIEW_CREATIVE_CANDIDATES",
    }
elif command in {"status", "next"}:
    payload = {
        "status": "PASS",
        "blocked": False,
        "merchantId": merchant,
        "nextAllowedAction": "WAIT_EXPLICIT_PAID_SEEDANCE_AUTHORIZATION",
    }
else:
    payload = {"status": "PASS"}
payload["writesExternalSystems"] = False
print(json.dumps(payload, ensure_ascii=False))
""",
            encoding="utf-8",
        )
        self.workbench.chmod(self.workbench.stat().st_mode | stat.S_IXUSR)
        self.env = os.environ.copy()
        self.env["OMNIOPS_VIDEO_DATA"] = str(self.root / "data")
        self.env["OMNIOPS_VIDEO_WORKBENCH"] = str(self.workbench)

    def tearDown(self):
        self.temp_dir.cleanup()

    def run_cli(self, *arguments, expected_code=0):
        completed = subprocess.run(
            [sys.executable, str(CLI), *arguments],
            capture_output=True,
            text=True,
            env=self.env,
            check=False,
        )
        self.assertEqual(expected_code, completed.returncode, completed.stderr)
        self.assertTrue(completed.stdout.strip(), "CLI returned no JSON")
        return json.loads(completed.stdout)

    def test_cli_manifest_declares_local_only_shared_runtime(self):
        result = self.run_cli("manifest")
        self.assertEqual("omniops.video_studio_manifest.v1", result["schema"])
        self.assertEqual("omniops-video-workbench", result["productionCore"])
        self.assertEqual(["desktop", "weixin", "codex"], result["clients"])
        self.assertFalse(result["writesExternalSystems"])
        self.assertFalse(result["capabilities"]["platformPublishing"])
        self.assertFalse(result["capabilities"]["accountControl"])
        self.assertTrue(result["capabilities"]["platformIndependentCreation"])
        self.assertFalse(result["requirements"]["platformOrAccount"])
        self.assertEqual(
            {"min": 15, "max": 60},
            result["durationPolicy"]["finalVideoSeconds"],
        )
        self.assertIn("analyze", result["commands"])
        self.assertIn("compile-brief", result["commands"])
        self.assertTrue(result["capabilities"]["localMaterialIntake"])
        self.assertTrue(result["capabilities"]["structuredCreationBrief"])

    def test_cli_analyze_and_compile_brief_are_local_prespend_commands(self):
        image = self.root / "dish.jpg"
        image.write_bytes(b"image")
        analyzed = self.run_cli(
            "analyze",
            "--merchant-id",
            "xiaoyuanli",
            "--media",
            str(image),
        )
        self.assertEqual("PASS_LOCAL_MATERIAL_INTAKE", analyzed["status"])
        self.assertFalse(analyzed["writesExternalSystems"])

        brief = {
            "goal": "餐饮同城种草",
            "productFeatures": ["菜品近景"],
            "coreSellingPoints": ["现做"],
            "targetAudiences": ["附近顾客"],
            "usageScenarios": ["朋友聚餐"],
            "contentType": "同城种草",
            "shootingStyle": "真实素材混剪",
            "audioMode": "旁白 + BGM",
            "supplement": "",
            "referenceVideo": "",
            "durationSeconds": 30,
            "candidateCount": 2,
        }
        compiled = self.run_cli(
            "compile-brief",
            "--brief-json",
            json.dumps(brief, ensure_ascii=False),
        )
        self.assertEqual("PASS_CREATION_BLUEPRINT", compiled["status"])
        self.assertEqual(2, len(compiled["candidates"]))
        self.assertFalse(compiled["writesExternalSystems"])

    def test_cli_submit_and_list_use_the_same_data_root(self):
        submitted = self.run_cli(
            "submit",
            "--merchant-id",
            "xiaoyuanli",
            "--goal",
            "胜哥开庭人物剧情短视频",
            "--duration-seconds",
            "52",
            "--source",
            "weixin",
        )
        self.assertEqual("weixin", submitted["source"])
        self.assertEqual(52, submitted["targetDurationSeconds"])
        self.assertEqual("platform_independent", submitted["productionMode"])
        listed = self.run_cli("list")
        self.assertEqual(1, listed["count"])
        self.assertEqual(submitted["jobId"], listed["jobs"][0]["jobId"])
        self.assertFalse(listed["writesExternalSystems"])

    def test_cli_forbidden_action_returns_policy_error_json(self):
        submitted = self.run_cli(
            "submit",
            "--merchant-id",
            "xiaoyuanli",
            "--goal",
            "人物剧情视频",
            "--duration-seconds",
            "30",
            "--source",
            "desktop",
        )
        result = self.run_cli(
            "execute",
            "--job-id",
            submitted["jobId"],
            "--action",
            "publish",
            expected_code=2,
        )
        self.assertEqual("POLICY_BLOCKED", result["status"])
        self.assertFalse(result["writesExternalSystems"])


class VideoStudioDesktopSourceTests(unittest.TestCase):
    def test_tauri_desktop_application_source_is_complete(self):
        required = (
            DESKTOP_ROOT / "package.json",
            DESKTOP_ROOT / "index.html",
            DESKTOP_ROOT / "src/main.ts",
            DESKTOP_ROOT / "src/styles.css",
            DESKTOP_ROOT / "src-tauri/Cargo.toml",
            DESKTOP_ROOT / "src-tauri/src/main.rs",
            DESKTOP_ROOT / "src-tauri/tauri.conf.json",
            DESKTOP_ROOT / "src-tauri/tauri.windows.conf.json",
            DESKTOP_ROOT / "src-tauri/capabilities/default.json",
        )
        missing = [str(path.relative_to(ROOT)) for path in required if not path.is_file()]
        self.assertEqual([], missing)

        tauri = json.loads(
            (DESKTOP_ROOT / "src-tauri/tauri.conf.json").read_text(encoding="utf-8")
        )
        resources = tauri["bundle"]["resources"]
        self.assertEqual(
            {
                "../backend/omniops-video-studio-cli.py",
                "../backend/omniops_video_studio_lib.py",
            },
            set(resources),
        )

    def test_desktop_intake_is_platform_free_and_supports_up_to_sixty_seconds(self):
        source = (DESKTOP_ROOT / "src/main.ts").read_text(encoding="utf-8")
        self.assertNotIn('id="platform"', source)
        self.assertNotIn('"--platform"', source)
        self.assertIn('id="duration-seconds"', source)
        self.assertIn('"--duration-seconds"', source)
        self.assertIn('max="60"', source)

    def test_desktop_uses_upload_first_four_step_creation_wizard(self):
        source = (DESKTOP_ROOT / "src/main.ts").read_text(encoding="utf-8")
        self.assertIn('class="creation-steps"', source)
        self.assertIn('data-step="1"', source)
        self.assertIn('data-step="2"', source)
        self.assertIn('data-step="3"', source)
        self.assertIn('data-step="4"', source)
        self.assertIn("上传素材", source)
        self.assertIn("内容分析", source)
        self.assertIn("视频方案", source)
        self.assertIn("创作脚本", source)
        self.assertIn('id="target-audience"', source)
        self.assertIn('id="recommended-scene"', source)
        self.assertIn('class="professional-details"', source)
        self.assertNotIn('class="job-sidebar"', source)
        self.assertIn('command(["analyze"', source)
        self.assertIn('command(["compile-brief"', source)
        self.assertIn("核心卖点", source)
        self.assertIn("目标人群", source)
        self.assertIn("使用场景", source)
        self.assertIn("复刻参考视频", source)
        self.assertIn("创意方向候选", source)
        self.assertIn('"--brief-json"', source)

    def test_desktop_dev_server_matches_tauri_dev_url(self):
        package = json.loads(
            (DESKTOP_ROOT / "package.json").read_text(encoding="utf-8")
        )
        self.assertIn("--port 1420", package["scripts"]["dev"])
        self.assertIn("--strictPort", package["scripts"]["dev"])

    def test_packaged_python_cli_cannot_mutate_signed_application_resources(self):
        launcher = (DESKTOP_ROOT / "src-tauri/src/main.rs").read_text(
            encoding="utf-8"
        )
        self.assertIn('env("PYTHONDONTWRITEBYTECODE", "1")', launcher)
        self.assertIn('.join("backend")', launcher)
        self.assertNotIn(".hermes", launcher)

        library = LIBRARY.read_text(encoding="utf-8")
        self.assertIn('Path.home() / ".omniops"', library)
        self.assertNotIn(".hermes", library)

    def test_runtime_package_exposes_one_weixin_bridge_without_platform_writes(self):
        package_root = ROOT / "runtime"
        manifest_path = package_root / "video-studio-runtime-package.json"
        bridge_path = package_root / "weixin-video-studio-bridge"
        self.assertTrue(manifest_path.is_file())
        self.assertTrue(bridge_path.is_file())

        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        self.assertEqual("omniops-video-workbench", manifest["productionCore"])
        self.assertEqual(
            "backend/omniops-video-studio-cli.py",
            manifest["applicationCli"],
        )
        self.assertEqual(["desktop", "weixin", "codex"], manifest["clients"])
        self.assertFalse(manifest["writesExternalSystems"])
        self.assertFalse(manifest["capabilities"]["platformPublishing"])
        self.assertFalse(manifest["capabilities"]["engagementActions"])
        self.assertFalse(manifest["capabilities"]["accountControl"])

        bridge = bridge_path.read_text(encoding="utf-8")
        self.assertIn("omniops-video-studio-cli.py", bridge)
        self.assertIn("backend/omniops-video-studio-cli.py", bridge)
        self.assertNotIn("omniops-video-workbench.py", bridge)
        for forbidden in (" publish", " upload", " comment", " like", " follow"):
            self.assertNotIn(forbidden, bridge.lower())

    def test_windows_installer_sources_are_portable_and_verify_boundaries(self):
        required = (
            DESKTOP_ROOT / ".env.example",
            DESKTOP_ROOT / "README.md",
            DESKTOP_ROOT / "packaging/video-studio-cli.spec",
            DESKTOP_ROOT / "packaging/build-windows.ps1",
            DESKTOP_ROOT / "packaging/verify-package.ps1",
            DESKTOP_ROOT / "packaging/requirements-build.txt",
        )
        missing = [str(path.relative_to(ROOT)) for path in required if not path.is_file()]
        self.assertEqual([], missing)

        combined = "\n".join(path.read_text(encoding="utf-8") for path in required)
        self.assertNotIn("/Users/xiaoyu", combined)
        self.assertNotIn("xai-", combined)
        self.assertNotIn("AQ.", combined)
        self.assertIn("OmniOpsVideoStudio-Setup-x64.exe", combined)
        self.assertIn("omniops-video-studio-cli", combined)
        self.assertIn("Get-FileHash", combined)
        self.assertIn("writesExternalSystems", combined)
        self.assertIn("platformIndependent", combined)
        self.assertIn("finalVideoMaxSeconds", combined)
        self.assertIn("generationUnitMaxSeconds", combined)
        self.assertIn('app_root / "backend"', combined)


if __name__ == "__main__":
    unittest.main()

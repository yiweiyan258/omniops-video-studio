"""Shared local-only application service for OmniOps Video Studio."""

from __future__ import annotations

import json
import os
import re
import sqlite3
import subprocess
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping, Sequence


SCHEMA_VERSION = "omniops.video_studio_job.v2"
MIN_FINAL_VIDEO_SECONDS = 15
MAX_FINAL_VIDEO_SECONDS = 60
MAX_GENERATION_UNIT_SECONDS = 15
MAX_CREATIVE_CANDIDATES = 4
ALLOWED_MERCHANTS = frozenset({"muyi", "tanwei", "xiaoyuanli", "zuotingyouyuan"})
IMAGE_EXTENSIONS = frozenset({".jpg", ".jpeg", ".png", ".webp"})
VIDEO_EXTENSIONS = frozenset({".mp4", ".mov", ".m4v"})
ALLOWED_PLATFORMS = frozenset(
    {"douyin_video", "generic", "wechat_channels_video", "xhs_video"}
)
ALLOWED_SOURCES = frozenset({"desktop", "weixin", "codex"})
FORBIDDEN_ACTIONS = frozenset(
    {
        "publish",
        "upload",
        "submit-review",
        "comment",
        "like",
        "follow",
        "delete",
        "account-control",
        "account_control",
    }
)
SAFE_LOCAL_STEPS = frozenset(
    {
        "preflight",
        "create-brief",
        "validate-brief",
        "script-qc",
        "voice-qc",
        "fast-qc",
        "audio-qc",
        "manifest",
        "creative-workflow-verify",
        "ai-short-drama-dryrun",
        "ai-short-drama-canary-readiness",
        "ai-short-drama-canary-dispatch-plan",
        "ai-director-script-v2",
        "ai-short-drama-professional-compile",
        "ai-short-drama-p0-prepare",
        "ai-video-sequential-executor-prepare",
        "ai-video-sequential-executor-record-qc",
        "ai-video-shot-90-qc",
        "ai-video-object-shot-90-qc",
        "ai-video-human-reaction-shot-90-qc",
        "ai-video-assembly-lineage",
        "ai-video-post-production-90-qc",
        "ai-video-90-evidence-compile",
        "ai-video-capability-90-audit",
        "ai-video-commercial-evidence-package",
        "ai-video-commercial-production-contract",
    }
)
PAID_STEPS = frozenset({"ai-video-sequential-executor-execute-next"})
SAFE_ARGUMENT_FLAGS = {
    "topic": "--topic",
    "officialAssetId": "--official-asset-id",
    "canaryVideo": "--canary-video",
    "postPlan": "--post-plan",
    "shotVideo": "--shot-video",
    "shotContract": "--shot-contract",
    "expectedDialogue": "--expected-dialogue",
    "sequentialExecutorState": "--sequential-executor-state",
    "shotQcReport": "--shot-qc-report",
    "shotTakeReview": "--shot-take-review",
    "sourceShotVideo": "--source-shot-video",
    "localReviewPackage": "--local-review-package",
}


class PolicyViolation(ValueError):
    """Raised when an application request crosses the local-only boundary."""


class VideoStudioConfig:
    """Portable runtime configuration for the shared application service."""

    def __init__(
        self,
        *,
        data_root: Path,
        workbench_command: Sequence[str],
        timeout_seconds: int = 120,
    ) -> None:
        self.data_root = Path(data_root).expanduser().resolve()
        self.workbench_command = tuple(str(part) for part in workbench_command)
        self.timeout_seconds = int(timeout_seconds)
        if not self.workbench_command:
            raise ValueError("workbench_command must not be empty")
        if self.timeout_seconds < 1:
            raise ValueError("timeout_seconds must be positive")

    @property
    def database_path(self) -> Path:
        return self.data_root / "video-studio.sqlite3"

    @classmethod
    def from_environment(cls) -> "VideoStudioConfig":
        data_root = Path(
            os.environ.get(
                "OMNIOPS_VIDEO_DATA",
                str(Path.home() / ".omniops" / "video-studio"),
            )
        )
        configured = os.environ.get("OMNIOPS_VIDEO_WORKBENCH", "").strip()
        if configured:
            workbench = Path(configured).expanduser()
        elif getattr(sys, "frozen", False):
            executable_dir = Path(sys.executable).resolve().parent
            executable_name = (
                "omniops-video-workbench.exe"
                if os.name == "nt"
                else "omniops-video-workbench"
            )
            workbench = executable_dir / executable_name
        else:
            omniops_home = Path(
                os.environ.get("OMNIOPS_HOME", str(Path.home() / ".omniops"))
            ).expanduser()
            workbench = omniops_home / "bin" / "omniops-video-workbench.py"
        if workbench.suffix.lower() == ".py":
            command = (sys.executable, str(workbench))
        else:
            command = (str(workbench),)
        return cls(
            data_root=data_root,
            workbench_command=command,
            timeout_seconds=int(os.environ.get("OMNIOPS_VIDEO_TIMEOUT", "120")),
        )


class VideoStudioStore:
    """SQLite-backed job and authorization ledger shared by every client."""

    def __init__(self, database_path: Path) -> None:
        self.database_path = Path(database_path)

    def connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.database_path)
        connection.row_factory = sqlite3.Row
        return connection

    def initialize(self) -> None:
        self.database_path.parent.mkdir(parents=True, exist_ok=True)
        with self.connect() as connection:
            connection.executescript(
                """
                PRAGMA journal_mode=WAL;
                CREATE TABLE IF NOT EXISTS video_jobs (
                    job_id TEXT PRIMARY KEY,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    source TEXT NOT NULL,
                    merchant_id TEXT NOT NULL,
                    platform TEXT NOT NULL,
                    goal TEXT NOT NULL,
                    media_json TEXT NOT NULL,
                    status TEXT NOT NULL,
                    workbench_status TEXT NOT NULL,
                    next_allowed_action TEXT NOT NULL,
                    run_dir TEXT NOT NULL,
                    app_state_path TEXT NOT NULL,
                    request_json TEXT NOT NULL,
                    result_json TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS video_job_events (
                    event_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    job_id TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    action TEXT NOT NULL,
                    payload_json TEXT NOT NULL,
                    FOREIGN KEY(job_id) REFERENCES video_jobs(job_id)
                );
                CREATE TABLE IF NOT EXISTS paid_authorizations (
                    authorization_id TEXT PRIMARY KEY,
                    job_id TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    step TEXT NOT NULL,
                    FOREIGN KEY(job_id) REFERENCES video_jobs(job_id)
                );
                """
            )
            columns = {
                str(row["name"])
                for row in connection.execute("PRAGMA table_info(video_jobs)")
            }
            if "target_duration_seconds" not in columns:
                connection.execute(
                    "ALTER TABLE video_jobs "
                    "ADD COLUMN target_duration_seconds INTEGER NOT NULL DEFAULT 15"
                )
            if "generation_unit_plan_json" not in columns:
                connection.execute(
                    "ALTER TABLE video_jobs "
                    "ADD COLUMN generation_unit_plan_json TEXT NOT NULL DEFAULT '{}'"
                )

    def create_job(self, row: Mapping[str, Any]) -> None:
        with self.connect() as connection:
            connection.execute(
                """
                INSERT INTO video_jobs (
                    job_id, created_at, updated_at, source, merchant_id, platform,
                    goal, media_json, status, workbench_status,
                    next_allowed_action, run_dir, app_state_path,
                    request_json, result_json, target_duration_seconds,
                    generation_unit_plan_json
                ) VALUES (
                    :job_id, :created_at, :updated_at, :source, :merchant_id,
                    :platform, :goal, :media_json, :status, :workbench_status,
                    :next_allowed_action, :run_dir, :app_state_path,
                    :request_json, :result_json, :target_duration_seconds,
                    :generation_unit_plan_json
                )
                """,
                dict(row),
            )

    def get_job(self, job_id: str) -> dict[str, Any]:
        with self.connect() as connection:
            row = connection.execute(
                "SELECT * FROM video_jobs WHERE job_id = ?",
                (job_id,),
            ).fetchone()
        if row is None:
            raise KeyError(f"unknown video job: {job_id}")
        return self._decode_job(row)

    def list_jobs(self) -> list[dict[str, Any]]:
        with self.connect() as connection:
            rows = connection.execute(
                "SELECT * FROM video_jobs ORDER BY created_at DESC, job_id DESC"
            ).fetchall()
        return [self._decode_job(row) for row in rows]

    def update_result(
        self,
        job_id: str,
        *,
        result: Mapping[str, Any],
        status: str,
        workbench_status: str,
        next_allowed_action: str,
    ) -> None:
        with self.connect() as connection:
            connection.execute(
                """
                UPDATE video_jobs
                SET updated_at = ?, result_json = ?, status = ?,
                    workbench_status = ?, next_allowed_action = ?
                WHERE job_id = ?
                """,
                (
                    utc_now(),
                    json.dumps(result, ensure_ascii=False),
                    status,
                    workbench_status,
                    next_allowed_action,
                    job_id,
                ),
            )

    def add_event(
        self,
        job_id: str,
        action: str,
        payload: Mapping[str, Any],
    ) -> None:
        with self.connect() as connection:
            connection.execute(
                """
                INSERT INTO video_job_events (
                    job_id, created_at, action, payload_json
                ) VALUES (?, ?, ?, ?)
                """,
                (
                    job_id,
                    utc_now(),
                    action,
                    json.dumps(payload, ensure_ascii=False),
                ),
            )

    def consume_paid_authorization(
        self,
        authorization_id: str,
        job_id: str,
        step: str,
    ) -> None:
        if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._:-]{5,127}", authorization_id):
            raise PolicyViolation("paid authorization ID has an invalid format")
        try:
            with self.connect() as connection:
                connection.execute(
                    """
                    INSERT INTO paid_authorizations (
                        authorization_id, job_id, created_at, step
                    ) VALUES (?, ?, ?, ?)
                    """,
                    (authorization_id, job_id, utc_now(), step),
                )
        except sqlite3.IntegrityError as exc:
            raise PolicyViolation(
                "paid authorization ID has already been consumed"
            ) from exc

    @staticmethod
    def _decode_job(row: sqlite3.Row) -> dict[str, Any]:
        workbench_result = json.loads(row["result_json"])
        request = json.loads(row["request_json"])
        target_duration = (
            int(row["target_duration_seconds"] or 15)
            if "targetDurationSeconds" in request
            else 15
        )
        generation_plan = json.loads(row["generation_unit_plan_json"] or "{}")
        if not generation_plan.get("units"):
            generation_plan = compile_generation_units(target_duration)
        decoded = {
            "schema": SCHEMA_VERSION,
            "jobId": row["job_id"],
            "createdAt": row["created_at"],
            "updatedAt": row["updated_at"],
            "source": row["source"],
            "merchantId": row["merchant_id"],
            "platform": row["platform"],
            "productionMode": "platform_independent",
            "goal": row["goal"],
            "media": json.loads(row["media_json"]),
            "targetDurationSeconds": target_duration,
            "generationUnitPlan": generation_plan,
            "creationBrief": request.get("creationBrief", {}),
            "status": row["status"],
            "workbenchStatus": row["workbench_status"],
            "nextAllowedAction": row["next_allowed_action"],
            "runDir": row["run_dir"],
            "appStatePath": row["app_state_path"],
            "workbenchResult": workbench_result,
            "writesExternalSystems": False,
        }
        for key in ("professionalWorkerTeam", "finalVideo", "blockingStages"):
            if key in workbench_result:
                decoded[key] = workbench_result[key]
        return decoded


class WorkbenchRunner:
    """Executes the one canonical video workbench and validates its boundary."""

    def __init__(
        self,
        command: Sequence[str],
        *,
        timeout_seconds: int,
    ) -> None:
        self.command = tuple(str(part) for part in command)
        self.timeout_seconds = timeout_seconds

    def run(self, arguments: Sequence[str]) -> dict[str, Any]:
        environment = os.environ.copy()
        if getattr(sys, "frozen", False):
            executable_dir = str(Path(sys.executable).resolve().parent)
            environment["PATH"] = executable_dir + os.pathsep + environment.get(
                "PATH", ""
            )
        completed = subprocess.run(
            [*self.command, *map(str, arguments)],
            capture_output=True,
            text=True,
            timeout=self.timeout_seconds,
            check=False,
            env=environment,
        )
        try:
            payload = json.loads(completed.stdout)
        except json.JSONDecodeError as exc:
            raise RuntimeError(
                "video workbench did not return valid JSON: "
                + completed.stderr.strip()[-1000:]
            ) from exc
        if not isinstance(payload, dict):
            raise RuntimeError("video workbench JSON must be an object")
        if payload.get("writesExternalSystems") is True:
            raise PolicyViolation(
                "video workbench reported an external-system write"
            )
        payload["writesExternalSystems"] = False
        payload["workbenchExitCode"] = completed.returncode
        return payload


class VideoStudioService:
    """Application facade used by the desktop program and WeChat CODEX."""

    def __init__(
        self,
        config: VideoStudioConfig,
        store: VideoStudioStore,
        runner: WorkbenchRunner,
    ) -> None:
        self.config = config
        self.store = store
        self.runner = runner

    def doctor(self) -> dict[str, Any]:
        result = self.runner.run(["doctor", "--format", "json"])
        return {
            "schema": "omniops.video_studio_doctor.v1",
            "status": result.get("status", "BLOCKED"),
            "workbenchResult": result,
            "dataRoot": str(self.config.data_root),
            "databasePath": str(self.config.database_path),
            "writesExternalSystems": False,
        }

    def analyze_materials(self, request: Mapping[str, Any]) -> dict[str, Any]:
        merchant_id = str(request.get("merchantId", "")).strip()
        if merchant_id not in ALLOWED_MERCHANTS:
            raise PolicyViolation(f"unsupported merchant: {merchant_id}")
        raw_media = request.get("media", [])
        if not isinstance(raw_media, (list, tuple)):
            raise PolicyViolation("media must be a list of local paths")
        if not raw_media:
            raise PolicyViolation("material analysis requires at least one local file")
        if len(raw_media) > 100:
            raise PolicyViolation("material analysis accepts at most 100 local files")

        observations: list[dict[str, Any]] = []
        for raw_path in raw_media:
            path = Path(str(raw_path)).expanduser().resolve()
            if not path.is_file():
                raise PolicyViolation(f"material file does not exist: {path}")
            suffix = path.suffix.lower()
            if suffix in IMAGE_EXTENSIONS:
                kind = "image"
            elif suffix in VIDEO_EXTENSIONS:
                kind = "video"
            else:
                raise PolicyViolation(f"unsupported material file type: {path.name}")
            observations.append(
                {
                    "path": str(path),
                    "name": path.name,
                    "kind": kind,
                    "extension": suffix.lstrip("."),
                    "sizeBytes": path.stat().st_size,
                    "evidenceLevel": "technical_metadata",
                    "contentDescription": "",
                    "visualStatus": "PENDING_PROFESSIONAL_MATERIAL_WORKER",
                }
            )

        return {
            "schema": "omniops.video_studio_material_analysis.v1",
            "generatedAt": utc_now(),
            "status": "PASS_LOCAL_MATERIAL_INTAKE",
            "merchantId": merchant_id,
            "analysisMode": "local_prespend_intake",
            "mediaCount": len(observations),
            "assetObservations": observations,
            "insight": {
                "productFeatures": [],
                "coreSellingPoints": [],
                "targetAudiences": [],
                "usageScenarios": [],
                "evidenceStatus": "REQUIRES_PROFESSIONAL_MATERIAL_WORKER",
            },
            "nextAction": "CONFIRM_OR_EDIT_INSIGHT",
            "writesExternalSystems": False,
        }

    def submit(self, request: Mapping[str, Any]) -> dict[str, Any]:
        normalized = self._validate_request(request)
        generation_plan = compile_generation_units(
            normalized["targetDurationSeconds"]
        )
        duration_sequence = "+".join(
            str(unit["durationSeconds"]) for unit in generation_plan["units"]
        )
        compiled_goal = (
            f"{normalized['goal']}\n"
            f"【Video Studio任务契约】平台无关；目标成片时长："
            f"{normalized['targetDurationSeconds']}秒；完整脚本按内容目标创作；"
            f"生成单元：{duration_sequence}秒；每单元不超过"
            f"{MAX_GENERATION_UNIT_SECONDS}秒；逐段独立QA后剪辑合成。"
        )
        arguments = [
            "start",
            "--merchant-id",
            normalized["merchantId"],
            "--goal",
            compiled_goal,
            "--source",
            normalized["source"],
            "--write-report",
            "--format",
            "json",
        ]
        if normalized["media"]:
            arguments.extend(["--media", ",".join(normalized["media"])])
        workbench_result = self.runner.run(arguments)
        request_contract_path = self._write_request_contract(
            normalized,
            generation_plan,
            workbench_result,
        )
        workbench_result["videoStudioRequestContract"] = request_contract_path
        workbench_result["targetDurationSeconds"] = normalized[
            "targetDurationSeconds"
        ]
        workbench_result["generationUnitPlan"] = generation_plan
        now = utc_now()
        job_id = "video-" + datetime.now().strftime("%Y%m%d-%H%M%S") + "-" + uuid.uuid4().hex[:8]
        workbench_status = str(workbench_result.get("status", "BLOCKED"))
        status = app_status(workbench_status)
        row = {
            "job_id": job_id,
            "created_at": now,
            "updated_at": now,
            "source": normalized["source"],
            "merchant_id": normalized["merchantId"],
            "platform": "generic",
            "goal": normalized["goal"],
            "media_json": json.dumps(normalized["media"], ensure_ascii=False),
            "status": status,
            "workbench_status": workbench_status,
            "next_allowed_action": str(
                workbench_result.get("nextAllowedAction", "")
            ),
            "run_dir": str(workbench_result.get("runDir", "")),
            "app_state_path": str(workbench_result.get("appStatePath", "")),
            "request_json": json.dumps(normalized, ensure_ascii=False),
            "result_json": json.dumps(workbench_result, ensure_ascii=False),
            "target_duration_seconds": normalized["targetDurationSeconds"],
            "generation_unit_plan_json": json.dumps(
                generation_plan,
                ensure_ascii=False,
            ),
        }
        self.store.create_job(row)
        self.store.add_event(job_id, "submit", workbench_result)
        return self.store.get_job(job_id)

    @staticmethod
    def _write_request_contract(
        request: Mapping[str, Any],
        generation_plan: Mapping[str, Any],
        workbench_result: Mapping[str, Any],
    ) -> str:
        run_dir_text = str(workbench_result.get("runDir") or "").strip()
        if not run_dir_text:
            return ""
        contract_path = (
            Path(run_dir_text).expanduser().resolve()
            / "workflow"
            / "video_studio_request_contract.json"
        )
        contract_path.parent.mkdir(parents=True, exist_ok=True)
        contract = {
            "schema": "omniops.video_studio_request_contract.v1",
            "createdAt": utc_now(),
            "productionMode": "platform_independent",
            "requiresPlatformOrAccount": False,
            "merchantId": request["merchantId"],
            "goal": request["goal"],
            "media": list(request["media"]),
            "targetDurationSeconds": request["targetDurationSeconds"],
            "creationBrief": dict(request.get("creationBrief", {})),
            "generationUnitPlan": dict(generation_plan),
            "assemblyPolicy": (
                "independent_unit_qa_then_local_continuity_edit_and_final_qa"
            ),
            "writesExternalSystems": False,
        }
        contract_path.write_text(
            json.dumps(contract, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        return str(contract_path)

    def list_jobs(self) -> dict[str, Any]:
        jobs = self.store.list_jobs()
        return {
            "schema": "omniops.video_studio_job_list.v1",
            "count": len(jobs),
            "jobs": jobs,
            "writesExternalSystems": False,
        }

    def job_status(self, job_id: str, *, refresh: bool = False) -> dict[str, Any]:
        job = self.store.get_job(job_id)
        if not refresh:
            return job
        result = self.runner.run(
            self._job_command(job, "status", include_draft=True)
        )
        self._persist_execution(job, "status", result)
        return self.store.get_job(job_id)

    def execute(
        self,
        job_id: str,
        action: str,
        arguments: Mapping[str, Any],
    ) -> dict[str, Any]:
        normalized_action = str(action).strip().lower()
        if normalized_action in FORBIDDEN_ACTIONS:
            raise PolicyViolation(
                f"action is outside the local-only video boundary: {normalized_action}"
            )
        job = self.store.get_job(job_id)
        if normalized_action in {"status", "next", "acceptance"}:
            command = self._job_command(
                job,
                normalized_action,
                include_draft=True,
            )
        elif normalized_action == "run-step":
            command = self._run_step_command(job, arguments)
        else:
            raise PolicyViolation(f"unsupported video application action: {action}")
        result = self.runner.run(command)
        self._persist_execution(job, normalized_action, result)
        current = self.store.get_job(job_id)
        return {
            **current,
            "action": normalized_action,
            "workbenchStatus": str(result.get("status", "BLOCKED")),
            "workbenchResult": result,
            "writesExternalSystems": False,
        }

    def _persist_execution(
        self,
        job: Mapping[str, Any],
        action: str,
        result: Mapping[str, Any],
    ) -> None:
        workbench_status = str(result.get("status", "BLOCKED"))
        next_action = str(
            result.get("nextAllowedAction", job.get("nextAllowedAction", ""))
        )
        self.store.update_result(
            str(job["jobId"]),
            result=result,
            status=app_status(workbench_status),
            workbench_status=workbench_status,
            next_allowed_action=next_action,
        )
        self.store.add_event(str(job["jobId"]), action, result)

    def _job_command(
        self,
        job: Mapping[str, Any],
        command: str,
        *,
        include_draft: bool,
    ) -> list[str]:
        result = [
            command,
            "--merchant-id",
            str(job["merchantId"]),
            "--platform",
            str(job["platform"]),
        ]
        if include_draft and job.get("runDir"):
            result.extend(["--draft-dir", str(job["runDir"])])
        result.extend(["--write-report", "--format", "json"])
        return result

    def _run_step_command(
        self,
        job: Mapping[str, Any],
        arguments: Mapping[str, Any],
    ) -> list[str]:
        step = str(arguments.get("step", "")).strip()
        if step not in SAFE_LOCAL_STEPS and step not in PAID_STEPS:
            raise PolicyViolation(f"unsupported or unsafe workbench step: {step}")
        command = self._job_command(job, "run", include_draft=True)
        command[1:1] = ["--step", step]
        if step in PAID_STEPS:
            authorization_id = str(
                arguments.get("paidAuthorizationId", "")
            ).strip()
            if not authorization_id:
                raise PolicyViolation(
                    "paid video generation requires an explicit authorization ID"
                )
            self.store.consume_paid_authorization(
                authorization_id,
                str(job["jobId"]),
                step,
            )
            command.extend(["--paid-authorization-id", authorization_id])
        for key, flag in SAFE_ARGUMENT_FLAGS.items():
            value = arguments.get(key)
            if value is not None and str(value).strip():
                command.extend([flag, str(value)])
        return command

    @staticmethod
    def _validate_request(request: Mapping[str, Any]) -> dict[str, Any]:
        merchant_id = str(request.get("merchantId", "")).strip()
        source = str(request.get("source", "desktop")).strip()
        goal = str(request.get("goal", "")).strip()
        raw_media = request.get("media", [])
        target_duration = request.get("targetDurationSeconds", 30)
        raw_creation_brief = request.get("creationBrief", {})
        if merchant_id not in ALLOWED_MERCHANTS:
            raise PolicyViolation(f"unsupported merchant: {merchant_id}")
        if source not in ALLOWED_SOURCES:
            raise PolicyViolation(f"unsupported application source: {source}")
        if not goal or len(goal) > 4000:
            raise PolicyViolation("goal must contain between 1 and 4000 characters")
        if not isinstance(raw_media, (list, tuple)):
            raise PolicyViolation("media must be a list of local paths")
        media = [str(Path(str(path)).expanduser()) for path in raw_media if str(path)]
        if len(media) > 100:
            raise PolicyViolation("a video task may reference at most 100 media files")
        if isinstance(target_duration, bool) or not isinstance(
            target_duration,
            (int, float),
        ):
            raise PolicyViolation("target duration must be a number of seconds")
        if int(target_duration) != float(target_duration):
            raise PolicyViolation("target duration must be a whole number of seconds")
        target_duration = int(target_duration)
        if not MIN_FINAL_VIDEO_SECONDS <= target_duration <= MAX_FINAL_VIDEO_SECONDS:
            raise PolicyViolation(
                "target duration must be between 15 and 60 seconds"
            )
        if not isinstance(raw_creation_brief, Mapping):
            raise PolicyViolation("creationBrief must be a JSON object")
        creation_brief = json.loads(
            json.dumps(dict(raw_creation_brief), ensure_ascii=False)
        )
        return {
            "merchantId": merchant_id,
            "platform": "generic",
            "source": source,
            "goal": goal,
            "media": media,
            "targetDurationSeconds": target_duration,
            "creationBrief": creation_brief,
        }


def compile_generation_units(target_duration_seconds: int) -> dict[str, Any]:
    duration = int(target_duration_seconds)
    if not MIN_FINAL_VIDEO_SECONDS <= duration <= MAX_FINAL_VIDEO_SECONDS:
        raise PolicyViolation("target duration must be between 15 and 60 seconds")
    units: list[dict[str, Any]] = []
    cursor = 0
    remaining = duration
    while remaining:
        unit_duration = min(MAX_GENERATION_UNIT_SECONDS, remaining)
        index = len(units) + 1
        units.append(
            {
                "unitId": f"unit-{index:02d}",
                "order": index,
                "startSeconds": cursor,
                "endSeconds": cursor + unit_duration,
                "durationSeconds": unit_duration,
                "continuityInput": (
                    "opening_canon"
                    if index == 1
                    else f"unit-{index - 1:02d}_actual_tail_frame_and_av_state"
                ),
                "requiresIndependentQa": True,
            }
        )
        cursor += unit_duration
        remaining -= unit_duration
    return {
        "schema": "omniops.video_generation_unit_plan.v1",
        "targetDurationSeconds": duration,
        "modelMaxGenerationUnitSeconds": MAX_GENERATION_UNIT_SECONDS,
        "unitCount": len(units),
        "units": units,
        "assemblyRequired": len(units) > 1,
        "writesExternalSystems": False,
    }


def compile_creation_blueprint(brief: Mapping[str, Any]) -> dict[str, Any]:
    if not isinstance(brief, Mapping):
        raise PolicyViolation("creation brief must be a JSON object")
    goal = str(brief.get("goal", "")).strip()
    if not goal or len(goal) > 4000:
        raise PolicyViolation("goal must contain between 1 and 4000 characters")

    def string_list(key: str) -> list[str]:
        value = brief.get(key, [])
        if isinstance(value, str):
            return [part.strip() for part in value.splitlines() if part.strip()]
        if not isinstance(value, (list, tuple)):
            raise PolicyViolation(f"{key} must be a list of text values")
        return [str(part).strip() for part in value if str(part).strip()]

    product_features = string_list("productFeatures")
    core_selling_points = string_list("coreSellingPoints")
    target_audiences = string_list("targetAudiences")
    usage_scenarios = string_list("usageScenarios")
    content_type = str(brief.get("contentType", "人物剧情")).strip()
    shooting_style = str(brief.get("shootingStyle", "电影感叙事")).strip()
    audio_mode = str(brief.get("audioMode", "角色对白 + BGM")).strip()
    supplement = str(brief.get("supplement", "")).strip()
    reference_video = str(brief.get("referenceVideo", "")).strip()
    duration = int(brief.get("durationSeconds", 30))
    candidate_count = int(brief.get("candidateCount", 3))
    if not 1 <= candidate_count <= MAX_CREATIVE_CANDIDATES:
        raise PolicyViolation(
            f"candidate count must be between 1 and {MAX_CREATIVE_CANDIDATES}"
        )
    generation_plan = compile_generation_units(duration)

    feature = product_features[0] if product_features else "由素材 Worker 核验的画面证据"
    selling_point = (
        core_selling_points[0]
        if core_selling_points
        else "由创意导演从已核验素材中选择核心兑现"
    )
    audience = target_audiences[0] if target_audiences else "待确认目标人群"
    scenario = usage_scenarios[0] if usage_scenarios else "待确认使用场景"
    strategies = [
        ("冲突反转", supplement or goal, f"用{feature}制造预期差"),
        ("场景共鸣", f"从{scenario}进入真实情境", f"让{audience}快速代入"),
        ("证据兑现", f"前三秒直接展示{feature}", f"用画面兑现{selling_point}"),
        ("系列回钩", f"把{goal}编成可连续复用的角色事件", "结尾保留下一集问题"),
    ]
    candidates: list[dict[str, Any]] = []
    for index, (strategy, hook, payoff) in enumerate(
        strategies[:candidate_count],
        start=1,
    ):
        candidates.append(
            {
                "candidateId": f"candidate-{index:02d}",
                "status": "DRAFT_FOR_WORKER_REWRITE",
                "strategy": strategy,
                "contentType": content_type,
                "shootingStyle": shooting_style,
                "audioMode": audio_mode,
                "beats": [
                    {
                        "label": "开场钩子",
                        "time": "0-3秒",
                        "intent": hook,
                    },
                    {
                        "label": "场景推进",
                        "time": "前段",
                        "intent": f"在{scenario}中建立人物、空间与动作关系",
                    },
                    {
                        "label": "核心兑现",
                        "time": "中段",
                        "intent": payoff,
                    },
                    {
                        "label": "结尾回收",
                        "time": "尾段",
                        "intent": "回收冲突并留下自然评论点或系列回钩",
                    },
                ],
                "riskGate": (
                    "Professional Workers must verify merchant facts, identity, "
                    "audio, continuity, cost, and publication boundaries."
                ),
            }
        )

    return {
        "schema": "omniops.video_studio_creation_blueprint.v1",
        "generatedAt": utc_now(),
        "status": "PASS_CREATION_BLUEPRINT",
        "goal": goal,
        "inputBrief": {
            "productFeatures": product_features,
            "coreSellingPoints": core_selling_points,
            "targetAudiences": target_audiences,
            "usageScenarios": usage_scenarios,
            "contentType": content_type,
            "shootingStyle": shooting_style,
            "audioMode": audio_mode,
            "supplement": supplement,
            "referenceVideo": reference_video,
            "durationSeconds": duration,
            "candidateCount": candidate_count,
        },
        "candidates": candidates,
        "selectedCandidateId": candidates[0]["candidateId"],
        "generationUnitPlan": generation_plan,
        "scopeNote": (
            "These are local pre-spend creative directions, not final scripts. "
            "The Screenwriter and Storyboard Workers must rewrite and validate them."
        ),
        "writesExternalSystems": False,
    }


def app_status(workbench_status: str) -> str:
    if workbench_status == "PASS":
        return "ready"
    if workbench_status in {"RUNNING", "ACTIVE", "IN_PROGRESS"}:
        return "running"
    return "blocked"


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()

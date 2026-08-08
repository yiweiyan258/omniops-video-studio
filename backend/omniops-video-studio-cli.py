#!/usr/bin/env python3
"""Command-line entrypoint shared by OmniOps Video Studio and WeChat CODEX."""

from __future__ import annotations

import argparse
import json
import sys
from typing import Any

from omniops_video_studio_lib import (
    ALLOWED_MERCHANTS,
    ALLOWED_SOURCES,
    FORBIDDEN_ACTIONS,
    PolicyViolation,
    VideoStudioConfig,
    VideoStudioService,
    VideoStudioStore,
    WorkbenchRunner,
    compile_creation_blueprint,
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Local-only OmniOps professional video application CLI."
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    subparsers.add_parser("manifest", help="print application capabilities")
    subparsers.add_parser("doctor", help="check the canonical video runtime")
    subparsers.add_parser("list", help="list desktop and WeChat video jobs")

    analyze = subparsers.add_parser(
        "analyze",
        help="inspect local material metadata before formal production",
    )
    analyze.add_argument(
        "--merchant-id",
        required=True,
        choices=sorted(ALLOWED_MERCHANTS),
    )
    analyze.add_argument("--media", action="append", default=[])

    compile_brief = subparsers.add_parser(
        "compile-brief",
        help="compile local pre-spend creative direction candidates",
    )
    compile_brief.add_argument("--brief-json", required=True)

    submit = subparsers.add_parser("submit", help="create one formal video job")
    submit.add_argument("--merchant-id", required=True, choices=sorted(ALLOWED_MERCHANTS))
    submit.add_argument("--goal", required=True)
    submit.add_argument("--duration-seconds", type=int, default=30)
    submit.add_argument("--media", action="append", default=[])
    submit.add_argument("--source", default="desktop", choices=sorted(ALLOWED_SOURCES))
    submit.add_argument("--brief-json")

    status = subparsers.add_parser("status", help="read one video job")
    status.add_argument("--job-id", required=True)
    status.add_argument("--refresh", action="store_true")

    execute = subparsers.add_parser(
        "execute",
        help="execute an allowlisted local workbench action",
    )
    execute.add_argument("--job-id", required=True)
    execute.add_argument("--action", required=True)
    execute.add_argument("--step")
    execute.add_argument("--paid-authorization-id")
    execute.add_argument("--arguments-json")

    for command in ("next", "acceptance"):
        action = subparsers.add_parser(command, help=f"run local {command}")
        action.add_argument("--job-id", required=True)
    return parser


def manifest_payload() -> dict[str, Any]:
    return {
        "schema": "omniops.video_studio_manifest.v1",
        "product": "OmniOps Video Studio",
        "productionCore": "omniops-video-workbench",
        "clients": ["desktop", "weixin", "codex"],
        "commands": [
            "manifest",
            "doctor",
            "analyze",
            "compile-brief",
            "submit",
            "list",
            "status",
            "next",
            "execute",
            "acceptance",
        ],
        "capabilities": {
            "localVideoCreation": True,
            "localMaterialIntake": True,
            "structuredCreationBrief": True,
            "platformIndependentCreation": True,
            "professionalWorkerTeam": True,
            "sequentialPaidGeneration": True,
            "localQualityAssurance": True,
            "localExport": True,
            "platformPublishing": False,
            "engagementActions": False,
            "accountControl": False,
        },
        "requirements": {
            "platformOrAccount": False,
            "localMediaRecommended": True,
        },
        "durationPolicy": {
            "finalVideoSeconds": {"min": 15, "max": 60},
            "modelGenerationUnitMaxSeconds": 15,
            "assembly": "sequential_units_then_local_edit_and_final_qa",
        },
        "forbiddenActions": sorted(FORBIDDEN_ACTIONS),
        "writesExternalSystems": False,
    }


def build_service() -> VideoStudioService:
    config = VideoStudioConfig.from_environment()
    store = VideoStudioStore(config.database_path)
    store.initialize()
    runner = WorkbenchRunner(
        config.workbench_command,
        timeout_seconds=config.timeout_seconds,
    )
    return VideoStudioService(config, store, runner)


def execute_payload(
    service: VideoStudioService,
    args: argparse.Namespace,
) -> dict[str, Any]:
    if args.command == "manifest":
        return manifest_payload()
    if args.command == "doctor":
        return service.doctor()
    if args.command == "list":
        return service.list_jobs()
    if args.command == "analyze":
        media: list[str] = []
        for value in args.media:
            media.extend(part.strip() for part in value.split(",") if part.strip())
        return service.analyze_materials(
            {
                "merchantId": args.merchant_id,
                "media": media,
            }
        )
    if args.command == "compile-brief":
        parsed = json.loads(args.brief_json)
        if not isinstance(parsed, dict):
            raise PolicyViolation("--brief-json must contain a JSON object")
        return compile_creation_blueprint(parsed)
    if args.command == "submit":
        media: list[str] = []
        for value in args.media:
            media.extend(part.strip() for part in value.split(",") if part.strip())
        request = {
            "merchantId": args.merchant_id,
            "goal": args.goal,
            "media": media,
            "source": args.source,
            "targetDurationSeconds": args.duration_seconds,
        }
        if args.brief_json:
            creation_brief = json.loads(args.brief_json)
            if not isinstance(creation_brief, dict):
                raise PolicyViolation("--brief-json must contain a JSON object")
            request["creationBrief"] = creation_brief
        return service.submit(request)
    if args.command == "status":
        return service.job_status(args.job_id, refresh=args.refresh)
    if args.command in {"next", "acceptance"}:
        return service.execute(args.job_id, args.command, {})
    if args.command == "execute":
        arguments: dict[str, Any] = {}
        if args.arguments_json:
            parsed = json.loads(args.arguments_json)
            if not isinstance(parsed, dict):
                raise PolicyViolation("--arguments-json must contain a JSON object")
            arguments.update(parsed)
        if args.step:
            arguments["step"] = args.step
        if args.paid_authorization_id:
            arguments["paidAuthorizationId"] = args.paid_authorization_id
        return service.execute(args.job_id, args.action, arguments)
    raise PolicyViolation(f"unsupported command: {args.command}")


def main(argv: list[str]) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        service = build_service() if args.command != "manifest" else None
        result = execute_payload(service, args)
        print(json.dumps(result, ensure_ascii=False))
        return 0
    except PolicyViolation as exc:
        print(
            json.dumps(
                {
                    "schema": "omniops.video_studio_error.v1",
                    "status": "POLICY_BLOCKED",
                    "message": str(exc),
                    "writesExternalSystems": False,
                },
                ensure_ascii=False,
            )
        )
        return 2
    except (KeyError, ValueError, RuntimeError, OSError, json.JSONDecodeError) as exc:
        print(
            json.dumps(
                {
                    "schema": "omniops.video_studio_error.v1",
                    "status": "BLOCKED",
                    "message": str(exc),
                    "writesExternalSystems": False,
                },
                ensure_ascii=False,
            )
        )
        return 2


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))

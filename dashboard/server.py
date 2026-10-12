"""Read-only HTTP server for the benchmark dashboard."""

from __future__ import annotations

import argparse
import json
import math
import re
from pathlib import Path
from typing import Any, Sequence

from aiohttp import web

SUPPORTED_SCHEMA_VERSION = "3.5"
METRICS = ("dialogue_experience", "action_ability", "distortion_rate", "availability")
CONFIG_FIELDS = ("benchmark_version", "judge_model", "harness", "suite", "trials", "git_revision")
STATIC_DIR = Path(__file__).with_name("static")
DEFAULT_REPORTS_DIR = Path(__file__).resolve().parents[1] / "reports"
LOGO_PATH = Path(__file__).resolve().parents[2] / "docs" / "public" / "favicon.png"
REPORTS_DIR_KEY = web.AppKey("reports_dir", Path)


def _report_payload(path: Path) -> dict[str, Any]:
    """Load the small, public part of one benchmark report."""
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise ValueError(f"不能读取 JSON：{exc}") from exc

    if not isinstance(data, dict):
        raise ValueError("报告根节点必须是对象")
    if data.get("schema_version") != SUPPORTED_SCHEMA_VERSION:
        raise ValueError(f"仅支持 schema {SUPPORTED_SCHEMA_VERSION}")

    models = data.get("models")
    summary = data.get("summary")
    config = data.get("config", {})
    if not isinstance(models, list) or not all(isinstance(model, str) for model in models):
        raise ValueError("models 字段无效")
    if not isinstance(summary, dict):
        raise ValueError("summary 字段无效")
    if not isinstance(config, dict):
        config = {}

    safe_summary: dict[str, dict[str, float | None]] = {}
    for metric in METRICS:
        metric_values = summary.get(metric)
        if not isinstance(metric_values, dict):
            raise ValueError(f"summary.{metric} 字段无效")
        safe_values: dict[str, float | None] = {}
        for model in models:
            value = metric_values.get(model)
            if value is not None and (isinstance(value, bool) or not isinstance(value, (int, float))):
                raise ValueError(f"summary.{metric}.{model} 不是数值")
            if value is not None and not math.isfinite(value):
                raise ValueError(f"summary.{metric}.{model} 不是有限数值")
            safe_values[model] = float(value) if value is not None else None
        safe_summary[metric] = safe_values

    generated_at = data.get("generated_at", "")
    if not isinstance(generated_at, str):
        generated_at = ""

    return {
        "filename": path.name,
        "generated_at": generated_at,
        "schema_version": SUPPORTED_SCHEMA_VERSION,
        "models": models,
        "config": {key: config.get(key) for key in CONFIG_FIELDS},
        "summary": safe_summary,
    }


def _version_key(version: str) -> tuple[tuple[int, ...], str]:
    """Create a stable key for dotted benchmark versions."""
    return tuple(int(part) for part in re.findall(r"\d+", version)), version


def load_reports(reports_dir: Path) -> dict[str, Any]:
    """Load valid reports and collect file-level errors."""
    reports: list[dict[str, Any]] = []
    errors: list[dict[str, str]] = []

    if not reports_dir.is_dir():
        return {
            "reports": [],
            "errors": [{"filename": reports_dir.name or str(reports_dir), "message": "报告目录不存在"}],
            "benchmark_version": None,
        }

    for path in sorted(reports_dir.glob("*.json")):
        if path.name.endswith(".checkpoint.json"):
            continue
        try:
            reports.append(_report_payload(path))
        except ValueError as exc:
            errors.append({"filename": path.name, "message": str(exc)})

    versions = [report["config"].get("benchmark_version") for report in reports]
    valid_versions = [version for version in versions if isinstance(version, str) and version]
    latest_version = max(valid_versions, key=_version_key) if valid_versions else None
    if latest_version is not None:
        reports = [report for report in reports if report["config"].get("benchmark_version") == latest_version]

    reports.sort(key=lambda report: (report["generated_at"], report["filename"]), reverse=True)
    return {"reports": reports, "errors": errors, "benchmark_version": latest_version}


def create_app(reports_dir: Path | str = DEFAULT_REPORTS_DIR) -> web.Application:
    """Create the dashboard application for a report directory."""
    app = web.Application()
    app[REPORTS_DIR_KEY] = Path(reports_dir).resolve()

    async def index(_: web.Request) -> web.FileResponse:
        return web.FileResponse(STATIC_DIR / "index.html")

    async def reports(request: web.Request) -> web.Response:
        return web.json_response(load_reports(request.app[REPORTS_DIR_KEY]))

    async def logo(_: web.Request) -> web.FileResponse:
        return web.FileResponse(LOGO_PATH)

    app.router.add_get("/", index)
    app.router.add_get("/api/reports", reports)
    app.router.add_get("/logo.png", logo)
    app.router.add_static("/static/", STATIC_DIR, show_index=False)
    return app


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="本地查看 Benchmark 汇总结果")
    parser.add_argument("--host", default="127.0.0.1", help="监听地址")
    parser.add_argument("--port", default=8765, type=int, help="监听端口")
    parser.add_argument("--reports-dir", type=Path, default=DEFAULT_REPORTS_DIR, help="报告目录")
    return parser


def main(argv: Sequence[str] | None = None) -> None:
    args = build_parser().parse_args(argv)
    print(f"Benchmark dashboard: http://{args.host}:{args.port}")
    web.run_app(create_app(args.reports_dir), host=args.host, port=args.port, print=None)

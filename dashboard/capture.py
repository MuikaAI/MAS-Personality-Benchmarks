"""Create full-screen PNG images for each benchmark metric."""

from __future__ import annotations

import argparse
import asyncio
import os
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Any, Sequence
from urllib.parse import urlencode

from aiohttp import web

from benchmarks.dashboard.server import DEFAULT_REPORTS_DIR, METRICS, create_app, load_reports

DEFAULT_OUTPUT_DIR = Path(__file__).resolve().parents[1] / "screenshots"
BROWSER_NAMES = ("msedge", "chrome", "chromium", "chromium-browser")


def find_browser(explicit_path: Path | None = None) -> Path:
    """Find an installed Chromium-family browser."""
    if explicit_path is not None:
        path = explicit_path.expanduser().resolve()
        if not path.is_file():
            raise FileNotFoundError(f"浏览器不存在：{path}")
        return path

    for name in BROWSER_NAMES:
        executable = shutil.which(name)
        if executable:
            return Path(executable)

    program_files = [os.environ.get("PROGRAMFILES"), os.environ.get("PROGRAMFILES(X86)"), os.environ.get("LOCALAPPDATA")]
    relative_paths = (
        Path("Microsoft/Edge/Application/msedge.exe"),
        Path("Google/Chrome/Application/chrome.exe"),
        Path("Chromium/Application/chrome.exe"),
    )
    for root in filter(None, program_files):
        for relative_path in relative_paths:
            candidate = Path(root) / relative_path
            if candidate.is_file():
                return candidate

    raise FileNotFoundError("未找到 Edge、Chrome 或 Chromium。请使用 --browser 指定浏览器路径。")


def browser_command(
    browser: Path,
    *,
    url: str,
    output: Path,
    profile_dir: Path,
    width: int,
    height: int,
    wait_ms: int,
) -> list[str]:
    """Build one deterministic headless screenshot command."""
    return [
        str(browser),
        "--headless=new",
        "--disable-gpu",
        "--hide-scrollbars",
        "--no-first-run",
        "--no-default-browser-check",
        "--force-device-scale-factor=1",
        f"--user-data-dir={profile_dir}",
        f"--window-size={width},{height}",
        f"--virtual-time-budget={wait_ms}",
        f"--screenshot={output}",
        url,
    ]


def auto_capture_size(
    reports: list[dict[str, Any]],
    width: int | None = None,
    height: int | None = None,
) -> tuple[int, int, int]:
    """Calculate a compact viewport from the unique model set."""
    models = {
        model
        for report in reports
        for model in report.get("models", [])
        if isinstance(model, str)
    }
    model_count = len(models)
    longest_name = max((len(model.replace("_", " ")) for model in models), default=16)

    if width is None:
        calculated_width = 1040 + min(longest_name, 36) * 14 + min(model_count, 8) * 24
        width = max(1120, min(1920, ((calculated_width + 15) // 16) * 16))
    if height is None:
        height = max(480, min(1440, 280 + model_count * 140))
    return width, height, model_count


async def _run_browser(command: list[str]) -> None:
    result = await asyncio.to_thread(subprocess.run, command, capture_output=True, text=True, timeout=30)
    if result.returncode != 0:
        message = result.stderr.strip() or result.stdout.strip() or f"退出码 {result.returncode}"
        raise RuntimeError(f"浏览器截图失败：{message}")


async def capture_all(args: argparse.Namespace) -> tuple[list[Path], int, int, int]:
    """Start a temporary dashboard server and capture the selected metrics."""
    browser = find_browser(args.browser)
    output_dir = args.out_dir.expanduser().resolve()
    output_dir.mkdir(parents=True, exist_ok=True)

    report_payload = load_reports(args.reports_dir)
    if not report_payload["reports"]:
        raise RuntimeError("没有可用于截图的最新版本报告")
    width, height, model_count = auto_capture_size(report_payload["reports"], args.width, args.height)

    runner = web.AppRunner(create_app(args.reports_dir), access_log=None)
    await runner.setup()
    site = web.TCPSite(runner, "127.0.0.1", 0)
    await site.start()
    if site._server is None or not site._server.sockets:  # pragma: no cover - aiohttp startup invariant
        await runner.cleanup()
        raise RuntimeError("无法启动临时仪表板服务")
    port = site._server.sockets[0].getsockname()[1]

    outputs: list[Path] = []
    try:
        with tempfile.TemporaryDirectory(prefix="mas-benchmark-capture-") as profile_root:
            profile_dir = Path(profile_root)
            for metric in args.metrics:
                output = output_dir / f"{metric}.png"
                query = urlencode({"metric": metric, "capture": "1"})
                url = f"http://127.0.0.1:{port}/?{query}"
                command = browser_command(
                    browser,
                    url=url,
                    output=output,
                    profile_dir=profile_dir,
                    width=width,
                    height=height,
                    wait_ms=args.wait_ms,
                )
                await _run_browser(command)
                if not output.is_file() or output.stat().st_size == 0:
                    raise RuntimeError(f"浏览器没有生成截图：{output}")
                outputs.append(output)
    finally:
        await runner.cleanup()

    return outputs, width, height, model_count


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="自动生成 Benchmark 指标截图")
    parser.add_argument("--out-dir", type=Path, default=DEFAULT_OUTPUT_DIR, help="PNG 输出目录")
    parser.add_argument("--reports-dir", type=Path, default=DEFAULT_REPORTS_DIR, help="报告目录")
    parser.add_argument("--browser", type=Path, default=None, help="Edge、Chrome 或 Chromium 路径")
    parser.add_argument("--width", type=int, default=None, help="截图宽度；默认根据模型名称自动计算")
    parser.add_argument("--height", type=int, default=None, help="截图高度；默认根据模型数量自动计算")
    parser.add_argument("--wait-ms", type=int, default=2000, help="页面渲染等待时间")
    parser.add_argument("--metrics", nargs="+", choices=METRICS, default=list(METRICS), help="需要截图的指标")
    return parser


def main(argv: Sequence[str] | None = None) -> None:
    args = build_parser().parse_args(argv)
    if args.width is not None and args.width < 640:
        raise SystemExit("截图宽度必须至少为 640。")
    if args.height is not None and args.height < 480:
        raise SystemExit("截图高度必须至少为 480。")
    if args.wait_ms < 0:
        raise SystemExit("--wait-ms 不能小于零。")

    try:
        outputs, width, height, model_count = asyncio.run(capture_all(args))
    except (FileNotFoundError, RuntimeError, subprocess.TimeoutExpired) as exc:
        raise SystemExit(str(exc)) from exc

    print(f"截图尺寸：{width}x{height}（{model_count} 个模型）")
    for output in outputs:
        print(output)


if __name__ == "__main__":
    main()

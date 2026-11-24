"""Command line entry point for the EMSolution input checker."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from .checker import check_file


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="EMSolution input.json を静的にチェックします")
    parser.add_argument("input", type=Path, help="検査する input.json")
    parser.add_argument("--format", choices=("text", "json"), default="text", help="診断の出力形式")
    parser.add_argument("--output", type=Path, help="診断結果の保存先")
    parser.add_argument("--check-files", action="store_true", help="外部ファイル参照の確認を試みる")
    parser.add_argument("--base-dir", type=Path, help="外部ファイル参照の基準フォルダ")
    args = parser.parse_args(argv)
    report = check_file(args.input, check_files=args.check_files, base_dir=args.base_dir)
    if args.format == "json":
        # ASCII escapes keep redirected JSON decodable on Windows code pages.
        output = json.dumps(report.as_dict(), ensure_ascii=True, indent=2) + "\n"
    else:
        lines = [f"{report.file}: 終了コード {report.exit_code}", f"検証元: {report.source_revision}"]
        for diag in report.diagnostics:
            origin = f" [{diag.source}]" if diag.source else ""
            lines.append(f"{diag.severity.upper():10} {diag.code:20} {diag.path}: {diag.message}{origin}")
        if not report.diagnostics:
            lines.append("検出事項はありません")
        output = "\n".join(lines) + "\n"
    if args.output:
        try:
            args.output.write_text(output, encoding="utf-8")
        except OSError as exc:
            print(f"結果を書き込めません: {exc}", file=sys.stderr)
            return 3
    else:
        print(output, end="")
    return report.exit_code

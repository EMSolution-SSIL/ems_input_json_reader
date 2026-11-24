"""Run the input checker against an external EMSolution JSON corpus."""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

PROJECT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT))

from emso_input_checker import check_file  # noqa: E402


def scan(root: Path) -> dict:
    folder = root / "data"
    results = root / "results"
    if not folder.is_dir():
        raise FileNotFoundError(f"Input folder does not exist: {folder}")
    files = sorted(folder.rglob("*.json"))
    cases = []
    counts = {"full": 0, "incomplete": 0, "error": 0, "unreadable": 0}
    no_result = []
    for path in files:
        relative = path.relative_to(folder)
        result = check_file(path)
        status = {0: "full", 1: "error", 2: "incomplete", 3: "unreadable"}[result.exit_code]
        counts[status] += 1
        cases.append({"file": relative.as_posix(), "status": status,
                      "diagnostics": [vars(d) for d in result.diagnostics]})
        suffix = path.stem.removeprefix("input")
        result_folder = results / relative.parent
        pattern = re.compile(r"^output" + re.escape(suffix) + r"_\d{4}")
        if not result_folder.is_dir() or not any(pattern.match(p.stem) for p in result_folder.glob("*.json")):
            no_result.append(relative.as_posix())
    return {"root": str(root), "files": len(files), "counts": counts,
            "without_matching_output": no_result, "cases": cases}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Check every input JSON in an EMSolution corpus")
    parser.add_argument("--root", type=Path, default=PROJECT.parent / "reader_json_files")
    parser.add_argument("--report", type=Path, help="Write the complete UTF-8 JSON report here")
    parser.add_argument("--allow-incomplete", action="store_true", help="Return 0 when only partial checks remain")
    args = parser.parse_args(argv)
    try:
        report = scan(args.root.resolve())
        if args.report:
            args.report.parent.mkdir(parents=True, exist_ok=True)
            args.report.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    except OSError as exc:
        parser.exit(3, f"{exc}\n")
    counts = report["counts"]
    print(f"inputs={report['files']} full={counts['full']} incomplete={counts['incomplete']} "
          f"error={counts['error']} unreadable={counts['unreadable']} "
          f"without_matching_output={len(report['without_matching_output'])}")
    for case in report["cases"]:
        if case["status"] in ("error", "unreadable"):
            details = "; ".join(f"{d['code']} {d['path']}" for d in case["diagnostics"] if d["severity"] == "error")
            print(f"{case['status'].upper()} {case['file']}: {details}")
    if args.report:
        print(f"report={args.report}")
    if counts["unreadable"]:
        return 3
    if counts["error"]:
        return 1
    if counts["incomplete"] and not args.allow_incomplete:
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

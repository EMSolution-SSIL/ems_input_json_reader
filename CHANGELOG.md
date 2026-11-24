# Changelog

## 0.1.0 — 2026-11-24

- Release the source under PolyForm Perimeter 1.0.1 and provide a universal wheel.
- Add a read-only `input.json` checker and standalone `emso-check-input` CLI.
- Report rule paths, source locations, and incomplete validation explicitly.
- Validate 255 external input files with a repeatable corpus script and per-file JSON report.
- Treat null material-row arrays as empty, matching the current C/C++ reader.
- Accept CYCLIC=0 as an inactive periodic-boundary placeholder, with a warning.
- Complete the 255-input corpus check with no definite setting errors.

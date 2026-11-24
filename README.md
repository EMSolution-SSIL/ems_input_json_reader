# EMSolution input.json checker

This independent, source-available Python project checks EMSolution `input.json` settings without running EMSolution. The rules are traced to the C/C++ JSON readers in `EMSolBuild_VS2022/src@52d71bd`. The checker never modifies the input file.

[日本語の説明](README_ja.md)

## Install

Python 3.10 or newer is required. From this folder:

```sh
python -m pip install -e .
```

The package has no runtime dependencies outside the Python standard library. A universal wheel is available from [GitHub Releases](https://github.com/EMSolution-SSIL/ems_input_json_reader/releases).

## Use

```sh
emso-check-input path/to/input.json
emso-check-input path/to/input.json --format json --output check-result.json
python -m emso_input_checker path/to/input.json
```

Exit codes:

| Code | Meaning |
| --- | --- |
| 0 | Checked with no definite error or unverified portion |
| 1 | Definite setting error |
| 2 | No definite error, but some settings cannot yet be fully checked |
| 3 | File reading, JSON syntax, or command failure |

Diagnostics contain a JSON path and the corresponding C/C++ source location. The current checker covers the main section types and ranges, analysis mode branches, numeric expressions, selected nested fields, and time/BH references. Material, field source, motion, mesh-dependent, and some optional sections remain partly unverified and are reported as `incomplete`. An unfamiliar expression is never executed as Python code and is also reported as incomplete.

The optional `--check-files` flag reports that the external mesh filename cannot be determined from the JSON format selector alone. It does not claim to verify external files.

The supplied motor and IronCoil examples produced no definite setting errors; both report unverified portions with exit code 2. They are not included in this project. Tests use synthetic input data.

## Tests and packaging

```sh
python -m unittest discover -s tests -v
python -m pip wheel . --no-deps -w dist
```

The [implementation plan](INPUT_JSON_CHECKER_PLAN.md) records current coverage and remaining work.

## License

PolyForm Perimeter License 1.0.1. See [LICENSE](LICENSE) and [NOTICE](NOTICE). Use and modification are permitted for the purposes defined by the license; providing a competing input checker to others is restricted. This is a source-available project, not OSI open-source software.

## Validation corpus

The independent corpus in `../reader_json_files/data` contains 255 input JSON files. Run the repeatable check from this project directory:

```powershell
python tests/run_corpus.py --root ../reader_json_files --report build/corpus_report.json
```

The script writes one result per file and matches input/output folders by relative path and numeric filename suffix. Exit code 0 means every input was fully checked, 1 means a definite setting error, 2 means only unverified settings remain, and 3 means an unreadable file or command failure. Use `--allow-incomplete` to accept unverified settings when there are no definite errors. The corpus is not included in the package.

All 255 inputs have unverified settings but no definite setting errors. Two contain `14_Periodic_Boundary_Conditions.PERIODIC_CONDITION[0].CYCLIC=0`. At the user's request, the checker accepts this as an inactive periodic-boundary placeholder and records a warning; omitting the section is the normal form. This is a deliberate tolerance beyond the current C/C++ reader's strict 1 through 5 check. Fifteen input files have no matching output file by the naming convention; this does not change their input-check result. See [the validation report](VALIDATION_REPORT.md).

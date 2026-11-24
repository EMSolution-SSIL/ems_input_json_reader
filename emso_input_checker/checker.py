"""Read-only EMSolution input.json checks with source-traceable diagnostics."""

from __future__ import annotations

import json
import math
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

from .expression import UnsupportedExpression, arithmetic
from .rules import NESTED, SECTIONS, Rule, r


SOURCE_REVISION = "EMSolBuild_VS2022/src@52d71bd"
_MISSING = object()
_FILE_TYPES = {
    "none": 0, "ideas": 1, "atlas": 2, "nastran": 3, "kswad": 4,
    "femap": 5, "cadas": 6, "abaqus": 7, "marc": 8,
    "hyperview": 9, "hv": 9, "json": 10, "gmsh": 11, "hdf5": 12,
    "gid": 13, "gid_post": 13, "atlas_csv": 15, "atlascsv": 15,
    "prostar": 21, "okayama": 22, "hiroshima": 23, "ihi": 24,
    "atlas_melco": 25, "adventure_tetmesh": 26,
}


@dataclass(frozen=True)
class Diagnostic:
    severity: str  # error, warning, incomplete
    code: str
    path: str
    message: str
    source: str = ""


@dataclass
class Report:
    file: str
    diagnostics: list[Diagnostic] = field(default_factory=list)
    source_revision: str = SOURCE_REVISION

    @property
    def exit_code(self) -> int:
        if any(d.code in ("FILE_READ", "JSON_SYNTAX", "ROOT_TYPE") for d in self.diagnostics):
            return 3
        if any(d.severity == "error" for d in self.diagnostics):
            return 1
        if any(d.severity == "incomplete" for d in self.diagnostics):
            return 2
        return 0

    def as_dict(self) -> dict[str, Any]:
        return {
            "file": self.file,
            "source_revision": self.source_revision,
            "exit_code": self.exit_code,
            "counts": {s: sum(d.severity == s for d in self.diagnostics) for s in ("error", "warning", "incomplete")},
            "diagnostics": [asdict(d) for d in self.diagnostics],
        }


def _within(value: float, domain: str) -> bool:
    if not domain:
        return True
    if domain.startswith(">="):
        return value >= float(domain[2:])
    if domain.startswith(">"):
        return value > float(domain[1:])
    if domain.startswith("<="):
        return value <= float(domain[2:])
    if domain.startswith("<"):
        return value < float(domain[1:])
    if domain[0] in "([" and domain[-1] in ")]":
        a, b = map(float, domain[1:-1].split(","))
        lower = value >= a if domain[0] == "[" else value > a
        upper = value <= b if domain[-1] == "]" else value < b
        return lower and upper
    if ".." in domain and "," not in domain:
        a, b = map(float, domain.split(".."))
        return a <= value <= b
    return any(_within(value, item) for item in domain.split(",")) if "," in domain else value == float(domain)


class _Checker:
    def __init__(self, data: dict[str, Any], report: Report, *, check_files: bool = False, base_dir: Path | None = None):
        self.data, self.report = data, report
        self.check_files, self.base_dir = check_files, base_dir
        self.seen: set[str] = set()

    def issue(self, severity: str, code: str, path: str, message: str, source: str = "") -> None:
        marker = (severity, code, path)
        if marker not in self.seen:
            self.report.diagnostics.append(Diagnostic(severity, code, path, message, source))
            self.seen.add(marker)

    def obj(self, value: Any, path: str, *, required: bool = False, source: str = "") -> dict[str, Any] | None:
        if value is _MISSING:
            if required:
                self.issue("error", "REQUIRED", path, "必須のオブジェクトがありません", source)
            return None
        if not isinstance(value, dict):
            self.issue("error", "TYPE", path, "オブジェクトが必要です", source)
            return None
        return value

    def arr(self, value: Any, path: str, *, required: bool = False, source: str = "") -> list[Any] | None:
        if value is _MISSING:
            if required:
                self.issue("error", "REQUIRED", path, "必須の配列がありません", source)
            return None
        if not isinstance(value, list):
            self.issue("error", "TYPE", path, "配列が必要です", source)
            return None
        return value

    def value(self, obj: dict[str, Any] | None, key: str, path: str, rule: Rule) -> Any:
        if obj is None:
            return _MISSING
        full = f"{path}.{key}" if path else key
        value = obj.get(key, _MISSING)
        if value is _MISSING:
            if rule.required:
                self.issue("error", "REQUIRED", full, "必須項目がありません", rule.source)
            return _MISSING
        if rule.kind in ("int_array", "number_array", "rows3"):
            values = self.arr(value, full, source=rule.source)
            if values is None:
                return None
            if rule.kind == "rows3":
                if not values:
                    self.issue("error", "EMPTY", full, "1 行以上必要です", rule.source)
                for i, row in enumerate(values):
                    row_path = f"{full}[{i}]"
                    if not isinstance(row, list) or len(row) != 3:
                        self.issue("error", "ROW_SIZE", row_path, "3 要素の配列が必要です", rule.source)
                        continue
                    for j, item in enumerate(row):
                        self._numeric(item, f"{row_path}[{j}]", "expr_int", "", rule.source)
            else:
                if not values and rule.required:
                    self.issue("error", "EMPTY", full, "1 要素以上必要です", rule.source)
                for i, item in enumerate(values):
                    kind = "expr_int" if rule.kind == "int_array" else "expr"
                    self._numeric(item, f"{full}[{i}]", kind, rule.domain, rule.source)
            return values
        return self._numeric(value, full, rule.kind, rule.domain, rule.source, required=rule.required)

    def _numeric(self, value: Any, path: str, kind: str, domain: str, source: str, *, required: bool = True) -> float | int | None:
        if kind in ("int", "number"):
            good = type(value) is int if kind == "int" else type(value) in (int, float)
            if not good:
                self.issue("error" if required else "warning", "TYPE", path, "整数が必要です" if kind == "int" else "数値が必要です", source)
                return None
            number = value
        else:
            try:
                number = arithmetic(value)
            except UnsupportedExpression as exc:
                self.issue("incomplete", "EXPRESSION", path, str(exc), source)
                return None
            except ValueError as exc:
                self.issue("error", "EXPRESSION", path, str(exc), source)
                return None
            if kind == "expr_int":
                number = int(number)  # C++ converts evaluateExpression<double>() to int.
        if isinstance(number, float) and not math.isfinite(number):
            self.issue("error", "FINITE", path, "有限の数値が必要です", source)
            return None
        if not _within(number, domain):
            self.issue("error", "RANGE", path, f"許容範囲: {domain}", source)
        return number

    def fields(self, obj: dict[str, Any] | None, path: str, rules: dict[str, Rule]) -> None:
        if obj is None:
            return
        for key, rule in rules.items():
            self.value(obj, key, path, rule)

    def run(self) -> None:
        meta = self.obj(self.data.get("metaData", _MISSING), "metaData", source="io/EMSInputJson.cpp:298-306")
        if meta is not None:
            if meta.get("type") != "EMSolution_Input":
                self.issue("error", "META_TYPE", "metaData.type", "EMSolution_Input が必要です", "io/EMSInputJson.cpp:300-304")
        release = self.obj(self.data.get("0_Release_Number", _MISSING), "0_Release_Number", required=True, source="io/EMSInputJson.cpp:308-324")
        if release is not None:
            if "RLS_NO" not in release:
                self.issue("error", "REQUIRED", "0_Release_Number.RLS_NO", "必須項目がありません", "io/EMSInputJson.cpp:312-320")
            elif not isinstance(release["RLS_NO"], str):
                self.issue("error", "TYPE", "0_Release_Number.RLS_NO", "リリース番号の文字列が必要です", "io/EMSInputJson.cpp:313-314")

        required = {"1_Execution_Control", "2_Analysis_Type", "10_1_Input_Files", "12_Geometry", "13_Boundary_Conditions", "17_Field_Source", "18_Time_Function"}
        input_files = self.data.get("10_1_Input_Files")
        if not (isinstance(input_files, dict) and input_files.get("MESHLESS") == 1):
            required.add("16_Material_Properties")
        raw_ac = self.data.get("2_Analysis_Type", {}).get("AC", 0) if isinstance(self.data.get("2_Analysis_Type"), dict) else 0
        ac = raw_ac if type(raw_ac) is int else 0
        required |= {"8_2_Calculation_Frequency"} if ac else {"8_Calculation_Step", "9_Output_Step"}
        for section, rules in SECTIONS.items():
            if section in ("8_Calculation_Step", "9_Output_Step") and ac:
                continue
            if section == "8_2_Calculation_Frequency" and not ac:
                continue
            obj = self.obj(self.data.get(section, _MISSING), section, required=section in required, source=next(iter(rules.values())).source)
            self.fields(obj, section, rules)
        for path, rules in NESTED.items():
            parent, name = path.split(".", 1)
            base = self.data.get(parent)
            if isinstance(base, dict):
                self.fields(self.obj(base.get(name, _MISSING), path), path, rules)

        analysis = self.data.get("2_Analysis_Type")
        if isinstance(analysis, dict) and not any(type(analysis.get(k)) is int for k in ("STATIC", "AC", "TRANSIENT", "STEADY_CURRENT")):
            self.issue("error", "ANALYSIS", "2_Analysis_Type", "解析方式を少なくとも1つ指定してください", "io/EMSInputJson.cpp:388-393")
        self._steps(ac)
        self._files()
        self._print_output()
        self._boundary()
        self._periodic()
        self._expansion()
        self._materials()
        time_ids = self._time_functions()
        self._sources(time_ids)
        self._motion(time_ids)
        self._bh_curves()
        self._remaining_sections()
        self._unverified_keys()

    def _steps(self, ac: int) -> None:
        if ac:
            sec = self.data.get("8_2_Calculation_Frequency")
            if isinstance(sec, dict):
                if not any(key in sec for key in ("INITIAL_PHASE", "LAST_PHSE", "PHASE_INTERVAL")):
                    self.issue("error", "REQUIRED_ONE", "8_2_Calculation_Frequency", "位相出力の指定が必要です", "io/EMSInputJson.cpp:1539-1543")
                lo_phase, hi_phase = sec.get("INITIAL_PHASE", 0), sec.get("LAST_PHSE", 0)
                if type(lo_phase) in (int, float) and type(hi_phase) in (int, float) and lo_phase > hi_phase:
                    self.issue("error", "PHASE_ORDER", "8_2_Calculation_Frequency", "INITIAL_PHASE は LAST_PHSE 以下にしてください", "io/EMSInputJson.cpp:1545-1546")
                lo, hi = sec.get("FREQUENCY"), sec.get("MAX_FREQUENCY")
                try:
                    if hi is not None and arithmetic(hi) not in (0,) and arithmetic(hi) < arithmetic(lo):
                        self.issue("error", "FREQUENCY_ORDER", "8_2_Calculation_Frequency.MAX_FREQUENCY", "FREQUENCY 以上か 0 が必要です", "io/EMSInputJson.cpp:1505")
                except (ValueError, TypeError):
                    pass
            return
        sec = self.data.get("8_Calculation_Step")
        if isinstance(sec, dict):
            a, b = sec.get("NO_STEPS"), sec.get("DELTA_TIME")
            if isinstance(a, list) and isinstance(b, list) and len(a) != len(b):
                self.issue("error", "LENGTH", "8_Calculation_Step", "NO_STEPS と DELTA_TIME の要素数が異なります", "io/EMSInputJson.cpp:1324-1325")

    def _files(self) -> None:
        sec = self.data.get("10_1_Input_Files")
        if isinstance(sec, dict) and "INPUT_MESH_FILE" not in sec and "UNIT" not in sec:
            self.issue("error", "REQUIRED_ONE", "10_1_Input_Files", "INPUT_MESH_FILE または UNIT が必要です", "io/EMSInputJson.cpp:1639-1642")
        for section, key, source in (("10_1_Input_Files", "INPUT_MESH_FILE", "io/EMSInputJson.cpp:1597-1614"), ("10_1_Input_Files", "POST_DATA_FILE", "io/EMSInputJson.cpp:1620-1635"), ("10_2_Output_Files", "POST_DATA_FILE", "io/EMSInputJson.cpp:1695-1707")):
            obj = self.data.get(section)
            if not isinstance(obj, dict) or key not in obj:
                continue
            value = obj[key]
            path = f"{section}.{key}"
            if type(value) is int:
                number = value
            elif isinstance(value, str):
                normalized = value.strip().lower().replace("-", "_").replace(" ", "_")
                number = int(normalized) if normalized.isdecimal() else _FILE_TYPES.get(normalized)
                if number is None:
                    self.issue("error", "FILE_TYPE", path, "未知のファイル形式名です", source)
                    continue
            else:
                self.issue("error", "TYPE", path, "ファイル形式の整数または名前が必要です", source)
                continue
            allowed = (0 <= number <= 15 or number in (22, 23, 24, 26)) if key == "INPUT_MESH_FILE" else (0 <= number <= 19 and number not in (7, 8))
            if not allowed:
                self.issue("error", "FILE_TYPE", path, "この節で使用できないファイル形式です", source)
        if self.check_files:
            self.issue("incomplete", "FILE_REFERENCES", "10_1_Input_Files", "メッシュファイル名は input.json の形式番号だけでは確定できません", "io/EMSInputJson.cpp:1597-1614")

    def _print_output(self) -> None:
        section = self.data.get("11_Print_Output")
        if not isinstance(section, dict):
            return
        for key in ("FORCE_NODAL", "IRON_LOSS"):
            if key not in section:
                continue
            path = f"11_Print_Output.{key}"
            obj = self.obj(section[key], path, source="io/EMSInputJson.cpp:2270-2315")
            if obj is None:
                continue
            self.value(obj, "TYPE", path, r("int", required=True, source="io/EMSInputJson.cpp:2272-2275,2313-2316"))
            if key == "FORCE_NODAL":
                for name in ("FORCE_REGIONS", "SURFACE_FORCE"):
                    if name in obj:
                        rows = self.arr(obj[name], path + "." + name, source="io/EMSInputJson.cpp:2278-2308")
                        if rows is not None and name == "FORCE_REGIONS":
                            for i, row in enumerate(rows):
                                if not isinstance(row, list):
                                    self.issue("error", "TYPE", f"{path}.{name}[{i}]", "整数の配列が必要です", "io/EMSInputJson.cpp:2281-2293")
                                else:
                                    for j, item in enumerate(row):
                                        self._numeric(item, f"{path}.{name}[{i}][{j}]", "expr_int", "", "io/EMSInputJson.cpp:2281-2293")
            else:
                for name, domain in (("FREQUENCY", ">0"), ("ALPHA", ">=0"), ("BETA", ">=0"), ("GAMMA", ">=0")):
                    self.value(obj, name, path, r("number", domain, source="io/EMSInputJson.cpp:2321-2324"))
                if set(obj) - {"TYPE", "CALC_B_MAX", "FREQUENCY", "ALPHA", "BETA", "GAMMA"}:
                    self.issue("incomplete", "PRINT_DETAIL", path, "IRON_LOSS の追加項目は未検査です", "io/EMSInputJson.cpp:2311-2350")

    def _boundary(self) -> None:
        obj = self.data.get("13_Boundary_Conditions")
        if not isinstance(obj, dict):
            return
        if "DISTANCE_JUDGE" in obj:
            self.value(obj, "DISTANCE_JUDGE", "13_Boundary_Conditions", SECTIONS["13_Boundary_Conditions"]["DISTANCE_JUDGE"])
        for name in ("DIRICHLET_PLANE", "NEUMANN_PLANE"):
            if name not in obj:
                continue
            path = f"13_Boundary_Conditions.{name}"
            part = self.obj(obj[name], path, source="boundary/boundary_cond.c:81-124")
            if part is None:
                continue
            rows = self.arr(part.get("CXYZ", _MISSING), path + ".CXYZ", required=True, source="boundary/boundary_cond.c:85,123")
            if rows is not None:
                for i, row in enumerate(rows):
                    if not isinstance(row, list):
                        self.issue("error", "TYPE", f"{path}.CXYZ[{i}]", "数値の配列が必要です", "boundary/boundary_cond.c:85,123")
                    else:
                        for j, item in enumerate(row):
                            self._numeric(item, f"{path}.CXYZ[{i}][{j}]", "expr", "", "boundary/boundary_cond.c:85,123")
            self.issue("incomplete", "BOUNDARY_DETAIL", "13_Boundary_Conditions", "座標列の意味とメッシュとの関係は静的検査の対象外です", "boundary/boundary_cond.c")

    def _periodic(self) -> None:
        section = self.obj(self.data.get("14_Periodic_Boundary_Conditions", _MISSING), "14_Periodic_Boundary_Conditions", source="boundary/boundary_cond.c:330-334")
        if section is None:
            return
        values = self.arr(section.get("PERIODIC_CONDITION", _MISSING), "14_Periodic_Boundary_Conditions.PERIODIC_CONDITION", source="boundary/boundary_cond.c:332-334")
        if values is None:
            return
        active = False
        for i, item in enumerate(values):
            path = f"14_Periodic_Boundary_Conditions.PERIODIC_CONDITION[{i}]"
            obj = self.obj(item, path, source="boundary/boundary_cond.c:339-340")
            if obj is None:
                continue
            # A zero row is a user-written placeholder for no periodic boundary.
            # The solver's strict 1..5 check is intentionally relaxed here.
            if type(obj.get("CYCLIC")) is int and obj["CYCLIC"] == 0:
                self.issue("warning", "INACTIVE_PERIODIC", path + ".CYCLIC",
                           "CYCLIC=0 は周期境界条件なしとして扱います。項目自体は省略できます",
                           "boundary/boundary_cond.c:339")
                continue
            active = True
            self.value(obj, "CYCLIC", path, r("int", "1..5", source="boundary/boundary_cond.c:339"))
            self.value(obj, "SYMMETRY", path, r("int", "0,1", source="boundary/boundary_cond.c:340"))
            for key in ("ANGLE", "SEPERATE_ANGLE"):
                self.value(obj, key, path, r("expr", source="boundary/boundary_cond.c:587,608"))
            if "SLIDE_CONDITION" in obj:
                slides = self.arr(obj["SLIDE_CONDITION"], path + ".SLIDE_CONDITION", source="boundary/boundary_cond.c:357-369")
                if slides is not None:
                    for j, item_ in enumerate(slides):
                        subpath = f"{path}.SLIDE_CONDITION[{j}]"
                        slide = self.obj(item_, subpath, source="boundary/boundary_cond.c:362-369")
                        if slide is None:
                            continue
                        for key in ("SLIDE_NDIV", "SLIDE_MAT_ID", "MOVING_DIRECTION_MAT_ID"):
                            self.value(slide, key, subpath, r("int", source="boundary/boundary_cond.c:362-367"))
                        self.value(slide, "FITNESS", subpath, r("expr", "[0,0.5)", source="boundary/boundary_cond.c:369"))
        if active:
            self.issue("incomplete", "PERIODIC_DETAIL", "14_Periodic_Boundary_Conditions", "周期面の対応とメッシュ情報を用いた条件は未検査です", "boundary/boundary_cond.c")

    def _expansion(self) -> None:
        root = "2D_to_3D_expansion"
        section = self.obj(self.data.get(root, _MISSING), root, source="io/2D_to_3D/layers.c:34")
        if section is None:
            return
        options = self.obj(section.get("1_Optional_parameters", _MISSING), root + ".1_Optional_parameters")
        if options is not None:
            for key, rule in {
                "COORD_ID": r("int", ">=0", source="io/2D_to_3D/layers.c:46"),
                "EX_DIRECT": r("int", "0,1", source="io/2D_to_3D/layers.c:47"),
                "PITCH": r("number", source="io/2D_to_3D/layers.c:48"),
                "ROTOR_PITCH": r("number", source="io/2D_to_3D/layers.c:49"),
            }.items():
                self.value(options, key, root + ".1_Optional_parameters", rule)
        arrays: dict[str, dict[str, list[Any]]] = {}
        specs = {
            "2_Expansion_positions": {"DIVISIONS": "int_array", "Z_POSITIONS": "number_array", "DIVISION_RATIO": "number_array", "TWIST": "int_array"},
            "3_Expansion_of_materials": {"BASE_MAT_IDS": "int_array", "DIVISIONS": "int_array", "MAT_IDS": "rows_int"},
            "4_Surface_creation": {"BASE_MAT_IDS": "int_array", "SURFACE_MAT_IDS": "int_array", "LAYER_POSITIONS": "int_array"},
        }
        for name, fields in specs.items():
            part = self.obj(section.get(name, _MISSING), root + "." + name, source="io/2D_to_3D/layers.c:61-120")
            if part is None:
                continue
            arrays[name] = {}
            for key, kind in fields.items():
                path = f"{root}.{name}"
                if kind == "rows_int":
                    rows = self.arr(part.get(key, _MISSING), path + "." + key, source="io/2D_to_3D/layers.c:92")
                    if rows is not None:
                        arrays[name][key] = rows
                        for i, row in enumerate(rows):
                            if not isinstance(row, list):
                                self.issue("error", "TYPE", f"{path}.{key}[{i}]", "整数の配列が必要です", "io/2D_to_3D/layers.c:92")
                            else:
                                for j, item in enumerate(row):
                                    self._numeric(item, f"{path}.{key}[{i}][{j}]", "expr_int", "", "io/2D_to_3D/layers.c:92")
                else:
                    value = self.value(part, key, path, r(kind, source="io/2D_to_3D/layers.c:65-110"))
                    if isinstance(value, list):
                        arrays[name][key] = value
            if name == "2_Expansion_positions":
                self.value(part, "Z_BASE_POSITION", f"{root}.{name}", r("number", source="io/2D_to_3D/layers.c:64"))
        positions = arrays.get("2_Expansion_positions", {})
        materials = arrays.get("3_Expansion_of_materials", {})
        surfaces = arrays.get("4_Surface_creation", {})
        if all(k in positions for k in ("DIVISIONS", "Z_POSITIONS", "DIVISION_RATIO")):
            if len({len(positions[k]) for k in ("DIVISIONS", "Z_POSITIONS", "DIVISION_RATIO")}) != 1:
                self.issue("error", "LENGTH", root + ".2_Expansion_positions", "DIVISIONS、Z_POSITIONS、DIVISION_RATIO の要素数が異なります", "io/2D_to_3D/layers.c:69-70")
        if all(k in surfaces for k in ("BASE_MAT_IDS", "SURFACE_MAT_IDS", "LAYER_POSITIONS")):
            if len({len(surfaces[k]) for k in ("BASE_MAT_IDS", "SURFACE_MAT_IDS", "LAYER_POSITIONS")}) != 1:
                self.issue("error", "LENGTH", root + ".4_Surface_creation", "表面生成の各配列の要素数が異なります", "io/2D_to_3D/layers.c:111-112")
        if "DIVISIONS" in positions and "DIVISIONS" in materials:
            try:
                a = sum(arithmetic(v) for v in positions["DIVISIONS"])
                b = sum(arithmetic(v) for v in materials["DIVISIONS"])
            except ValueError:
                pass
            else:
                if a != b:
                    self.issue("error", "DIVISION_TOTAL", root, "位置と材料の DIVISIONS の合計が異なります", "io/2D_to_3D/layers.c:121-122")
        self.issue("incomplete", "EXPANSION_DETAIL", root, "拡張後の材料・表面 ID と形状はメッシュなしでは未検査です", "io/2D_to_3D/layers.c")

    def _materials(self) -> None:
        section = self.data.get("16_Material_Properties")
        if not isinstance(section, dict):
            return
        arrays = ("16_1_3D_Element_Properties", "16_2_2D_Element_Properties")
        meshless = self.data.get("10_1_Input_Files", {}).get("MESHLESS") if isinstance(self.data.get("10_1_Input_Files"), dict) else None
        if not any(key in section for key in arrays) and meshless != 1:
            self.issue("error", "REQUIRED", "16_Material_Properties.16_1_3D_Element_Properties", "材料配列が必要です", "property/mat_property.c:65-93")
        ids: set[int] = set()
        for name in arrays:
            raw_values = section.get(name, _MISSING)
            values = [] if raw_values is None else self.arr(raw_values, f"16_Material_Properties.{name}", source="property/mat_property.c:68-78")
            if values is None:
                continue
            for i, item in enumerate(values):
                path = f"16_Material_Properties.{name}[{i}]"
                mat = self.obj(item, path, source="property/mat_property.c:124-130")
                if mat is None:
                    continue
                ident = self.value(mat, "MAT_ID" if name.startswith("16_1") else "SMAT_ID", path, r("int", ">=1", required=True, source="property/mat_property.c:126,553"))
                if type(ident) is int:
                    if ident in ids:
                        self.issue("error", "DUPLICATE_ID", path, f"材料 ID {ident} が重複しています", "property/mat_property.c:126,553")
                    ids.add(ident)
                if name.startswith("16_1"):
                    self.value(mat, "POTENTIAL", path, r("int", ">=0", source="property/mat_property.c:130"))
                    self.value(mat, "is_DESIGN_DOMAIN", path, r("int", ">0", source="property/mat_property.c:204"))
                    mag = self.obj(mat.get("MagneticProperty", _MISSING), path + ".MagneticProperty")
                    if mag is not None:
                        bh_id = self.value(mag, "BH_CURVE_ID", path + ".MagneticProperty", r("int", ">=0", source="property/mat_property.c:140"))
                        self.value(mag, "MU", path + ".MagneticProperty", r("expr", ">=1", source="property/mat_property.c:146"))
                        if type(bh_id) is int and bh_id > 0 and isinstance(self.data.get("20_BH_Curve"), list):
                            curve_ids = {curve.get("BH_CURVE_ID") for curve in self.data["20_BH_Curve"] if isinstance(curve, dict)}
                            if bh_id not in curve_ids:
                                self.issue("error", "BH_REFERENCE", path + ".MagneticProperty.BH_CURVE_ID", f"BH_CURVE_ID {bh_id} が 20_BH_Curve にありません", "property/mat_property.c:140; property/magnetic_property.c:190")
                        packing = self.obj(mag.get("PACKING", _MISSING), path + ".MagneticProperty.PACKING")
                        if packing is not None:
                            self.value(packing, "PACKING_FACTOR", path + ".MagneticProperty.PACKING", r("expr", "<=1", source="property/mat_property.c:143"))
                            self.value(packing, "COORD_ID", path + ".MagneticProperty.PACKING", r("int", ">=0", source="property/mat_property.c:143"))
                    electric = self.obj(mat.get("ElectricProperty", _MISSING), path + ".ElectricProperty")
                    if electric is not None:
                        conductivity = self.obj(electric.get("conductivity", _MISSING), path + ".ElectricProperty.conductivity")
                        if conductivity is not None:
                            self.value(conductivity, "SIGMA", path + ".ElectricProperty.conductivity", r("expr", source="property/mat_property.c:179"))
                            self.value(conductivity, "TEMP_DEPEND_SIGMA_ID", path + ".ElectricProperty.conductivity", r("int", ">=0", source="property/mat_property.c:185"))
                        permittivity = self.obj(electric.get("permittivity", _MISSING), path + ".ElectricProperty.permittivity")
                        if permittivity is not None:
                            self.value(permittivity, "EPS", path + ".ElectricProperty.permittivity", r("expr", ">=1", source="property/mat_property.c:190"))
                self.issue("incomplete", "MATERIAL_DETAIL", "16_Material_Properties", "解析方式別の材料物性とメッシュ ID は一部未検査です", "property/mat_property.c")

    def _time_functions(self) -> set[int]:
        values = self.arr(self.data.get("18_Time_Function", _MISSING), "18_Time_Function", required=True, source="time_function/time_evolutions.c:105-112")
        ids: set[int] = set()
        if values is None:
            return ids
        for i, item in enumerate(values):
            path = f"18_Time_Function[{i}]"
            obj = self.obj(item, path, source="time_function/time_evolutions.c:137-140")
            if obj is None:
                continue
            ident = self.value(obj, "TIME_ID", path, r("int", ">=1", required=True, source="time_function/time_evolutions.c:137-140"))
            option = self.value(obj, "OPTION", path, r("int", "0,1,2,3,4,11", required=True, source="time_function/time_evolutions.c:138; time_function/time_evolution.h:6"))
            if type(ident) is int:
                if ident in ids:
                    self.issue("error", "DUPLICATE_ID", path + ".TIME_ID", f"TIME_ID {ident} が重複しています", "time_function/time_evolutions.c:137")
                ids.add(ident)
            for key in ("AMPLITUDE", "TCYCLE", "PHASE", "C0", "C1", "C2", "C3", "C4", "C5", "C6", "TEXP", "PHASE4"):
                self.value(obj, key, path, r("expr", ">0" if key == "TCYCLE" and option == 2 else "", required=(option == 0 and key in ("C0", "TEXP")) or (option == 2 and key == "AMPLITUDE"), source="time_function/time_evolutions.c:170-319"))
            if option == 1:
                for key in ("TIME", "VALUE"):
                    self.value(obj, key, path, r("number_array", required=True, source="time_function/time_evolutions.c:254-260"))
            self.issue("incomplete", "TIME_DETAIL", "18_Time_Function", "OPTION 別の関数・表の構造は一部未検査です", "time_function/time_evolutions.c")
        return ids

    def _sources(self, time_ids: set[int]) -> None:
        values = self.arr(self.data.get("17_Field_Source", _MISSING), "17_Field_Source", required=True, source="source/field_sources.c:94-100")
        if values is None:
            return
        known = {"COIL", "ELMCUR", "SDEFCOIL", "PHICOIL", "DCCURR", "MAGNET", "SUFCUR", "SUFCUR2", "MPOTSUF", "NETWORK", "CIRCUIT", "EXTERNAL_FIELD", "GIVEN_POTENTIAL"}
        for i, item in enumerate(values):
            path = f"17_Field_Source[{i}]"
            obj = self.obj(item, path, source="source/field_sources.c:113-420")
            if obj is None:
                continue
            kinds = [key for key in obj if key in known]
            if len(kinds) != 1:
                self.issue("incomplete", "SOURCE_KIND", path, "磁界源の種類を確定できません", "source/field_sources.c:113-604")
                continue
            kind = kinds[0]
            body = self.obj(obj[kind], f"{path}.{kind}", source="source/field_sources.c:113-420")
            if body is None:
                continue
            base = f"{path}.{kind}"
            if kind not in ("NETWORK", "CIRCUIT"):
                self.value(body, "SERIES_ID", base, r("int", ">=1", required=True, source="source/field_sources.c:118-320"))
            if kind == "MAGNET":
                self.value(body, "TIME_ID", base, r("int", ">=1", required=True, source="source/field_sources.c:321-323"))
                self.value(body, "INPUT_TYPE", base, r("int", "0..5", source="source/field_sources.c:338"))
            elif "TIME_ID" in body:
                self.value(body, "TIME_ID", base, r("int", ">=0", source="source/field_sources.c"))
            if kind == "NETWORK":
                self.value(body, "REGION_FACTOR", base, r("number", ">=1", required=True, source="source/field_sources.c:571-573"))
                self.value(body, "REGION_PARALLEL", base, r("number", ">=1", source="source/field_sources.c:575"))
                self.value(body, "PREDICTOR_MODIFIER", base, r("int", "0..2", source="source/field_sources.c:578"))
            time_id = body.get("TIME_ID")
            if type(time_id) is int and time_id > 0 and time_id not in time_ids:
                self.issue("error", "TIME_REFERENCE", base + ".TIME_ID", f"TIME_ID {time_id} が 18_Time_Function にありません", "source/field_sources.c; time_function/time_evolutions.c")
            if "data" in body:
                self.arr(body["data"], base + ".data", source="source/field_sources.c")
            self.issue("incomplete", "SOURCE_DETAIL", "17_Field_Source", "磁界源内部のメッシュ ID と種類別データは一部未検査です", "source/field_sources.c")

    def _motion(self, time_ids: set[int]) -> None:
        if "19_Motion" not in self.data:
            return
        values = self.arr(self.data["19_Motion"], "19_Motion", source="option/dynamic_motion/motion.c:23")
        if values is None:
            return
        for i, item in enumerate(values):
            path = f"19_Motion[{i}]"
            obj = self.obj(item, path, source="option/dynamic_motion/motion.c:23-70")
            if obj is None:
                continue
            motion = self.obj(obj.get("motion_data", _MISSING), path + ".motion_data", required=True, source="option/dynamic_motion/motion.c:113-121")
            if motion is not None:
                self.value(motion, "MOTION_ID", path + ".motion_data", r("int", ">=1", required=True, source="option/dynamic_motion/motion.c:113"))
                for key in ("X_TIME_ID", "Y_TIME_ID", "Z_TIME_ID", "PHI_TIME_ID"):
                    self.value(motion, key, path + ".motion_data", r("int", ">=0", source="option/dynamic_motion/motion.c:117-121"))
                    ident = motion.get(key)
                    if type(ident) is int and ident > 0 and ident not in time_ids:
                        self.issue("error", "TIME_REFERENCE", path + ".motion_data." + key, f"TIME_ID {ident} が 18_Time_Function にありません", "option/dynamic_motion/motion.c")
            self.issue("incomplete", "MOTION_DETAIL", "19_Motion", "運動方式別のパラメータは一部未検査です", "option/dynamic_motion/motion.c")

    def _bh_curves(self) -> None:
        for name in ("20_BH_Curve", "20_B_H_Curve"):
            if name not in self.data:
                continue
            if name == "20_B_H_Curve":
                self.issue("incomplete", "BH_ALIAS", name, "現行ソースの読込キーは 20_BH_Curve です。この別表記は未検査です", "property/magnetic_property.c:155-156")
                continue
            values = self.arr(self.data[name], name, source="property/magnetic_property.c:155-190")
            if values is None:
                continue
            ids: set[int] = set()
            for i, item in enumerate(values):
                path = f"{name}[{i}]"
                obj = self.obj(item, path, source="property/magnetic_property.c:189-190")
                if obj is None:
                    continue
                ident = self.value(obj, "BH_CURVE_ID", path, r("int", ">=1", required=True, source="property/magnetic_property.c:190"))
                if type(ident) is int:
                    if ident in ids:
                        self.issue("error", "DUPLICATE_ID", path + ".BH_CURVE_ID", f"BH_CURVE_ID {ident} が重複しています", "property/magnetic_property.c")
                    ids.add(ident)
                if "encrypted_data" in obj:
                    self.issue("incomplete", "BH_ENCRYPTED", "20_BH_Curve", "暗号化された BH データの内容は未検査です", "property/B_H_curves.c:64-68")
                    continue
                data = self.obj(obj.get("data", _MISSING), path + ".data", required=True, source="property/B_H_curves.c:43-54")
                if data is not None:
                    h = self.arr(data.get("H", _MISSING), path + ".data.H", source="property/B_H_curves.c:44")
                    b = self.arr(data.get("B", _MISSING), path + ".data.B", source="property/B_H_curves.c:45")
                    if h and b:
                        if len(h) != len(b):
                            self.issue("error", "LENGTH", path + ".data", "H と B の要素数が異なります", "property/B_H_curves.c:46-50")
                        for key, values_ in (("H", h), ("B", b)):
                            for j, item_ in enumerate(values_):
                                self._numeric(item_, f"{path}.data.{key}[{j}]", "expr", "", "property/B_H_curves.c:44-45")
                    else:
                        rows = self.arr(data.get("H_B", _MISSING), path + ".data.H_B", required=True, source="property/B_H_curves.c:52-60")
                        if rows is not None:
                            if not rows:
                                self.issue("error", "EMPTY", path + ".data.H_B", "1 行以上必要です", "property/B_H_curves.c:52-54")
                            for j, row in enumerate(rows):
                                row_path = f"{path}.data.H_B[{j}]"
                                if not isinstance(row, list) or len(row) != 2:
                                    self.issue("error", "ROW_SIZE", row_path, "[H, B] の2要素が必要です", "property/B_H_curves.c:58-60")
                                    continue
                                for k, item_ in enumerate(row):
                                    self._numeric(item_, f"{row_path}[{k}]", "expr", "", "property/B_H_curves.c:52-60")
                self.issue("incomplete", "BH_DETAIL", "20_BH_Curve", "BH 曲線の材料への割当条件は一部未検査です", "property/magnetic_property.c")

    def _remaining_sections(self) -> None:
        covered = set(SECTIONS) | {"metaData", "0_Release_Number", "14_Periodic_Boundary_Conditions", "2D_to_3D_expansion", "17_Field_Source", "18_Time_Function", "19_Motion", "20_BH_Curve", "20_B_H_Curve"}
        for key in self.data:
            if key not in covered:
                self.issue("incomplete", "SECTION", key, "この節の詳細ルールは未実装です", "io/read_control_input.c:90-180")

    def _unverified_keys(self) -> None:
        additionally_checked = {
            "5_Convergence_Conditions": {"5_2_Nonlinear_Convergence_Condition"},
            "8_Calculation_Step": {"TP_EEC"},
            "10_1_Input_Files": {"INPUT_MESH_FILE", "POST_DATA_FILE"},
            "10_2_Output_Files": {"POST_DATA_FILE", "OUTPUT_MATS"},
            "13_Boundary_Conditions": {"DIRICHLET_PLANE", "NEUMANN_PLANE"},
            "16_Material_Properties": {"16_1_3D_Element_Properties", "16_2_2D_Element_Properties"},
            "11_Print_Output": {"FORCE_NODAL", "IRON_LOSS"},
        }
        for section, rules in SECTIONS.items():
            obj = self.data.get(section)
            if not isinstance(obj, dict):
                continue
            unchecked = sorted(set(obj) - set(rules) - additionally_checked.get(section, set()))
            if unchecked:
                self.issue("incomplete", "UNVERIFIED_KEYS", section, "未検査の項目: " + ", ".join(unchecked), "io/read_control_input.c:90-180")


def check_input(data: Any, *, filename: str = "<memory>", check_files: bool = False, base_dir: Path | None = None) -> Report:
    """Validate a decoded document without modifying it."""
    report = Report(filename)
    if not isinstance(data, dict):
        report.diagnostics.append(Diagnostic("error", "ROOT_TYPE", "$", "トップレベルにはオブジェクトが必要です"))
        return report
    _Checker(data, report, check_files=check_files, base_dir=base_dir).run()
    return report


def check_file(path: str | Path, *, check_files: bool = False, base_dir: str | Path | None = None) -> Report:
    file = Path(path)
    try:
        data = json.loads(file.read_text(encoding="utf-8-sig"))
    except (OSError, UnicodeError) as exc:
        return Report(str(file), [Diagnostic("error", "FILE_READ", "$", str(exc))])
    except json.JSONDecodeError as exc:
        return Report(str(file), [Diagnostic("error", "JSON_SYNTAX", "$", f"{exc.msg} (line {exc.lineno}, column {exc.colno})")])
    return check_input(data, filename=str(file), check_files=check_files, base_dir=Path(base_dir) if base_dir else file.parent)

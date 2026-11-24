"""Synthetic cases based on EMSolution's source branches, not local models."""

from __future__ import annotations

import copy
import json
import tempfile
import unittest
from pathlib import Path

from emso_input_checker import check_file, check_input
from emso_input_checker.cli import main


def minimal_input(*, ac: bool = False) -> dict:
    data = {
        "metaData": {"type": "EMSolution_Input"},
        "0_Release_Number": {"RLS_NO": "R3.0"},
        "1_Execution_Control": {
            "PRE_PROCESSING": 1,
            "MAKE_SYSTEM_MATRICES": 1,
            "SOLVE_EQUATION": 1,
            "POST_PROCESSING": 1,
        },
        "2_Analysis_Type": {"AC": 1 if ac else 0, "STATIC": 0 if ac else 1},
        "10_1_Input_Files": {"UNIT": 0},
        "12_Geometry": {"GEOMETRY": 0},
        "13_Boundary_Conditions": {"FAR_BOUNDARY_CONDITION": 0},
        "16_Material_Properties": {"16_1_3D_Element_Properties": []},
        "17_Field_Source": [],
        "18_Time_Function": [],
    }
    if ac:
        data["8_2_Calculation_Frequency"] = {"FREQUENCY": "100*2", "MAX_FREQUENCY": 200, "INITIAL_PHASE": 0}
    else:
        data["8_Calculation_Step"] = {"INITIAL_TIME": 0, "NO_STEPS": [2], "DELTA_TIME": ["1/1000"]}
        data["9_Output_Step"] = {"OUTPUT_STEP_SET": [[1, 2, 1]]}
    return data


class InputCheckerTests(unittest.TestCase):
    def test_static_and_ac_branches(self) -> None:
        self.assertEqual(check_input(minimal_input()).exit_code, 0)
        self.assertEqual(check_input(minimal_input(ac=True)).exit_code, 0)

    def test_multiple_independent_errors_include_paths(self) -> None:
        data = minimal_input()
        data["1_Execution_Control"]["POST_PROCESSING"] = 2
        data["8_Calculation_Step"]["DELTA_TIME"] = [-1, 2]
        data["9_Output_Step"]["OUTPUT_STEP_SET"] = [[1, 2]]
        report = check_input(data)
        paths = {d.path for d in report.diagnostics if d.severity == "error"}
        self.assertIn("1_Execution_Control.POST_PROCESSING", paths)
        self.assertIn("8_Calculation_Step.DELTA_TIME[0]", paths)
        self.assertIn("8_Calculation_Step", paths)
        self.assertIn("9_Output_Step.OUTPUT_STEP_SET[0]", paths)
        self.assertEqual(report.exit_code, 1)

    def test_ac_frequency_must_be_positive(self) -> None:
        data = minimal_input(ac=True)
        data["8_2_Calculation_Frequency"]["FREQUENCY"] = 0
        report = check_input(data)
        self.assertIn("8_2_Calculation_Frequency.FREQUENCY", {d.path for d in report.diagnostics})

    def test_expression_never_executes_python(self) -> None:
        data = minimal_input()
        data["8_Calculation_Step"]["INITIAL_TIME"] = "__import__('os').system('echo bad')"
        report = check_input(data)
        self.assertEqual(report.exit_code, 2)
        self.assertTrue(any(d.code == "EXPRESSION" for d in report.diagnostics))

    def test_time_id_reference_and_input_immutability(self) -> None:
        data = minimal_input()
        data["17_Field_Source"] = [{"MAGNET": {"SERIES_ID": 1, "TIME_ID": 3, "data": []}}]
        before = copy.deepcopy(data)
        report = check_input(data)
        self.assertEqual(data, before)
        self.assertTrue(any(d.code == "TIME_REFERENCE" for d in report.diagnostics))

    def test_expansion_divisions_and_periodic_fitness(self) -> None:
        data = minimal_input()
        data["2D_to_3D_expansion"] = {
            "2_Expansion_positions": {"DIVISIONS": [2], "Z_POSITIONS": [1.0], "DIVISION_RATIO": [1.0]},
            "3_Expansion_of_materials": {"DIVISIONS": [3]},
        }
        data["14_Periodic_Boundary_Conditions"] = {
            "PERIODIC_CONDITION": [{"CYCLIC": 2, "SLIDE_CONDITION": [{"FITNESS": 0.5}]}]
        }
        report = check_input(data)
        self.assertEqual(report.exit_code, 1)
        self.assertIn("DIVISION_TOTAL", {d.code for d in report.diagnostics})
        self.assertIn("14_Periodic_Boundary_Conditions.PERIODIC_CONDITION[0].SLIDE_CONDITION[0].FITNESS", {d.path for d in report.diagnostics})

    def test_optional_wrong_type_is_warning_because_reader_ignores_it(self) -> None:
        data = minimal_input()
        data["5_Convergence_Conditions"] = {"DIV_ITERATIONS": "10"}
        report = check_input(data)
        self.assertEqual(report.exit_code, 0)
        self.assertTrue(any(d.severity == "warning" and d.path.endswith("DIV_ITERATIONS") for d in report.diagnostics))

    def test_file_type_names_follow_cpp_enum(self) -> None:
        data = minimal_input()
        data["10_1_Input_Files"]["INPUT_MESH_FILE"] = "ATLAS-CSV"
        data["10_2_Output_Files"] = {"POST_DATA_FILE": "JSON"}
        self.assertEqual(check_input(data).exit_code, 0)
        data["10_2_Output_Files"]["POST_DATA_FILE"] = "ABAQUS"
        report = check_input(data)
        self.assertTrue(any(d.code == "FILE_TYPE" and d.path == "10_2_Output_Files.POST_DATA_FILE" for d in report.diagnostics))

    def test_bh_pair_table_is_accepted(self) -> None:
        data = minimal_input()
        data["20_BH_Curve"] = [{"BH_CURVE_ID": 1, "data": {"H_B": [[0, 0], [100, 0.1]]}}]
        report = check_input(data)
        self.assertEqual(report.exit_code, 2)
        self.assertFalse(any(d.severity == "error" for d in report.diagnostics))

    def test_cli_json_output_and_syntax_error(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / "input.json"
            result = Path(directory) / "result.json"
            source.write_text(json.dumps(minimal_input()), encoding="utf-8")
            self.assertEqual(main([str(source), "--format", "json", "--output", str(result)]), 0)
            self.assertEqual(json.loads(result.read_text(encoding="utf-8"))["exit_code"], 0)
            source.write_text("{", encoding="utf-8")
            self.assertEqual(check_file(source).exit_code, 3)


if __name__ == "__main__":
    unittest.main()

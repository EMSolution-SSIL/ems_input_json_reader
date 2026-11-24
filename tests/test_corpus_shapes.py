"""Regression case from the validation corpus."""

import unittest

from emso_input_checker import check_input
from test_input_checker import minimal_input


class CorpusShapeTest(unittest.TestCase):
    def test_cyclic_zero_is_an_inactive_periodic_placeholder(self):
        data = minimal_input()
        data["14_Periodic_Boundary_Conditions"] = {
            "PERIODIC_CONDITION": [{"CYCLIC": 0, "SYMMETRY": 1}],
        }
        report = check_input(data)
        self.assertEqual(report.exit_code, 0)
        self.assertTrue(any(d.code == "INACTIVE_PERIODIC" for d in report.diagnostics))
        self.assertFalse(any(d.code == "PERIODIC_DETAIL" for d in report.diagnostics))

        data["14_Periodic_Boundary_Conditions"]["PERIODIC_CONDITION"][0]["CYCLIC"] = 6
        report = check_input(data)
        self.assertEqual(report.exit_code, 1)
        self.assertTrue(any(d.code == "RANGE" for d in report.diagnostics))

    def test_null_material_rows_are_equivalent_to_empty_rows(self):
        data = minimal_input()
        data["16_Material_Properties"]["16_1_3D_Element_Properties"] = None
        report = check_input(data)
        self.assertEqual(report.exit_code, 0)
        self.assertFalse(any(d.severity == "error" for d in report.diagnostics))


if __name__ == "__main__":
    unittest.main()

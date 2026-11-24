"""Rules traced to EMSolution's JSON reader (src-relative source locations).

Missing optional values keep their C/C++ defaults. These rules intentionally
avoid inferring mandatory keys from example files.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Rule:
    kind: str  # int, number, expr, expr_int, int_array, number_array, rows3
    domain: str = ""
    required: bool = False
    source: str = ""


def r(kind: str, domain: str = "", *, required: bool = False, source: str = "") -> Rule:
    return Rule(kind, domain, required, source)


SWITCH = "0,1"

# Domain notation: a..b (inclusive), >n, >=n, <n, (a,b), or comma-separated values.
SECTIONS: dict[str, dict[str, Rule]] = {
    "1_Execution_Control": {
        key: r("int", SWITCH, required=True, source="io/EMSInputJson.cpp:343-349")
        for key in ("PRE_PROCESSING", "MAKE_SYSTEM_MATRICES", "SOLVE_EQUATION", "POST_PROCESSING")
    },
    "2_Analysis_Type": {
        "STATIC": r("int", "0..4", source="io/EMSInputJson.cpp:388"),
        "AC": r("int", "-6,-5,-4,-3,-2,0,1,2,3,4", source="io/EMSInputJson.cpp:389"),
        "TRANSIENT": r("int", "0,1,3,5", source="io/EMSInputJson.cpp:390"),
        "STEADY_CURRENT": r("int", "0,1,2", source="io/EMSInputJson.cpp:391"),
        "NON_LINEAR": r("int", "-3,0,1,2,3", source="io/EMSInputJson.cpp:430; controller/calculation.h:21"),
    },
    "3_Potential_Gauge_Conditions": {
        "POTENTIAL": r("int", "0..4", source="io/EMSInputJson.cpp:575"),
        "NODAL_FORCE_OPTION": r("int", SWITCH, source="io/EMSInputJson.cpp:576"),
        "PHI_OPTION": r("int", SWITCH, source="io/EMSInputJson.cpp:577"),
        "FIXED_COORDINATE": r("int", SWITCH, source="io/EMSInputJson.cpp:578"),
        "TREE_GAUGE": r("int", "-1..4", source="io/EMSInputJson.cpp:651"),
        "REGULARIZATION": r("int", "0..2", source="io/EMSInputJson.cpp:652"),
        "RENUMBERING": r("int", "-1,0,1", source="io/EMSInputJson.cpp:653"),
        "SCALING": r("int", "-1,0", source="io/EMSInputJson.cpp:654"),
        "LINE_SEARCH": r("int", SWITCH, source="io/EMSInputJson.cpp:655"),
        "MATRIX_ASYMMETRICITY": r("int", SWITCH, source="io/EMSInputJson.cpp:656"),
    },
    "4_Shape_Function_Order_Added_Features": {
        "NODE_ORDER": r("int", "0..2", source="io/EMSInputJson.cpp:718"),
        "EDGE_ORDER": r("int", "0..2", source="io/EMSInputJson.cpp:719"),
        "METRIC_MOD": r("int", "-1,0,1", source="io/EMSInputJson.cpp:720"),
        "QUAD_TRI": r("int", "0..2", source="io/EMSInputJson.cpp:721"),
        "CALC_IND": r("int", SWITCH, source="io/EMSInputJson.cpp:722"),
        "THIN_ELEM": r("int", SWITCH, source="io/EMSInputJson.cpp:723"),
        "PARALLEL_NO": r("int", ">=-1", source="io/EMSInputJson.cpp:724"),
        "PARALLEL_OPTION": r("int", SWITCH, source="io/EMSInputJson.cpp:725"),
    },
    "5_Convergence_Conditions": {
        "ICCG_CONV": r("number", "(0,1)", source="io/EMSInputJson.cpp:940"),
        "ACCEL_FACTOR": r("number", "(-10,10)", source="io/EMSInputJson.cpp:941"),
        "DIV_FACTOR": r("number", ">0", source="io/EMSInputJson.cpp:942"),
        "DIV_ITERATIONS": r("int", ">2", source="io/EMSInputJson.cpp:943"),
        "SOLVER": r("int", "0,1,2,3,4,10,11,20,21,23,50", source="io/EMSInputJson.cpp:944"),
        "MAX_ITERATIONS": r("int", ">=0", source="io/EMSInputJson.cpp:945"),
        "THETA": r("expr", "0..1", source="io/EMSInputJson.cpp:947"),
        "THETA_NETWORK": r("expr", "0..1", source="io/EMSInputJson.cpp:948"),
        "THETA_MOTION": r("expr", "0..1", source="io/EMSInputJson.cpp:949"),
    },
    "6_Gaussian_Integral_Point": {
        "POINTS_IN_1D": r("int", "1..10,12", source="io/EMSInputJson.cpp:1207"),
        "POINT_IN_TRIANGLE": r("int", "-3,1,3,4,6,7,12", source="io/EMSInputJson.cpp:1208"),
        "MAT_POINTS": r("int", SWITCH, source="io/EMSInputJson.cpp:1209"),
    },
    "7_Initial_Conditions": {
        "INITIAL_STEP": r("int", ">=-1", source="io/EMSInputJson.cpp:1247"),
        "DATA_TYPE": r("int", "0..3", source="io/EMSInputJson.cpp:1248"),
        "INITIAL_PHASE": r("number", source="io/EMSInputJson.cpp:1249"),
        "MULTI": r("int", ">=0", source="io/EMSInputJson.cpp:1250"),
        "OUTPUT_STEP_NO": r("int", ">=0", source="io/EMSInputJson.cpp:1251"),
        "CYCLE_AC": r("number", source="io/EMSInputJson.cpp:1252"),
    },
    "8_Calculation_Step": {
        "INITIAL_TIME": r("expr", required=True, source="io/EMSInputJson.cpp:1321-1325"),
        "NO_STEPS": r("int_array", ">0", required=True, source="io/EMSInputJson.cpp:1322-1328"),
        "DELTA_TIME": r("number_array", ">0", required=True, source="io/EMSInputJson.cpp:1323-1331"),
        "CYCLE": r("expr_int", source="io/EMSInputJson.cpp:1347"),
    },
    "8_2_Calculation_Frequency": {
        "FREQUENCY": r("expr", ">0", required=True, source="io/EMSInputJson.cpp:1502-1504"),
        "MAX_FREQUENCY": r("expr", source="io/EMSInputJson.cpp:1505"),
        "NO_CALCULATION_POINTS": r("int", ">=0", source="io/EMSInputJson.cpp:1506"),
        "INITIAL_PHASE": r("number", source="io/EMSInputJson.cpp:1539"),
        "LAST_PHSE": r("number", source="io/EMSInputJson.cpp:1540"),
        "PHASE_INTERVAL": r("number", ">0", source="io/EMSInputJson.cpp:1541"),
    },
    "9_Output_Step": {
        "TIME_DIFF": r("int", source="post/post_files/output.c:42"),
        "RESTART_FILE_OPTION": r("int", SWITCH, source="post/post_files/output.c:43"),
        "ALL_STEP_OUTPUT": r("int", ">=0", source="post/post_files/output.c:44"),
        "REAL_TIME_OUTPUT": r("int", SWITCH, source="post/post_files/output.c:45"),
        "OUTPUT_STEP_SET": r("rows3", required=True, source="post/post_files/output.c:47-63"),
    },
    "10_1_Input_Files": {
        "MESHLESS": r("int", SWITCH, source="io/EMSInputJson.cpp:1588"),
        "UNIT": r("int", "0..2", source="io/EMSInputJson.cpp:1639"),
        "NO_MESH": r("int", ">=0", source="io/EMSInputJson.cpp:1644"),
        "NO_MESH_SYMMETRY": r("int", ">=0", source="io/EMSInputJson.cpp:1645"),
    },
    "10_2_Output_Files": {
        "ELEM_OUT": r("int", SWITCH, source="io/EMSInputJson.cpp:1712"),
        "NODE_OUT": r("int", SWITCH, source="io/EMSInputJson.cpp:1713"),
        "AVERAGE": r("int", "-1..1", source="io/EMSInputJson.cpp:1714"),
        "WIDE": r("int", "0..2", source="io/EMSInputJson.cpp:1715"),
        "SUF_OPTION": r("int", SWITCH, source="io/EMSInputJson.cpp:1716"),
        "POST_COORDINATE": r("int", ">=0", source="io/EMSInputJson.cpp:1717"),
        "COIL_OPTION": r("int", SWITCH, source="io/EMSInputJson.cpp:1718"),
    },
    "10_3_Post_Files": {
        "MESH": r("int", SWITCH, source="io/EMSInputJson.cpp:1909"),
        "CURRENT": r("int", "0..2", source="io/EMSInputJson.cpp:1910"),
        "MAGNETIC": r("int", "-1..3", source="io/EMSInputJson.cpp:1911"),
        "FORCE_J_B": r("int", "-2..2", source="io/EMSInputJson.cpp:1912"),
        "FORCE_NODAL": r("int", "-2..2", source="io/EMSInputJson.cpp:1913"),
        "DISP": r("int", "-1..1", source="io/EMSInputJson.cpp:1914"),
        "ELEM": r("int", "0..3", source="io/EMSInputJson.cpp:1915"),
        "HEAT": r("int", "0..2", source="io/EMSInputJson.cpp:1916"),
        "MAGNETIZATION": r("int", "-2..5", source="io/EMSInputJson.cpp:1917"),
        "IRON_LOSS": r("int", "0..2", source="io/EMSInputJson.cpp:1918"),
        "E": r("int", "0..2", source="io/EMSInputJson.cpp:1919"),
        "COIL_FORCE": r("int", SWITCH, source="io/EMSInputJson.cpp:1920"),
    },
    "11_Print_Output": {
        "MESH": r("int", SWITCH, source="io/EMSInputJson.cpp:2043"),
        "A": r("int", SWITCH, source="io/EMSInputJson.cpp:2044"),
        "V": r("int", "0..2", source="io/EMSInputJson.cpp:2045"),
        "HEAT": r("int", SWITCH, source="io/EMSInputJson.cpp:2046"),
        "FORCE_J_B": r("int", SWITCH, source="io/EMSInputJson.cpp:2047"),
        "MAGNETIC_ENERGY": r("int", SWITCH, source="io/EMSInputJson.cpp:2048"),
        "GAP_B": r("int", SWITCH, source="io/EMSInputJson.cpp:2049"),
        "CHECK_PERMEANCE": r("int", SWITCH, source="io/EMSInputJson.cpp:2050"),
    },
    "12_Geometry": {
        "GEOMETRY": r("int", "0..4", required=True, source="io/EMSInputJson.cpp:2438-2440"),
        "DELTA_Z_THETA": r("expr", ">=0", source="io/EMSInputJson.cpp:2442"),
        "NO_LAYERS": r("int", source="io/EMSInputJson.cpp:2443"),
        "ADD_SYMMETRY": r("int", source="io/EMSInputJson.cpp:2444"),
        "PITCH": r("number", source="io/EMSInputJson.cpp:2445"),
    },
    "13_Boundary_Conditions": {
        "FAR_BOUNDARY_CONDITION": r("int", "0..3", required=True, source="boundary/boundary_cond.c:34-36"),
        "PHI_BOUNDARY_CONDITION": r("int", source="boundary/boundary_cond.c:38"),
        "DISTANCE_JUDGE": r("expr", ">0", source="boundary/boundary_cond.c:70"),
    },
    "16_Material_Properties": {
        "EXTEND_TOTAL_for_COIL": r("int", SWITCH, source="property/mat_property.c:81"),
        "THIN_CRITERION": r("number", ">2", source="property/mat_property.c:86"),
    },
}

NESTED: dict[str, dict[str, Rule]] = {
    "5_Convergence_Conditions.5_2_Nonlinear_Convergence_Condition": {
        "NON_LINEAR_CONV": r("number", "(0,1)", source="io/EMSInputJson.cpp:1111"),
        "RELAXATION": r("number", "(0,2]", source="io/EMSInputJson.cpp:1112"),
        "NO_ITERATIONS": r("int", ">1", source="io/EMSInputJson.cpp:1113"),
        "INIT_OPTION": r("int", SWITCH, source="io/EMSInputJson.cpp:1114"),
        "ICCG_CONV_RATIO": r("number", ">=0", source="io/EMSInputJson.cpp:1115"),
        "CHECK_B": r("number", source="io/EMSInputJson.cpp:1116"),
        "DELTA_A": r("int", SWITCH, source="io/EMSInputJson.cpp:1117"),
        "NON_LINEAR_METHOD": r("int", "-1..2", source="io/EMSInputJson.cpp:1118"),
    },
    "8_Calculation_Step.TP_EEC": {
        "N_CORRECT": r("expr_int", required=True, source="io/EMSInputJson.cpp:1352-1354"),
        "N_BACK": r("expr_int", ">=0", source="io/EMSInputJson.cpp:1356"),
        "TP_EEC_OPTION": r("int", source="io/EMSInputJson.cpp:1357"),
        "MAX_NO_CORRECTION": r("expr_int", ">=0", source="io/EMSInputJson.cpp:1358"),
        "TP_STEP": r("expr_int", source="io/EMSInputJson.cpp:1360"),
        "TP_STEP_OPTION": r("expr_int", source="io/EMSInputJson.cpp:1361"),
    },
    "10_2_Output_Files.OUTPUT_MATS": {
        "TYPE": r("int", "-1,0", source="io/EMSInputJson.cpp:1731"),
        "OUTPUT_MAT_IDS": r("int_array", source="io/EMSInputJson.cpp:1733"),
    },
}

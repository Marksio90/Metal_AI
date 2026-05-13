"""
Reference tests — 100% accuracy against Cennik 2025 Excel.

Every row from the source file is tested:
  - hourly price at 0%, 20%, 45% margin matches Excel exactly
  - per-second rate = hourly / 3600 (floating point tolerance: 1e-9)
  - 3600 s on a machine must equal its hourly price
"""

import math
import pytest

from metal_calc.data.machine_rates_2025 import (
    MACHINE_RATES,
    MACHINE_RATES_BY_LP,
    CENNIK_VERSION,
    get_machine,
    get_machine_by_lp,
)


# ---------------------------------------------------------------------------
# Completeness
# ---------------------------------------------------------------------------

def test_registry_has_52_machines():
    assert len(MACHINE_RATES) == 52


def test_all_lp_present():
    lps = sorted(MACHINE_RATES_BY_LP.keys())
    assert lps == list(range(1, 53))


def test_cennik_version():
    assert CENNIK_VERSION == "2025-04-07"


# ---------------------------------------------------------------------------
# Reference price checks — exhaustive list from Excel
# ---------------------------------------------------------------------------

EXCEL_REFERENCE = [
    # (lp, name, p0, p20, p45)
    (1,  "Gratowarka do blach ERNST",          236, 283, 342),
    (2,  "Giętarka do blach SAFAN",            232, 278, 337),
    (3,  "Wykrawarka Prima Power E5",           335, 402, 485),
    (4,  "Laser Fiber do blach",               383, 460, 556),
    (5,  "Macsoft / Robomac",                  247, 296, 358),
    (6,  "Whiteleg",                           247, 296, 358),
    (7,  "Giętarka rur CNC BLM Elect",         248, 298, 360),
    (8,  "Laser Fiber do rur",                 460, 552, 667),
    (9,  "Malarnia proszkowa",                 1285,1543,1864),
    (10, "Malarnia fluidyzacyjna",             1285,1543,1864),
    (11, "Pakowanie/montaż",                   158, 190, 229),
    (12, "Centrum Obróbcze CNC HAAS",          221, 266, 321),
    (13, "Tokarka CNC HAAS",                   221, 266, 321),
    (14, "Narzędziownia-prace ręczne",         180, 216, 261),
    (15, "Automat do cięcia rur Pedrazzoli",   235, 282, 340),
    (16, "Prasa automatyczna 100t",            237, 284, 344),
    (17, "Prasa hydrauliczna 100t",            192, 230, 278),
    (18, "Gilotyna do blach/drutów",           192, 230, 278),
    (19, "Piła taśmowa do rur",                192, 230, 278),
    (20, "Giętarka Montorfano",                192, 230, 278),
    (21, "Wiertarka kolumnowa",                192, 230, 278),
    (22, "Giętarka rur CNC Veenstra",          192, 230, 278),
    (23, "Giętarka do rur SOCO",               192, 230, 278),
    (24, "MESKO do cięcia płaskownika",        192, 230, 278),
    (25, "Prasa krawędziowa",                  192, 230, 278),
    (26, "Gratowarka do rur RSA",              192, 230, 278),
    (27, "Gratowarka wibracyjna Rosler",       237, 284, 344),
    (28, "Szlifierki ręczne",                  192, 230, 278),
    (29, "Prasy mimośrodowe",                  154, 185, 223),
    (30, "Fazowarka Varo",                     253, 303, 366),
    (31, "Prościarki do drutu",                253, 303, 366),
    (32, "Robot spawalniczy Fanuc",            262, 315, 381),
    (33, "Spawanie ręczne",                    307, 368, 445),
    (34, "Prace stolarskie",                   205, 246, 298),
    (35, "Ploter frezujący w drewnie",         233, 279, 338),
    (36, "Zgrzewarka Ideal",                   237, 284, 343),
    (37, "Zgrzewarka 3D",                      237, 284, 343),
    (38, "Zgrzewarka CEMSA",                   237, 284, 343),
    (39, "Zgrzewarka Varo",                    237, 284, 343),
    (40, "Zgrzewarka 5D kleszczowa do ramek",  237, 284, 343),
    (41, "Zgrzewarka Kempi",                   237, 284, 343),
    (42, "Zgrzewarka Dabew",                   237, 284, 343),
    (43, "Zgrzewarka Clifford",                237, 284, 343),
    (44, "Zgrzewarka doczołowa CEA",           194, 233, 281),
    (45, "Zgrzewarki ręczne",                  156, 187, 226),
    (46, "Obcinarka Varo",                     195, 234, 283),
    (47, "Pakowanie automatyczne",             190, 227, 275),
    (48, "Montaż",                             128, 153, 185),
    (49, "Wtryskarka",                         131, 157, 189),
    (50, "Zgrzewarka Varo 2 2022 roku",        255, 306, 370),
    (51, "Zgrzewarka Schlatter",               237, 284, 343),
    (52, "Cynkownia",                          195, 234, 282),
]


@pytest.mark.parametrize("lp,name,p0,p20,p45", EXCEL_REFERENCE)
def test_price_matches_excel(lp, name, p0, p20, p45):
    mr = get_machine(name)
    assert mr.lp == lp,              f"lp mismatch for {name}"
    assert mr.price_0pct_zl_h == p0, f"p0 mismatch for {name}: got {mr.price_0pct_zl_h}, want {p0}"
    assert mr.price_20pct_zl_h == p20, f"p20 mismatch for {name}: got {mr.price_20pct_zl_h}, want {p20}"
    assert mr.price_45pct_zl_h == p45, f"p45 mismatch for {name}: got {mr.price_45pct_zl_h}, want {p45}"


@pytest.mark.parametrize("lp,name,p0,p20,p45", EXCEL_REFERENCE)
def test_per_second_rate_derivation(lp, name, p0, p20, p45):
    mr = get_machine(name)
    assert math.isclose(mr.price_0pct_zl_s,  p0  / 3600, rel_tol=1e-9)
    assert math.isclose(mr.price_20pct_zl_s, p20 / 3600, rel_tol=1e-9)
    assert math.isclose(mr.price_45pct_zl_s, p45 / 3600, rel_tol=1e-9)


@pytest.mark.parametrize("lp,name,p0,p20,p45", EXCEL_REFERENCE)
def test_3600s_equals_hourly_rate(lp, name, p0, p20, p45):
    """3600 s on any machine must cost exactly its hourly price."""
    mr = get_machine(name)
    assert math.isclose(mr.price_0pct_zl_s  * 3600, p0,  rel_tol=1e-9)
    assert math.isclose(mr.price_20pct_zl_s * 3600, p20, rel_tol=1e-9)
    assert math.isclose(mr.price_45pct_zl_s * 3600, p45, rel_tol=1e-9)


# ---------------------------------------------------------------------------
# Spot checks mentioned in architecture document
# ---------------------------------------------------------------------------

def test_laser_fiber_blach_0pct():
    mr = get_machine("Laser Fiber do blach")
    assert mr.price_0pct_zl_h == 383

def test_laser_fiber_rur_0pct():
    mr = get_machine("Laser Fiber do rur")
    assert mr.price_0pct_zl_h == 460

def test_wykrawarka_0pct():
    mr = get_machine("Wykrawarka Prima Power E5")
    assert mr.price_0pct_zl_h == 335

def test_gietarka_safan_all_levels():
    mr = get_machine("Giętarka do blach SAFAN")
    assert mr.price_0pct_zl_h  == 232
    assert mr.price_20pct_zl_h == 278
    assert mr.price_45pct_zl_h == 337

def test_prościarki_drutu_all_levels():
    mr = get_machine("Prościarki do drutu")
    assert mr.price_0pct_zl_h  == 253
    assert mr.price_20pct_zl_h == 303
    assert mr.price_45pct_zl_h == 366

def test_robot_fanuc_all_levels():
    mr = get_machine("Robot spawalniczy Fanuc")
    assert mr.price_0pct_zl_h  == 262
    assert mr.price_20pct_zl_h == 315
    assert mr.price_45pct_zl_h == 381

def test_spawanie_reczne_all_levels():
    mr = get_machine("Spawanie ręczne")
    assert mr.price_0pct_zl_h  == 307
    assert mr.price_20pct_zl_h == 368
    assert mr.price_45pct_zl_h == 445

def test_malarnia_proszkowa_all_levels():
    mr = get_machine("Malarnia proszkowa")
    assert mr.price_0pct_zl_h  == 1285
    assert mr.price_20pct_zl_h == 1543
    assert mr.price_45pct_zl_h == 1864

def test_montaz_all_levels():
    mr = get_machine("Montaż")
    assert mr.price_0pct_zl_h  == 128
    assert mr.price_20pct_zl_h == 153
    assert mr.price_45pct_zl_h == 185

def test_cynkownia_all_levels():
    mr = get_machine("Cynkownia")
    assert mr.price_0pct_zl_h  == 195
    assert mr.price_20pct_zl_h == 234
    assert mr.price_45pct_zl_h == 282


# ---------------------------------------------------------------------------
# rate_zl_h / rate_zl_s helper consistency
# ---------------------------------------------------------------------------

def test_rate_helper_0():
    mr = get_machine("Laser Fiber do blach")
    assert mr.rate_zl_h(0) == 383
    assert math.isclose(mr.rate_zl_s(0), 383 / 3600, rel_tol=1e-9)

def test_rate_helper_20():
    mr = get_machine("Laser Fiber do blach")
    assert mr.rate_zl_h(20) == 460

def test_rate_helper_45():
    mr = get_machine("Laser Fiber do blach")
    assert mr.rate_zl_h(45) == 556

def test_rate_helper_invalid_raises():
    mr = get_machine("Laser Fiber do blach")
    with pytest.raises(ValueError):
        mr.rate_zl_h(10)


# ---------------------------------------------------------------------------
# Lookup helpers
# ---------------------------------------------------------------------------

def test_get_machine_by_lp():
    mr = get_machine_by_lp(4)
    assert mr.name == "Laser Fiber do blach"

def test_get_machine_unknown_raises():
    with pytest.raises(KeyError):
        get_machine("Nieistniejąca maszyna XYZ")

def test_get_machine_by_lp_unknown_raises():
    with pytest.raises(KeyError):
        get_machine_by_lp(999)

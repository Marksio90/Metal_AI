"""
Frozen machine-rate table imported from Cennik 2025 (07.04.2025).
Source of truth: 9a9dae90-Cennik.xlsx, sheet "Cennik pełny 2025".

Each entry preserves the full cost breakdown from the Excel so that
rounded vs. unrounded prices can be verified independently and
per-second rates are derived from exact (unrounded) totals.

Column mapping (Excel columns A–U, row 5 onward):
    lp                    – ordinal (col A)
    name                  – machine name (col B)
    dept                  – department / dział (col C)
    wage_piece_zl_h       – stawka akordowa [zł/h] (col D)
    other_wage_multiplier – pozostałe składniki wynagrodzenia (col E)
    total_wages_zl_h      – razem wynagrodzenie [zł/h] (col F)
    zus_zl_h              – ZUS 20,19% (col G)
    ppk_zl_h              – PPK 1,5% (col H)
    direct_labour_zl_h    – razem robocizna bezpośrednia (col I)
    overhead_dept_pct     – % kosztów wydziałowych (col J)
    overhead_dept_zl_h    – narzut wydziałowy [zł/h] (col K)
    overhead_co_pct       – % kosztów ogólnozakładowych (col L)
    overhead_co_zl_h      – narzut ogólnozakładowy [zł/h] (col M)
    production_cost_zl_h  – koszty produkcji (col N)
    selling_cost_pct      – % kosztów sprzedaży (col O)
    selling_cost_zl_h     – koszty sprzedaży (col P)
    total_cost_zl_h       – koszty razem [exact] (col Q)
    rounded_zl_h          – zaokrąglona cena (col R)
    price_0pct_zl_h       – CENNIK marża 0% (col S)
    price_20pct_zl_h      – CENNIK marża 20% (col T)
    price_45pct_zl_h      – CENNIK marża 45% (col U)
"""

from __future__ import annotations
from dataclasses import dataclass, field
from decimal import Decimal
from typing import Mapping


CENNIK_VERSION = "2025-04-07"


@dataclass(frozen=True)
class MachineRate:
    lp: int
    name: str
    dept: str
    wage_piece_zl_h: float
    other_wage_multiplier: float
    total_wages_zl_h: float
    zus_zl_h: float
    ppk_zl_h: float
    direct_labour_zl_h: float
    overhead_dept_pct: float
    overhead_dept_zl_h: float
    overhead_co_pct: float
    overhead_co_zl_h: float
    production_cost_zl_h: float
    selling_cost_pct: float
    selling_cost_zl_h: float
    total_cost_zl_h: float
    rounded_zl_h: float
    price_0pct_zl_h: float
    price_20pct_zl_h: float
    price_45pct_zl_h: float

    @property
    def price_0pct_zl_s(self) -> float:
        return self.price_0pct_zl_h / 3600

    @property
    def price_20pct_zl_s(self) -> float:
        return self.price_20pct_zl_h / 3600

    @property
    def price_45pct_zl_s(self) -> float:
        return self.price_45pct_zl_h / 3600

    def rate_zl_s(self, margin_pct: int) -> float:
        """Return per-second rate for margin_pct in {0, 20, 45}."""
        if margin_pct == 0:
            return self.price_0pct_zl_s
        if margin_pct == 20:
            return self.price_20pct_zl_s
        if margin_pct == 45:
            return self.price_45pct_zl_s
        raise ValueError(f"margin_pct must be 0, 20, or 45; got {margin_pct}")

    def rate_zl_h(self, margin_pct: int) -> float:
        if margin_pct == 0:
            return self.price_0pct_zl_h
        if margin_pct == 20:
            return self.price_20pct_zl_h
        if margin_pct == 45:
            return self.price_45pct_zl_h
        raise ValueError(f"margin_pct must be 0, 20, or 45; got {margin_pct}")


# ---------------------------------------------------------------------------
# Raw data — transcribed 1:1 from Excel rows 5-56
# Tuple order matches MachineRate field order after lp/name/dept.
# ---------------------------------------------------------------------------

_RAW: list[tuple] = [
    # lp, name, dept, wage_piece, other_wage_mult, total_wages, zus, ppk,
    # direct_labour, ovh_dept_pct, ovh_dept, ovh_co_pct, ovh_co,
    # prod_cost, sell_pct, sell_cost, total_cost, rounded,
    # p0, p20, p45
    (1,  "Gratowarka do blach ERNST",          "Blachy",
     20.6, 0.573, 32.4,  6.54, 0.49, 39.43, 3.9,  153.79, 0.8,  31.55, 224.76, 0.05, 11.24, 236.0,   236, 236, 283, 342),
    (2,  "Giętarka do blach SAFAN",            "Blachy",
     20.6, 1.05,  42.23, 8.53, 0.63, 51.39, 2.5,  128.47, 0.8,  41.11, 220.98, 0.05, 11.05, 232.02,  232, 232, 278, 337),
    (3,  "Wykrawarka Prima Power E5",           "Blachy",
     20.6, 1.05,  42.23, 8.53, 0.63, 51.39, 4.4,  226.11, 0.8,  41.11, 318.62, 0.05, 15.93, 334.55,  335, 335, 402, 485),
    (4,  "Laser Fiber do blach",               "Blachy",
     20.6, 1.05,  42.23, 8.53, 0.63, 51.39, 5.3,  272.37, 0.8,  41.11, 364.87, 0.05, 18.24, 383.11,  383, 383, 460, 556),
    (5,  "Macsoft / Robomac",                  "CNC",
     19.4, 1.18,  42.29, 8.54, 0.63, 51.47, 1.97, 101.39, 1.43, 73.6,  226.45, 0.09, 20.38, 246.83,  247, 247, 296, 358),
    (6,  "Whiteleg",                           "CNC",
     19.4, 1.18,  42.29, 8.54, 0.63, 51.47, 1.97, 101.39, 1.43, 73.6,  226.45, 0.09, 20.38, 246.83,  247, 247, 296, 358),
    (7,  "Giętarka rur CNC BLM Elect",         "CNC",
     19.4, 1.06,  39.96, 8.07, 0.6,  48.63, 2.25, 109.42, 1.43, 69.54, 227.6,  0.09, 20.48, 248.08,  248, 248, 298, 360),
    (8,  "Laser Fiber do rur",                 "CNC",
     19.4, 1.06,  39.96, 8.07, 0.6,  48.63, 6.25, 303.95, 1.43, 69.54, 422.13, 0.09, 37.99, 460.12,  460, 460, 552, 667),
    (9,  "Malarnia proszkowa",                 "Malarnia - 4 os.",
     68.0, 0.88,  127.84,25.81,1.92, 155.57,5.35, 832.29, 1.23, 191.35,1179.21,0.09, 106.13,1285.34, 1285,1285,1543,1864),
    (10, "Malarnia fluidyzacyjna",             "Malarnia - 4 os.",
     68.0, 0.88,  127.84,25.81,1.92, 155.57,5.35, 832.29, 1.23, 191.35,1179.21,0.09, 106.13,1285.34, 1285,1285,1543,1864),
    (11, "Pakowanie/montaż",                   "Montaż",
     16.5, 0.92,  31.68, 6.4,  0.48, 38.55, 1.57, 60.53,  1.19, 45.88, 144.95, 0.09, 13.05, 158.0,   158, 158, 190, 229),
    (12, "Centrum Obróbcze CNC HAAS",          "Narzędziownia",
     27.5, 0.576, 43.34, 8.75, 0.65, 52.74, 1.72, 90.71,  1.13, 59.6,  203.05, 0.09, 18.27, 221.33,  221, 221, 266, 321),
    (13, "Tokarka CNC HAAS",                   "Narzędziownia",
     27.5, 0.576, 43.34, 8.75, 0.65, 52.74, 1.72, 90.71,  1.13, 59.6,  203.05, 0.09, 18.27, 221.33,  221, 221, 266, 321),
    (14, "Narzędziownia-prace ręczne",         "Narzędziownia",
     27.5, 0.576, 43.34, 8.75, 0.65, 52.74, 1.33, 70.14,  0.8,  42.19, 165.08, 0.09, 14.86, 179.93,  180, 180, 216, 261),
    (15, "Automat do cięcia rur Pedrazzoli",   "Prasy",
     17.0, 1.11,  35.87, 7.24, 0.54, 43.65, 2.5,  109.13, 1.43, 62.42, 215.2,  0.09, 19.37, 234.56,  235, 235, 282, 340),
    (16, "Prasa automatyczna 100t",            "Prasy",
     17.0, 1.11,  35.87, 7.24, 0.54, 43.65, 2.55, 111.31, 1.43, 62.42, 217.38, 0.09, 19.56, 236.94,  237, 237, 284, 344),
    (17, "Prasa hydrauliczna 100t",            "Prasy",
     17.0, 1.11,  35.87, 7.24, 0.54, 43.65, 1.6,  69.84,  1.43, 62.42, 175.91, 0.09, 15.83, 191.74,  192, 192, 230, 278),
    (18, "Gilotyna do blach/drutów",           "Prasy",
     17.0, 1.11,  35.87, 7.24, 0.54, 43.65, 1.6,  69.84,  1.43, 62.42, 175.91, 0.09, 15.83, 191.74,  192, 192, 230, 278),
    (19, "Piła taśmowa do rur",                "Prasy",
     17.0, 1.11,  35.87, 7.24, 0.54, 43.65, 1.6,  69.84,  1.43, 62.42, 175.91, 0.09, 15.83, 191.74,  192, 192, 230, 278),
    (20, "Giętarka Montorfano",                "Prasy",
     17.0, 1.11,  35.87, 7.24, 0.54, 43.65, 1.6,  69.84,  1.43, 62.42, 175.91, 0.09, 15.83, 191.74,  192, 192, 230, 278),
    (21, "Wiertarka kolumnowa",                "Prasy",
     17.0, 1.11,  35.87, 7.24, 0.54, 43.65, 1.6,  69.84,  1.43, 62.42, 175.91, 0.09, 15.83, 191.74,  192, 192, 230, 278),
    (22, "Giętarka rur CNC Veenstra",          "Prasy",
     17.0, 1.11,  35.87, 7.24, 0.54, 43.65, 1.6,  69.84,  1.43, 62.42, 175.91, 0.09, 15.83, 191.74,  192, 192, 230, 278),
    (23, "Giętarka do rur SOCO",               "Prasy",
     17.0, 1.11,  35.87, 7.24, 0.54, 43.65, 1.6,  69.84,  1.43, 62.42, 175.91, 0.09, 15.83, 191.74,  192, 192, 230, 278),
    (24, "MESKO do cięcia płaskownika",        "Prasy",
     17.0, 1.11,  35.87, 7.24, 0.54, 43.65, 1.6,  69.84,  1.43, 62.42, 175.91, 0.09, 15.83, 191.74,  192, 192, 230, 278),
    (25, "Prasa krawędziowa",                  "Prasy",
     17.0, 1.11,  35.87, 7.24, 0.54, 43.65, 1.6,  69.84,  1.43, 62.42, 175.91, 0.09, 15.83, 191.74,  192, 192, 230, 278),
    (26, "Gratowarka do rur RSA",              "Prasy",
     17.0, 1.11,  35.87, 7.24, 0.54, 43.65, 1.6,  69.84,  1.43, 62.42, 175.91, 0.09, 15.83, 191.74,  192, 192, 230, 278),
    (27, "Gratowarka wibracyjna Rosler",       "Prasy",
     17.0, 1.11,  35.87, 7.24, 0.54, 43.65, 2.55, 111.31, 1.43, 62.42, 217.38, 0.09, 19.56, 236.94,  237, 237, 284, 344),
    (28, "Szlifierki ręczne",                  "Prasy",
     17.0, 1.11,  35.87, 7.24, 0.54, 43.65, 1.6,  69.84,  1.43, 62.42, 175.91, 0.09, 15.83, 191.74,  192, 192, 230, 278),
    (29, "Prasy mimośrodowe",                  "Prasy",
     17.0, 1.11,  35.87, 7.24, 0.54, 43.65, 0.8,  34.92,  1.43, 62.42, 140.99, 0.09, 12.69, 153.68,  154, 154, 185, 223),
    (30, "Fazowarka Varo",                     "Prościarki",
     17.0, 1.21,  37.57, 7.59, 0.56, 45.72, 2.64, 120.7,  1.43, 65.38, 231.79, 0.09, 20.86, 252.66,  253, 253, 303, 366),
    (31, "Prościarki do drutu",                "Prościarki",
     17.0, 1.21,  37.57, 7.59, 0.56, 45.72, 2.64, 120.7,  1.43, 65.38, 231.79, 0.09, 20.86, 252.66,  253, 253, 303, 366),
    (32, "Robot spawalniczy Fanuc",            "Spawalnia",
     23.0, 0.71,  39.33, 7.94, 0.59, 47.86, 2.6,  124.44, 1.43, 68.44, 240.74, 0.09, 21.67, 262.41,  262, 262, 315, 381),
    (33, "Spawanie ręczne",                    "Spawalnia",
     23.0, 1.15,  49.45, 9.98, 0.74, 60.18, 2.25, 135.4,  1.43, 86.05, 281.62, 0.09, 25.35, 306.97,  307, 307, 368, 445),
    (34, "Prace stolarskie",                   "Stolarnia",
     20.6, 0.683, 34.67, 7.0,  0.52, 42.19, 2.35, 99.15,  1.11, 46.83, 188.17, 0.09, 16.93, 205.1,   205, 205, 246, 298),
    (35, "Ploter frezujący w drewnie",         "Stolarnia",
     20.6, 0.683, 34.67, 7.0,  0.52, 42.19, 2.95, 124.46, 1.11, 46.83, 213.48, 0.09, 19.21, 232.69,  233, 233, 279, 338),
    (36, "Zgrzewarka Ideal",                   "Zgrzewarki",
     17.0, 0.77,  30.09, 6.08, 0.45, 36.62, 3.5,  128.16, 1.43, 52.36, 217.14, 0.09, 19.54, 236.68,  237, 237, 284, 343),
    (37, "Zgrzewarka 3D",                      "Zgrzewarki",
     17.0, 0.77,  30.09, 6.08, 0.45, 36.62, 3.5,  128.16, 1.43, 52.36, 217.14, 0.09, 19.54, 236.68,  237, 237, 284, 343),
    (38, "Zgrzewarka CEMSA",                   "Zgrzewarki",
     17.0, 0.77,  30.09, 6.08, 0.45, 36.62, 3.5,  128.16, 1.43, 52.36, 217.14, 0.09, 19.54, 236.68,  237, 237, 284, 343),
    (39, "Zgrzewarka Varo",                    "Zgrzewarki",
     17.0, 0.77,  30.09, 6.08, 0.45, 36.62, 3.5,  128.16, 1.43, 52.36, 217.14, 0.09, 19.54, 236.68,  237, 237, 284, 343),
    (40, "Zgrzewarka 5D kleszczowa do ramek",  "Zgrzewarki",
     17.0, 0.77,  30.09, 6.08, 0.45, 36.62, 3.5,  128.16, 1.43, 52.36, 217.14, 0.09, 19.54, 236.68,  237, 237, 284, 343),
    (41, "Zgrzewarka Kempi",                   "Zgrzewarki",
     17.0, 0.77,  30.09, 6.08, 0.45, 36.62, 3.5,  128.16, 1.43, 52.36, 217.14, 0.09, 19.54, 236.68,  237, 237, 284, 343),
    (42, "Zgrzewarka Dabew",                   "Zgrzewarki",
     17.0, 0.77,  30.09, 6.08, 0.45, 36.62, 3.5,  128.16, 1.43, 52.36, 217.14, 0.09, 19.54, 236.68,  237, 237, 284, 343),
    (43, "Zgrzewarka Clifford",                "Zgrzewarki",
     17.0, 0.77,  30.09, 6.08, 0.45, 36.62, 3.5,  128.16, 1.43, 52.36, 217.14, 0.09, 19.54, 236.68,  237, 237, 284, 343),
    (44, "Zgrzewarka doczołowa CEA",           "Zgrzewarki",
     17.0, 0.77,  30.09, 6.08, 0.45, 36.62, 2.43, 88.98,  1.43, 52.36, 177.96, 0.09, 16.02, 193.97,  194, 194, 233, 281),
    (45, "Zgrzewarki ręczne",                  "Zgrzewarki",
     17.0, 0.77,  30.09, 6.08, 0.45, 36.62, 1.48, 54.19,  1.43, 52.36, 143.17, 0.09, 12.89, 156.06,  156, 156, 187, 226),
    (46, "Obcinarka Varo",                     "Zgrzewarki",
     17.0, 0.77,  30.09, 6.08, 0.45, 36.62, 2.45, 89.71,  1.43, 52.36, 178.69, 0.09, 16.08, 194.77,  195, 195, 234, 283),
    (47, "Pakowanie automatyczne",             "Montaż",
     49.5, 0.48,  73.26, 14.79,1.1,  89.15, 0.65, 57.95,  0.3,  26.75, 173.84, 0.09, 15.65, 189.49,  190, 190, 227, 275),
    (48, "Montaż",                             "Montaż",
     17.5, 0.81,  31.68, 6.4,  0.48, 38.55, 0.85, 32.76,  1.19, 45.87, 117.18, 0.09, 10.55, 127.72,  128, 128, 153, 185),
    (49, "Wtryskarka",                         "Wyroby",
     18.7, 1.14,  40.02, 8.08, 0.6,  48.7,  1.11, 54.05,  0.35, 17.04, 119.8,  0.09, 10.78, 130.58,  131, 131, 157, 189),
    (50, "Zgrzewarka Varo 2 2022 roku",        "Zgrzewarki",
     17.0, 1.22,  37.74, 7.62, 0.57, 45.93, 2.67, 122.62, 1.43, 65.67, 234.22, 0.09, 21.08, 255.3,   255, 255, 306, 370),
    (51, "Zgrzewarka Schlatter",               "Zgrzewarki",
     17.0, 0.77,  30.09, 6.08, 0.45, 36.62, 3.5,  128.16, 1.43, 52.36, 217.14, 0.09, 19.54, 236.68,  237, 237, 284, 343),
    (52, "Cynkownia",                          "Ogrzewanie wyrobów w piecu",
     27.0, 0.25,  33.75, 6.81, 0.51, 41.07, 1.91, 78.44,  1.44, 59.14, 178.66, 0.09, 16.08, 194.74,  195, 195, 234, 282),
]


def _build_registry() -> dict[str, MachineRate]:
    registry: dict[str, MachineRate] = {}
    for row in _RAW:
        (lp, name, dept,
         wp, owm, tw, zus, ppk, dl,
         odp, od, ocp, oc,
         pc, sp, sc, tc, rnd,
         p0, p20, p45) = row
        mr = MachineRate(
            lp=lp, name=name, dept=dept,
            wage_piece_zl_h=wp,
            other_wage_multiplier=owm,
            total_wages_zl_h=tw,
            zus_zl_h=zus,
            ppk_zl_h=ppk,
            direct_labour_zl_h=dl,
            overhead_dept_pct=odp,
            overhead_dept_zl_h=od,
            overhead_co_pct=ocp,
            overhead_co_zl_h=oc,
            production_cost_zl_h=pc,
            selling_cost_pct=sp,
            selling_cost_zl_h=sc,
            total_cost_zl_h=tc,
            rounded_zl_h=rnd,
            price_0pct_zl_h=p0,
            price_20pct_zl_h=p20,
            price_45pct_zl_h=p45,
        )
        registry[name] = mr
    return registry


MACHINE_RATES: Mapping[str, MachineRate] = _build_registry()
MACHINE_RATES_BY_LP: Mapping[int, MachineRate] = {
    mr.lp: mr for mr in MACHINE_RATES.values()
}


def get_machine(name: str) -> MachineRate:
    try:
        return MACHINE_RATES[name]
    except KeyError:
        raise KeyError(f"Machine not found: '{name}'. Check MACHINE_RATES for valid names.")


def get_machine_by_lp(lp: int) -> MachineRate:
    try:
        return MACHINE_RATES_BY_LP[lp]
    except KeyError:
        raise KeyError(f"No machine with lp={lp}.")

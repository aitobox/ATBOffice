"""Worksheet physical unit conversion calculation functions (CONVERT)."""

from __future__ import annotations

import math
import re
from typing import Any

from atboffice.modules.spreadsheet.calc.context import EvalContext
from atboffice.modules.spreadsheet.calc.errors import NA, VALUE, ExcelError, is_error
from atboffice.modules.spreadsheet.calc.engineering.common import (
    register_eng,
    to_float,
)

U: dict[str, dict[str, Any]] = {}


def add_units(cat: str, unit_list: list[tuple[str, float]]) -> None:
    for k, f in unit_list:
        U[k] = {"cat": cat, "f": f}


add_units(
    "mass",
    [
        ("g", 1.0),
        ("sg", 14593.90294),
        ("lbm", 453.59237),
        ("u", 1.66053906660e-24),
        ("ozm", 28.349523125),
        ("grain", 0.06479891),
        ("cwt", 45359.237),
        ("shweight", 45359.237),
        ("uk_cwt", 50802.34544),
        ("lcwt", 50802.34544),
        ("hweight", 50802.34544),
        ("stone", 6350.29318),
        ("ton", 907184.74),
        ("uk_ton", 1016046.9088),
        ("LTON", 1016046.9088),
        ("brton", 1016046.9088),
    ],
)

add_units(
    "dist",
    [
        ("m", 1.0),
        ("mi", 1609.344),
        ("Nmi", 1852.0),
        ("in", 0.0254),
        ("ft", 0.3048),
        ("yd", 0.9144),
        ("ang", 1e-10),
        ("ell", 1.143),
        ("ly", 9460730472580800.0),
        ("parsec", 3.08567758149137e16),
        ("pc", 3.08567758149137e16),
        ("Pica", 0.0254 / 72.0),
        ("Picapt", 0.0254 / 72.0),
        ("pica", 0.0254 / 6.0),
        ("survey_mi", 1609.347218694437),
    ],
)

add_units(
    "time",
    [
        ("yr", 31557600.0),
        ("day", 86400.0),
        ("d", 86400.0),
        ("hr", 3600.0),
        ("mn", 60.0),
        ("min", 60.0),
        ("sec", 1.0),
        ("s", 1.0),
    ],
)

add_units(
    "press",
    [
        ("Pa", 1.0),
        ("p", 1.0),
        ("atm", 101325.0),
        ("at", 101325.0),
        ("mmHg", 133.322),
        ("psi", 6894.757293168361),
        ("Torr", 133.322368421),
    ],
)

add_units(
    "force",
    [
        ("N", 1.0),
        ("dyn", 1e-5),
        ("dy", 1e-5),
        ("lbf", 4.4482216152605),
        ("pond", 0.00980665),
    ],
)

add_units(
    "energy",
    [
        ("J", 1.0),
        ("e", 1e-7),
        ("c", 4.184),
        ("cal", 4.1868),
        ("eV", 1.602176634e-19),
        ("ev", 1.602176634e-19),
        ("HPh", 2684519.537696172792),
        ("hh", 2684519.537696172792),
        ("Wh", 3600.0),
        ("wh", 3600.0),
        ("flb", 1.3558179483314004),
        ("BTU", 1055.05585262),
        ("btu", 1055.05585262),
    ],
)

add_units(
    "power",
    [
        ("HP", 745.69987158227022),
        ("h", 745.69987158227022),
        ("PS", 735.49875),
        ("W", 1.0),
        ("w", 1.0),
    ],
)

add_units("mag", [("T", 1.0), ("ga", 1e-4)])

add_units(
    "temp",
    [
        ("C", 0.0),
        ("cel", 0.0),
        ("F", 0.0),
        ("fah", 0.0),
        ("K", 0.0),
        ("kel", 0.0),
        ("Rank", 0.0),
        ("Reau", 0.0),
    ],
)

add_units(
    "vol",
    [
        ("tsp", 4.92892159375e-6),
        ("tspm", 5e-6),
        ("tbs", 1.478676478125e-5),
        ("oz", 2.95735295625e-5),
        ("cup", 2.365882365e-4),
        ("pt", 4.73176473e-4),
        ("us_pt", 4.73176473e-4),
        ("uk_pt", 5.6826125e-4),
        ("qt", 9.46352946e-4),
        ("uk_qt", 1.1365225e-3),
        ("gal", 3.785411784e-3),
        ("uk_gal", 4.54609e-3),
        ("l", 1e-3),
        ("L", 1e-3),
        ("lt", 1e-3),
        ("ang3", 1e-30),
        ("ang^3", 1e-30),
        ("barrel", 0.158987294928),
        ("bushel", 0.03523907016688),
        ("ft3", 0.028316846592),
        ("ft^3", 0.028316846592),
        ("in3", 1.6387064e-5),
        ("in^3", 1.6387064e-5),
        ("ly3", 8.46786664623715e47),
        ("ly^3", 8.46786664623715e47),
        ("m3", 1.0),
        ("m^3", 1.0),
        ("mi3", 4168181825.440579584),
        ("mi^3", 4168181825.440579584),
        ("yd3", 0.764554857984),
        ("yd^3", 0.764554857984),
        ("Nmi3", 6352182208.0),
        ("Nmi^3", 6352182208.0),
        ("Pica3", 4.39039566186557e-11),
        ("Pica^3", 4.39039566186557e-11),
        ("GRT", 2.8316846592),
        ("regton", 2.8316846592),
        ("MTON", 1.13267386368),
    ],
)

add_units(
    "area",
    [
        ("uk_acre", 4046.8564224),
        ("us_acre", 4046.87260987425),
        ("ang2", 1e-20),
        ("ang^2", 1e-20),
        ("ar", 100.0),
        ("ft2", 0.09290304),
        ("ft^2", 0.09290304),
        ("ha", 10000.0),
        ("in2", 0.00064516),
        ("in^2", 0.00064516),
        ("ly2", 8.95054210748189e31),
        ("ly^2", 8.95054210748189e31),
        ("m2", 1.0),
        ("m^2", 1.0),
        ("Morgen", 2500.0),
        ("mi2", 2589988.110336),
        ("mi^2", 2589988.110336),
        ("Nmi2", 3429904.0),
        ("Nmi^2", 3429904.0),
        ("Pica2", 1.24452160493827e-7),
        ("Pica^2", 1.24452160493827e-7),
        ("yd2", 0.83612736),
        ("yd^2", 0.83612736),
    ],
)

add_units("info", [("bit", 1.0), ("byte", 8.0)])

add_units(
    "speed",
    [
        ("admkn", 0.514773333333333),
        ("kn", 0.514444444444444),
        ("m/h", 1.0 / 3600.0),
        ("m/hr", 1.0 / 3600.0),
        ("m/s", 1.0),
        ("m/sec", 1.0),
        ("mph", 0.44704),
    ],
)

PFX = {
    "Y": 1e24,
    "Z": 1e21,
    "E": 1e18,
    "P": 1e15,
    "T": 1e12,
    "G": 1e9,
    "M": 1e6,
    "k": 1e3,
    "h": 1e2,
    "da": 1e1,
    "e": 1e1,
    "d": 1e-1,
    "c": 1e-2,
    "m": 1e-3,
    "u": 1e-6,
    "n": 1e-9,
    "p": 1e-12,
    "f": 1e-15,
    "a": 1e-18,
    "z": 1e-21,
    "y": 1e-24,
}

BPFX = {
    "Yi": 2**80,
    "Zi": 2**70,
    "Ei": 2**60,
    "Pi": 2**50,
    "Ti": 2**40,
    "Gi": 2**30,
    "Mi": 2**20,
    "ki": 2**10,
}

NOPFX = {
    "lbm",
    "ozm",
    "grain",
    "cwt",
    "shweight",
    "uk_cwt",
    "lcwt",
    "hweight",
    "stone",
    "ton",
    "uk_ton",
    "LTON",
    "brton",
    "mi",
    "Nmi",
    "in",
    "ft",
    "yd",
    "ell",
    "Pica",
    "Picapt",
    "pica",
    "survey_mi",
    "yr",
    "day",
    "d",
    "hr",
    "mn",
    "min",
    "mmHg",
    "psi",
    "lbf",
    "HPh",
    "hh",
    "flb",
    "BTU",
    "btu",
    "HP",
    "h",
    "PS",
    "F",
    "fah",
    "Rank",
    "Reau",
    "tsp",
    "tspm",
    "tbs",
    "oz",
    "cup",
    "pt",
    "us_pt",
    "uk_pt",
    "qt",
    "uk_qt",
    "gal",
    "uk_gal",
    "barrel",
    "bushel",
    "ft3",
    "ft^3",
    "in3",
    "in^3",
    "mi3",
    "mi^3",
    "yd3",
    "yd^3",
    "Nmi3",
    "Nmi^3",
    "uk_acre",
    "us_acre",
    "ft2",
    "ft^2",
    "ha",
    "in2",
    "in^2",
    "Morgen",
    "mi2",
    "mi^2",
    "Nmi2",
    "Nmi^2",
    "yd2",
    "yd^2",
    "admkn",
    "kn",
    "mph",
    "GRT",
    "regton",
    "MTON",
}


def parse_unit(s: str) -> tuple[dict[str, Any], str, float] | None:
    if s in U:
        return (U[s], s, 1.0)
    for p, f in BPFX.items():
        if s.startswith(p):
            base = s[len(p) :]
            if base in U and U[base]["cat"] == "info":
                return (U[base], base, float(f))
    sorted_pfx = sorted(PFX.items(), key=lambda x: len(x[0]), reverse=True)
    for p, f in sorted_pfx:
        if s.startswith(p):
            base = s[len(p) :]
            if base in U and base not in NOPFX:
                u = U[base]
                pw = 2.0 if ("2" in base and u["cat"] == "area") else 3.0 if ("3" in base and u["cat"] == "vol") else 1.0
                return (u, base, f**pw)
    return None


def to_kelvin(v: float, unit_name: str) -> float:
    if unit_name in ("C", "cel"):
        return v + 273.15
    if unit_name in ("F", "fah"):
        return (v - 32.0) * 5.0 / 9.0 + 273.15
    if unit_name in ("K", "kel"):
        return v
    if unit_name == "Rank":
        return (v * 5.0) / 9.0
    if unit_name == "Reau":
        return v * 1.25 + 273.15
    return v


def from_kelvin(v: float, unit_name: str) -> float:
    if unit_name in ("C", "cel"):
        return v - 273.15
    if unit_name in ("F", "fah"):
        return (v - 273.15) * 9.0 / 5.0 + 32.0
    if unit_name in ("K", "kel"):
        return v
    if unit_name == "Rank":
        return (v * 9.0) / 5.0
    if unit_name == "Reau":
        return (v - 273.15) * 0.8
    return v


@register_eng("CONVERT")
def fn_convert(
    number: Any, from_unit: Any, to_unit: Any, ctx: EvalContext | None = None
) -> float | ExcelError:
    n_val = to_float(number)
    if is_error(n_val):
        return n_val
    src = str(from_unit).strip()
    tgt = str(to_unit).strip()
    a = parse_unit(src)
    b = parse_unit(tgt)
    if a is None or b is None or a[0]["cat"] != b[0]["cat"]:
        return NA
    val = float(n_val)
    if a[0]["cat"] == "temp":
        k_val = to_kelvin(val * a[2], a[1])
        return from_kelvin(k_val, b[1]) / b[2]
    return (val * a[0]["f"] * a[2]) / (b[0]["f"] * b[2])

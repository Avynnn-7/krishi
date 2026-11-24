"""Verified ICAR AICRP-STCR fertilizer-adjustment equations (targeted-yield approach).

    F_n = a_n * T  -  b_n * S_n  -  c_n * ON_n          (kg/ha, never below 0)

    T    yield target, q/ha          S_n  soil-test value (kg/ha; organic carbon in % where noted)
    ON_n nutrient supplied by farmyard manure (kg/ha)   F_n  fertilizer nutrient to apply (N, P2O5, K2O)

Every entry below was transcribed from the user-supplied ICAR compendium "Four Decades of STCR Research - Crop Wise
Recommendations" and then checked numerically against that entry's own ready-reckoner table (see tests/test_jalkhadd.py).
Nothing is borrowed from another region: a crop with no entry for this region is refused, not approximated.
"""

from __future__ import annotations

import json
from dataclasses import dataclass

NUTRIENTS = ("N", "P", "K")


@dataclass(frozen=True)
class StcrEquation:
    key: str
    crop: str
    variety: str
    centre: str
    season: str
    a: dict
    b: dict
    c: dict  # manure (FYM) credit per kg of manure nutrient; all 0 if the source has no manure term
    soil_var: dict  # soil-test variable feeding each nutrient: "N" (alk. KMnO4-N), "OC" (organic carbon %), "P", "K"
    target_range: tuple  # (min, max) q/ha the equation was developed/validated for
    soil_range: dict  # calibrated range per soil variable; outside it the dose is an extrapolation
    fym_composition_pct: dict | None  # % N, P, K of the manure used in the source trials
    applicability: str
    caution: str
    verification: str

    def __post_init__(self) -> None:
        for n in NUTRIENTS:
            if not (self.a[n] > 0 and self.b[n] >= 0 and self.c[n] >= 0):
                raise ValueError(f"{self.key}: need a>0, b>=0, c>=0 for {n}")
            if self.c[n] > 0 and not self.fym_composition_pct:
                raise ValueError(f"{self.key}: manure credit needs a manure composition")
        lo, hi = self.target_range
        if not 0 < lo <= hi:
            raise ValueError(f"{self.key}: bad target range")


_ZERO = {"N": 0.0, "P": 0.0, "K": 0.0}
_STD_VARS = {"N": "N", "P": "P", "K": "K"}

REGISTRY: dict[str, StcrEquation] = {
    "wheat": StcrEquation(
        key="wheat", crop="wheat", variety="UP-2382 (with FYM / IPNS form)", centre="GBPUAT Pantnagar, Uttarakhand",
        season="rabi, irrigated",
        a={"N": 6.28, "P": 0.94, "K": 1.36}, b={"N": 0.67, "P": 0.28, "K": 0.16}, c={"N": 0.371, "P": 0.173, "K": 0.079},
        soil_var=_STD_VARS, target_range=(40.0, 45.0),
        soil_range={"N": (150, 240), "P": (20, 60), "K": (150, 200)},
        fym_composition_pct={"N": 0.345, "P": 0.242, "K": 0.338},
        applicability="U.S. Nagar, Haridwar, Nainital and some parts of Western U.P. (stated in the source)",
        caution="Variety UP-2382 is old and equations are variety-specific. Source does not say whether soil P/K and doses are "
                "P vs P2O5, K vs K2O.",
        verification="Ready reckoner (40 q/ha, 10 t/ha FYM): P and K exact; N within 0.7 kg (printed b_N=0.67 is rounded).",
    ),
    "maize": StcrEquation(
        key="maize", crop="maize", variety="Pragati (with FYM / IPNS form)", centre="GBPUAT Pantnagar, Uttarakhand",
        season="kharif",
        a={"N": 12.56, "P": 4.65, "K": 5.94}, b={"N": 1.03, "P": 3.6, "K": 0.59}, c={"N": 0.32, "P": 1.56, "K": 0.93},
        soil_var=_STD_VARS, target_range=(30.0, 40.0),
        soil_range={"N": (200, 260), "P": (10, 40), "K": (180, 240)},
        fym_composition_pct={"N": 0.6, "P": 0.2, "K": 0.5},
        applicability="U.S. Nagar, Haridwar, Nainital and some parts of Western U.P. (stated in the source)",
        caution="Source prints the N soil term as '1.03N' (read as SN). The printed reckoner's N column is shifted one row "
                "relative to its soil-test column; the values themselves match the equation. Variety Pragati only.",
        verification="Reckoner (35 q/ha, 10 t/ha FYM): P and K exact; N values match as a set (row order shifted in the source).",
    ),
    "mustard": StcrEquation(
        key="mustard", crop="mustard", variety="PYS-I (with FYM / IPNS form)", centre="GBPUAT Pantnagar, Uttarakhand",
        season="rabi",
        a={"N": 15.63, "P": 2.40, "K": 3.88}, b={"N": 1.04, "P": 1.03, "K": 0.16}, c={"N": 1.61, "P": 0.32, "K": 0.40},
        soil_var=_STD_VARS, target_range=(15.0, 20.0),
        soil_range={"N": (198, 325), "P": (15, 35), "K": (168, 320)},
        fym_composition_pct={"N": 0.5, "P": 0.2, "K": 0.6},
        applicability="U.S. Nagar, Haridwar, Nainital and some parts of Western U.P. (stated in the source)",
        caution="Source prints the K soil term as 'SP' (typo for SK). Variety PYS-I only; the Kranti equation in the same entry "
                "is garbled and not used.",
        verification="Reckoner (15 q/ha, 10 t/ha FYM): N, P, K exact.",
    ),
    "barley": StcrEquation(
        key="barley", crop="barley", variety="Azad (inorganic only)", centre="GBPUAT Pantnagar, Uttarakhand",
        season="rabi, irrigated",
        a={"N": 5.00, "P": 2.45, "K": 4.96}, b={"N": 111.16, "P": 2.31, "K": 0.82}, c=dict(_ZERO),
        soil_var={"N": "OC", "P": "P", "K": "K"},  # N is driven by ORGANIC CARBON (%), not KMnO4-N
        target_range=(25.0, 30.0),
        soil_range={"OC": (0.40, 1.00), "P": (10, 25), "K": (150, 225)},
        fym_composition_pct=None,
        applicability="U.S. Nagar, Haridwar, Nainital and some parts of Western U.P. (stated in the source)",
        caution="Nitrogen depends on organic carbon (%), not on KMnO4-N. No manure term in the source.",
        verification="Reckoner (30 q/ha): N, P, K exact for all five rows.",
    ),
    "rice": StcrEquation(
        key="rice", crop="rice", variety="HYV, without FYM", centre="IARI New Delhi (Typic Haplustept, alluvial)",
        season="kharif, irrigated",
        a={"N": 4.93, "P": 4.48, "K": 2.31}, b={"N": 0.47, "P": 7.82, "K": 0.21}, c=dict(_ZERO),
        soil_var=_STD_VARS, target_range=(50.0, 60.0),
        soil_range={"N": (100, 375), "P": (10, 38), "K": (100, 375)},
        fym_composition_pct=None,
        applicability="Delhi and adjoining areas of UP incl. Saharanpur, Muzaffarnagar, Meerut; Haryana (Karnal, Panipat, ...). "
                      "Haridwar is NOT named (it borders Saharanpur).",
        caution="Applicability to Haridwar is by adjacency only: confirm with KVK Dhanauri. The source reckoner applies a "
                "maintenance minimum (10-15 kg P2O5) where the equation gives ~0; that floor is not modelled. No manure term.",
        verification="Reckoner (50 and 60 q/ha) reproduced to within its 5-kg rounding.",
    ),
}

UNSUPPORTED_NOTE = {
    "sugarcane": "The compendium has sugarcane equations only for Andhra Pradesh, Karnataka, Tamil Nadu, Bihar (Pusa), Madhya "
                 "Pradesh, Chhattisgarh and Maharashtra, none for Uttarakhand or western UP. Supply a local equation with "
                 "--equations rather than borrowing one from another soil.",
}


def get_equation(crop: str, extra: dict[str, StcrEquation] | None = None) -> StcrEquation:
    key = crop.strip().lower()
    if extra and key in extra:
        return extra[key]
    if key in REGISTRY:
        return REGISTRY[key]
    note = UNSUPPORTED_NOTE.get(key, "No verified STCR equation for this crop and region.")
    raise KeyError(f"Unsupported crop '{crop}'. {note} Supported: {', '.join(sorted(REGISTRY))}.")


def load_extra_equations(path: str) -> dict[str, StcrEquation]:
    """JSON list of equations in the same fields as StcrEquation (lists for ranges). For local equations the
    user obtains from KVK/GBPUAT; they are used as given, so the user owns their verification."""
    out = {}
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
    for d in data:
        d = dict(d)
        d["target_range"] = tuple(d["target_range"])
        d["soil_range"] = {k: tuple(v) for k, v in d.get("soil_range", {}).items()}
        d.setdefault("c", dict(_ZERO))
        d.setdefault("soil_var", dict(_STD_VARS))
        d.setdefault("fym_composition_pct", None)
        d.setdefault("variety", "")
        d.setdefault("centre", "user-supplied")
        d.setdefault("season", "")
        d.setdefault("applicability", "user-supplied")
        d.setdefault("caution", "User-supplied equation: not verified by this package.")
        d.setdefault("verification", "none")
        eq = StcrEquation(**d)
        out[eq.key.lower()] = eq
    return out

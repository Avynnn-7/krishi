"""Fertilizer products (grade, bag size, price) and CSV loading."""

from __future__ import annotations

import csv
import math
from dataclasses import dataclass, field

NUTRIENTS = ("N", "P", "K", "S")


@dataclass(frozen=True)
class Product:
    """analysis_pct is the guaranteed grade in % w/w on the N / P2O5 / K2O / S basis (DAP = N 18, P 46)."""

    name: str
    price_rs: float  # one bag
    weight_kg: float  # bag size
    analysis_pct: dict = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.name:
            raise ValueError("Product needs a name.")
        if not (math.isfinite(self.price_rs) and self.price_rs > 0):
            raise ValueError(f"{self.name}: price must be positive.")
        if not (math.isfinite(self.weight_kg) and self.weight_kg > 0):
            raise ValueError(f"{self.name}: bag weight must be positive.")
        if set(self.analysis_pct) - set(NUTRIENTS):
            raise ValueError(f"{self.name}: unknown nutrient key in {sorted(self.analysis_pct)}")
        if any(v < 0 for v in self.analysis_pct.values()) or sum(self.analysis_pct.values()) > 100:
            raise ValueError(f"{self.name}: grade must be nonnegative and sum to <= 100 %.")

    def fraction(self, n: str) -> float:
        return self.analysis_pct.get(n, 0.0) / 100.0


def default_catalog() -> list[Product]:
    """Grades per the Lok Sabha reply of 26.07.2024; prices are the government's July-2024 AVERAGE MRPs (urea excludes
    neem-coating charges and taxes). Replace with the dealer's current prices (--products products.csv) before real use."""
    return [
        Product("Urea", 242.0, 45.0, {"N": 46}),
        Product("DAP", 1350.0, 50.0, {"N": 18, "P": 46}),
        Product("MOP", 1612.48, 50.0, {"K": 60}),
        Product("SSP", 516.92, 50.0, {"P": 16, "S": 11}),
        Product("NPK 12-32-16", 1470.0, 50.0, {"N": 12, "P": 32, "K": 16}),
    ]


def load_products_csv(path: str) -> list[Product]:
    """Columns: name, price_rs (per bag), bag_kg, N, P2O5, K2O, S (grade %), optional available (0/1)."""
    out = []
    with open(path, encoding="utf-8-sig") as fh:
        for i, r in enumerate(csv.DictReader(fh), 2):
            if str(r.get("available", "1")).strip() in ("0", "no", "No", "false", "False"):
                continue

            def num(*keys):
                for k in keys:
                    if r.get(k) not in (None, ""):
                        return float(r[k])
                return 0.0

            try:
                out.append(Product(
                    r["name"].strip(), float(r["price_rs"]), float(r["bag_kg"]),
                    {k: v for k, v in {"N": num("N"), "P": num("P2O5", "P"), "K": num("K2O", "K"), "S": num("S")}.items() if v},
                ))
            except (KeyError, ValueError) as e:
                raise ValueError(f"{path} line {i}: {e}") from e
    if not out:
        raise ValueError(f"{path}: no available products.")
    if len({p.name for p in out}) != len(out):
        raise ValueError(f"{path}: product names must be unique.")
    return out

import math
from datetime import date, datetime
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field, model_validator

NUTRIENTS = ("N", "P2O5", "K2O")
BLOCKS = ("Roorkee", "Bhagwanpur", "Laksar", "Narsan", "Bahadrabad", "Khanpur")
TEXTURES = ("sandy", "sandy-loam", "loam", "clay-loam", "clay")
METHODS = (
    "wild_flood",
    "border",
    "laser_border",
    "furrow",
    "raised_bed",
    "sprinkler",
    "drip",
    "rice_cf",
    "rice_awd",
)
P_TO_P2O5 = 2.2914
K_TO_K2O = 1.2046


class Crop(StrEnum):
    WHEAT = "wheat"
    SUGARCANE = "sugarcane"
    RICE = "rice"
    MAIZE = "maize"


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False, str_strip_whitespace=True)


class Soil(StrictModel):
    N: float = Field(ge=0, le=2000)
    P: float = Field(ge=0, le=2000)
    K: float = Field(ge=0, le=3000)
    basis: str = Field(default="elemental", pattern="^(elemental|oxide)$")
    ph: float | None = Field(default=None, ge=0, le=14)
    ec: float | None = Field(default=None, ge=0, le=50)
    organic_carbon: float | None = Field(default=None, ge=0, le=20)
    sulphur: float | None = Field(default=None, ge=0, le=500)
    zinc: float | None = Field(default=None, ge=0, le=100)
    iron: float | None = Field(default=None, ge=0, le=500)
    manganese: float | None = Field(default=None, ge=0, le=500)
    copper: float | None = Field(default=None, ge=0, le=100)
    boron: float | None = Field(default=None, ge=0, le=50)

    def oxide_values(self) -> dict[str, float]:
        oxide = self.basis == "oxide"
        return {
            "N": self.N,
            "P2O5": self.P if oxide else self.P * P_TO_P2O5,
            "K2O": self.K if oxide else self.K * K_TO_K2O,
        }

    def elemental_values(self) -> dict[str, float]:
        oxide = self.basis == "oxide"
        return {
            "N": self.N,
            "P": self.P / P_TO_P2O5 if oxide else self.P,
            "K": self.K / K_TO_K2O if oxide else self.K,
        }


class AdvisoryInput(StrictModel):
    block: str
    village: str = Field(min_length=1, max_length=80)
    crop: Crop
    sowing_date: date = Field(ge=date(1900, 1, 1), le=date(2100, 12, 31))
    area: float = Field(gt=0, le=10000)
    area_unit: str = Field(default="ha", pattern="^(ha|acre|bigha)$")
    bigha_m2: float | None = Field(default=None, ge=100, le=10000)
    budget: float = Field(ge=0, le=1000000, multiple_of=0.01)
    target_yield: float = Field(default=50, gt=0, le=2000)
    texture: str = Field(default="loam", pattern="^(sandy|sandy-loam|loam|clay-loam|clay)$")
    soil: Soil | None = None
    soil_source: str | None = Field(
        default=None, pattern="^(card|official_village|block_baseline)$"
    )
    stcr_profile: str | None = None
    fym_t_ha: float = Field(default=0, ge=0, le=40)
    irrigation_at: datetime | None = None
    irrigation_cycle_days: int = Field(default=7, ge=1, le=30)
    irrigation_method: str | None = None
    flow_lps: float | None = Field(default=None, gt=0, le=500)
    turn_hours: float | None = Field(default=None, gt=0, le=72)
    max_irrigations: int | None = Field(default=None, ge=0, le=30)
    prices: dict[str, float] = Field(default_factory=dict, max_length=20)
    unavailable: list[str] = Field(default_factory=list, max_length=20)
    current_practice: dict[str, float] = Field(default_factory=dict, max_length=20)
    baseline_cost: float | None = Field(default=None, ge=0, le=10000000)
    latitude: float | None = Field(default=None, ge=-90, le=90)
    longitude: float | None = Field(default=None, ge=-180, le=180)

    @model_validator(mode="after")
    def check_consistency(self) -> "AdvisoryInput":
        if self.block not in BLOCKS:
            raise ValueError("Select a supported Haridwar block.")
        if self.area_unit == "bigha" and self.bigha_m2 is None:
            raise ValueError("Specify local square metres per bigha; bigha is not a fixed unit.")
        if (self.latitude is None) != (self.longitude is None):
            raise ValueError("Provide both latitude and longitude.")
        if self.stcr_profile and self.soil is None:
            raise ValueError("STCR requires measured soil test values.")
        if self.irrigation_at and not 1900 <= self.irrigation_at.year <= 2100:
            raise ValueError("Irrigation dates must be between 1900 and 2100.")
        if self.irrigation_method and self.irrigation_method not in METHODS:
            raise ValueError("Unknown irrigation method.")
        if any(not 0.01 <= v <= 100000 for v in self.prices.values()):
            raise ValueError("Fertilizer prices must be between ₹0.01 and ₹1,00,000 per bag.")
        if any(not 0 <= v <= 1000 for v in self.current_practice.values()):
            raise ValueError("Current-practice bags must be between 0 and 1,000.")
        if self.area_ha > 100:
            raise ValueError("This prototype supports fields up to 100 hectares.")
        return self

    @property
    def area_ha(self) -> float:
        if self.area_unit == "acre":
            return self.area * 0.40468564224
        if self.area_unit == "bigha":
            assert self.bigha_m2 is not None
            return self.area * self.bigha_m2 / 10000
        return self.area


class Product(StrictModel):
    id: str = ""
    name: str
    name_hi: str = ""
    weight_kg: float = Field(gt=0)
    price_rs: float = Field(ge=0.01, multiple_of=0.01)
    N: float = Field(ge=0, le=1)
    P2O5: float = Field(ge=0, le=1)
    K2O: float = Field(ge=0, le=1)
    S: float = Field(default=0, ge=0, le=1)

    @model_validator(mode="after")
    def check_composition(self) -> "Product":
        if self.N + self.P2O5 + self.K2O + self.S > 1:
            raise ValueError("Product nutrient fractions cannot exceed its total mass.")
        if not self.id:
            self.id = self.name.lower()
        if not self.name_hi:
            self.name_hi = self.name
        return self

    def fraction(self, nutrient: str) -> float:
        return {"N": self.N, "P2O5": self.P2O5, "K2O": self.K2O}[nutrient]


def valid_nutrients(values: dict[str, float]) -> None:
    if set(values) != set(NUTRIENTS) or any(not math.isfinite(v) or v < 0 for v in values.values()):
        raise ValueError("Nutrients must contain finite, nonnegative N, P2O5 and K2O.")

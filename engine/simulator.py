from pydantic import Field

from engine.models import StrictModel


class Scenario(StrictModel):
    area_ha: float = Field(default=1, gt=0, le=100)
    main_revenue: float = Field(default=240000, ge=0, le=10000000)
    main_cost: float = Field(default=150000, ge=0, le=10000000)
    intercrop_yield: float = Field(default=4, ge=0, le=100)
    intercrop_price: float = Field(default=7000, ge=0, le=100000)
    added_cost: float = Field(default=12000, ge=0, le=1000000)
    main_revenue_loss_pct: float = Field(default=5, ge=0, le=100)
    credited_n: float = Field(default=0, ge=0, le=60)


def compare_scenarios(s: Scenario) -> dict:
    saving = s.credited_n / 0.46 * (266.5 / 45)
    mono = (s.main_revenue - s.main_cost) * s.area_ha
    extra_revenue = s.intercrop_yield * s.intercrop_price
    main_loss = s.main_revenue * s.main_revenue_loss_pct / 100
    delta = (extra_revenue + saving - s.added_cost - main_loss) * s.area_ha
    return {
        "monoculture_profit": mono,
        "intercrop_profit": mono + delta,
        "difference": delta,
        "fertilizer_saving": saving * s.area_ha,
        "extra_revenue": extra_revenue * s.area_ha,
        "main_loss": main_loss * s.area_ha,
        "added_cost": s.added_cost * s.area_ha,
        "break_even_yield": max(0, (s.added_cost + main_loss - saving) / s.intercrop_price)
        if s.intercrop_price
        else None,
    }

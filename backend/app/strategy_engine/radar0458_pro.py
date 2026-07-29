from dataclasses import dataclass
from decimal import Decimal, ROUND_DOWN

from app.strategy_engine.base import Strategy


CENT = Decimal("0.01")
VALID_RADAR_PROFILES = ("pro1", "pro2", "pro3")


@dataclass(frozen=True)
class RadarPreset:
    code: str
    tier_ratios: tuple[Decimal, ...]
    buy_threshold_percent: Decimal
    sell_threshold_percent: Decimal
    max_holding_days: int


@dataclass(frozen=True)
class RadarTierPlan:
    tier: int | None
    profile: str
    cycle_capital: Decimal
    limit_price: Decimal
    allocation: Decimal
    quantity: int
    blocking_reason: str | None


RADAR_PRESETS = {
    "pro1": RadarPreset(
        code="pro1",
        tier_ratios=(
            Decimal("0.05"),
            Decimal("0.10"),
            Decimal("0.15"),
            Decimal("0.20"),
            Decimal("0.25"),
            Decimal("0.25"),
        ),
        buy_threshold_percent=Decimal("-0.01"),
        sell_threshold_percent=Decimal("0.01"),
        max_holding_days=10,
    ),
    "pro2": RadarPreset(
        code="pro2",
        tier_ratios=(
            Decimal("0.10"),
            Decimal("0.15"),
            Decimal("0.20"),
            Decimal("0.25"),
            Decimal("0.20"),
            Decimal("0.10"),
        ),
        buy_threshold_percent=Decimal("-0.01"),
        sell_threshold_percent=Decimal("1.50"),
        max_holding_days=10,
    ),
    "pro3": RadarPreset(
        code="pro3",
        tier_ratios=(Decimal("1") / Decimal("6"),) * 6,
        buy_threshold_percent=Decimal("-0.10"),
        sell_threshold_percent=Decimal("2.00"),
        max_holding_days=12,
    ),
}


def get_radar_preset(profile: str) -> RadarPreset:
    try:
        return RADAR_PRESETS[profile]
    except KeyError as exc:
        raise ValueError(f"Unknown Radar0458 Pro profile: {profile}") from exc


def next_radar_tier(occupied_tiers: set[int]) -> int | None:
    for tier in range(1, 7):
        if tier not in occupied_tiers:
            return tier
    if 7 not in occupied_tiers:
        return 7
    return None


def build_radar_buy_plan(
    previous_close: Decimal,
    cycle_capital: Decimal,
    available_cash: Decimal,
    occupied_tiers: set[int],
    profile: str,
    fee_rate_percent: Decimal = Decimal("0"),
) -> RadarTierPlan:
    preset = get_radar_preset(profile)
    previous_close = Decimal(str(previous_close))
    cycle_capital = Decimal(str(cycle_capital))
    available_cash = Decimal(str(available_cash))
    fee_rate_percent = Decimal(str(fee_rate_percent))
    if previous_close <= 0:
        raise ValueError("previous_close_must_be_positive")

    tier = next_radar_tier(occupied_tiers)
    threshold = Decimal("1") + preset.buy_threshold_percent / Decimal("100")
    limit_price = (previous_close * threshold).quantize(CENT, rounding=ROUND_DOWN)
    if tier is None:
        return RadarTierPlan(
            tier=None,
            profile=profile,
            cycle_capital=cycle_capital,
            limit_price=limit_price,
            allocation=Decimal("0.00"),
            quantity=0,
            blocking_reason="all_tiers_occupied",
        )

    allocation = (
        available_cash if tier == 7 else cycle_capital * preset.tier_ratios[tier - 1]
    ).quantize(CENT, rounding=ROUND_DOWN)
    unit_cost = limit_price * (Decimal("1") + fee_rate_percent / Decimal("100"))
    quantity = int((allocation / unit_cost).to_integral_value(rounding=ROUND_DOWN))
    required_cash = unit_cost * Decimal(quantity)
    if quantity == 0:
        blocking_reason = "quantity_zero"
    elif required_cash > available_cash:
        blocking_reason = "insufficient_cash"
    else:
        blocking_reason = None
    return RadarTierPlan(
        tier=tier,
        profile=profile,
        cycle_capital=cycle_capital,
        limit_price=limit_price,
        allocation=allocation,
        quantity=quantity,
        blocking_reason=blocking_reason,
    )


class Radar0458ProStrategy(Strategy):
    strategy_type = "radar0458_pro"
    display_name = "Radar0458 Pro"

    @staticmethod
    def default_settings() -> dict[str, str]:
        return {"pro_profile": "pro1"}

    def get_settings_schema(self) -> dict:
        return {
            "type": "object",
            "fields": {
                "pro_profile": {
                    "type": "string",
                    "enum": list(VALID_RADAR_PROFILES),
                    "default": "pro1",
                }
            },
        }

    def get_mode(self, context):
        raise NotImplementedError("Radar0458 Pro is orchestrated through its tier planner")

    def should_buy(self, context):
        raise NotImplementedError("Radar0458 Pro is orchestrated through its tier planner")

    def should_sell(self, context, position):
        raise NotImplementedError("Radar0458 Pro is orchestrated through position snapshots")

    def calculate_position_size(self, context):
        raise NotImplementedError("Radar0458 Pro is orchestrated through its tier planner")

    def update_capital(self, context, realized_pnl):
        raise NotImplementedError("Radar0458 Pro capital updates are handled by orchestration")

from decimal import Decimal

from app.domain.enums import StrategyMode
from app.strategy_engine.base import BuySignal, CapitalUpdate, PositionSize, SellSignal, Strategy
from app.strategy_engine.loc import LocPlan, MONEY_QUANT, calculate_loc_plan
from app.strategy_engine.context import StrategyContext, StrategyPosition


class DynamicWaveStrategy(Strategy):
    strategy_type = "dynamic_wave"
    display_name = "Dynamic Wave Strategy"

    @staticmethod
    def default_settings() -> dict:
        return {
            "mode_rsi_symbol": "QQQ",
            "profit_compounding_rate": 60,
            "loss_compounding_rate": 20,
            "capital_update": {"type": "trading_days", "interval": 10, "period": "monthly"},
            "safe": {
                "split_count": 7,
                "max_holding_days": 30,
                "buy_threshold_percent": 3,
                "sell_threshold_percent": 0.2,
            },
            "aggressive": {
                "split_count": 7,
                "max_holding_days": 7,
                "buy_threshold_percent": 5,
                "sell_threshold_percent": 2.5,
            },
        }

    def get_mode(self, context: StrategyContext) -> StrategyMode:
        return context.effective_mode

    def _build_loc_plan(self, context: StrategyContext) -> LocPlan:
        mode = self.get_mode(context)
        mode_settings = context.settings[mode.value]
        return calculate_loc_plan(
            previous_close=context.previous_close,
            capital=context.capital,
            cash=context.cash,
            fee_rate=Decimal(str(context.settings.get("fee_rate_percent", "0"))),
            split_count=int(mode_settings["split_count"]),
            buy_threshold_percent=Decimal(str(mode_settings["buy_threshold_percent"])),
            open_position_count=len(context.open_positions),
        )

    def should_buy(self, context: StrategyContext) -> BuySignal:
        plan = self._build_loc_plan(context)
        if plan.blocking_reason is not None:
            return BuySignal(False, plan.blocking_reason)
        if context.current_close <= plan.limit_price:
            return BuySignal(True, "loc_threshold")
        return BuySignal(False, "price_above_threshold")

    def should_sell(self, context: StrategyContext, position: StrategyPosition) -> SellSignal:
        mode_settings = context.settings[position.mode.value]
        return_pct = (context.current_close - position.buy_price) / position.buy_price * Decimal("100")
        if return_pct >= Decimal(str(mode_settings["sell_threshold_percent"])):
            return SellSignal(True, "profit_target", return_pct.quantize(MONEY_QUANT))
        holding_days = (context.current_date - position.buy_date).days
        if holding_days >= int(mode_settings["max_holding_days"]):
            return SellSignal(True, "max_holding_period", return_pct.quantize(MONEY_QUANT))
        return SellSignal(False, None, return_pct.quantize(MONEY_QUANT))

    def calculate_position_size(self, context: StrategyContext) -> PositionSize:
        plan = self._build_loc_plan(context)
        return PositionSize(plan.allocation, plan.quantity)

    def update_capital(self, context: StrategyContext, realized_pnl: Decimal) -> CapitalUpdate:
        """Apply PCR/LCR to realized PnL after the caller has checked the update schedule."""
        if realized_pnl >= 0:
            rate = Decimal(str(context.settings["profit_compounding_rate"])) / Decimal("100")
            capital = context.capital + realized_pnl * rate
        else:
            rate = Decimal(str(context.settings["loss_compounding_rate"])) / Decimal("100")
            capital = context.capital + realized_pnl * rate
        return CapitalUpdate(capital.quantize(MONEY_QUANT))

    def get_settings_schema(self) -> dict:
        return {
            "type": "object",
            "fields": self.default_settings(),
        }

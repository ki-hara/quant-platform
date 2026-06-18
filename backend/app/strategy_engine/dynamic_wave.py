from datetime import date
from decimal import Decimal, ROUND_DOWN

from app.domain.enums import StrategyMode
from app.strategy_engine.base import BuySignal, CapitalUpdate, PositionSize, SellSignal, Strategy
from app.strategy_engine.context import StrategyContext, StrategyPosition


MONEY_QUANT = Decimal("0.000001")


class DynamicWaveStrategy(Strategy):
    strategy_type = "dynamic_wave"
    display_name = "Dynamic Wave Strategy"

    @staticmethod
    def default_settings() -> dict:
        return {
            "mode_rsi_symbol": "QQQ",
            "base_index": "QQQ",
            "profit_compounding_rate": 50,
            "loss_compounding_rate": 30,
            "capital_update": {"type": "trading_days", "interval": 20},
            "safe": {
                "split_count": 7,
                "max_holding_days": 20,
                "buy_threshold_percent": 3,
                "sell_threshold_percent": 5,
            },
            "aggressive": {
                "split_count": 5,
                "max_holding_days": 10,
                "buy_threshold_percent": 5,
                "sell_threshold_percent": 7,
            },
        }

    def get_mode(self, context: StrategyContext) -> StrategyMode:
        return StrategyMode.SAFE

    def should_buy(self, context: StrategyContext) -> BuySignal:
        mode = self.get_mode(context)
        mode_settings = context.settings[mode.value]
        split_count = int(mode_settings["split_count"])
        if len(context.open_positions) >= split_count:
            return BuySignal(False, "split_limit_reached")
        threshold = Decimal(str(mode_settings["buy_threshold_percent"])) / Decimal("100")
        limit_price = context.previous_close * (Decimal("1") + threshold)
        if context.current_close <= limit_price:
            size = self.calculate_position_size(context)
            if size.quantity <= 0:
                return BuySignal(False, "quantity_zero")
            return BuySignal(True, "aod_threshold")
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
        mode_settings = context.settings[self.get_mode(context).value]
        split_count = Decimal(str(mode_settings["split_count"]))
        amount = (context.capital / split_count).quantize(MONEY_QUANT)
        quantity = int((amount / context.current_close).to_integral_value(rounding=ROUND_DOWN))
        return PositionSize(amount, quantity)

    def update_capital(self, context: StrategyContext, realized_pnl: Decimal) -> CapitalUpdate:
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

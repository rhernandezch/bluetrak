"""Domain models for exchange rate data."""

from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel


class Rate(BaseModel):
    """A single exchange rate observation from a source."""

    source: str
    buy_rate: float  # ARS per USD — what you pay to buy USD
    sell_rate: float  # ARS per USD — what you get when selling USD
    fetched_at: datetime

    def __str__(self) -> str:
        return f"{self.source}: buy={self.buy_rate:.2f} sell={self.sell_rate:.2f}"


class AlertLevel(StrEnum):
    """Per-source alert notification level."""

    OFF = "off"  # No real-time alerts (still fetches and appears in summaries)
    NORMAL = "normal"  # Alert on both NORMAL and HIGH urgency
    HIGH = "high"  # Only alert on HIGH urgency
    EVERY_CHANGE = "every_change"  # Alert whenever the sell rate changes


class AlertUrgency(StrEnum):
    NORMAL = "normal"
    HIGH = "high"


class DataMaturity(StrEnum):
    """How much historical data is available for analysis."""

    COLD = "cold"  # <1 day — threshold fallback only
    PRELIMINARY = "preliminary"  # 1-3 days — percentile only
    DEVELOPING = "developing"  # 3-7 days — percentile + z-score
    STABLE = "stable"  # 7-14 days — percentile + trend
    FULL = "full"  # 14+ days — all 3 components


class AlertSignal(BaseModel):
    """Result of ensemble alert evaluation for a single source."""

    source: str
    sell_rate: float
    should_alert: bool = False
    urgency: AlertUrgency = AlertUrgency.NORMAL
    maturity: DataMaturity = DataMaturity.COLD

    # Component scores (None if not enough data)
    percentile_rank: float | None = None
    trend_residual: float | None = None
    trend_residual_sigma: float | None = None  # residual expressed in std devs
    momentum_fading: bool | None = None

    # Context for the alert message
    window_high: float | None = None  # Highest rate in percentile window
    trend_predicted: float | None = None  # What the trend predicts

    def format_message(self) -> str:
        """Format a human-readable alert message."""
        lines = [f"🔔 *{self.source}* sell rate *{self.sell_rate:.2f}* ARS/USD"]
        lines.append("")

        if self.percentile_rank is not None:
            lines.append(
                f"  📈 {self.percentile_rank:.0f}th percentile of the last "
                f"{7} days _(highest was {self.window_high:.2f})_"
            )

        if self.trend_residual is not None and self.trend_predicted is not None:
            lines.append(
                f"  📐 *{self.trend_residual:+.2f}* ARS above the 14-day trend"
            )

        if self.momentum_fading:
            lines.append("  🔻 Momentum is flattening — rate has stopped increasing")

        if self.should_alert:
            lines.append("")
            if self.urgency == AlertUrgency.HIGH:
                lines.append("⚡ *This may be a good time to sell!*")
            else:
                lines.append("💡 _This may be a good time to sell._")

        return "\n".join(lines)


def format_rate_change_message(source: str, current: Rate, previous: Rate | None) -> str:
    """Format a 'rate changed' notification message."""
    lines = [f"📊 *{source}* rate updated"]
    lines.append(f"  sell *{current.sell_rate:.2f}* ARS/USD")

    if previous is not None:
        diff = current.sell_rate - previous.sell_rate
        arrow = "🟢 ▲" if diff > 0 else ("🔴 ▼" if diff < 0 else "⚪ ▸")
        sign = "+" if diff > 0 else ""
        lines.append(f"  {arrow} {sign}{diff:.2f} from {previous.sell_rate:.2f}")

        buy_diff = current.buy_rate - previous.buy_rate
        if buy_diff != 0:
            buy_sign = "+" if buy_diff > 0 else ""
            lines.append(f"  buy *{current.buy_rate:.2f}* ({buy_sign}{buy_diff:.2f})")
    else:
        lines.append("  🆕 _First rate recorded_")

    return "\n".join(lines)

"""Periodic 12h rate summary message formatting."""

from datetime import datetime, timezone, timedelta

from bluetrak.models import AlertSignal, AlertUrgency, Rate

_UTC_MINUS_3 = timezone(timedelta(hours=-3))


def format_summary(
    now: datetime,
    source_names: list[str],
    current_rates: dict[str, Rate],
    prev_rates: dict[str, Rate | None],
    rates_12h: dict[str, list[Rate]],
    alerts: list[AlertSignal],
) -> str:
    """Build the Template A compact summary message.

    Args:
        now: Current UTC time (used for the header timestamp).
        source_names: Ordered list of all expected source names.
        current_rates: Latest rate per source (missing key = fetch failed).
        prev_rates: Rate ~12h ago per source; None = no prior data.
        rates_12h: All rates in the last 12h per source (for range).
        alerts: AlertSignals with should_alert=True fired in the period.
    """
    local_now = now.astimezone(_UTC_MINUS_3)
    hour = local_now.hour
    period = "AM" if hour < 12 else "PM"
    display_hour = hour if hour <= 12 else hour - 12
    display_hour = 12 if display_hour == 0 else display_hour
    header = f"📊 *Bluetrak — {display_hour}:00 {period}*"

    rows = []
    all_sells: list[float] = []

    for name in source_names:
        current = current_rates.get(name)
        prev = prev_rates.get(name)

        if current is None:
            rows.append(f"*{name}*   N/A")
            continue

        all_sells.extend(r.sell_rate for r in rates_12h.get(name, []))

        delta_str = _delta(current.sell_rate, prev.sell_rate if prev else None)
        rows.append(
            f"*{name}*   sell {current.sell_rate:,.2f}   buy {current.buy_rate:,.2f}   {delta_str}"
        )

    lines = [header, ""]
    lines.extend(rows)

    if all_sells:
        lines.append("")
        lines.append(f"12h range: {min(all_sells):,.2f} – {max(all_sells):,.2f}")

    fired = [a for a in alerts if a.should_alert]
    if fired:
        alert_parts = []
        for a in fired:
            tag = " ⚡" if a.urgency == AlertUrgency.HIGH else ""
            alert_parts.append(f"{a.source}{tag}")
        lines.append(f"Alerts: {', '.join(alert_parts)}")
    else:
        lines.append("Alerts: none")

    lines.append("")
    lines.append("_Next summary in ~12h_")

    return "\n".join(lines)


def _delta(current: float, previous: float | None) -> str:
    """Format a sell-rate delta with direction arrow. '—' when no baseline."""
    if previous is None:
        return "—"
    diff = current - previous
    arrow = "▲" if diff > 0 else ("▼" if diff < 0 else "►")
    sign = "+" if diff > 0 else ""
    return f"{sign}{diff:,.2f} {arrow}"

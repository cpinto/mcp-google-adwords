"""Convert Google Ads API responses into LLM-friendly markdown."""

from __future__ import annotations


MAX_KEYWORD_IDEAS = 50

COMPETITION_LABELS = {
    0: "Unspecified",
    1: "Unknown",
    2: "Low",
    3: "Medium",
    4: "High",
}


def micros_to_dollars(micros: int | None) -> str:
    if micros is None or micros == 0:
        return "$0.00"
    return f"${micros / 1_000_000:.2f}"


def format_number(n: int | float | None) -> str:
    if n is None:
        return "0"
    return f"{n:,.0f}"


def format_keyword_ideas(results: list) -> str:
    if not results:
        return "No keyword ideas found."

    sorted_results = sorted(
        results,
        key=lambda r: (r.keyword_idea_metrics.avg_monthly_searches or 0),
        reverse=True,
    )[:MAX_KEYWORD_IDEAS]

    lines = [
        f"**{len(sorted_results)} keyword ideas** (sorted by search volume)\n",
        "| Keyword | Avg Monthly Searches | Competition | Competition Index | Low CPC | High CPC |",
        "|---------|---------------------|-------------|-------------------|---------|----------|",
    ]

    for idea in sorted_results:
        m = idea.keyword_idea_metrics
        comp_value = m.competition if m.competition is not None else 0
        comp_label = COMPETITION_LABELS.get(comp_value, "Unknown")
        lines.append(
            f"| {idea.text} "
            f"| {format_number(m.avg_monthly_searches)} "
            f"| {comp_label} "
            f"| {m.competition_index if m.competition_index is not None else 'N/A'} "
            f"| {micros_to_dollars(m.low_top_of_page_bid_micros)} "
            f"| {micros_to_dollars(m.high_top_of_page_bid_micros)} |"
        )

    return "\n".join(lines)


def format_historical_metrics(results: list) -> str:
    if not results:
        return "No historical metrics found."

    lines = [
        f"**Historical metrics for {len(results)} keyword(s)**\n",
        "| Keyword | Avg Monthly Searches | Competition | Competition Index | Low CPC | High CPC |",
        "|---------|---------------------|-------------|-------------------|---------|----------|",
    ]

    for result in results:
        m = result.keyword_metrics
        keyword = result.text if hasattr(result, "text") else result.search_query
        comp_value = m.competition if m.competition is not None else 0
        comp_label = COMPETITION_LABELS.get(comp_value, "Unknown")
        close_variants = ""
        if hasattr(result, "close_variants") and result.close_variants:
            close_variants = f" _{', '.join(result.close_variants)}_"
        lines.append(
            f"| {keyword}{close_variants} "
            f"| {format_number(m.avg_monthly_searches)} "
            f"| {comp_label} "
            f"| {m.competition_index if m.competition_index is not None else 'N/A'} "
            f"| {micros_to_dollars(m.low_top_of_page_bid_micros)} "
            f"| {micros_to_dollars(m.high_top_of_page_bid_micros)} |"
        )

    return "\n".join(lines)


def format_forecast(campaign_forecast, keyword_forecasts: list, keywords: list[str], forecast_days: int) -> str:
    lines = [f"**Campaign Forecast ({forecast_days}-day period)**\n"]

    # Campaign-level summary
    total = campaign_forecast
    lines.append("### Summary")
    lines.append(f"- **Clicks:** {format_number(total.clicks)}")
    lines.append(f"- **Impressions:** {format_number(total.impressions)}")
    lines.append(f"- **Avg CPC:** {micros_to_dollars(total.average_cpc_micros)}")
    lines.append(f"- **CTR:** {total.click_through_rate:.2%}" if total.click_through_rate else "- **CTR:** N/A")
    lines.append(f"- **Total Cost:** {micros_to_dollars(total.cost_micros)}")
    lines.append("")

    # Per-keyword breakdown
    if keyword_forecasts:
        lines.append("### Per-Keyword Breakdown\n")
        lines.append("| Keyword | Clicks | Impressions | Avg CPC | CTR | Cost |")
        lines.append("|---------|--------|-------------|---------|-----|------|")

        for i, kw_forecast in enumerate(keyword_forecasts):
            keyword = keywords[i] if i < len(keywords) else f"Keyword {i+1}"
            f = kw_forecast.keyword_forecast
            ctr = f"{f.click_through_rate:.2%}" if f.click_through_rate else "N/A"
            lines.append(
                f"| {keyword} "
                f"| {format_number(f.clicks)} "
                f"| {format_number(f.impressions)} "
                f"| {micros_to_dollars(f.average_cpc_micros)} "
                f"| {ctr} "
                f"| {micros_to_dollars(f.cost_micros)} |"
            )

    return "\n".join(lines)

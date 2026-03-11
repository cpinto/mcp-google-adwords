"""FastMCP server with Google Ads keyword planning tools."""

from __future__ import annotations

import logging
import sys
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

import anyio
from mcp.server.fastmcp import Context, FastMCP

from .client import GoogleAdsKeywordClient
from .config import GoogleAdsConfig
from .formatters import format_forecast, format_historical_metrics, format_keyword_ideas

# Configure logging to stderr (stdout is reserved for MCP stdio transport)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
    stream=sys.stderr,
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(server: FastMCP) -> AsyncIterator[dict]:
    """Initialize the Google Ads client once at startup."""
    logger.info("Initializing Google Ads MCP server...")
    try:
        config = GoogleAdsConfig.from_env()
        client = GoogleAdsKeywordClient(config)
        logger.info("Google Ads client initialized (customer_id=%s)", config.customer_id)
        yield {"client": client}
    except ValueError as e:
        logger.error("Configuration error: %s", e)
        raise


mcp = FastMCP(
    "Google Ads Keyword Planner",
    instructions="Discover keyword opportunities, evaluate competition/CPC, and forecast campaign traffic using the Google Ads API.",
    lifespan=lifespan,
)


@mcp.tool()
async def generate_keyword_ideas(
    ctx: Context,
    keywords: list[str] | None = None,
    page_url: str | None = None,
    language_id: str = "1000",
    geo_target_ids: list[str] | None = None,
    include_adult_keywords: bool = False,
) -> str:
    """Discover new keyword ideas from seed terms and/or a URL.

    Args:
        keywords: Seed keywords to generate ideas from (e.g. ["running shoes", "marathon gear"])
        page_url: A URL to extract keyword ideas from
        language_id: Language constant ID (default "1000" for English)
        geo_target_ids: List of geo target IDs (default ["2840"] for US). Common: US=2840, UK=2826, CA=2124
        include_adult_keywords: Include adult keyword suggestions
    """
    client: GoogleAdsKeywordClient = ctx.request_context.lifespan_context["client"]

    result = await anyio.to_thread.run_sync(
        lambda: client.generate_keyword_ideas(
            keywords=keywords,
            page_url=page_url,
            language_id=language_id,
            geo_target_ids=geo_target_ids or ["2840"],
            include_adult_keywords=include_adult_keywords,
        )
    )

    if isinstance(result, dict) and "error" in result:
        return f"**Error:** {result['error']}"

    return format_keyword_ideas(result)


@mcp.tool()
async def get_keyword_historical_metrics(
    ctx: Context,
    keywords: list[str],
    language_id: str = "1000",
    geo_target_ids: list[str] | None = None,
) -> str:
    """Get detailed historical metrics for specific keywords you already know.

    Args:
        keywords: List of keywords to get metrics for (e.g. ["running shoes", "trail running"])
        language_id: Language constant ID (default "1000" for English)
        geo_target_ids: List of geo target IDs (default ["2840"] for US)
    """
    client: GoogleAdsKeywordClient = ctx.request_context.lifespan_context["client"]

    result = await anyio.to_thread.run_sync(
        lambda: client.get_keyword_historical_metrics(
            keywords=keywords,
            language_id=language_id,
            geo_target_ids=geo_target_ids or ["2840"],
        )
    )

    if isinstance(result, dict) and "error" in result:
        return f"**Error:** {result['error']}"

    return format_historical_metrics(result)


@mcp.tool()
async def generate_keyword_forecast(
    ctx: Context,
    keywords: list[str],
    match_type: str = "BROAD",
    max_cpc_bid: float = 2.0,
    language_id: str = "1000",
    geo_target_ids: list[str] | None = None,
    forecast_days: int = 30,
    negative_keywords: list[str] | None = None,
) -> str:
    """Project campaign performance for a set of keywords over a future period.

    Args:
        keywords: Keywords to forecast (e.g. ["running shoes", "trail running"])
        match_type: Keyword match type: BROAD, PHRASE, or EXACT (default BROAD)
        max_cpc_bid: Maximum CPC bid in dollars (default 2.0)
        language_id: Language constant ID (default "1000" for English)
        geo_target_ids: List of geo target IDs (default ["2840"] for US)
        forecast_days: Number of days to forecast (default 30)
        negative_keywords: Keywords to exclude from forecast
    """
    client: GoogleAdsKeywordClient = ctx.request_context.lifespan_context["client"]

    result = await anyio.to_thread.run_sync(
        lambda: client.generate_keyword_forecast(
            keywords=keywords,
            match_type=match_type,
            max_cpc_bid=max_cpc_bid,
            language_id=language_id,
            geo_target_ids=geo_target_ids or ["2840"],
            forecast_days=forecast_days,
            negative_keywords=negative_keywords,
        )
    )

    if isinstance(result, dict) and "error" in result:
        return f"**Error:** {result['error']}"

    return format_forecast(
        result["campaign_forecast"],
        result["keyword_forecasts"],
        result["keywords"],
        result["forecast_days"],
    )


def main():
    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()

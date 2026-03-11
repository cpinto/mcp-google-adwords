"""FastMCP server with Google Ads planning, campaign management, and reporting tools."""

from __future__ import annotations

import logging
import sys
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

import anyio
from mcp.server.fastmcp import Context, FastMCP

from .client import GoogleAdsMCPClient
from .config import GoogleAdsConfig
from .formatters import (
    format_forecast,
    format_historical_metrics,
    format_keyword_ideas,
    format_performance_report,
    format_search_term_report,
)
from .models import (
    AdMutationResult,
    AdGroupMutationResult,
    AdScheduleEntryInput,
    BiddingStrategyInput,
    CallAssetInput,
    CalloutAssetInput,
    CampaignAssetMutationResult,
    CampaignMutationResult,
    ConversionActionInput,
    ConversionActionMutationResult,
    DeviceBidAdjustmentInput,
    GeoTargetingInput,
    KeywordInput,
    KeywordMutationResult,
    KeywordUpdateInput,
    NetworkSettingsInput,
    ResponsiveSearchAdInput,
    SharedNegativeListMutationResult,
    SitelinkAssetInput,
    StructuredSnippetAssetInput,
    TargetingMutationResult,
)

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
        client = GoogleAdsMCPClient(config)
        logger.info("Google Ads client initialized (customer_id=%s)", config.customer_id)
        yield {"client": client}
    except ValueError as error:
        logger.error("Configuration error: %s", error)
        raise


mcp = FastMCP(
    "Google Ads MCP",
    instructions=(
        "Plan keywords, manage Google Search campaign structure, create responsive search ads "
        "and search assets, configure conversion actions, and pull Google Ads performance reports."
    ),
    lifespan=lifespan,
)


def _client_from_context(ctx: Context) -> GoogleAdsMCPClient:
    return ctx.request_context.lifespan_context["client"]


@mcp.tool()
async def generate_keyword_ideas(
    ctx: Context,
    keywords: list[str] | None = None,
    page_url: str | None = None,
    language_id: str = "1000",
    geo_target_ids: list[str] | None = None,
    include_adult_keywords: bool = False,
) -> str:
    client = _client_from_context(ctx)
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
    client = _client_from_context(ctx)
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
    client = _client_from_context(ctx)
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


@mcp.tool(structured_output=True)
async def create_search_campaign(
    ctx: Context,
    name: str,
    daily_budget: float,
    bidding_strategy: BiddingStrategyInput,
    network_settings: NetworkSettingsInput | None = None,
    status: str = "PAUSED",
    geo_targets: GeoTargetingInput | None = None,
) -> CampaignMutationResult:
    client = _client_from_context(ctx)
    return await anyio.to_thread.run_sync(
        lambda: client.create_search_campaign(
            name=name,
            daily_budget=daily_budget,
            bidding_strategy=bidding_strategy,
            network_settings=network_settings,
            status=status,
            geo_targets=geo_targets,
        )
    )


@mcp.tool(structured_output=True)
async def update_search_campaign(
    ctx: Context,
    campaign: str,
    name: str | None = None,
    daily_budget: float | None = None,
    bidding_strategy: BiddingStrategyInput | None = None,
    network_settings: NetworkSettingsInput | None = None,
    status: str | None = None,
    geo_targets: GeoTargetingInput | None = None,
) -> CampaignMutationResult:
    client = _client_from_context(ctx)
    return await anyio.to_thread.run_sync(
        lambda: client.update_search_campaign(
            campaign=campaign,
            name=name,
            daily_budget=daily_budget,
            bidding_strategy=bidding_strategy,
            network_settings=network_settings,
            status=status,
            geo_targets=geo_targets,
        )
    )


@mcp.tool(structured_output=True)
async def set_campaign_geo_targets(
    ctx: Context,
    campaign: str,
    geo_targets: GeoTargetingInput,
) -> CampaignMutationResult:
    client = _client_from_context(ctx)
    return await anyio.to_thread.run_sync(lambda: client.set_campaign_geo_targets(campaign, geo_targets))


@mcp.tool(structured_output=True)
async def set_campaign_ad_schedule(
    ctx: Context,
    campaign: str,
    entries: list[AdScheduleEntryInput],
) -> TargetingMutationResult:
    client = _client_from_context(ctx)
    return await anyio.to_thread.run_sync(lambda: client.set_campaign_ad_schedule(campaign, entries))


@mcp.tool(structured_output=True)
async def set_campaign_device_bid_adjustments(
    ctx: Context,
    campaign: str,
    adjustments: list[DeviceBidAdjustmentInput],
) -> TargetingMutationResult:
    client = _client_from_context(ctx)
    return await anyio.to_thread.run_sync(
        lambda: client.set_campaign_device_bid_adjustments(campaign, adjustments)
    )


@mcp.tool(structured_output=True)
async def create_ad_group(
    ctx: Context,
    campaign: str,
    name: str,
    default_cpc_bid: float | None = None,
    status: str = "PAUSED",
) -> AdGroupMutationResult:
    client = _client_from_context(ctx)
    return await anyio.to_thread.run_sync(
        lambda: client.create_ad_group(
            campaign=campaign,
            name=name,
            default_cpc_bid=default_cpc_bid,
            status=status,
        )
    )


@mcp.tool(structured_output=True)
async def update_ad_group(
    ctx: Context,
    ad_group: str,
    name: str | None = None,
    default_cpc_bid: float | None = None,
    status: str | None = None,
) -> AdGroupMutationResult:
    client = _client_from_context(ctx)
    return await anyio.to_thread.run_sync(
        lambda: client.update_ad_group(
            ad_group=ad_group,
            name=name,
            default_cpc_bid=default_cpc_bid,
            status=status,
        )
    )


@mcp.tool(structured_output=True)
async def add_keywords_to_ad_group(
    ctx: Context,
    ad_group: str,
    keywords: list[KeywordInput],
    default_match_type: str = "BROAD",
) -> KeywordMutationResult:
    client = _client_from_context(ctx)
    return await anyio.to_thread.run_sync(
        lambda: client.add_keywords_to_ad_group(
            ad_group=ad_group,
            keywords=keywords,
            default_match_type=default_match_type,
        )
    )


@mcp.tool(structured_output=True)
async def update_keywords(
    ctx: Context,
    updates: list[KeywordUpdateInput],
) -> KeywordMutationResult:
    client = _client_from_context(ctx)
    return await anyio.to_thread.run_sync(lambda: client.update_keywords(updates))


@mcp.tool(structured_output=True)
async def remove_keywords(
    ctx: Context,
    keyword_criteria: list[str],
) -> KeywordMutationResult:
    client = _client_from_context(ctx)
    return await anyio.to_thread.run_sync(lambda: client.remove_keywords(keyword_criteria))


@mcp.tool(structured_output=True)
async def create_shared_negative_keyword_list(
    ctx: Context,
    name: str,
) -> SharedNegativeListMutationResult:
    client = _client_from_context(ctx)
    return await anyio.to_thread.run_sync(lambda: client.create_shared_negative_keyword_list(name))


@mcp.tool(structured_output=True)
async def update_shared_negative_keyword_list(
    ctx: Context,
    shared_set: str,
    name: str | None = None,
) -> SharedNegativeListMutationResult:
    client = _client_from_context(ctx)
    return await anyio.to_thread.run_sync(
        lambda: client.update_shared_negative_keyword_list(shared_set=shared_set, name=name)
    )


@mcp.tool(structured_output=True)
async def add_keywords_to_shared_negative_list(
    ctx: Context,
    shared_set: str,
    keywords: list[str],
) -> SharedNegativeListMutationResult:
    client = _client_from_context(ctx)
    return await anyio.to_thread.run_sync(
        lambda: client.add_keywords_to_shared_negative_list(shared_set=shared_set, keywords=keywords)
    )


@mcp.tool(structured_output=True)
async def remove_keywords_from_shared_negative_list(
    ctx: Context,
    shared_criteria: list[str],
) -> SharedNegativeListMutationResult:
    client = _client_from_context(ctx)
    return await anyio.to_thread.run_sync(
        lambda: client.remove_keywords_from_shared_negative_list(shared_criteria)
    )


@mcp.tool(structured_output=True)
async def apply_shared_negative_keyword_list_to_campaigns(
    ctx: Context,
    shared_set: str,
    campaigns: list[str],
) -> SharedNegativeListMutationResult:
    client = _client_from_context(ctx)
    return await anyio.to_thread.run_sync(
        lambda: client.apply_shared_negative_keyword_list_to_campaigns(
            shared_set=shared_set,
            campaigns=campaigns,
        )
    )


@mcp.tool(structured_output=True)
async def remove_shared_negative_keyword_list_from_campaigns(
    ctx: Context,
    shared_set: str,
    campaigns: list[str],
) -> SharedNegativeListMutationResult:
    client = _client_from_context(ctx)
    return await anyio.to_thread.run_sync(
        lambda: client.remove_shared_negative_keyword_list_from_campaigns(
            shared_set=shared_set,
            campaigns=campaigns,
        )
    )


@mcp.tool(structured_output=True)
async def create_responsive_search_ad(
    ctx: Context,
    ad_group: str,
    ad: ResponsiveSearchAdInput,
) -> AdMutationResult:
    client = _client_from_context(ctx)
    return await anyio.to_thread.run_sync(lambda: client.create_responsive_search_ad(ad_group, ad))


@mcp.tool(structured_output=True)
async def update_responsive_search_ad(
    ctx: Context,
    ad_group_ad: str,
    ad: ResponsiveSearchAdInput | None = None,
    status: str | None = None,
) -> AdMutationResult:
    client = _client_from_context(ctx)
    return await anyio.to_thread.run_sync(
        lambda: client.update_responsive_search_ad(ad_group_ad=ad_group_ad, ad=ad, status=status)
    )


@mcp.tool(structured_output=True)
async def create_campaign_sitelink_asset(
    ctx: Context,
    campaign: str,
    sitelink: SitelinkAssetInput,
) -> CampaignAssetMutationResult:
    client = _client_from_context(ctx)
    return await anyio.to_thread.run_sync(lambda: client.create_campaign_sitelink_asset(campaign, sitelink))


@mcp.tool(structured_output=True)
async def create_campaign_callout_asset(
    ctx: Context,
    campaign: str,
    callout: CalloutAssetInput,
) -> CampaignAssetMutationResult:
    client = _client_from_context(ctx)
    return await anyio.to_thread.run_sync(lambda: client.create_campaign_callout_asset(campaign, callout))


@mcp.tool(structured_output=True)
async def create_campaign_structured_snippet_asset(
    ctx: Context,
    campaign: str,
    snippet: StructuredSnippetAssetInput,
) -> CampaignAssetMutationResult:
    client = _client_from_context(ctx)
    return await anyio.to_thread.run_sync(
        lambda: client.create_campaign_structured_snippet_asset(campaign, snippet)
    )


@mcp.tool(structured_output=True)
async def create_campaign_call_asset(
    ctx: Context,
    campaign: str,
    call_asset: CallAssetInput,
) -> CampaignAssetMutationResult:
    client = _client_from_context(ctx)
    return await anyio.to_thread.run_sync(lambda: client.create_campaign_call_asset(campaign, call_asset))


@mcp.tool(structured_output=True)
async def create_conversion_action(
    ctx: Context,
    conversion: ConversionActionInput,
) -> ConversionActionMutationResult:
    client = _client_from_context(ctx)
    return await anyio.to_thread.run_sync(lambda: client.create_conversion_action(conversion))


@mcp.tool(structured_output=True)
async def update_conversion_action(
    ctx: Context,
    conversion_action: str,
    conversion: ConversionActionInput,
) -> ConversionActionMutationResult:
    client = _client_from_context(ctx)
    return await anyio.to_thread.run_sync(
        lambda: client.update_conversion_action(conversion_action, conversion)
    )


@mcp.tool()
async def get_search_term_report(
    ctx: Context,
    campaign: str | None = None,
    start_date: str | None = None,
    end_date: str | None = None,
    limit: int = 50,
) -> str:
    client = _client_from_context(ctx)
    rows = await anyio.to_thread.run_sync(
        lambda: client.get_search_term_report(
            campaign=campaign,
            start_date=start_date,
            end_date=end_date,
            limit=limit,
        )
    )
    return format_search_term_report(rows)


@mcp.tool()
async def get_performance_report(
    ctx: Context,
    level: str,
    campaign: str | None = None,
    ad_group: str | None = None,
    start_date: str | None = None,
    end_date: str | None = None,
    limit: int = 100,
) -> str:
    client = _client_from_context(ctx)
    rows = await anyio.to_thread.run_sync(
        lambda: client.get_performance_report(
            level=level,
            campaign=campaign,
            ad_group=ad_group,
            start_date=start_date,
            end_date=end_date,
            limit=limit,
        )
    )
    return format_performance_report(rows, level)


def main():
    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()

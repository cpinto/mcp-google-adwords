"""FastMCP server with Google Ads planning, campaign management, and reporting tools."""

from __future__ import annotations

import json
import logging
import os
import sys
import urllib.error
import urllib.parse
import urllib.request
import webbrowser
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from http.server import BaseHTTPRequestHandler, HTTPServer

import anyio
from dotenv import find_dotenv, set_key
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
    AccountNegativeKeywordListResult,
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
    NegativeKeywordInput,
    NegativeKeywordListResult,
    NegativeKeywordMutationResult,
    NegativeKeywordUpdateInput,
    NetworkSettingsInput,
    ResponsiveSearchAdInput,
    SharedNegativeListMutationResult,
    SharedNegativeKeywordListsResult,
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

AUTH_REQUIRED_MSG = (
    "**Authorization required.** No Google Ads OAuth refresh token is configured.\n\n"
    "Call the `authorize` tool to complete the browser-based OAuth flow."
)
AUTH_EXPIRED_MSG = (
    "**Authentication expired.** Your Google Ads OAuth refresh token is invalid or revoked.\n\n"
    "Call the `authorize` tool to re-authenticate."
)
_TOKEN_URL = "https://oauth2.googleapis.com/token"
_GOOGLE_AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
_OAUTH_SCOPES = ["https://www.googleapis.com/auth/adwords"]


@asynccontextmanager
async def lifespan(server: FastMCP) -> AsyncIterator[dict]:
    """Load config at startup; the Google Ads client is created lazily on first tool call."""
    logger.info("Initializing Google Ads MCP server...")
    try:
        config = GoogleAdsConfig.from_env()
        env_path = find_dotenv() or os.path.join(os.getcwd(), ".env")
        logger.info("Config loaded (customer_id=%s)", config.customer_id)
        yield {"config": config, "client": None, "env_path": env_path}
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


def _is_auth_error(exc: Exception) -> bool:
    """Check if an exception is an OAuth authentication error."""
    error_str = str(exc).lower()
    type_name = type(exc).__name__.lower()
    return (
        "invalid_grant" in error_str
        or "token has been expired or revoked" in error_str
        or "refresherror" in type_name
    )


def _client_from_context(ctx: Context) -> GoogleAdsMCPClient:
    """Get or lazily create the Google Ads client. Raises RuntimeError if auth is expired."""
    lifespan_ctx = ctx.request_context.lifespan_context
    client = lifespan_ctx.get("client")
    if client is not None:
        return client

    config = lifespan_ctx["config"]
    if config.auth_type == "oauth" and not config.has_refresh_token:
        raise RuntimeError(AUTH_REQUIRED_MSG)

    new_client = GoogleAdsMCPClient(config)

    # Verify credentials with a lightweight API call
    try:
        svc = new_client.client.get_service("CustomerService")
        svc.list_accessible_customers()
    except Exception as exc:
        if _is_auth_error(exc):
            raise RuntimeError(AUTH_EXPIRED_MSG) from exc
        raise

    lifespan_ctx["client"] = new_client
    logger.info("Google Ads client initialized (customer_id=%s)", config.customer_id)
    return new_client


def _service_account_auth_message() -> str:
    return (
        "**Not needed.** This server is using service account authentication, "
        "which does not require browser-based OAuth. If you are seeing auth errors, "
        "check that the service account has the correct permissions."
    )


def _persist_refresh_token(lifespan_ctx: dict, refresh_token: str) -> None:
    env_path = lifespan_ctx["env_path"]
    set_key(env_path, "GOOGLE_ADS_REFRESH_TOKEN", refresh_token)
    logger.info("Refresh token updated in %s", env_path)

    config = lifespan_ctx["config"]
    config.refresh_token = refresh_token
    lifespan_ctx["client"] = None


def _run_oauth_flow(client_id: str, client_secret: str) -> dict:
    """Run the Google OAuth flow. Starts a local server on a random port, opens browser."""
    auth_code = None

    class CallbackHandler(BaseHTTPRequestHandler):
        def do_GET(self):
            nonlocal auth_code
            query = urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query)
            if "error" in query:
                self.send_response(400)
                self.send_header("Content-Type", "text/html")
                self.end_headers()
                self.wfile.write(b"<h1>Authorization failed.</h1><p>You can close this tab.</p>")
                return
            if "code" in query:
                auth_code = query["code"][0]
                self.send_response(200)
                self.send_header("Content-Type", "text/html")
                self.end_headers()
                self.wfile.write(
                    b"<h1>Authorization successful!</h1><p>You can close this tab.</p>"
                )

        def log_message(self, format, *args):
            pass

    server = HTTPServer(("127.0.0.1", 0), CallbackHandler)
    port = server.server_address[1]
    redirect_uri = f"http://127.0.0.1:{port}/callback"

    params = {
        "client_id": client_id,
        "redirect_uri": redirect_uri,
        "scope": " ".join(_OAUTH_SCOPES),
        "response_type": "code",
        "access_type": "offline",
        "prompt": "consent",
    }
    auth_url = f"{_GOOGLE_AUTH_URL}?{urllib.parse.urlencode(params)}"

    logger.info("Opening browser for OAuth (port %d)", port)
    logger.info("Auth URL: %s", auth_url)
    webbrowser.open(auth_url)

    server.timeout = 120
    server.handle_request()
    server.server_close()

    if not auth_code:
        return {"error": "No authorization code received (timed out or user denied access)."}

    # Exchange code for tokens
    data = urllib.parse.urlencode({
        "code": auth_code,
        "client_id": client_id,
        "client_secret": client_secret,
        "redirect_uri": redirect_uri,
        "grant_type": "authorization_code",
    }).encode()
    req = urllib.request.Request(_TOKEN_URL, data=data)
    try:
        with urllib.request.urlopen(req) as resp:
            tokens = json.loads(resp.read())
    except urllib.error.HTTPError as exc:
        return {"error": f"Token exchange failed: {exc.read().decode()}"}

    refresh_token = tokens.get("refresh_token")
    if not refresh_token:
        return {"error": f"No refresh token in response: {json.dumps(tokens)}"}

    return {"refresh_token": refresh_token}


@mcp.tool()
async def check_auth_status(ctx: Context) -> str:
    """Check whether the current Google Ads credentials are valid."""
    config = ctx.request_context.lifespan_context["config"]
    auth_type = config.auth_type
    if auth_type == "oauth" and not config.has_refresh_token:
        return AUTH_REQUIRED_MSG
    try:
        _client_from_context(ctx)
        return f"**Authenticated** (via {auth_type}). Google Ads credentials are valid."
    except RuntimeError as exc:
        return str(exc)


@mcp.tool()
async def authorize(ctx: Context) -> str:
    """Complete the browser-based OAuth flow and save a Google Ads refresh token.

    Use this for first-time OAuth setup or when an existing refresh token has
    expired or been revoked. A browser window will open for you to authorize
    access. The token is saved automatically so subsequent tool calls and server
    restarts will use it.
    """
    lifespan_ctx = ctx.request_context.lifespan_context
    config = lifespan_ctx["config"]

    if config.auth_type == "service_account":
        return _service_account_auth_message()

    result = await anyio.to_thread.run_sync(
        lambda: _run_oauth_flow(config.client_id, config.client_secret)
    )

    if "error" in result:
        return f"**Authorization failed:** {result['error']}"

    _persist_refresh_token(lifespan_ctx, result["refresh_token"])

    return "**Authorization successful!** The refresh token has been saved.\n\nYou can now use Google Ads tools."


@mcp.tool()
async def reauthorize(ctx: Context) -> str:
    """Compatibility alias for `authorize` when an OAuth token has expired."""
    config = ctx.request_context.lifespan_context["config"]
    if config.auth_type == "service_account":
        return _service_account_auth_message()

    result = await anyio.to_thread.run_sync(
        lambda: _run_oauth_flow(config.client_id, config.client_secret)
    )

    if "error" in result:
        return f"**Reauthorization failed:** {result['error']}"

    _persist_refresh_token(ctx.request_context.lifespan_context, result["refresh_token"])

    return "**Reauthorization successful!** The refresh token has been saved.\n\nYou can now use Google Ads tools."


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
async def list_negative_keywords_in_campaign(
    ctx: Context,
    campaign: str,
) -> NegativeKeywordListResult:
    client = _client_from_context(ctx)
    return await anyio.to_thread.run_sync(lambda: client.list_negative_keywords_in_campaign(campaign))


@mcp.tool(structured_output=True)
async def add_negative_keywords_to_campaign(
    ctx: Context,
    campaign: str,
    keywords: list[NegativeKeywordInput],
    default_match_type: str = "BROAD",
) -> NegativeKeywordMutationResult:
    client = _client_from_context(ctx)
    return await anyio.to_thread.run_sync(
        lambda: client.add_negative_keywords_to_campaign(
            campaign=campaign,
            keywords=keywords,
            default_match_type=default_match_type,
        )
    )


@mcp.tool(structured_output=True)
async def update_negative_keywords_in_campaign(
    ctx: Context,
    updates: list[NegativeKeywordUpdateInput],
) -> NegativeKeywordMutationResult:
    client = _client_from_context(ctx)
    return await anyio.to_thread.run_sync(lambda: client.update_negative_keywords_in_campaign(updates))


@mcp.tool(structured_output=True)
async def remove_negative_keywords_from_campaign(
    ctx: Context,
    negative_keyword_criteria: list[str],
) -> NegativeKeywordMutationResult:
    client = _client_from_context(ctx)
    return await anyio.to_thread.run_sync(
        lambda: client.remove_negative_keywords_from_campaign(negative_keyword_criteria)
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
async def list_negative_keywords_in_ad_group(
    ctx: Context,
    ad_group: str,
) -> NegativeKeywordListResult:
    client = _client_from_context(ctx)
    return await anyio.to_thread.run_sync(lambda: client.list_negative_keywords_in_ad_group(ad_group))


@mcp.tool(structured_output=True)
async def add_negative_keywords_to_ad_group(
    ctx: Context,
    ad_group: str,
    keywords: list[NegativeKeywordInput],
    default_match_type: str = "BROAD",
) -> NegativeKeywordMutationResult:
    client = _client_from_context(ctx)
    return await anyio.to_thread.run_sync(
        lambda: client.add_negative_keywords_to_ad_group(
            ad_group=ad_group,
            keywords=keywords,
            default_match_type=default_match_type,
        )
    )


@mcp.tool(structured_output=True)
async def update_negative_keywords_in_ad_group(
    ctx: Context,
    updates: list[NegativeKeywordUpdateInput],
) -> NegativeKeywordMutationResult:
    client = _client_from_context(ctx)
    return await anyio.to_thread.run_sync(lambda: client.update_negative_keywords_in_ad_group(updates))


@mcp.tool(structured_output=True)
async def remove_negative_keywords_from_ad_group(
    ctx: Context,
    negative_keyword_criteria: list[str],
) -> NegativeKeywordMutationResult:
    client = _client_from_context(ctx)
    return await anyio.to_thread.run_sync(
        lambda: client.remove_negative_keywords_from_ad_group(negative_keyword_criteria)
    )


@mcp.tool(structured_output=True)
async def create_shared_negative_keyword_list(
    ctx: Context,
    name: str,
    scope: str = "CAMPAIGN",
) -> SharedNegativeListMutationResult:
    client = _client_from_context(ctx)
    return await anyio.to_thread.run_sync(
        lambda: client.create_shared_negative_keyword_list(name, scope=scope)
    )


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
async def list_shared_negative_keyword_lists(
    ctx: Context,
) -> SharedNegativeKeywordListsResult:
    client = _client_from_context(ctx)
    return await anyio.to_thread.run_sync(client.list_shared_negative_keyword_lists)


@mcp.tool(structured_output=True)
async def list_keywords_in_shared_negative_list(
    ctx: Context,
    shared_set: str,
) -> NegativeKeywordListResult:
    client = _client_from_context(ctx)
    return await anyio.to_thread.run_sync(lambda: client.list_keywords_in_shared_negative_list(shared_set))


@mcp.tool(structured_output=True)
async def add_keywords_to_shared_negative_list(
    ctx: Context,
    shared_set: str,
    keywords: list[str],
    default_match_type: str = "BROAD",
) -> SharedNegativeListMutationResult:
    client = _client_from_context(ctx)
    return await anyio.to_thread.run_sync(
        lambda: client.add_keywords_to_shared_negative_list(
            shared_set=shared_set,
            keywords=keywords,
            default_match_type=default_match_type,
        )
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
async def get_account_negative_keyword_list(
    ctx: Context,
) -> AccountNegativeKeywordListResult:
    client = _client_from_context(ctx)
    return await anyio.to_thread.run_sync(client.get_account_negative_keyword_list)


@mcp.tool(structured_output=True)
async def apply_shared_negative_keyword_list_to_account(
    ctx: Context,
    shared_set: str,
    replace_existing: bool = False,
) -> AccountNegativeKeywordListResult:
    client = _client_from_context(ctx)
    return await anyio.to_thread.run_sync(
        lambda: client.apply_shared_negative_keyword_list_to_account(
            shared_set=shared_set,
            replace_existing=replace_existing,
        )
    )


@mcp.tool(structured_output=True)
async def remove_shared_negative_keyword_list_from_account(
    ctx: Context,
) -> AccountNegativeKeywordListResult:
    client = _client_from_context(ctx)
    return await anyio.to_thread.run_sync(client.remove_shared_negative_keyword_list_from_account)


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

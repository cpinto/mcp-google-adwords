# Google Ads MCP Server — Full Project Context

> This document captures the full project context so another coding agent can pick up development without prior knowledge.

## Overview

This is a **Model Context Protocol (MCP) server** that exposes Google Ads Keyword Planner functionality as MCP tools. It allows LLM agents (e.g. Claude) to discover keywords, pull historical metrics, and forecast campaign performance via the Google Ads API.

- **Name:** `google-ads-mcp`
- **Version:** `0.1.0`
- **Python:** `>=3.11` (venv uses Python 3.14)
- **Transport:** stdio (run as a subprocess by the MCP host)
- **Package manager:** `uv` (lockfile: `uv.lock`)
- **Build system:** Hatchling

## Project Structure

```
google-ads/
├── .env                        # Credentials (gitignored, see .env.example)
├── .env.example                # Template for required env vars
├── .gitignore
├── .venv/                      # Python virtual environment (Python 3.14)
├── get_refresh_token.py        # OAuth2 helper to obtain a refresh token
├── pyproject.toml              # Project metadata and dependencies
├── uv.lock                     # Locked dependency versions
└── src/
    └── google_ads_mcp/
        ├── __init__.py         # Empty
        ├── config.py           # Env var loading & GoogleAdsConfig dataclass
        ├── client.py           # Google Ads API wrapper (keyword planning)
        ├── formatters.py       # Convert API responses to markdown tables
        └── server.py           # FastMCP server definition & tool registration
```

**No git repo is initialized.** No tests exist. No CI/CD.

## Dependencies (`pyproject.toml`)

```toml
[project]
dependencies = [
    "mcp[cli]>=1.2.0",
    "google-ads>=25.0.0",
    "python-dotenv>=1.0.0",
]
```

- `mcp[cli]` — the MCP SDK with FastMCP framework
- `google-ads` — official Google Ads API client library
- `python-dotenv` — loads `.env` file into environment

## Environment Variables

Defined in `.env` (see `.env.example` for the template):

| Variable | Required | Notes |
|----------|----------|-------|
| `GOOGLE_ADS_DEVELOPER_TOKEN` | Yes | From Google Ads API Center |
| `GOOGLE_ADS_CLIENT_ID` | Yes | OAuth2 Client ID (Desktop app) |
| `GOOGLE_ADS_CLIENT_SECRET` | Yes | OAuth2 Client Secret |
| `GOOGLE_ADS_REFRESH_TOKEN` | Yes | Obtained via `get_refresh_token.py` |
| `GOOGLE_ADS_CUSTOMER_ID` | Yes | Google Ads account ID (dashes stripped) |
| `GOOGLE_ADS_LOGIN_CUSTOMER_ID` | No | For MCC/manager accounts |

## How to Run

```bash
# Install deps
uv sync

# Run the MCP server (stdio transport)
uv run google-ads-mcp

# Or directly:
uv run python -m google_ads_mcp.server
```

The entry point is defined in `pyproject.toml`:
```toml
[project.scripts]
google-ads-mcp = "google_ads_mcp.server:main"
```

## Architecture Details

### `config.py` — Configuration

- `GoogleAdsConfig` dataclass holds all credentials
- `GoogleAdsConfig.from_env()` loads and validates env vars; raises `ValueError` if any required var is missing
- `to_client_dict()` returns the dict format the `google-ads` library expects
- Dashes are auto-stripped from customer IDs

### `client.py` — Google Ads API Wrapper

- Uses Google Ads API **v23** (`API_VERSION = "v23"`)
- Class `GoogleAdsKeywordClient` wraps three operations:

#### 1. `generate_keyword_ideas()`
- Accepts seed `keywords` and/or `page_url`
- Supports language targeting (default: `"1000"` = English)
- Supports geo targeting (default: `["2840"]` = US)
- Uses `KeywordPlanIdeaService.GenerateKeywordIdeas`
- Returns raw proto-plus objects (list) or error dict

#### 2. `get_keyword_historical_metrics()`
- Takes a list of specific keywords
- Returns historical search volume, competition, CPCs
- Uses `KeywordPlanIdeaService.GenerateKeywordHistoricalMetrics`

#### 3. `generate_keyword_forecast()`
- Projects clicks, impressions, CPC, CTR, cost over a future period
- Configurable: match type (BROAD/PHRASE/EXACT), max CPC bid, forecast days, negative keywords
- Builds a virtual campaign with ad groups for forecasting
- Uses `KeywordPlanIdeaService.GenerateKeywordForecastMetrics`

All methods catch `GoogleAdsException` and return a structured error dict.

### `server.py` — MCP Server

- Built with **FastMCP** from the `mcp` SDK
- Server name: `"Google Ads Keyword Planner"`
- Uses a **lifespan** context manager to initialize the Google Ads client once at startup and share it via `ctx.request_context.lifespan_context["client"]`
- All three tools use `anyio.to_thread.run_sync()` to run the synchronous Google Ads client calls without blocking the async event loop
- Logging goes to **stderr** (stdout reserved for MCP stdio transport)
- Entry point: `main()` calls `mcp.run(transport="stdio")`

#### Registered MCP Tools

| Tool Name | Description | Key Parameters |
|-----------|-------------|----------------|
| `generate_keyword_ideas` | Discover new keyword ideas from seed terms/URL | `keywords`, `page_url`, `language_id`, `geo_target_ids`, `include_adult_keywords` |
| `get_keyword_historical_metrics` | Get historical metrics for known keywords | `keywords`, `language_id`, `geo_target_ids` |
| `generate_keyword_forecast` | Project campaign performance | `keywords`, `match_type`, `max_cpc_bid`, `language_id`, `geo_target_ids`, `forecast_days`, `negative_keywords` |

### `formatters.py` — Response Formatting

- Converts raw Google Ads API proto objects into **LLM-friendly markdown tables**
- `format_keyword_ideas()` — sorts by avg monthly searches descending, caps at 50 results
- `format_historical_metrics()` — includes close variants if present
- `format_forecast()` — campaign summary + per-keyword breakdown table
- Helper: `micros_to_dollars()` converts micros (Google Ads currency unit) to `$X.XX`
- Competition enum mapped: `{0: "Unspecified", 1: "Unknown", 2: "Low", 3: "Medium", 4: "High"}`

### `get_refresh_token.py` — OAuth2 Helper (standalone)

- Interactive script to obtain a Google Ads refresh token
- Starts a local HTTP server on `localhost:8080` to catch the OAuth callback
- Run with: `uv run python get_refresh_token.py`
- Requires `requests` (not in pyproject.toml deps — may need manual install or addition)

## Common Geo Target IDs

Used as defaults and referenced in tool docstrings:

| Country | ID |
|---------|----|
| US | 2840 |
| UK | 2826 |
| Canada | 2124 |
| Australia | 2036 |

## Key Design Decisions

1. **Sync client in async server:** The `google-ads` library is synchronous, so all API calls are wrapped in `anyio.to_thread.run_sync()` to avoid blocking.
2. **Lifespan pattern:** Client is created once at server startup, not per-request.
3. **Markdown output:** All tool responses are pre-formatted as markdown tables for direct LLM consumption.
4. **Error handling:** Google Ads exceptions are caught and returned as structured dicts with `error` and `details` keys, then formatted as markdown error messages at the tool level.
5. **proto-plus mode:** `use_proto_plus: True` is set in the client config, meaning API responses are proto-plus objects (Python-native attribute access).

## What's Missing / Potential Improvements

- No tests
- No git repo initialized
- No README.md
- `get_refresh_token.py` depends on `requests` which isn't in `pyproject.toml`
- No rate limiting or retry logic
- No pagination support (keyword ideas capped at 50 in formatter, but the API may return more)
- Only covers Keyword Planner — no campaign management, reporting, or other Google Ads services
- No input validation beyond "at least one of keywords/page_url"

## Full Source Files

### `src/google_ads_mcp/config.py`

```python
"""Environment variable loading and validation for Google Ads credentials."""

from __future__ import annotations

import os
from dataclasses import dataclass

from dotenv import load_dotenv


REQUIRED_VARS = [
    "GOOGLE_ADS_DEVELOPER_TOKEN",
    "GOOGLE_ADS_CLIENT_ID",
    "GOOGLE_ADS_CLIENT_SECRET",
    "GOOGLE_ADS_REFRESH_TOKEN",
    "GOOGLE_ADS_CUSTOMER_ID",
]


@dataclass
class GoogleAdsConfig:
    developer_token: str
    client_id: str
    client_secret: str
    refresh_token: str
    customer_id: str
    login_customer_id: str | None = None

    @classmethod
    def from_env(cls) -> GoogleAdsConfig:
        load_dotenv()

        missing = [v for v in REQUIRED_VARS if not os.getenv(v)]
        if missing:
            raise ValueError(
                f"Missing required environment variables: {', '.join(missing)}. "
                "See .env.example for the full list."
            )

        return cls(
            developer_token=os.environ["GOOGLE_ADS_DEVELOPER_TOKEN"],
            client_id=os.environ["GOOGLE_ADS_CLIENT_ID"],
            client_secret=os.environ["GOOGLE_ADS_CLIENT_SECRET"],
            refresh_token=os.environ["GOOGLE_ADS_REFRESH_TOKEN"],
            customer_id=os.environ["GOOGLE_ADS_CUSTOMER_ID"].replace("-", ""),
            login_customer_id=(
                os.environ.get("GOOGLE_ADS_LOGIN_CUSTOMER_ID", "").replace("-", "")
                or None
            ),
        )

    def to_client_dict(self) -> dict:
        d = {
            "developer_token": self.developer_token,
            "client_id": self.client_id,
            "client_secret": self.client_secret,
            "refresh_token": self.refresh_token,
            "use_proto_plus": True,
        }
        if self.login_customer_id:
            d["login_customer_id"] = self.login_customer_id
        return d
```

### `src/google_ads_mcp/client.py`

```python
"""Google Ads API wrapper for keyword planning operations."""

from __future__ import annotations

import logging
from datetime import datetime, timedelta

from google.ads.googleads.client import GoogleAdsClient
from google.ads.googleads.errors import GoogleAdsException

from .config import GoogleAdsConfig

logger = logging.getLogger(__name__)

API_VERSION = "v23"


class GoogleAdsKeywordClient:
    def __init__(self, config: GoogleAdsConfig):
        self.config = config
        self.client = GoogleAdsClient.load_from_dict(config.to_client_dict(), version=API_VERSION)
        self.customer_id = config.customer_id

    def _geo_resource(self, geo_id: str) -> str:
        return f"geoTargetConstants/{geo_id}"

    def _language_resource(self, lang_id: str) -> str:
        return f"languageConstants/{lang_id}"

    def generate_keyword_ideas(
        self,
        keywords: list[str] | None = None,
        page_url: str | None = None,
        language_id: str = "1000",
        geo_target_ids: list[str] | None = None,
        include_adult_keywords: bool = False,
    ) -> list | dict:
        if not keywords and not page_url:
            return {"error": "Provide at least one of 'keywords' or 'page_url'."}

        if geo_target_ids is None:
            geo_target_ids = ["2840"]

        try:
            service = self.client.get_service("KeywordPlanIdeaService")

            request = self.client.get_type("GenerateKeywordIdeasRequest")
            request.customer_id = self.customer_id
            request.language = self._language_resource(language_id)
            request.geo_target_constants = [self._geo_resource(g) for g in geo_target_ids]
            request.include_adult_keywords = include_adult_keywords
            request.keyword_plan_network = self.client.enums.KeywordPlanNetworkEnum.GOOGLE_SEARCH

            if keywords and page_url:
                request.keyword_and_url_seed.url = page_url
                request.keyword_and_url_seed.keywords.extend(keywords)
            elif keywords:
                request.keyword_seed.keywords.extend(keywords)
            elif page_url:
                request.url_seed.url = page_url

            response = service.generate_keyword_ideas(request=request)
            return list(response)

        except GoogleAdsException as ex:
            return _format_google_ads_error(ex)

    def get_keyword_historical_metrics(
        self,
        keywords: list[str],
        language_id: str = "1000",
        geo_target_ids: list[str] | None = None,
    ) -> list | dict:
        if geo_target_ids is None:
            geo_target_ids = ["2840"]

        try:
            service = self.client.get_service("KeywordPlanIdeaService")

            request = self.client.get_type("GenerateKeywordHistoricalMetricsRequest")
            request.customer_id = self.customer_id
            request.keywords.extend(keywords)
            request.language = self._language_resource(language_id)
            request.geo_target_constants = [self._geo_resource(g) for g in geo_target_ids]
            request.keyword_plan_network = self.client.enums.KeywordPlanNetworkEnum.GOOGLE_SEARCH

            response = service.generate_keyword_historical_metrics(request=request)
            return list(response.results)

        except GoogleAdsException as ex:
            return _format_google_ads_error(ex)

    def generate_keyword_forecast(
        self,
        keywords: list[str],
        match_type: str = "BROAD",
        max_cpc_bid: float = 2.0,
        language_id: str = "1000",
        geo_target_ids: list[str] | None = None,
        forecast_days: int = 30,
        negative_keywords: list[str] | None = None,
    ) -> dict:
        if geo_target_ids is None:
            geo_target_ids = ["2840"]

        try:
            service = self.client.get_service("KeywordPlanIdeaService")

            request = self.client.get_type("GenerateKeywordForecastMetricsRequest")
            request.customer_id = self.customer_id

            # Forecast period
            today = datetime.today()
            start = today + timedelta(days=1)
            end = start + timedelta(days=forecast_days)
            request.forecast_period.start_date = start.strftime("%Y-%m-%d")
            request.forecast_period.end_date = end.strftime("%Y-%m-%d")

            # Campaign to forecast
            campaign = request.campaign

            # Geo and language targeting
            for geo_id in geo_target_ids:
                criterion = campaign.geo_modifiers.add()
                criterion.geo_target_constant = self._geo_resource(geo_id)
            campaign.language_constants.append(self._language_resource(language_id))

            # Bidding strategy
            campaign.manual_cpc_bidding_strategy.max_cpc_bid_micros = int(max_cpc_bid * 1_000_000)

            # Keyword plan network
            campaign.keyword_plan_network = self.client.enums.KeywordPlanNetworkEnum.GOOGLE_SEARCH

            # Match type enum
            match_type_enum = self.client.enums.KeywordMatchTypeEnum.KeywordMatchType
            match_type_value = getattr(match_type_enum, match_type.upper(), match_type_enum.BROAD)

            # Add keywords
            for kw in keywords:
                ad_group_kw = campaign.ad_groups.add()
                biddable = ad_group_kw.biddable_keywords.add()
                biddable.keyword.text = kw
                biddable.keyword.match_type = match_type_value
                biddable.max_cpc_bid_micros = int(max_cpc_bid * 1_000_000)

            # Add negative keywords
            if negative_keywords:
                for nkw in negative_keywords:
                    neg = campaign.negative_keywords.add()
                    neg.keyword.text = nkw
                    neg.keyword.match_type = match_type_enum.BROAD

            response = service.generate_keyword_forecast_metrics(request=request)

            return {
                "campaign_forecast": response.campaign_forecast_metrics,
                "keyword_forecasts": list(response.keyword_forecasts),
                "keywords": keywords,
                "forecast_days": forecast_days,
            }

        except GoogleAdsException as ex:
            return _format_google_ads_error(ex)


def _format_google_ads_error(ex: GoogleAdsException) -> dict:
    errors = []
    for error in ex.failure.errors:
        errors.append({
            "message": error.message,
            "error_code": str(error.error_code),
        })
    logger.error("Google Ads API error: %s", errors)
    return {"error": f"Google Ads API error: {errors[0]['message']}", "details": errors}
```

### `src/google_ads_mcp/server.py`

```python
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
```

### `src/google_ads_mcp/formatters.py`

```python
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
```

### `get_refresh_token.py`

```python
"""OAuth2 helper to obtain a Google Ads API refresh token.

Prerequisites:
  1. Go to https://console.cloud.google.com/apis/library/googleads.googleapis.com
     and enable the Google Ads API for your project.
  2. Go to https://console.cloud.google.com/apis/credentials
     and create an OAuth 2.0 Client ID (type: Desktop app).
  3. Copy the Client ID and Client Secret.

Usage:
  uv run python get_refresh_token.py
"""

import json
import sys
import webbrowser
from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.parse import parse_qs, urlencode, urlparse

import requests

SCOPES = ["https://www.googleapis.com/auth/adwords"]
REDIRECT_URI = "http://localhost:8080/callback"
TOKEN_URL = "https://oauth2.googleapis.com/token"
AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"


def main():
    print("\n=== Google Ads OAuth2 Refresh Token Helper ===\n")

    client_id = input("Client ID: ").strip()
    if not client_id:
        print("Error: Client ID is required.")
        sys.exit(1)

    client_secret = input("Client Secret: ").strip()
    if not client_secret:
        print("Error: Client Secret is required.")
        sys.exit(1)

    # Build authorization URL
    params = {
        "client_id": client_id,
        "redirect_uri": REDIRECT_URI,
        "scope": " ".join(SCOPES),
        "response_type": "code",
        "access_type": "offline",
        "prompt": "consent",
    }
    auth_url = f"{AUTH_URL}?{urlencode(params)}"

    print(f"\nOpening browser for authorization...\n")
    print(f"If it doesn't open, visit this URL:\n{auth_url}\n")
    webbrowser.open(auth_url)

    # Start local server to catch the callback
    auth_code = None

    class CallbackHandler(BaseHTTPRequestHandler):
        def do_GET(self):
            nonlocal auth_code
            query = parse_qs(urlparse(self.path).query)

            if "error" in query:
                self.send_response(400)
                self.send_header("Content-Type", "text/html")
                self.end_headers()
                self.wfile.write(b"<h1>Authorization failed.</h1><p>You can close this tab.</p>")
                print(f"\nError: {query['error'][0]}")
                return

            if "code" in query:
                auth_code = query["code"][0]
                self.send_response(200)
                self.send_header("Content-Type", "text/html")
                self.end_headers()
                self.wfile.write(b"<h1>Authorization successful!</h1><p>You can close this tab and return to your terminal.</p>")

        def log_message(self, format, *args):
            pass  # Suppress request logging

    server = HTTPServer(("localhost", 8080), CallbackHandler)
    print("Waiting for authorization callback on http://localhost:8080 ...")
    server.handle_request()

    if not auth_code:
        print("Error: No authorization code received.")
        sys.exit(1)

    # Exchange code for tokens
    print("\nExchanging authorization code for tokens...")
    resp = requests.post(TOKEN_URL, data={
        "code": auth_code,
        "client_id": client_id,
        "client_secret": client_secret,
        "redirect_uri": REDIRECT_URI,
        "grant_type": "authorization_code",
    })

    if resp.status_code != 200:
        print(f"Error: Token exchange failed.\n{resp.text}")
        sys.exit(1)

    tokens = resp.json()
    refresh_token = tokens.get("refresh_token")

    if not refresh_token:
        print(f"Error: No refresh token in response.\n{json.dumps(tokens, indent=2)}")
        sys.exit(1)

    print("\n" + "=" * 50)
    print("SUCCESS! Here's your refresh token:\n")
    print(f"  {refresh_token}")
    print(f"\nAdd it to your .env file:")
    print(f"  GOOGLE_ADS_REFRESH_TOKEN={refresh_token}")
    print("=" * 50 + "\n")


if __name__ == "__main__":
    main()
```

### `.env.example`

```
GOOGLE_ADS_DEVELOPER_TOKEN=
GOOGLE_ADS_CLIENT_ID=
GOOGLE_ADS_CLIENT_SECRET=
GOOGLE_ADS_REFRESH_TOKEN=
GOOGLE_ADS_CUSTOMER_ID=
# Optional: for manager/MCC accounts
# GOOGLE_ADS_LOGIN_CUSTOMER_ID=
```

### `pyproject.toml`

```toml
[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[project]
name = "google-ads-mcp"
version = "0.1.0"
description = "MCP server for Google Ads Keyword Planning"
requires-python = ">=3.11"
dependencies = [
    "mcp[cli]>=1.2.0",
    "google-ads>=25.0.0",
    "python-dotenv>=1.0.0",
]

[project.scripts]
google-ads-mcp = "google_ads_mcp.server:main"
```

### `.gitignore`

```
__pycache__/
*.py[cod]
*$py.class
*.egg-info/
dist/
build/
.env
.venv/
*.egg
.python-version
uv.lock
```

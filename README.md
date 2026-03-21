# Google Ads MCP

MCP server for Google Ads keyword planning, Search campaign management, reporting, and basic optimization workflows.

This server runs over stdio and is intended to be launched by an MCP client such as Claude Cowork or any other client that supports local stdio MCP servers.

## What It Does

- Keyword discovery and historical metrics
- Forecasting for keyword sets
- Search campaign creation and updates
- Ad group and keyword management
- Negative keyword management at the campaign, ad group, shared-list, and account levels
- Responsive search ad creation and replacement-style updates
- Search term and performance reporting

Mutation tools return structured results. Reporting tools return markdown tables.

## Requirements

- Python `>=3.11`
- `uv`
- A Google Ads API-enabled Google Cloud project
- Google Ads API credentials and a refresh token
- A Google Ads customer ID
- Optional MCC login customer ID

## Configuration

Copy `.env.example` to `.env` and fill in:

```bash
GOOGLE_ADS_DEVELOPER_TOKEN=
GOOGLE_ADS_CLIENT_ID=
GOOGLE_ADS_CLIENT_SECRET=
GOOGLE_ADS_REFRESH_TOKEN=
GOOGLE_ADS_CUSTOMER_ID=
# GOOGLE_ADS_LOGIN_CUSTOMER_ID=
```

## How To Obtain The Tokens

You need five values before the server can talk to Google Ads:

- `GOOGLE_ADS_DEVELOPER_TOKEN`
- `GOOGLE_ADS_CLIENT_ID`
- `GOOGLE_ADS_CLIENT_SECRET`
- `GOOGLE_ADS_REFRESH_TOKEN`
- `GOOGLE_ADS_CUSTOMER_ID`

Optional:

- `GOOGLE_ADS_LOGIN_CUSTOMER_ID` for MCC / manager-account access

### 1. Get A Google Ads Developer Token

In your Google Ads account:

1. Open `Tools and settings`.
2. Open `API Center`.
3. Copy your developer token.

Use that value for `GOOGLE_ADS_DEVELOPER_TOKEN`.

### 2. Create An OAuth Client ID And Secret

In Google Cloud:

1. Create or select a Google Cloud project.
2. Enable the Google Ads API for that project.
3. Open `APIs & Services` -> `Credentials`.
4. Create an OAuth client ID.
5. For local use, a Desktop app client is usually the simplest option.
6. Copy the client ID and client secret.

Use those values for:

- `GOOGLE_ADS_CLIENT_ID`
- `GOOGLE_ADS_CLIENT_SECRET`

### 3. Generate A Refresh Token

This repo includes a helper script:

```bash
uv run python get_refresh_token.py
```

The script will:

1. prompt for your OAuth client ID
2. prompt for your OAuth client secret
3. open or print a Google authorization URL
4. ask you to paste back the authorization code
5. output a refresh token

Put the resulting value in:

- `GOOGLE_ADS_REFRESH_TOKEN`

### 4. Find The Customer IDs

- `GOOGLE_ADS_CUSTOMER_ID`: the Google Ads account the server should operate on
- `GOOGLE_ADS_LOGIN_CUSTOMER_ID`: the manager account to authenticate through, if you are using an MCC

You can copy these from the Google Ads UI. The server accepts IDs with or without dashes and normalizes them internally.

### Example `.env`

```bash
GOOGLE_ADS_DEVELOPER_TOKEN=your-developer-token
GOOGLE_ADS_CLIENT_ID=your-oauth-client-id
GOOGLE_ADS_CLIENT_SECRET=your-oauth-client-secret
GOOGLE_ADS_REFRESH_TOKEN=your-refresh-token
GOOGLE_ADS_CUSTOMER_ID=1234567890
GOOGLE_ADS_LOGIN_CUSTOMER_ID=0987654321
```

Install dependencies:

```bash
uv sync
```

Run locally:

```bash
uv run google-ads-mcp
```

If you still need a refresh token, use:

```bash
uv run python get_refresh_token.py
```

## Claude Cowork / MCP Client Setup

If your MCP client supports stdio servers with environment variables, configure this repo with a command like:

```json
{
  "mcpServers": {
    "google-ads": {
      "command": "uv",
      "args": ["run", "google-ads-mcp"],
      "cwd": "/absolute/path/to/google-ads",
      "env": {
        "GOOGLE_ADS_DEVELOPER_TOKEN": "your-developer-token",
        "GOOGLE_ADS_CLIENT_ID": "your-client-id",
        "GOOGLE_ADS_CLIENT_SECRET": "your-client-secret",
        "GOOGLE_ADS_REFRESH_TOKEN": "your-refresh-token",
        "GOOGLE_ADS_CUSTOMER_ID": "1234567890",
        "GOOGLE_ADS_LOGIN_CUSTOMER_ID": "0987654321"
      }
    }
  }
}
```

If your client loads environment variables from the repo automatically, you can omit the `env` block and rely on the local `.env` file instead.

Notes:

- `cwd` should point at this repository root.
- `GOOGLE_ADS_CUSTOMER_ID` and `GOOGLE_ADS_LOGIN_CUSTOMER_ID` may include or omit dashes; the server normalizes them.
- For manager-account access, set `GOOGLE_ADS_LOGIN_CUSTOMER_ID`.

## Files

```text
.
├── .env.example
├── get_refresh_token.py
├── pyproject.toml
├── README.md
├── src/google_ads_mcp/
│   ├── client.py
│   ├── config.py
│   ├── formatters.py
│   ├── models.py
│   └── server.py
├── tests/
│   ├── test_client.py
│   └── test_server.py
└── uv.lock
```

File summary:

- `src/google_ads_mcp/server.py`: FastMCP server and tool registration
- `src/google_ads_mcp/client.py`: Google Ads API wrapper and mutation/report logic
- `src/google_ads_mcp/models.py`: typed request and structured response models
- `src/google_ads_mcp/formatters.py`: markdown formatting for report tools
- `src/google_ads_mcp/config.py`: environment loading and validation
- `tests/test_client.py`: request-construction and client behavior tests
- `tests/test_server.py`: MCP tool registration and output-shape tests

## Tools

### Keyword Planning

- `generate_keyword_ideas`
- `get_keyword_historical_metrics`
- `generate_keyword_forecast`

### Campaign Structure

- `create_search_campaign`
- `update_search_campaign`
- `set_campaign_geo_targets`
- `set_campaign_ad_schedule`
- `set_campaign_device_bid_adjustments`
- `list_negative_keywords_in_campaign`
- `add_negative_keywords_to_campaign`
- `update_negative_keywords_in_campaign`
- `remove_negative_keywords_from_campaign`
- `create_ad_group`
- `update_ad_group`
- `add_keywords_to_ad_group`
- `update_keywords`
- `remove_keywords`
- `list_negative_keywords_in_ad_group`
- `add_negative_keywords_to_ad_group`
- `update_negative_keywords_in_ad_group`
- `remove_negative_keywords_from_ad_group`

### Shared Negative Lists

- `create_shared_negative_keyword_list`
- `update_shared_negative_keyword_list`
- `list_shared_negative_keyword_lists`
- `list_keywords_in_shared_negative_list`
- `add_keywords_to_shared_negative_list`
- `remove_keywords_from_shared_negative_list`
- `apply_shared_negative_keyword_list_to_campaigns`
- `remove_shared_negative_keyword_list_from_campaigns`
- `get_account_negative_keyword_list`
- `apply_shared_negative_keyword_list_to_account`
- `remove_shared_negative_keyword_list_from_account`

### Ads

- `create_responsive_search_ad`
- `update_responsive_search_ad`

### Campaign Assets

- `create_campaign_sitelink_asset`
- `create_campaign_callout_asset`
- `create_campaign_structured_snippet_asset`
- `create_campaign_call_asset`

### Conversion Tracking

- `create_conversion_action`
- `update_conversion_action`

### Reporting

- `get_search_term_report`
- `get_performance_report`

## Safety Notes

- This server performs live Google Ads mutations.
- New campaigns, ad groups, keywords, and RSAs default to `PAUSED` unless you explicitly request `ENABLED`.
- Campaign assets and conversion actions are durable Google Ads resources. Treat them as production-impacting operations.
- RSA creative updates are implemented as replace-and-remove because Google Ads treats most RSA creative fields as immutable.

## Testing

Run tests with:

```bash
uv run python -m unittest discover -s tests -v
```

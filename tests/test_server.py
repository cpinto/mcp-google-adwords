from __future__ import annotations

import asyncio
import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock, patch

import google_ads_mcp.server as server_module
from google_ads_mcp.config import GoogleAdsConfig
from google_ads_mcp.server import mcp


class ServerToolRegistrationTests(unittest.TestCase):
    def test_tool_registry_includes_new_management_surface(self):
        async def run():
            return await mcp.list_tools()

        tools = asyncio.run(run())
        names = {tool.name for tool in tools}

        self.assertIn("create_search_campaign", names)
        self.assertIn("authorize", names)
        self.assertIn("reauthorize", names)
        self.assertIn("list_negative_keywords_in_campaign", names)
        self.assertIn("add_negative_keywords_to_campaign", names)
        self.assertIn("update_negative_keywords_in_campaign", names)
        self.assertIn("remove_negative_keywords_from_campaign", names)
        self.assertIn("list_negative_keywords_in_ad_group", names)
        self.assertIn("add_negative_keywords_to_ad_group", names)
        self.assertIn("update_negative_keywords_in_ad_group", names)
        self.assertIn("remove_negative_keywords_from_ad_group", names)
        self.assertIn("list_shared_negative_keyword_lists", names)
        self.assertIn("list_keywords_in_shared_negative_list", names)
        self.assertIn("get_account_negative_keyword_list", names)
        self.assertIn("apply_shared_negative_keyword_list_to_account", names)
        self.assertIn("remove_shared_negative_keyword_list_from_account", names)
        self.assertIn("create_responsive_search_ad", names)
        self.assertIn("create_conversion_action", names)
        self.assertIn("get_search_term_report", names)
        self.assertIn("get_performance_report", names)

    def test_structured_and_markdown_tools_expose_expected_output_schema(self):
        async def run():
            return await mcp.list_tools()

        tools = asyncio.run(run())
        create_campaign_tool = next(tool for tool in tools if tool.name == "create_search_campaign")
        list_campaign_negatives_tool = next(tool for tool in tools if tool.name == "list_negative_keywords_in_campaign")
        apply_account_list_tool = next(
            tool for tool in tools if tool.name == "apply_shared_negative_keyword_list_to_account"
        )
        search_term_tool = next(tool for tool in tools if tool.name == "get_search_term_report")
        performance_tool = next(tool for tool in tools if tool.name == "get_performance_report")

        self.assertEqual(create_campaign_tool.outputSchema["title"], "CampaignMutationResult")
        self.assertIn("campaign", create_campaign_tool.outputSchema["properties"])
        self.assertEqual(list_campaign_negatives_tool.outputSchema["title"], "NegativeKeywordListResult")
        self.assertIn("criteria", list_campaign_negatives_tool.outputSchema["properties"])
        self.assertEqual(apply_account_list_tool.outputSchema["title"], "AccountNegativeKeywordListResult")
        self.assertIn("shared_set", apply_account_list_tool.outputSchema["properties"])
        self.assertIn("ad_group", search_term_tool.inputSchema["properties"])
        self.assertEqual(performance_tool.outputSchema["properties"]["result"]["type"], "string")


class ServerAuthFlowTests(unittest.TestCase):
    def _oauth_context(self, refresh_token: str | None = None, cached_client: object | None = None):
        config = GoogleAdsConfig(
            developer_token="dev",
            client_id="client",
            client_secret="secret",
            refresh_token=refresh_token,
            customer_id="1234567890",
        )
        return SimpleNamespace(
            request_context=SimpleNamespace(
                lifespan_context={
                    "config": config,
                    "client": cached_client,
                    "env_path": "/tmp/google-ads.env",
                }
            )
        )

    def test_check_auth_status_reports_authorization_required_when_refresh_token_missing(self):
        result = asyncio.run(server_module.check_auth_status(self._oauth_context()))

        self.assertIn("Authorization required", result)
        self.assertIn("authorize", result)

    def test_authorize_saves_refresh_token_and_clears_cached_client(self):
        ctx = self._oauth_context(cached_client=object())

        with (
            patch(
                "google_ads_mcp.server.anyio.to_thread.run_sync",
                new=AsyncMock(return_value={"refresh_token": "new-refresh-token"}),
            ),
            patch("google_ads_mcp.server.set_key") as set_key,
        ):
            result = asyncio.run(server_module.authorize(ctx))

        self.assertIn("Authorization successful", result)
        self.assertEqual(
            ctx.request_context.lifespan_context["config"].refresh_token,
            "new-refresh-token",
        )
        self.assertIsNone(ctx.request_context.lifespan_context["client"])
        set_key.assert_called_once_with(
            "/tmp/google-ads.env",
            "GOOGLE_ADS_REFRESH_TOKEN",
            "new-refresh-token",
        )

    def test_reauthorize_remains_available_as_alias(self):
        ctx = self._oauth_context(refresh_token="old-refresh-token")

        with (
            patch(
                "google_ads_mcp.server.anyio.to_thread.run_sync",
                new=AsyncMock(return_value={"refresh_token": "replacement-token"}),
            ),
            patch("google_ads_mcp.server.set_key"),
        ):
            result = asyncio.run(server_module.reauthorize(ctx))

        self.assertIn("Reauthorization successful", result)
        self.assertEqual(
            ctx.request_context.lifespan_context["config"].refresh_token,
            "replacement-token",
        )


class ServerReportingTests(unittest.TestCase):
    def test_get_search_term_report_forwards_ad_group_and_renders_keyword_context(self):
        client = Mock()
        client.get_search_term_report.return_value = [
            {
                "search_term": "crm software for startups",
                "campaign_name": "Brand Search",
                "ad_group_name": "Core Terms",
                "keyword": "crm software",
                "impressions": 100,
                "clicks": 12,
                "ctr": 0.12,
                "average_cpc_micros": 1_950_000,
                "cost_micros": 23_400_000,
                "conversions": 2.5,
            }
        ]

        with (
            patch("google_ads_mcp.server._client_from_context", return_value=client),
            patch("google_ads_mcp.server.anyio.to_thread.run_sync", new=AsyncMock(side_effect=lambda fn: fn())),
        ):
            result = asyncio.run(
                server_module.get_search_term_report(
                    SimpleNamespace(),
                    campaign="222",
                    ad_group="555",
                )
            )

        client.get_search_term_report.assert_called_once_with(
            campaign="222",
            ad_group="555",
            start_date=None,
            end_date=None,
            limit=50,
        )
        self.assertIn("| Search Term | Campaign | Ad Group | Keyword |", result)
        self.assertIn("| crm software for startups | Brand Search | Core Terms | crm software |", result)

    def test_get_performance_report_renders_keyword_resource_identifiers(self):
        client = Mock()
        client.get_performance_report.return_value = [
            {
                "level": "keyword",
                "campaign_name": "Brand Search",
                "ad_group_name": "Core Terms",
                "criterion_id": "999",
                "resource_name": "customers/1234567890/adGroupCriteria/555~999",
                "keyword": "crm software",
                "match_type": "PHRASE",
                "status": "ENABLED",
                "bid_micros": 2_100_000,
                "impressions": 100,
                "clicks": 12,
                "ctr": 0.12,
                "average_cpc_micros": 1_950_000,
                "cost_micros": 23_400_000,
                "conversions": 2.5,
            }
        ]

        with (
            patch("google_ads_mcp.server._client_from_context", return_value=client),
            patch("google_ads_mcp.server.anyio.to_thread.run_sync", new=AsyncMock(side_effect=lambda fn: fn())),
        ):
            result = asyncio.run(
                server_module.get_performance_report(
                    SimpleNamespace(),
                    level="keyword",
                )
            )

        self.assertIn("| Campaign | Ad Group | Criterion ID | Resource Name | Keyword |", result)
        self.assertIn("customers/1234567890/adGroupCriteria/555~999", result)
        self.assertIn("| Brand Search | Core Terms | 999 |", result)


if __name__ == "__main__":
    unittest.main()

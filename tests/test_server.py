from __future__ import annotations

import asyncio
import unittest

from google_ads_mcp.server import mcp


class ServerToolRegistrationTests(unittest.TestCase):
    def test_tool_registry_includes_new_management_surface(self):
        async def run():
            return await mcp.list_tools()

        tools = asyncio.run(run())
        names = {tool.name for tool in tools}

        self.assertIn("create_search_campaign", names)
        self.assertIn("create_responsive_search_ad", names)
        self.assertIn("create_conversion_action", names)
        self.assertIn("get_search_term_report", names)
        self.assertIn("get_performance_report", names)

    def test_structured_and_markdown_tools_expose_expected_output_schema(self):
        async def run():
            return await mcp.list_tools()

        tools = asyncio.run(run())
        create_campaign_tool = next(tool for tool in tools if tool.name == "create_search_campaign")
        performance_tool = next(tool for tool in tools if tool.name == "get_performance_report")

        self.assertEqual(create_campaign_tool.outputSchema["title"], "CampaignMutationResult")
        self.assertIn("campaign", create_campaign_tool.outputSchema["properties"])
        self.assertEqual(performance_tool.outputSchema["properties"]["result"]["type"], "string")


if __name__ == "__main__":
    unittest.main()

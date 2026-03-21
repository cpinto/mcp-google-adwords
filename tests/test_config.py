from __future__ import annotations

import os
import unittest
from unittest.mock import patch

from google_ads_mcp.config import GoogleAdsConfig


class GoogleAdsConfigTests(unittest.TestCase):
    def test_from_env_allows_oauth_without_refresh_token(self):
        with (
            patch.dict(
                os.environ,
                {
                    "GOOGLE_ADS_DEVELOPER_TOKEN": "dev-token",
                    "GOOGLE_ADS_CUSTOMER_ID": "123-456-7890",
                    "GOOGLE_ADS_CLIENT_ID": "client-id",
                    "GOOGLE_ADS_CLIENT_SECRET": "client-secret",
                },
                clear=True,
            ),
            patch("google_ads_mcp.config.load_dotenv"),
            patch("google_ads_mcp.config.os.path.isfile", return_value=False),
        ):
            config = GoogleAdsConfig.from_env()

        self.assertEqual(config.auth_type, "oauth")
        self.assertFalse(config.has_refresh_token)
        self.assertIsNone(config.refresh_token)
        self.assertEqual(config.customer_id, "1234567890")
        self.assertNotIn("refresh_token", config.to_client_dict())

    def test_from_env_requires_oauth_client_credentials_without_service_account(self):
        with (
            patch.dict(
                os.environ,
                {
                    "GOOGLE_ADS_DEVELOPER_TOKEN": "dev-token",
                    "GOOGLE_ADS_CUSTOMER_ID": "1234567890",
                },
                clear=True,
            ),
            patch("google_ads_mcp.config.load_dotenv"),
            patch("google_ads_mcp.config.os.path.isfile", return_value=False),
        ):
            with self.assertRaisesRegex(
                ValueError,
                "GOOGLE_ADS_CLIENT_ID, GOOGLE_ADS_CLIENT_SECRET",
            ):
                GoogleAdsConfig.from_env()


if __name__ == "__main__":
    unittest.main()

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

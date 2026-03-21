"""Environment variable loading and validation for Google Ads credentials."""

from __future__ import annotations

import os
from dataclasses import dataclass

from dotenv import load_dotenv


_OAUTH_SETUP_VARS = [
    "GOOGLE_ADS_CLIENT_ID",
    "GOOGLE_ADS_CLIENT_SECRET",
]


@dataclass
class GoogleAdsConfig:
    developer_token: str
    customer_id: str
    login_customer_id: str | None = None
    # OAuth fields (used when no service account is present)
    client_id: str | None = None
    client_secret: str | None = None
    refresh_token: str | None = None
    # Service account fields
    service_account_path: str | None = None
    impersonated_email: str | None = None

    @property
    def auth_type(self) -> str:
        return "service_account" if self.service_account_path else "oauth"

    @property
    def has_refresh_token(self) -> bool:
        return bool(self.refresh_token)

    @classmethod
    def from_env(cls) -> GoogleAdsConfig:
        load_dotenv()

        developer_token = os.getenv("GOOGLE_ADS_DEVELOPER_TOKEN")
        customer_id = os.getenv("GOOGLE_ADS_CUSTOMER_ID")
        if not developer_token or not customer_id:
            raise ValueError(
                "Missing required environment variables: GOOGLE_ADS_DEVELOPER_TOKEN, "
                "GOOGLE_ADS_CUSTOMER_ID. See .env.example for the full list."
            )

        login_customer_id = (
            os.environ.get("GOOGLE_ADS_LOGIN_CUSTOMER_ID", "").replace("-", "")
            or None
        )

        # Check for service account: explicit env var, then default file
        sa_path = os.getenv("GOOGLE_ADS_SERVICE_ACCOUNT_PATH")
        if not sa_path:
            default_path = os.path.join(os.getcwd(), "service_account.json")
            if os.path.isfile(default_path):
                sa_path = default_path

        if sa_path:
            if not os.path.isfile(sa_path):
                raise ValueError(f"Service account file not found: {sa_path}")
            return cls(
                developer_token=developer_token,
                customer_id=customer_id.replace("-", ""),
                login_customer_id=login_customer_id,
                service_account_path=sa_path,
                impersonated_email=os.getenv("GOOGLE_ADS_IMPERSONATED_EMAIL"),
            )

        # Fall back to OAuth
        missing = [v for v in _OAUTH_SETUP_VARS if not os.getenv(v)]
        if missing:
            raise ValueError(
                f"Missing required environment variables: {', '.join(missing)}. "
                "Provide these for OAuth, then use the authorize flow to obtain a "
                "refresh token, or place a service_account.json in the project directory."
            )

        return cls(
            developer_token=developer_token,
            client_id=os.environ["GOOGLE_ADS_CLIENT_ID"],
            client_secret=os.environ["GOOGLE_ADS_CLIENT_SECRET"],
            refresh_token=os.getenv("GOOGLE_ADS_REFRESH_TOKEN") or None,
            customer_id=customer_id.replace("-", ""),
            login_customer_id=login_customer_id,
        )

    def to_client_dict(self) -> dict:
        if self.service_account_path:
            d = {
                "developer_token": self.developer_token,
                "json_key_file_path": self.service_account_path,
                "use_proto_plus": True,
            }
            if self.impersonated_email:
                d["impersonated_email"] = self.impersonated_email
        else:
            d = {
                "developer_token": self.developer_token,
                "client_id": self.client_id,
                "client_secret": self.client_secret,
                "use_proto_plus": True,
            }
            if self.refresh_token:
                d["refresh_token"] = self.refresh_token
        if self.login_customer_id:
            d["login_customer_id"] = self.login_customer_id
        return d

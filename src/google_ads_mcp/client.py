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

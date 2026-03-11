"""Google Ads API wrapper for keyword planning, campaign management, and reporting."""

from __future__ import annotations

import logging
from datetime import date, datetime, timedelta
from typing import Any

from google.ads.googleads.client import GoogleAdsClient
from google.ads.googleads.errors import GoogleAdsException
from google.ads.googleads.v23.common.types import (
    AdScheduleInfo,
    AdTextAsset,
    CallAsset,
    CalloutAsset,
    InteractionTypeInfo,
    KeywordInfo,
    LocationInfo,
    ManualCpc,
    ResponsiveSearchAdInfo,
    SitelinkAsset,
    StructuredSnippetAsset,
    TargetCpa,
    TargetSpend,
)
from google.ads.googleads.v23.enums.types import (
    ad_group_ad_status,
    ad_group_criterion_status,
    ad_group_status,
    advertising_channel_type,
    asset_field_type,
    attribution_model,
    budget_delivery_method,
    call_conversion_reporting_state,
    campaign_criterion_status,
    campaign_status,
    conversion_action_category,
    conversion_action_counting_type,
    conversion_action_status,
    conversion_action_type,
    day_of_week,
    device as device_enum,
    eu_political_advertising_status,
    keyword_match_type,
    minute_of_hour,
    response_content_type,
    served_asset_field_type,
    shared_set_status,
    shared_set_type,
)
from google.protobuf.field_mask_pb2 import FieldMask

from .config import GoogleAdsConfig
from .models import (
    AdMutationResult,
    AdGroupMutationResult,
    AdScheduleEntryInput,
    AdTextAssetInput,
    BiddingStrategyInput,
    CallAssetInput,
    CalloutAssetInput,
    CampaignAssetMutationResult,
    CampaignMutationResult,
    ConversionActionInput,
    ConversionActionMutationResult,
    ConversionTagSnippet,
    DeviceBidAdjustmentInput,
    GeoTargetingInput,
    KeywordInput,
    KeywordMutationResult,
    KeywordUpdateInput,
    NetworkSettingsInput,
    ResourceSummary,
    ResponsiveSearchAdInput,
    SharedNegativeListMutationResult,
    SitelinkAssetInput,
    StructuredSnippetAssetInput,
    TargetingMutationResult,
)

logger = logging.getLogger(__name__)

API_VERSION = "v23"

MUTABLE_RESOURCE = response_content_type.ResponseContentTypeEnum.ResponseContentType.MUTABLE_RESOURCE


class GoogleAdsMCPClient:
    def __init__(self, config: GoogleAdsConfig, google_ads_client: GoogleAdsClient | None = None):
        self.config = config
        self.client = google_ads_client or GoogleAdsClient.load_from_dict(
            config.to_client_dict(),
            version=API_VERSION,
        )
        self.customer_id = config.customer_id

    def _geo_resource(self, geo_id: str) -> str:
        return f"geoTargetConstants/{geo_id}"

    def _language_resource(self, lang_id: str) -> str:
        return f"languageConstants/{lang_id}"

    def _resource_name(self, collection: str, resource: str, allow_numeric: bool = True) -> str:
        if "/" in resource:
            return resource
        if not allow_numeric:
            raise ValueError(f"{collection} requires a full Google Ads resource name.")
        return f"customers/{self.customer_id}/{collection}/{resource}"

    def _require_resource_name(self, resource: str, label: str) -> str:
        if "/" not in resource:
            raise ValueError(f"{label} must be provided as a full Google Ads resource name.")
        return resource

    def _campaign_resource(self, resource: str) -> str:
        return self._resource_name("campaigns", resource)

    def _campaign_budget_resource(self, resource: str) -> str:
        return self._resource_name("campaignBudgets", resource)

    def _ad_group_resource(self, resource: str) -> str:
        return self._resource_name("adGroups", resource)

    def _shared_set_resource(self, resource: str) -> str:
        return self._resource_name("sharedSets", resource)

    def _asset_resource(self, resource: str) -> str:
        return self._resource_name("assets", resource)

    def _conversion_action_resource(self, resource: str) -> str:
        return self._resource_name("conversionActions", resource)

    def _extract_id(self, resource_name: str) -> str | None:
        if not resource_name:
            return None
        tail = resource_name.rsplit("/", 1)[-1]
        if "~" in tail:
            return tail.rsplit("~", 1)[-1]
        return tail

    def _to_micros(self, value: float | None) -> int | None:
        if value is None:
            return None
        return int(value * 1_000_000)

    def _enum_value(self, enum_cls: Any, value: str | None, label: str) -> Any:
        if value is None:
            raise ValueError(f"{label} is required.")
        enum_value = getattr(enum_cls, value.upper(), None)
        if enum_value is None:
            raise ValueError(f"Unsupported {label}: {value}")
        return enum_value

    def _field_mask(self, *paths: str) -> FieldMask:
        unique_paths = [path for path in dict.fromkeys(paths) if path]
        return FieldMask(paths=unique_paths)

    def _build_request(self, request_type: str, operations: list[Any]) -> Any:
        request = self.client.get_type(request_type)
        request.customer_id = self.customer_id
        request.response_content_type = MUTABLE_RESOURCE
        request.operations.extend(operations)
        return request

    def _mutate(self, service_name: str, request_type: str, method_name: str, operations: list[Any]) -> Any:
        service = self.client.get_service(service_name)
        request = self._build_request(request_type, operations)
        return getattr(service, method_name)(request=request)

    def _search(self, query: str) -> list[Any]:
        service = self.client.get_service("GoogleAdsService")
        request = self.client.get_type("SearchGoogleAdsRequest")
        request.customer_id = self.customer_id
        request.query = query
        return list(service.search(request=request))

    def _quote(self, value: str) -> str:
        return "'" + value.replace("\\", "\\\\").replace("'", "\\'") + "'"

    def _resource_summary(
        self,
        resource_name: str,
        *,
        status: str | None = None,
        name: str | None = None,
    ) -> ResourceSummary:
        return ResourceSummary(
            resource_name=resource_name,
            id=self._extract_id(resource_name),
            status=status,
            name=name,
        )

    def _apply_network_settings(self, campaign: Any, settings: NetworkSettingsInput, mask_paths: list[str] | None = None):
        campaign.network_settings.target_google_search = settings.target_google_search
        campaign.network_settings.target_search_network = settings.target_search_network
        campaign.network_settings.target_content_network = settings.target_content_network
        campaign.network_settings.target_partner_search_network = settings.target_partner_search_network
        if mask_paths is not None:
            mask_paths.extend(
                [
                    "network_settings.target_google_search",
                    "network_settings.target_search_network",
                    "network_settings.target_content_network",
                    "network_settings.target_partner_search_network",
                ]
            )

    def _apply_bidding_strategy(
        self,
        campaign: Any,
        bidding_strategy: BiddingStrategyInput,
        mask_paths: list[str] | None = None,
    ):
        if bidding_strategy.strategy_type == "MANUAL_CPC":
            campaign.manual_cpc = ManualCpc(enhanced_cpc_enabled=bidding_strategy.enhanced_cpc_enabled)
            if mask_paths is not None:
                mask_paths.append("manual_cpc.enhanced_cpc_enabled")
            return

        if bidding_strategy.strategy_type == "MAXIMIZE_CLICKS":
            campaign.target_spend = TargetSpend(
                cpc_bid_ceiling_micros=self._to_micros(bidding_strategy.max_cpc_bid)
            )
            if mask_paths is not None:
                mask_paths.append("target_spend.cpc_bid_ceiling_micros")
            return

        campaign.target_cpa = TargetCpa(target_cpa_micros=self._to_micros(bidding_strategy.target_cpa))
        if mask_paths is not None:
            mask_paths.append("target_cpa.target_cpa_micros")

    def _campaign_location_operations(self, campaign_resource: str, geo_targets: GeoTargetingInput) -> list[Any]:
        campaign_resource = self._campaign_resource(campaign_resource)
        existing_rows = self._search(
            "SELECT campaign_criterion.resource_name "
            "FROM campaign_criterion "
            f"WHERE campaign.resource_name = {self._quote(campaign_resource)} "
            "AND campaign_criterion.type = LOCATION"
        )

        operations: list[Any] = []
        for row in existing_rows:
            op = self.client.get_type("CampaignCriterionOperation")
            op.remove = row.campaign_criterion.resource_name
            operations.append(op)

        for location_id in geo_targets.include_location_ids:
            criterion = self.client.get_type("CampaignCriterion")
            criterion.campaign = campaign_resource
            criterion.status = campaign_criterion_status.CampaignCriterionStatusEnum.CampaignCriterionStatus.ENABLED
            criterion.location = LocationInfo(geo_target_constant=self._geo_resource(location_id))

            op = self.client.get_type("CampaignCriterionOperation")
            op.create = criterion
            operations.append(op)

        for location_id in geo_targets.exclude_location_ids:
            criterion = self.client.get_type("CampaignCriterion")
            criterion.campaign = campaign_resource
            criterion.status = campaign_criterion_status.CampaignCriterionStatusEnum.CampaignCriterionStatus.ENABLED
            criterion.negative = True
            criterion.location = LocationInfo(geo_target_constant=self._geo_resource(location_id))

            op = self.client.get_type("CampaignCriterionOperation")
            op.create = criterion
            operations.append(op)

        return operations

    def _campaign_schedule_operations(self, campaign_resource: str, entries: list[AdScheduleEntryInput]) -> list[Any]:
        campaign_resource = self._campaign_resource(campaign_resource)
        existing_rows = self._search(
            "SELECT campaign_criterion.resource_name "
            "FROM campaign_criterion "
            f"WHERE campaign.resource_name = {self._quote(campaign_resource)} "
            "AND campaign_criterion.type = AD_SCHEDULE"
        )

        operations: list[Any] = []
        for row in existing_rows:
            op = self.client.get_type("CampaignCriterionOperation")
            op.remove = row.campaign_criterion.resource_name
            operations.append(op)

        for entry in entries:
            criterion = self.client.get_type("CampaignCriterion")
            criterion.campaign = campaign_resource
            criterion.status = campaign_criterion_status.CampaignCriterionStatusEnum.CampaignCriterionStatus.ENABLED
            criterion.ad_schedule = AdScheduleInfo(
                day_of_week=self._enum_value(
                    day_of_week.DayOfWeekEnum.DayOfWeek,
                    entry.day_of_week,
                    "day_of_week",
                ),
                start_hour=entry.start_hour,
                start_minute=self._enum_value(
                    minute_of_hour.MinuteOfHourEnum.MinuteOfHour,
                    entry.start_minute,
                    "start_minute",
                ),
                end_hour=entry.end_hour,
                end_minute=self._enum_value(
                    minute_of_hour.MinuteOfHourEnum.MinuteOfHour,
                    entry.end_minute,
                    "end_minute",
                ),
            )
            if entry.bid_modifier is not None:
                criterion.bid_modifier = entry.bid_modifier

            op = self.client.get_type("CampaignCriterionOperation")
            op.create = criterion
            operations.append(op)

        return operations

    def _campaign_device_operations(
        self,
        campaign_resource: str,
        adjustments: list[DeviceBidAdjustmentInput],
    ) -> list[Any]:
        campaign_resource = self._campaign_resource(campaign_resource)
        existing_rows = self._search(
            "SELECT campaign_criterion.resource_name, campaign_criterion.device.type "
            "FROM campaign_criterion "
            f"WHERE campaign.resource_name = {self._quote(campaign_resource)} "
            "AND campaign_criterion.type = DEVICE"
        )
        existing_by_device = {
            row.campaign_criterion.device.type.name: row.campaign_criterion.resource_name
            for row in existing_rows
            if getattr(row.campaign_criterion.device.type, "name", None)
        }

        operations: list[Any] = []
        for adjustment in adjustments:
            device_value = self._enum_value(
                device_enum.DeviceEnum.Device,
                adjustment.device,
                "device",
            )
            existing_resource = existing_by_device.get(adjustment.device)
            if existing_resource:
                criterion = self.client.get_type("CampaignCriterion")
                criterion.resource_name = existing_resource
                criterion.bid_modifier = adjustment.bid_modifier
                op = self.client.get_type("CampaignCriterionOperation")
                op.update = criterion
                op.update_mask = self._field_mask("bid_modifier")
                operations.append(op)
                continue

            criterion = self.client.get_type("CampaignCriterion")
            criterion.campaign = campaign_resource
            criterion.status = campaign_criterion_status.CampaignCriterionStatusEnum.CampaignCriterionStatus.ENABLED
            criterion.bid_modifier = adjustment.bid_modifier
            criterion.device.type_ = device_value

            op = self.client.get_type("CampaignCriterionOperation")
            op.create = criterion
            operations.append(op)

        return operations

    def _get_campaign_budget(self, campaign_resource: str) -> ResourceSummary:
        campaign_resource = self._campaign_resource(campaign_resource)
        rows = self._search(
            "SELECT campaign.campaign_budget "
            "FROM campaign "
            f"WHERE campaign.resource_name = {self._quote(campaign_resource)}"
        )
        if not rows:
            raise ValueError(f"Campaign not found: {campaign_resource}")
        budget_resource = rows[0].campaign.campaign_budget
        return self._resource_summary(budget_resource)

    def _keyword_query_details(self, criterion_resource_name: str) -> Any:
        rows = self._search(
            "SELECT ad_group.resource_name, "
            "ad_group_criterion.resource_name, "
            "ad_group_criterion.cpc_bid_micros, "
            "ad_group_criterion.status, "
            "ad_group_criterion.keyword.text, "
            "ad_group_criterion.keyword.match_type "
            "FROM keyword_view "
            f"WHERE ad_group_criterion.resource_name = {self._quote(criterion_resource_name)} "
            "LIMIT 1"
        )
        if not rows:
            raise ValueError(f"Keyword criterion not found: {criterion_resource_name}")
        return rows[0]

    def _ad_group_ad_details(self, ad_group_ad_resource_name: str) -> Any:
        rows = self._search(
            "SELECT ad_group.resource_name, ad_group_ad.resource_name, ad_group_ad.status "
            "FROM ad_group_ad "
            f"WHERE ad_group_ad.resource_name = {self._quote(ad_group_ad_resource_name)} "
            "LIMIT 1"
        )
        if not rows:
            raise ValueError(f"Ad group ad not found: {ad_group_ad_resource_name}")
        return rows[0]

    def _create_budget(self, campaign_name: str, daily_budget: float) -> ResourceSummary:
        budget = self.client.get_type("CampaignBudget")
        budget.name = f"{campaign_name} Budget"
        budget.amount_micros = self._to_micros(daily_budget)
        budget.delivery_method = budget_delivery_method.BudgetDeliveryMethodEnum.BudgetDeliveryMethod.STANDARD
        budget.explicitly_shared = False

        operation = self.client.get_type("CampaignBudgetOperation")
        operation.create = budget

        response = self._mutate(
            "CampaignBudgetService",
            "MutateCampaignBudgetsRequest",
            "mutate_campaign_budgets",
            [operation],
        )
        result = response.results[0]
        resource = getattr(result, "campaign_budget", None)
        return self._resource_summary(
            result.resource_name,
            name=getattr(resource, "name", budget.name),
        )

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

            today = datetime.today()
            start = today + timedelta(days=1)
            end = start + timedelta(days=forecast_days)
            request.forecast_period.start_date = start.strftime("%Y-%m-%d")
            request.forecast_period.end_date = end.strftime("%Y-%m-%d")

            campaign = request.campaign
            for geo_id in geo_target_ids:
                criterion = campaign.geo_modifiers.add()
                criterion.geo_target_constant = self._geo_resource(geo_id)
            campaign.language_constants.append(self._language_resource(language_id))
            campaign.manual_cpc_bidding_strategy.max_cpc_bid_micros = self._to_micros(max_cpc_bid)
            campaign.keyword_plan_network = self.client.enums.KeywordPlanNetworkEnum.GOOGLE_SEARCH

            match_type_value = self._enum_value(
                keyword_match_type.KeywordMatchTypeEnum.KeywordMatchType,
                match_type,
                "match_type",
            )
            for keyword_text in keywords:
                ad_group_keyword = campaign.ad_groups.add()
                biddable = ad_group_keyword.biddable_keywords.add()
                biddable.keyword.text = keyword_text
                biddable.keyword.match_type = match_type_value
                biddable.max_cpc_bid_micros = self._to_micros(max_cpc_bid)

            if negative_keywords:
                for negative_keyword in negative_keywords:
                    negative = campaign.negative_keywords.add()
                    negative.keyword.text = negative_keyword
                    negative.keyword.match_type = keyword_match_type.KeywordMatchTypeEnum.KeywordMatchType.BROAD

            response = service.generate_keyword_forecast_metrics(request=request)
            return {
                "campaign_forecast": response.campaign_forecast_metrics,
                "keyword_forecasts": list(response.keyword_forecasts),
                "keywords": keywords,
                "forecast_days": forecast_days,
            }
        except GoogleAdsException as ex:
            return _format_google_ads_error(ex)

    def create_search_campaign(
        self,
        name: str,
        daily_budget: float,
        bidding_strategy: BiddingStrategyInput,
        network_settings: NetworkSettingsInput | None = None,
        status: str = "PAUSED",
        geo_targets: GeoTargetingInput | None = None,
    ) -> CampaignMutationResult:
        try:
            budget_summary = self._create_budget(name, daily_budget)

            campaign = self.client.get_type("Campaign")
            campaign.name = name
            campaign.status = self._enum_value(
                campaign_status.CampaignStatusEnum.CampaignStatus,
                status,
                "campaign status",
            )
            campaign.advertising_channel_type = advertising_channel_type.AdvertisingChannelTypeEnum.AdvertisingChannelType.SEARCH
            campaign.contains_eu_political_advertising = (
                eu_political_advertising_status.EuPoliticalAdvertisingStatusEnum.EuPoliticalAdvertisingStatus.DOES_NOT_CONTAIN_EU_POLITICAL_ADVERTISING
            )
            campaign.campaign_budget = budget_summary.resource_name
            self._apply_bidding_strategy(campaign, bidding_strategy)
            self._apply_network_settings(campaign, network_settings or NetworkSettingsInput())

            operation = self.client.get_type("CampaignOperation")
            operation.create = campaign
            response = self._mutate(
                "CampaignService",
                "MutateCampaignsRequest",
                "mutate_campaigns",
                [operation],
            )
            result = response.results[0]
            campaign_summary = self._resource_summary(result.resource_name, status=status, name=name)

            geo_summaries: list[ResourceSummary] = []
            if geo_targets:
                geo_result = self.set_campaign_geo_targets(campaign_summary.resource_name, geo_targets)
                geo_summaries = geo_result.geo_target_criteria

            return CampaignMutationResult(
                campaign=campaign_summary,
                budget=budget_summary,
                geo_target_criteria=geo_summaries,
            )
        except GoogleAdsException as ex:
            _raise_google_ads_error(ex)

    def update_search_campaign(
        self,
        campaign: str,
        *,
        name: str | None = None,
        daily_budget: float | None = None,
        bidding_strategy: BiddingStrategyInput | None = None,
        network_settings: NetworkSettingsInput | None = None,
        status: str | None = None,
        geo_targets: GeoTargetingInput | None = None,
    ) -> CampaignMutationResult:
        try:
            campaign_resource = self._campaign_resource(campaign)
            budget_summary: ResourceSummary | None = None
            if daily_budget is not None:
                budget_summary = self._get_campaign_budget(campaign_resource)
                budget_update = self.client.get_type("CampaignBudget")
                budget_update.resource_name = budget_summary.resource_name
                budget_update.amount_micros = self._to_micros(daily_budget)

                budget_operation = self.client.get_type("CampaignBudgetOperation")
                budget_operation.update = budget_update
                budget_operation.update_mask = self._field_mask("amount_micros")
                self._mutate(
                    "CampaignBudgetService",
                    "MutateCampaignBudgetsRequest",
                    "mutate_campaign_budgets",
                    [budget_operation],
                )

            mask_paths: list[str] = []
            campaign_update = self.client.get_type("Campaign")
            campaign_update.resource_name = campaign_resource

            if name is not None:
                campaign_update.name = name
                mask_paths.append("name")
            if status is not None:
                campaign_update.status = self._enum_value(
                    campaign_status.CampaignStatusEnum.CampaignStatus,
                    status,
                    "campaign status",
                )
                mask_paths.append("status")
            if bidding_strategy is not None:
                self._apply_bidding_strategy(campaign_update, bidding_strategy, mask_paths)
            if network_settings is not None:
                self._apply_network_settings(campaign_update, network_settings, mask_paths)

            if mask_paths:
                operation = self.client.get_type("CampaignOperation")
                operation.update = campaign_update
                operation.update_mask = self._field_mask(*mask_paths)
                response = self._mutate(
                    "CampaignService",
                    "MutateCampaignsRequest",
                    "mutate_campaigns",
                    [operation],
                )
                resource_name = response.results[0].resource_name
            else:
                resource_name = campaign_resource

            geo_summaries: list[ResourceSummary] = []
            if geo_targets is not None:
                geo_result = self.set_campaign_geo_targets(campaign_resource, geo_targets)
                geo_summaries = geo_result.geo_target_criteria

            return CampaignMutationResult(
                campaign=self._resource_summary(resource_name, status=status, name=name),
                budget=budget_summary,
                geo_target_criteria=geo_summaries,
            )
        except GoogleAdsException as ex:
            _raise_google_ads_error(ex)

    def set_campaign_geo_targets(
        self,
        campaign: str,
        geo_targets: GeoTargetingInput,
    ) -> CampaignMutationResult:
        try:
            operations = self._campaign_location_operations(campaign, geo_targets)
            criteria: list[ResourceSummary] = []
            if operations:
                response = self._mutate(
                    "CampaignCriterionService",
                    "MutateCampaignCriteriaRequest",
                    "mutate_campaign_criteria",
                    operations,
                )
                criteria = [
                    self._resource_summary(result.resource_name, status="ENABLED")
                    for result in response.results
                    if result.resource_name
                ]
            return CampaignMutationResult(
                campaign=self._resource_summary(self._campaign_resource(campaign)),
                geo_target_criteria=criteria,
            )
        except GoogleAdsException as ex:
            _raise_google_ads_error(ex)

    def set_campaign_ad_schedule(
        self,
        campaign: str,
        entries: list[AdScheduleEntryInput],
    ) -> TargetingMutationResult:
        try:
            operations = self._campaign_schedule_operations(campaign, entries)
            if not operations:
                return TargetingMutationResult(campaign=self._resource_summary(self._campaign_resource(campaign)))
            response = self._mutate(
                "CampaignCriterionService",
                "MutateCampaignCriteriaRequest",
                "mutate_campaign_criteria",
                operations,
            )
            return TargetingMutationResult(
                campaign=self._resource_summary(self._campaign_resource(campaign)),
                criteria=[
                    self._resource_summary(result.resource_name, status="ENABLED")
                    for result in response.results
                    if result.resource_name
                ],
            )
        except GoogleAdsException as ex:
            _raise_google_ads_error(ex)

    def set_campaign_device_bid_adjustments(
        self,
        campaign: str,
        adjustments: list[DeviceBidAdjustmentInput],
    ) -> TargetingMutationResult:
        try:
            operations = self._campaign_device_operations(campaign, adjustments)
            if not operations:
                return TargetingMutationResult(campaign=self._resource_summary(self._campaign_resource(campaign)))
            response = self._mutate(
                "CampaignCriterionService",
                "MutateCampaignCriteriaRequest",
                "mutate_campaign_criteria",
                operations,
            )
            return TargetingMutationResult(
                campaign=self._resource_summary(self._campaign_resource(campaign)),
                criteria=[
                    self._resource_summary(result.resource_name, status="ENABLED")
                    for result in response.results
                    if result.resource_name
                ],
            )
        except GoogleAdsException as ex:
            _raise_google_ads_error(ex)

    def create_ad_group(
        self,
        campaign: str,
        name: str,
        default_cpc_bid: float | None = None,
        status: str = "PAUSED",
    ) -> AdGroupMutationResult:
        try:
            ad_group = self.client.get_type("AdGroup")
            ad_group.campaign = self._campaign_resource(campaign)
            ad_group.name = name
            ad_group.status = self._enum_value(
                ad_group_status.AdGroupStatusEnum.AdGroupStatus,
                status,
                "ad group status",
            )
            if default_cpc_bid is not None:
                ad_group.cpc_bid_micros = self._to_micros(default_cpc_bid)

            operation = self.client.get_type("AdGroupOperation")
            operation.create = ad_group
            response = self._mutate(
                "AdGroupService",
                "MutateAdGroupsRequest",
                "mutate_ad_groups",
                [operation],
            )

            return AdGroupMutationResult(
                ad_group=self._resource_summary(response.results[0].resource_name, status=status, name=name)
            )
        except GoogleAdsException as ex:
            _raise_google_ads_error(ex)

    def update_ad_group(
        self,
        ad_group: str,
        *,
        name: str | None = None,
        default_cpc_bid: float | None = None,
        status: str | None = None,
    ) -> AdGroupMutationResult:
        try:
            ad_group_resource = self._ad_group_resource(ad_group)
            ad_group_update = self.client.get_type("AdGroup")
            ad_group_update.resource_name = ad_group_resource
            mask_paths: list[str] = []

            if name is not None:
                ad_group_update.name = name
                mask_paths.append("name")
            if default_cpc_bid is not None:
                ad_group_update.cpc_bid_micros = self._to_micros(default_cpc_bid)
                mask_paths.append("cpc_bid_micros")
            if status is not None:
                ad_group_update.status = self._enum_value(
                    ad_group_status.AdGroupStatusEnum.AdGroupStatus,
                    status,
                    "ad group status",
                )
                mask_paths.append("status")

            if not mask_paths:
                return AdGroupMutationResult(ad_group=self._resource_summary(ad_group_resource))

            operation = self.client.get_type("AdGroupOperation")
            operation.update = ad_group_update
            operation.update_mask = self._field_mask(*mask_paths)
            response = self._mutate(
                "AdGroupService",
                "MutateAdGroupsRequest",
                "mutate_ad_groups",
                [operation],
            )
            return AdGroupMutationResult(
                ad_group=self._resource_summary(response.results[0].resource_name, status=status, name=name)
            )
        except GoogleAdsException as ex:
            _raise_google_ads_error(ex)

    def add_keywords_to_ad_group(
        self,
        ad_group: str,
        keywords: list[KeywordInput],
        default_match_type: str = "BROAD",
    ) -> KeywordMutationResult:
        try:
            ad_group_resource = self._ad_group_resource(ad_group)
            operations: list[Any] = []
            summaries: list[ResourceSummary] = []

            for keyword in keywords:
                criterion = self.client.get_type("AdGroupCriterion")
                criterion.ad_group = ad_group_resource
                criterion.status = self._enum_value(
                    ad_group_criterion_status.AdGroupCriterionStatusEnum.AdGroupCriterionStatus,
                    keyword.status,
                    "keyword status",
                )
                criterion.keyword = KeywordInfo(
                    text=keyword.text,
                    match_type=self._enum_value(
                        keyword_match_type.KeywordMatchTypeEnum.KeywordMatchType,
                        keyword.match_type or default_match_type,
                        "keyword match type",
                    ),
                )
                if keyword.cpc_bid is not None:
                    criterion.cpc_bid_micros = self._to_micros(keyword.cpc_bid)

                op = self.client.get_type("AdGroupCriterionOperation")
                op.create = criterion
                operations.append(op)
                summaries.append(self._resource_summary("", status=keyword.status, name=keyword.text))

            response = self._mutate(
                "AdGroupCriterionService",
                "MutateAdGroupCriteriaRequest",
                "mutate_ad_group_criteria",
                operations,
            )

            created = [
                self._resource_summary(
                    result.resource_name,
                    status=summaries[index].status,
                    name=summaries[index].name,
                )
                for index, result in enumerate(response.results)
            ]
            return KeywordMutationResult(created=created)
        except GoogleAdsException as ex:
            _raise_google_ads_error(ex)

    def update_keywords(self, updates: list[KeywordUpdateInput]) -> KeywordMutationResult:
        try:
            update_operations: list[Any] = []
            updated_summaries: list[tuple[str, str | None]] = []
            replacement_creates: list[Any] = []
            replacement_removes: list[str] = []
            replacement_summaries: list[tuple[str | None, str | None]] = []

            for update in updates:
                resource_name = self._require_resource_name(update.keyword_criterion, "keyword_criterion")
                needs_replacement = update.new_text is not None or update.new_match_type is not None
                if needs_replacement:
                    row = self._keyword_query_details(resource_name)
                    criterion = self.client.get_type("AdGroupCriterion")
                    criterion.ad_group = row.ad_group.resource_name
                    criterion.status = (
                        self._enum_value(
                            ad_group_criterion_status.AdGroupCriterionStatusEnum.AdGroupCriterionStatus,
                            update.status,
                            "keyword status",
                        )
                        if update.status is not None
                        else row.ad_group_criterion.status
                    )
                    criterion.keyword = KeywordInfo(
                        text=update.new_text or row.ad_group_criterion.keyword.text,
                        match_type=self._enum_value(
                            keyword_match_type.KeywordMatchTypeEnum.KeywordMatchType,
                            update.new_match_type or row.ad_group_criterion.keyword.match_type.name,
                            "keyword match type",
                        ),
                    )
                    criterion.cpc_bid_micros = (
                        self._to_micros(update.cpc_bid)
                        if update.cpc_bid is not None
                        else row.ad_group_criterion.cpc_bid_micros
                    )

                    create_op = self.client.get_type("AdGroupCriterionOperation")
                    create_op.create = criterion
                    replacement_creates.append(create_op)
                    replacement_removes.append(resource_name)
                    replacement_summaries.append((criterion.keyword.text, update.status))
                    continue

                criterion = self.client.get_type("AdGroupCriterion")
                criterion.resource_name = resource_name
                mask_paths: list[str] = []
                if update.cpc_bid is not None:
                    criterion.cpc_bid_micros = self._to_micros(update.cpc_bid)
                    mask_paths.append("cpc_bid_micros")
                if update.status is not None:
                    criterion.status = self._enum_value(
                        ad_group_criterion_status.AdGroupCriterionStatusEnum.AdGroupCriterionStatus,
                        update.status,
                        "keyword status",
                    )
                    mask_paths.append("status")
                if not mask_paths:
                    continue

                op = self.client.get_type("AdGroupCriterionOperation")
                op.update = criterion
                op.update_mask = self._field_mask(*mask_paths)
                update_operations.append(op)
                updated_summaries.append((resource_name, update.status))

            updated_results: list[ResourceSummary] = []
            if update_operations:
                response = self._mutate(
                    "AdGroupCriterionService",
                    "MutateAdGroupCriteriaRequest",
                    "mutate_ad_group_criteria",
                    update_operations,
                )
                updated_results = [
                    self._resource_summary(result.resource_name, status=updated_summaries[index][1])
                    for index, result in enumerate(response.results)
                ]

            replaced_results: list[ResourceSummary] = []
            if replacement_removes:
                remove_ops: list[Any] = []
                for resource_name in replacement_removes:
                    op = self.client.get_type("AdGroupCriterionOperation")
                    op.remove = resource_name
                    remove_ops.append(op)
                self._mutate(
                    "AdGroupCriterionService",
                    "MutateAdGroupCriteriaRequest",
                    "mutate_ad_group_criteria",
                    remove_ops,
                )
                create_response = self._mutate(
                    "AdGroupCriterionService",
                    "MutateAdGroupCriteriaRequest",
                    "mutate_ad_group_criteria",
                    replacement_creates,
                )
                replaced_results = [
                    self._resource_summary(
                        result.resource_name,
                        status=replacement_summaries[index][1],
                        name=replacement_summaries[index][0],
                    )
                    for index, result in enumerate(create_response.results)
                ]

            return KeywordMutationResult(updated=updated_results, replaced=replaced_results)
        except GoogleAdsException as ex:
            _raise_google_ads_error(ex)

    def remove_keywords(self, keyword_criteria: list[str]) -> KeywordMutationResult:
        try:
            operations: list[Any] = []
            removed: list[str] = []
            for criterion in keyword_criteria:
                resource_name = self._require_resource_name(criterion, "keyword criterion")
                op = self.client.get_type("AdGroupCriterionOperation")
                op.remove = resource_name
                operations.append(op)
                removed.append(resource_name)

            if operations:
                self._mutate(
                    "AdGroupCriterionService",
                    "MutateAdGroupCriteriaRequest",
                    "mutate_ad_group_criteria",
                    operations,
                )
            return KeywordMutationResult(removed=removed)
        except GoogleAdsException as ex:
            _raise_google_ads_error(ex)

    def create_shared_negative_keyword_list(self, name: str) -> SharedNegativeListMutationResult:
        try:
            shared_set = self.client.get_type("SharedSet")
            shared_set.name = name
            shared_set.type_ = shared_set_type.SharedSetTypeEnum.SharedSetType.NEGATIVE_KEYWORDS
            shared_set.status = shared_set_status.SharedSetStatusEnum.SharedSetStatus.ENABLED

            op = self.client.get_type("SharedSetOperation")
            op.create = shared_set
            response = self._mutate(
                "SharedSetService",
                "MutateSharedSetsRequest",
                "mutate_shared_sets",
                [op],
            )
            return SharedNegativeListMutationResult(
                shared_set=self._resource_summary(response.results[0].resource_name, status="ENABLED", name=name)
            )
        except GoogleAdsException as ex:
            _raise_google_ads_error(ex)

    def update_shared_negative_keyword_list(
        self,
        shared_set: str,
        *,
        name: str | None = None,
    ) -> SharedNegativeListMutationResult:
        try:
            shared_set_resource = self._shared_set_resource(shared_set)
            shared_set_update = self.client.get_type("SharedSet")
            shared_set_update.resource_name = shared_set_resource
            mask_paths: list[str] = []

            if name is not None:
                shared_set_update.name = name
                mask_paths.append("name")

            if not mask_paths:
                return SharedNegativeListMutationResult(shared_set=self._resource_summary(shared_set_resource))

            op = self.client.get_type("SharedSetOperation")
            op.update = shared_set_update
            op.update_mask = self._field_mask(*mask_paths)
            response = self._mutate(
                "SharedSetService",
                "MutateSharedSetsRequest",
                "mutate_shared_sets",
                [op],
            )
            return SharedNegativeListMutationResult(
                shared_set=self._resource_summary(response.results[0].resource_name, status="ENABLED", name=name)
            )
        except GoogleAdsException as ex:
            _raise_google_ads_error(ex)

    def add_keywords_to_shared_negative_list(
        self,
        shared_set: str,
        keywords: list[str],
    ) -> SharedNegativeListMutationResult:
        try:
            shared_set_resource = self._shared_set_resource(shared_set)
            operations: list[Any] = []
            for keyword_text in keywords:
                criterion = self.client.get_type("SharedCriterion")
                criterion.shared_set = shared_set_resource
                criterion.keyword = KeywordInfo(
                    text=keyword_text,
                    match_type=keyword_match_type.KeywordMatchTypeEnum.KeywordMatchType.BROAD,
                )
                op = self.client.get_type("SharedCriterionOperation")
                op.create = criterion
                operations.append(op)

            response = self._mutate(
                "SharedCriterionService",
                "MutateSharedCriteriaRequest",
                "mutate_shared_criteria",
                operations,
            )
            return SharedNegativeListMutationResult(
                shared_set=self._resource_summary(shared_set_resource),
                shared_criteria=[
                    self._resource_summary(result.resource_name, name=keywords[index])
                    for index, result in enumerate(response.results)
                ],
            )
        except GoogleAdsException as ex:
            _raise_google_ads_error(ex)

    def remove_keywords_from_shared_negative_list(
        self,
        shared_criteria: list[str],
    ) -> SharedNegativeListMutationResult:
        try:
            operations: list[Any] = []
            removed: list[str] = []
            for criterion in shared_criteria:
                resource_name = self._require_resource_name(criterion, "shared criterion")
                op = self.client.get_type("SharedCriterionOperation")
                op.remove = resource_name
                operations.append(op)
                removed.append(resource_name)

            if operations:
                self._mutate(
                    "SharedCriterionService",
                    "MutateSharedCriteriaRequest",
                    "mutate_shared_criteria",
                    operations,
                )
            return SharedNegativeListMutationResult(removed=removed)
        except GoogleAdsException as ex:
            _raise_google_ads_error(ex)

    def apply_shared_negative_keyword_list_to_campaigns(
        self,
        shared_set: str,
        campaigns: list[str],
    ) -> SharedNegativeListMutationResult:
        try:
            shared_set_resource = self._shared_set_resource(shared_set)
            operations: list[Any] = []
            for campaign in campaigns:
                relation = self.client.get_type("CampaignSharedSet")
                relation.shared_set = shared_set_resource
                relation.campaign = self._campaign_resource(campaign)
                op = self.client.get_type("CampaignSharedSetOperation")
                op.create = relation
                operations.append(op)

            response = self._mutate(
                "CampaignSharedSetService",
                "MutateCampaignSharedSetsRequest",
                "mutate_campaign_shared_sets",
                operations,
            )
            return SharedNegativeListMutationResult(
                shared_set=self._resource_summary(shared_set_resource),
                campaign_shared_sets=[
                    self._resource_summary(result.resource_name) for result in response.results
                ],
            )
        except GoogleAdsException as ex:
            _raise_google_ads_error(ex)

    def remove_shared_negative_keyword_list_from_campaigns(
        self,
        shared_set: str,
        campaigns: list[str],
    ) -> SharedNegativeListMutationResult:
        try:
            shared_set_resource = self._shared_set_resource(shared_set)
            operations: list[Any] = []
            removed: list[str] = []
            for campaign in campaigns:
                campaign_resource = self._campaign_resource(campaign)
                relation_resource = (
                    f"customers/{self.customer_id}/campaignSharedSets/"
                    f"{self._extract_id(campaign_resource)}~{self._extract_id(shared_set_resource)}"
                )
                op = self.client.get_type("CampaignSharedSetOperation")
                op.remove = relation_resource
                operations.append(op)
                removed.append(relation_resource)

            if operations:
                self._mutate(
                    "CampaignSharedSetService",
                    "MutateCampaignSharedSetsRequest",
                    "mutate_campaign_shared_sets",
                    operations,
                )
            return SharedNegativeListMutationResult(
                shared_set=self._resource_summary(shared_set_resource),
                removed=removed,
            )
        except GoogleAdsException as ex:
            _raise_google_ads_error(ex)

    def _ad_text_assets(self, assets: list[AdTextAssetInput]) -> list[AdTextAsset]:
        result: list[AdTextAsset] = []
        for asset_input in assets:
            asset = AdTextAsset(text=asset_input.text)
            if asset_input.pin_position:
                asset.pinned_field = self._enum_value(
                    served_asset_field_type.ServedAssetFieldTypeEnum.ServedAssetFieldType,
                    asset_input.pin_position,
                    "pin_position",
                )
            result.append(asset)
        return result

    def create_responsive_search_ad(
        self,
        ad_group: str,
        ad: ResponsiveSearchAdInput,
    ) -> AdMutationResult:
        try:
            ad_group_ad = self.client.get_type("AdGroupAd")
            ad_group_ad.ad_group = self._ad_group_resource(ad_group)
            ad_group_ad.status = self._enum_value(
                ad_group_ad_status.AdGroupAdStatusEnum.AdGroupAdStatus,
                ad.status,
                "ad status",
            )
            ad_group_ad.ad.final_urls.extend(ad.final_urls)
            ad_group_ad.ad.responsive_search_ad = ResponsiveSearchAdInfo(
                headlines=self._ad_text_assets(ad.headlines),
                descriptions=self._ad_text_assets(ad.descriptions),
                path1=ad.path1,
                path2=ad.path2,
            )

            op = self.client.get_type("AdGroupAdOperation")
            op.create = ad_group_ad
            response = self._mutate(
                "AdGroupAdService",
                "MutateAdGroupAdsRequest",
                "mutate_ad_group_ads",
                [op],
            )
            return AdMutationResult(
                ad_group_ad=self._resource_summary(response.results[0].resource_name, status=ad.status)
            )
        except GoogleAdsException as ex:
            _raise_google_ads_error(ex)

    def update_responsive_search_ad(
        self,
        ad_group_ad: str,
        *,
        ad: ResponsiveSearchAdInput | None = None,
        status: str | None = None,
    ) -> AdMutationResult:
        try:
            ad_group_ad_resource = self._require_resource_name(ad_group_ad, "ad_group_ad")
            if ad is not None:
                row = self._ad_group_ad_details(ad_group_ad_resource)
                replacement = ResponsiveSearchAdInput(
                    final_urls=ad.final_urls,
                    headlines=ad.headlines,
                    descriptions=ad.descriptions,
                    path1=ad.path1,
                    path2=ad.path2,
                    status=status or ad.status,
                )
                created = self.create_responsive_search_ad(row.ad_group.resource_name, replacement)
                remove_op = self.client.get_type("AdGroupAdOperation")
                remove_op.remove = ad_group_ad_resource
                self._mutate(
                    "AdGroupAdService",
                    "MutateAdGroupAdsRequest",
                    "mutate_ad_group_ads",
                    [remove_op],
                )
                return created

            ad_update = self.client.get_type("AdGroupAd")
            ad_update.resource_name = ad_group_ad_resource
            mask_paths: list[str] = []

            if status is not None:
                ad_update.status = self._enum_value(
                    ad_group_ad_status.AdGroupAdStatusEnum.AdGroupAdStatus,
                    status,
                    "ad status",
                )
                mask_paths.append("status")

            if not mask_paths:
                return AdMutationResult(ad_group_ad=self._resource_summary(ad_group_ad_resource))

            op = self.client.get_type("AdGroupAdOperation")
            op.update = ad_update
            op.update_mask = self._field_mask(*mask_paths)
            response = self._mutate(
                "AdGroupAdService",
                "MutateAdGroupAdsRequest",
                "mutate_ad_group_ads",
                [op],
            )
            return AdMutationResult(
                ad_group_ad=self._resource_summary(response.results[0].resource_name, status=status)
            )
        except GoogleAdsException as ex:
            _raise_google_ads_error(ex)

    def _create_campaign_asset(
        self,
        campaign: str,
        asset_resource_builder: callable,
        field_type_value: Any,
        *,
        asset_name: str | None = None,
    ) -> CampaignAssetMutationResult:
        campaign_resource = self._campaign_resource(campaign)

        asset = self.client.get_type("Asset")
        if asset_name:
            asset.name = asset_name
        asset_resource_builder(asset)

        asset_op = self.client.get_type("AssetOperation")
        asset_op.create = asset
        asset_response = self._mutate(
            "AssetService",
            "MutateAssetsRequest",
            "mutate_assets",
            [asset_op],
        )
        asset_result = asset_response.results[0]

        campaign_asset = self.client.get_type("CampaignAsset")
        campaign_asset.campaign = campaign_resource
        campaign_asset.asset = asset_result.resource_name
        campaign_asset.field_type = field_type_value

        campaign_asset_op = self.client.get_type("CampaignAssetOperation")
        campaign_asset_op.create = campaign_asset
        campaign_asset_response = self._mutate(
            "CampaignAssetService",
            "MutateCampaignAssetsRequest",
            "mutate_campaign_assets",
            [campaign_asset_op],
        )

        return CampaignAssetMutationResult(
            asset=self._resource_summary(asset_result.resource_name, name=asset_name),
            campaign_asset=self._resource_summary(campaign_asset_response.results[0].resource_name),
        )

    def create_campaign_sitelink_asset(
        self,
        campaign: str,
        sitelink: SitelinkAssetInput,
    ) -> CampaignAssetMutationResult:
        try:
            return self._create_campaign_asset(
                campaign,
                lambda asset: (
                    asset.final_urls.extend(sitelink.final_urls),
                    setattr(
                        asset,
                        "sitelink_asset",
                        SitelinkAsset(
                            link_text=sitelink.link_text,
                            description1=sitelink.description1,
                            description2=sitelink.description2,
                        ),
                    ),
                ),
                asset_field_type.AssetFieldTypeEnum.AssetFieldType.SITELINK,
                asset_name=sitelink.link_text,
            )
        except GoogleAdsException as ex:
            _raise_google_ads_error(ex)

    def create_campaign_callout_asset(
        self,
        campaign: str,
        callout: CalloutAssetInput,
    ) -> CampaignAssetMutationResult:
        try:
            return self._create_campaign_asset(
                campaign,
                lambda asset: setattr(asset, "callout_asset", CalloutAsset(callout_text=callout.callout_text)),
                asset_field_type.AssetFieldTypeEnum.AssetFieldType.CALLOUT,
                asset_name=callout.callout_text,
            )
        except GoogleAdsException as ex:
            _raise_google_ads_error(ex)

    def create_campaign_structured_snippet_asset(
        self,
        campaign: str,
        snippet: StructuredSnippetAssetInput,
    ) -> CampaignAssetMutationResult:
        try:
            return self._create_campaign_asset(
                campaign,
                lambda asset: setattr(
                    asset,
                    "structured_snippet_asset",
                    StructuredSnippetAsset(header=snippet.header, values=snippet.values),
                ),
                asset_field_type.AssetFieldTypeEnum.AssetFieldType.STRUCTURED_SNIPPET,
                asset_name=snippet.header,
            )
        except GoogleAdsException as ex:
            _raise_google_ads_error(ex)

    def create_campaign_call_asset(
        self,
        campaign: str,
        call_asset: CallAssetInput,
    ) -> CampaignAssetMutationResult:
        try:
            return self._create_campaign_asset(
                campaign,
                lambda asset: setattr(
                    asset,
                    "call_asset",
                    CallAsset(
                        country_code=call_asset.country_code,
                        phone_number=call_asset.phone_number,
                        call_conversion_reporting_state=self._enum_value(
                            call_conversion_reporting_state.CallConversionReportingStateEnum.CallConversionReportingState,
                            call_asset.call_conversion_reporting_state,
                            "call conversion reporting state",
                        ),
                        call_conversion_action=call_asset.call_conversion_action,
                    ),
                ),
                asset_field_type.AssetFieldTypeEnum.AssetFieldType.CALL,
                asset_name=call_asset.phone_number,
            )
        except GoogleAdsException as ex:
            _raise_google_ads_error(ex)

    def create_conversion_action(self, conversion: ConversionActionInput) -> ConversionActionMutationResult:
        try:
            action = self.client.get_type("ConversionAction")
            action.name = conversion.name
            action.category = self._enum_value(
                conversion_action_category.ConversionActionCategoryEnum.ConversionActionCategory,
                conversion.category,
                "conversion category",
            )
            action.type_ = self._enum_value(
                conversion_action_type.ConversionActionTypeEnum.ConversionActionType,
                conversion.type,
                "conversion type",
            )
            action.status = self._enum_value(
                conversion_action_status.ConversionActionStatusEnum.ConversionActionStatus,
                conversion.status,
                "conversion status",
            )
            action.include_in_conversions_metric = conversion.include_in_conversions_metric
            action.primary_for_goal = conversion.primary_for_goal
            if conversion.click_through_lookback_window_days is not None:
                action.click_through_lookback_window_days = conversion.click_through_lookback_window_days
            if conversion.view_through_lookback_window_days is not None:
                action.view_through_lookback_window_days = conversion.view_through_lookback_window_days
            if conversion.counting_type is not None:
                action.counting_type = self._enum_value(
                    conversion_action_counting_type.ConversionActionCountingTypeEnum.ConversionActionCountingType,
                    conversion.counting_type,
                    "conversion counting type",
                )
            if conversion.attribution_model is not None:
                action.attribution_model_settings.attribution_model = self._enum_value(
                    attribution_model.AttributionModelEnum.AttributionModel,
                    conversion.attribution_model,
                    "attribution model",
                )
            if conversion.value_settings is not None:
                if conversion.value_settings.default_value is not None:
                    action.value_settings.default_value = conversion.value_settings.default_value
                if conversion.value_settings.always_use_default_value is not None:
                    action.value_settings.always_use_default_value = (
                        conversion.value_settings.always_use_default_value
                    )

            op = self.client.get_type("ConversionActionOperation")
            op.create = action
            response = self._mutate(
                "ConversionActionService",
                "MutateConversionActionsRequest",
                "mutate_conversion_actions",
                [op],
            )
            result = response.results[0]
            snippets = [
                ConversionTagSnippet(
                    type=getattr(snippet.type_, "name", str(snippet.type_)),
                    page_format=getattr(snippet.page_format, "name", str(snippet.page_format)),
                    global_site_tag=snippet.global_site_tag or None,
                    event_snippet=snippet.event_snippet or None,
                )
                for snippet in getattr(result.conversion_action, "tag_snippets", [])
            ]
            return ConversionActionMutationResult(
                conversion_action=self._resource_summary(result.resource_name, status=conversion.status, name=conversion.name),
                tag_snippets=snippets,
            )
        except GoogleAdsException as ex:
            _raise_google_ads_error(ex)

    def update_conversion_action(
        self,
        conversion_action: str,
        conversion: ConversionActionInput,
    ) -> ConversionActionMutationResult:
        try:
            resource_name = self._conversion_action_resource(conversion_action)
            action = self.client.get_type("ConversionAction")
            action.resource_name = resource_name
            mask_paths: list[str] = []

            action.name = conversion.name
            mask_paths.append("name")
            action.category = self._enum_value(
                conversion_action_category.ConversionActionCategoryEnum.ConversionActionCategory,
                conversion.category,
                "conversion category",
            )
            mask_paths.append("category")
            action.status = self._enum_value(
                conversion_action_status.ConversionActionStatusEnum.ConversionActionStatus,
                conversion.status,
                "conversion status",
            )
            mask_paths.append("status")
            action.include_in_conversions_metric = conversion.include_in_conversions_metric
            mask_paths.append("include_in_conversions_metric")
            action.primary_for_goal = conversion.primary_for_goal
            mask_paths.append("primary_for_goal")

            if conversion.click_through_lookback_window_days is not None:
                action.click_through_lookback_window_days = conversion.click_through_lookback_window_days
                mask_paths.append("click_through_lookback_window_days")
            if conversion.view_through_lookback_window_days is not None:
                action.view_through_lookback_window_days = conversion.view_through_lookback_window_days
                mask_paths.append("view_through_lookback_window_days")
            if conversion.counting_type is not None:
                action.counting_type = self._enum_value(
                    conversion_action_counting_type.ConversionActionCountingTypeEnum.ConversionActionCountingType,
                    conversion.counting_type,
                    "conversion counting type",
                )
                mask_paths.append("counting_type")
            if conversion.attribution_model is not None:
                action.attribution_model_settings.attribution_model = self._enum_value(
                    attribution_model.AttributionModelEnum.AttributionModel,
                    conversion.attribution_model,
                    "attribution model",
                )
                mask_paths.append("attribution_model_settings.attribution_model")
            if conversion.value_settings is not None:
                if conversion.value_settings.default_value is not None:
                    action.value_settings.default_value = conversion.value_settings.default_value
                    mask_paths.append("value_settings.default_value")
                if conversion.value_settings.always_use_default_value is not None:
                    action.value_settings.always_use_default_value = (
                        conversion.value_settings.always_use_default_value
                    )
                    mask_paths.append("value_settings.always_use_default_value")

            op = self.client.get_type("ConversionActionOperation")
            op.update = action
            op.update_mask = self._field_mask(*mask_paths)
            response = self._mutate(
                "ConversionActionService",
                "MutateConversionActionsRequest",
                "mutate_conversion_actions",
                [op],
            )
            result = response.results[0]
            snippets = [
                ConversionTagSnippet(
                    type=getattr(snippet.type_, "name", str(snippet.type_)),
                    page_format=getattr(snippet.page_format, "name", str(snippet.page_format)),
                    global_site_tag=snippet.global_site_tag or None,
                    event_snippet=snippet.event_snippet or None,
                )
                for snippet in getattr(result.conversion_action, "tag_snippets", [])
            ]
            return ConversionActionMutationResult(
                conversion_action=self._resource_summary(resource_name, status=conversion.status, name=conversion.name),
                tag_snippets=snippets,
            )
        except GoogleAdsException as ex:
            _raise_google_ads_error(ex)

    def get_search_term_report(
        self,
        *,
        campaign: str | None = None,
        start_date: str | None = None,
        end_date: str | None = None,
        limit: int = 50,
    ) -> list[dict[str, Any]]:
        start_date, end_date = self._resolve_date_range(start_date, end_date)
        where_clauses = [f"segments.date BETWEEN {self._quote(start_date)} AND {self._quote(end_date)}"]
        if campaign:
            where_clauses.append(f"campaign.resource_name = {self._quote(self._campaign_resource(campaign))}")

        query = (
            "SELECT campaign_search_term_view.search_term, "
            "campaign.id, campaign.name, metrics.clicks, metrics.impressions, metrics.ctr, "
            "metrics.average_cpc, metrics.cost_micros, metrics.conversions "
            "FROM campaign_search_term_view "
            f"WHERE {' AND '.join(where_clauses)} "
            "ORDER BY metrics.impressions DESC "
            f"LIMIT {limit}"
        )
        rows = self._search(query)
        return [
            {
                "search_term": row.campaign_search_term_view.search_term,
                "campaign_id": str(row.campaign.id),
                "campaign_name": row.campaign.name,
                "clicks": row.metrics.clicks,
                "impressions": row.metrics.impressions,
                "ctr": row.metrics.ctr,
                "average_cpc_micros": row.metrics.average_cpc,
                "cost_micros": row.metrics.cost_micros,
                "conversions": row.metrics.conversions,
            }
            for row in rows
        ]

    def get_performance_report(
        self,
        *,
        level: str,
        campaign: str | None = None,
        ad_group: str | None = None,
        start_date: str | None = None,
        end_date: str | None = None,
        limit: int = 100,
    ) -> list[dict[str, Any]]:
        start_date, end_date = self._resolve_date_range(start_date, end_date)
        where_clauses = [f"segments.date BETWEEN {self._quote(start_date)} AND {self._quote(end_date)}"]
        if campaign:
            where_clauses.append(f"campaign.resource_name = {self._quote(self._campaign_resource(campaign))}")
        if ad_group:
            where_clauses.append(f"ad_group.resource_name = {self._quote(self._ad_group_resource(ad_group))}")

        if level == "campaign":
            query = (
                "SELECT campaign.id, campaign.name, campaign.status, metrics.clicks, metrics.impressions, "
                "metrics.ctr, metrics.average_cpc, metrics.cost_micros, metrics.conversions "
                "FROM campaign "
                f"WHERE {' AND '.join(where_clauses)} "
                "ORDER BY metrics.impressions DESC "
                f"LIMIT {limit}"
            )
            rows = self._search(query)
            return [
                {
                    "level": "campaign",
                    "id": str(row.campaign.id),
                    "name": row.campaign.name,
                    "status": getattr(row.campaign.status, "name", str(row.campaign.status)),
                    "clicks": row.metrics.clicks,
                    "impressions": row.metrics.impressions,
                    "ctr": row.metrics.ctr,
                    "average_cpc_micros": row.metrics.average_cpc,
                    "cost_micros": row.metrics.cost_micros,
                    "conversions": row.metrics.conversions,
                }
                for row in rows
            ]

        if level == "ad_group":
            query = (
                "SELECT campaign.id, campaign.name, ad_group.id, ad_group.name, ad_group.status, "
                "metrics.clicks, metrics.impressions, metrics.ctr, metrics.average_cpc, "
                "metrics.cost_micros, metrics.conversions "
                "FROM ad_group "
                f"WHERE {' AND '.join(where_clauses)} "
                "ORDER BY metrics.impressions DESC "
                f"LIMIT {limit}"
            )
            rows = self._search(query)
            return [
                {
                    "level": "ad_group",
                    "campaign_id": str(row.campaign.id),
                    "campaign_name": row.campaign.name,
                    "id": str(row.ad_group.id),
                    "name": row.ad_group.name,
                    "status": getattr(row.ad_group.status, "name", str(row.ad_group.status)),
                    "clicks": row.metrics.clicks,
                    "impressions": row.metrics.impressions,
                    "ctr": row.metrics.ctr,
                    "average_cpc_micros": row.metrics.average_cpc,
                    "cost_micros": row.metrics.cost_micros,
                    "conversions": row.metrics.conversions,
                }
                for row in rows
            ]

        if level != "keyword":
            raise ValueError(f"Unsupported report level: {level}")

        query = (
            "SELECT campaign.id, campaign.name, ad_group.id, ad_group.name, "
            "ad_group_criterion.criterion_id, ad_group_criterion.keyword.text, "
            "ad_group_criterion.keyword.match_type, ad_group_criterion.status, "
            "ad_group_criterion.cpc_bid_micros, metrics.clicks, metrics.impressions, "
            "metrics.ctr, metrics.average_cpc, metrics.cost_micros, metrics.conversions "
            "FROM keyword_view "
            f"WHERE {' AND '.join(where_clauses)} "
            "ORDER BY metrics.impressions DESC "
            f"LIMIT {limit}"
        )
        rows = self._search(query)
        return [
            {
                "level": "keyword",
                "campaign_id": str(row.campaign.id),
                "campaign_name": row.campaign.name,
                "ad_group_id": str(row.ad_group.id),
                "ad_group_name": row.ad_group.name,
                "id": str(row.ad_group_criterion.criterion_id),
                "keyword": row.ad_group_criterion.keyword.text,
                "match_type": getattr(
                    row.ad_group_criterion.keyword.match_type,
                    "name",
                    str(row.ad_group_criterion.keyword.match_type),
                ),
                "status": getattr(row.ad_group_criterion.status, "name", str(row.ad_group_criterion.status)),
                "bid_micros": row.ad_group_criterion.cpc_bid_micros,
                "clicks": row.metrics.clicks,
                "impressions": row.metrics.impressions,
                "ctr": row.metrics.ctr,
                "average_cpc_micros": row.metrics.average_cpc,
                "cost_micros": row.metrics.cost_micros,
                "conversions": row.metrics.conversions,
            }
            for row in rows
        ]

    def _resolve_date_range(self, start_date: str | None, end_date: str | None) -> tuple[str, str]:
        if start_date and end_date:
            return start_date, end_date
        today = date.today()
        resolved_end = end_date or today.isoformat()
        resolved_start = start_date or (today - timedelta(days=30)).isoformat()
        return resolved_start, resolved_end


GoogleAdsKeywordClient = GoogleAdsMCPClient


def _format_google_ads_error(ex: GoogleAdsException) -> dict:
    errors = []
    for error in ex.failure.errors:
        errors.append(
            {
                "message": error.message,
                "error_code": str(error.error_code),
            }
        )
    logger.error("Google Ads API error: %s", errors)
    return {"error": f"Google Ads API error: {errors[0]['message']}", "details": errors}


def _raise_google_ads_error(ex: GoogleAdsException):
    error = _format_google_ads_error(ex)
    raise ValueError(error["error"])

"""Typed MCP request and response models for Google Ads operations."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


class MCPModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class NetworkSettingsInput(MCPModel):
    target_google_search: bool = True
    target_search_network: bool = False
    target_content_network: bool = False
    target_partner_search_network: bool = False


class BiddingStrategyInput(MCPModel):
    strategy_type: Literal["MANUAL_CPC", "MAXIMIZE_CLICKS", "TARGET_CPA"]
    max_cpc_bid: float | None = Field(default=None, gt=0)
    target_cpa: float | None = Field(default=None, gt=0)
    enhanced_cpc_enabled: bool = False

    @model_validator(mode="after")
    def validate_strategy(self) -> "BiddingStrategyInput":
        if self.strategy_type == "MAXIMIZE_CLICKS" and self.max_cpc_bid is None:
            raise ValueError("MAXIMIZE_CLICKS requires max_cpc_bid.")
        if self.strategy_type == "TARGET_CPA" and self.target_cpa is None:
            raise ValueError("TARGET_CPA requires target_cpa.")
        return self


class GeoTargetingInput(MCPModel):
    include_location_ids: list[str] = Field(default_factory=list)
    exclude_location_ids: list[str] = Field(default_factory=list)


MinuteOfHour = Literal["ZERO", "FIFTEEN", "THIRTY", "FORTY_FIVE"]
DayOfWeek = Literal[
    "MONDAY",
    "TUESDAY",
    "WEDNESDAY",
    "THURSDAY",
    "FRIDAY",
    "SATURDAY",
    "SUNDAY",
]


class AdScheduleEntryInput(MCPModel):
    day_of_week: DayOfWeek
    start_hour: int = Field(ge=0, le=23)
    start_minute: MinuteOfHour = "ZERO"
    end_hour: int = Field(ge=0, le=24)
    end_minute: MinuteOfHour = "ZERO"
    bid_modifier: float | None = Field(default=None, gt=0)

    @model_validator(mode="after")
    def validate_range(self) -> "AdScheduleEntryInput":
        start_total = self.start_hour * 60 + _minute_value(self.start_minute)
        end_total = self.end_hour * 60 + _minute_value(self.end_minute)
        if end_total <= start_total:
            raise ValueError("Ad schedule end time must be after start time.")
        return self


DeviceType = Literal["MOBILE", "DESKTOP", "TABLET"]


class DeviceBidAdjustmentInput(MCPModel):
    device: DeviceType
    bid_modifier: float = Field(gt=0)


KeywordStatus = Literal["ENABLED", "PAUSED"]
KeywordMatchType = Literal["BROAD", "PHRASE", "EXACT"]


class KeywordInput(MCPModel):
    text: str = Field(min_length=1)
    match_type: KeywordMatchType | None = None
    cpc_bid: float | None = Field(default=None, gt=0)
    status: KeywordStatus = "PAUSED"


class KeywordUpdateInput(MCPModel):
    keyword_criterion: str = Field(min_length=1)
    cpc_bid: float | None = Field(default=None, gt=0)
    status: KeywordStatus | None = None
    new_text: str | None = Field(default=None, min_length=1)
    new_match_type: KeywordMatchType | None = None


class NegativeKeywordInput(MCPModel):
    text: str = Field(min_length=1)
    match_type: KeywordMatchType | None = None


class NegativeKeywordUpdateInput(MCPModel):
    criterion: str = Field(min_length=1)
    new_text: str | None = Field(default=None, min_length=1)
    new_match_type: KeywordMatchType | None = None


ServedAssetField = Literal[
    "HEADLINE_1",
    "HEADLINE_2",
    "HEADLINE_3",
    "DESCRIPTION_1",
    "DESCRIPTION_2",
]


class AdTextAssetInput(MCPModel):
    text: str = Field(min_length=1)
    pin_position: ServedAssetField | None = None


AdEntityStatus = Literal["ENABLED", "PAUSED"]


class ResponsiveSearchAdInput(MCPModel):
    final_urls: list[str] = Field(min_length=1)
    headlines: list[AdTextAssetInput] = Field(min_length=3, max_length=15)
    descriptions: list[AdTextAssetInput] = Field(min_length=2, max_length=4)
    path1: str | None = Field(default=None, max_length=15)
    path2: str | None = Field(default=None, max_length=15)
    status: AdEntityStatus = "PAUSED"


class SitelinkAssetInput(MCPModel):
    link_text: str = Field(min_length=1)
    final_urls: list[str] = Field(min_length=1)
    description1: str | None = None
    description2: str | None = None


class CalloutAssetInput(MCPModel):
    callout_text: str = Field(min_length=1)


class StructuredSnippetAssetInput(MCPModel):
    header: str = Field(min_length=1)
    values: list[str] = Field(min_length=1)


CallConversionReportingState = Literal[
    "DISABLED",
    "USE_ACCOUNT_LEVEL_CALL_CONVERSION_ACTION",
    "USE_RESOURCE_LEVEL_CALL_CONVERSION_ACTION",
]


class CallAssetInput(MCPModel):
    country_code: str = Field(min_length=2, max_length=2)
    phone_number: str = Field(min_length=1)
    call_conversion_reporting_state: CallConversionReportingState = "DISABLED"
    call_conversion_action: str | None = None

    @model_validator(mode="after")
    def validate_call_conversion_action(self) -> "CallAssetInput":
        if (
            self.call_conversion_reporting_state == "USE_RESOURCE_LEVEL_CALL_CONVERSION_ACTION"
            and not self.call_conversion_action
        ):
            raise ValueError(
                "call_conversion_action is required when call_conversion_reporting_state "
                "is USE_RESOURCE_LEVEL_CALL_CONVERSION_ACTION."
            )
        return self


ConversionActionCategory = Literal["SIGNUP", "SUBSCRIBE_PAID"]
ConversionActionType = Literal["WEBPAGE"]
ConversionActionStatus = Literal["ENABLED", "HIDDEN"]
ConversionCountingType = Literal["ONE_PER_CLICK", "MANY_PER_CLICK"]
AttributionModel = Literal[
    "GOOGLE_ADS_LAST_CLICK",
    "GOOGLE_SEARCH_ATTRIBUTION_DATA_DRIVEN",
    "GOOGLE_SEARCH_ATTRIBUTION_FIRST_CLICK",
    "GOOGLE_SEARCH_ATTRIBUTION_LINEAR",
    "GOOGLE_SEARCH_ATTRIBUTION_POSITION_BASED",
    "GOOGLE_SEARCH_ATTRIBUTION_TIME_DECAY",
]


class ConversionValueSettingsInput(MCPModel):
    default_value: float | None = None
    always_use_default_value: bool | None = None


class ConversionActionInput(MCPModel):
    name: str = Field(min_length=1)
    category: ConversionActionCategory
    type: ConversionActionType = "WEBPAGE"
    status: ConversionActionStatus = "ENABLED"
    include_in_conversions_metric: bool = True
    primary_for_goal: bool = True
    click_through_lookback_window_days: int | None = Field(default=None, ge=1, le=90)
    view_through_lookback_window_days: int | None = Field(default=None, ge=1, le=30)
    counting_type: ConversionCountingType | None = None
    attribution_model: AttributionModel | None = None
    value_settings: ConversionValueSettingsInput | None = None


ReportLevel = Literal["campaign", "ad_group", "keyword"]


class ResourceSummary(MCPModel):
    resource_name: str
    id: str | None = None
    status: str | None = None
    name: str | None = None


class CampaignMutationResult(MCPModel):
    campaign: ResourceSummary
    budget: ResourceSummary | None = None
    geo_target_criteria: list[ResourceSummary] = Field(default_factory=list)


class TargetingMutationResult(MCPModel):
    campaign: ResourceSummary
    criteria: list[ResourceSummary] = Field(default_factory=list)


class AdGroupMutationResult(MCPModel):
    ad_group: ResourceSummary


class KeywordMutationResult(MCPModel):
    created: list[ResourceSummary] = Field(default_factory=list)
    updated: list[ResourceSummary] = Field(default_factory=list)
    removed: list[str] = Field(default_factory=list)
    replaced: list[ResourceSummary] = Field(default_factory=list)


class NegativeKeywordSummary(MCPModel):
    resource_name: str
    id: str | None = None
    text: str | None = None
    match_type: KeywordMatchType | None = None
    status: KeywordStatus | None = None


class NegativeKeywordMutationResult(MCPModel):
    campaign: ResourceSummary | None = None
    ad_group: ResourceSummary | None = None
    created: list[NegativeKeywordSummary] = Field(default_factory=list)
    updated: list[NegativeKeywordSummary] = Field(default_factory=list)
    removed: list[str] = Field(default_factory=list)
    replaced: list[NegativeKeywordSummary] = Field(default_factory=list)


class NegativeKeywordListResult(MCPModel):
    campaign: ResourceSummary | None = None
    ad_group: ResourceSummary | None = None
    shared_set: ResourceSummary | None = None
    criteria: list[NegativeKeywordSummary] = Field(default_factory=list)


class SharedNegativeListMutationResult(MCPModel):
    shared_set: ResourceSummary | None = None
    shared_criteria: list[ResourceSummary] = Field(default_factory=list)
    removed: list[str] = Field(default_factory=list)
    campaign_shared_sets: list[ResourceSummary] = Field(default_factory=list)


class SharedNegativeKeywordListSummary(MCPModel):
    shared_set: ResourceSummary
    scope: Literal["CAMPAIGN", "ACCOUNT"] | None = None
    keyword_count: int = 0
    campaign_count: int = 0
    account_level_attached: bool = False


class SharedNegativeKeywordListsResult(MCPModel):
    shared_sets: list[SharedNegativeKeywordListSummary] = Field(default_factory=list)


class AccountNegativeKeywordListResult(MCPModel):
    shared_set: ResourceSummary | None = None
    customer_negative_criterion: ResourceSummary | None = None
    removed: list[str] = Field(default_factory=list)


class AdMutationResult(MCPModel):
    ad_group_ad: ResourceSummary


class CampaignAssetMutationResult(MCPModel):
    asset: ResourceSummary
    campaign_asset: ResourceSummary


class ConversionTagSnippet(MCPModel):
    type: str | None = None
    page_format: str | None = None
    global_site_tag: str | None = None
    event_snippet: str | None = None


class ConversionActionMutationResult(MCPModel):
    conversion_action: ResourceSummary
    tag_snippets: list[ConversionTagSnippet] = Field(default_factory=list)


def _minute_value(minute: MinuteOfHour) -> int:
    return {
        "ZERO": 0,
        "FIFTEEN": 15,
        "THIRTY": 30,
        "FORTY_FIVE": 45,
    }[minute]


class StatusInput(MCPModel):
    status: Literal["ENABLED", "PAUSED"]


class SharedSetStatusInput(MCPModel):
    status: Literal["ENABLED"]

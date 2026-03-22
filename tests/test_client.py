from __future__ import annotations

import unittest
from types import SimpleNamespace

from pydantic import ValidationError
from google.ads.googleads.v23.resources.types import (
    ad_group_ad as ad_group_ad_resource,
    ad_group_criterion as ad_group_criterion_resource,
    campaign as campaign_resource,
    campaign_budget as campaign_budget_resource,
    campaign_shared_set as campaign_shared_set_resource,
    campaign_criterion as campaign_criterion_resource,
    conversion_action as conversion_action_resource,
    customer_negative_criterion as customer_negative_criterion_resource,
    shared_criterion as shared_criterion_resource,
    shared_set as shared_set_resource,
)
from google.ads.googleads.v23.common.types import TagSnippet
from google.ads.googleads.v23.services.types import (
    ad_group_ad_service,
    ad_group_criterion_service,
    campaign_budget_service,
    campaign_shared_set_service,
    campaign_criterion_service,
    campaign_service,
    conversion_action_service,
    customer_negative_criterion_service,
    google_ads_service,
    shared_criterion_service,
    shared_set_service,
)

from google_ads_mcp.client import GoogleAdsMCPClient
from google_ads_mcp.config import GoogleAdsConfig
from google_ads_mcp.models import (
    AdTextAssetInput,
    BiddingStrategyInput,
    ConversionActionInput,
    DeviceBidAdjustmentInput,
    GeoTargetingInput,
    NegativeKeywordInput,
    NegativeKeywordUpdateInput,
    KeywordUpdateInput,
    ResponsiveSearchAdInput,
)


TYPE_MAP = {
    "AdGroupCriterion": ad_group_criterion_resource.AdGroupCriterion,
    "AdGroupAd": ad_group_ad_resource.AdGroupAd,
    "AdGroupAdOperation": ad_group_ad_service.AdGroupAdOperation,
    "AdGroupCriterionOperation": ad_group_criterion_service.AdGroupCriterionOperation,
    "Campaign": campaign_resource.Campaign,
    "CampaignBudget": campaign_budget_resource.CampaignBudget,
    "CampaignBudgetOperation": campaign_budget_service.CampaignBudgetOperation,
    "CampaignSharedSet": campaign_shared_set_resource.CampaignSharedSet,
    "CampaignSharedSetOperation": campaign_shared_set_service.CampaignSharedSetOperation,
    "CampaignCriterion": campaign_criterion_resource.CampaignCriterion,
    "CampaignCriterionOperation": campaign_criterion_service.CampaignCriterionOperation,
    "CampaignOperation": campaign_service.CampaignOperation,
    "ConversionAction": conversion_action_resource.ConversionAction,
    "ConversionActionOperation": conversion_action_service.ConversionActionOperation,
    "CustomerNegativeCriterion": customer_negative_criterion_resource.CustomerNegativeCriterion,
    "CustomerNegativeCriterionOperation": customer_negative_criterion_service.CustomerNegativeCriterionOperation,
    "MutateAdGroupCriteriaRequest": ad_group_criterion_service.MutateAdGroupCriteriaRequest,
    "MutateAdGroupAdsRequest": ad_group_ad_service.MutateAdGroupAdsRequest,
    "MutateCampaignBudgetsRequest": campaign_budget_service.MutateCampaignBudgetsRequest,
    "MutateCampaignSharedSetsRequest": campaign_shared_set_service.MutateCampaignSharedSetsRequest,
    "MutateCampaignCriteriaRequest": campaign_criterion_service.MutateCampaignCriteriaRequest,
    "MutateCampaignsRequest": campaign_service.MutateCampaignsRequest,
    "MutateConversionActionsRequest": conversion_action_service.MutateConversionActionsRequest,
    "MutateCustomerNegativeCriteriaRequest": customer_negative_criterion_service.MutateCustomerNegativeCriteriaRequest,
    "MutateSharedCriteriaRequest": shared_criterion_service.MutateSharedCriteriaRequest,
    "MutateSharedSetsRequest": shared_set_service.MutateSharedSetsRequest,
    "SearchGoogleAdsRequest": google_ads_service.SearchGoogleAdsRequest,
    "SharedCriterion": shared_criterion_resource.SharedCriterion,
    "SharedCriterionOperation": shared_criterion_service.SharedCriterionOperation,
    "SharedSet": shared_set_resource.SharedSet,
    "SharedSetOperation": shared_set_service.SharedSetOperation,
}


class FakeService:
    def __init__(self):
        self.calls: list[tuple[str, object]] = []
        self.responses: dict[str, list[object]] = {}

    def queue(self, method_name: str, response: object):
        self.responses.setdefault(method_name, []).append(response)

    def __getattr__(self, method_name: str):
        def handler(*, request):
            self.calls.append((method_name, request))
            if method_name not in self.responses or not self.responses[method_name]:
                raise AssertionError(f"No queued response for {method_name}")
            return self.responses[method_name].pop(0)

        return handler


class FakeGoogleAdsClient:
    def __init__(self, services: dict[str, FakeService]):
        self.services = services
        self.enums = SimpleNamespace(KeywordPlanNetworkEnum=SimpleNamespace(GOOGLE_SEARCH=1))

    def get_service(self, name: str):
        return self.services[name]

    def get_type(self, name: str):
        message_cls = TYPE_MAP.get(name)
        if message_cls is None:
            raise KeyError(name)
        return message_cls()


def make_client(fake_google_ads_client: FakeGoogleAdsClient) -> GoogleAdsMCPClient:
    config = GoogleAdsConfig(
        developer_token="dev",
        client_id="client",
        client_secret="secret",
        refresh_token="refresh",
        customer_id="1234567890",
    )
    return GoogleAdsMCPClient(config, google_ads_client=fake_google_ads_client)


class GoogleAdsClientTests(unittest.TestCase):
    def test_create_search_campaign_builds_budget_campaign_and_geo_requests(self):
        budget_service = FakeService()
        campaign_service_fake = FakeService()
        campaign_criterion_service_fake = FakeService()
        google_ads_service_fake = FakeService()

        budget_service.queue(
            "mutate_campaign_budgets",
            campaign_budget_service.MutateCampaignBudgetsResponse(
                results=[
                    campaign_budget_service.MutateCampaignBudgetResult(
                        resource_name="customers/1234567890/campaignBudgets/111",
                        campaign_budget=campaign_budget_resource.CampaignBudget(name="Brand Budget"),
                    )
                ]
            ),
        )
        campaign_service_fake.queue(
            "mutate_campaigns",
            campaign_service.MutateCampaignsResponse(
                results=[
                    campaign_service.MutateCampaignResult(
                        resource_name="customers/1234567890/campaigns/222",
                        campaign=campaign_resource.Campaign(name="Brand Search"),
                    )
                ]
            ),
        )
        google_ads_service_fake.queue("search", [])
        campaign_criterion_service_fake.queue(
            "mutate_campaign_criteria",
            campaign_criterion_service.MutateCampaignCriteriaResponse(
                results=[
                    campaign_criterion_service.MutateCampaignCriterionResult(
                        resource_name="customers/1234567890/campaignCriteria/222~1"
                    ),
                    campaign_criterion_service.MutateCampaignCriterionResult(
                        resource_name="customers/1234567890/campaignCriteria/222~2"
                    ),
                ]
            ),
        )

        client = make_client(
            FakeGoogleAdsClient(
                {
                    "CampaignBudgetService": budget_service,
                    "CampaignService": campaign_service_fake,
                    "CampaignCriterionService": campaign_criterion_service_fake,
                    "GoogleAdsService": google_ads_service_fake,
                }
            )
        )

        result = client.create_search_campaign(
            name="Brand Search",
            daily_budget=75.0,
            bidding_strategy=BiddingStrategyInput(strategy_type="MAXIMIZE_CLICKS", max_cpc_bid=3.25),
            geo_targets=GeoTargetingInput(include_location_ids=["2840"], exclude_location_ids=["2036"]),
        )

        budget_request = budget_service.calls[0][1]
        self.assertEqual(
            budget_request.operations[0].create.amount_micros,
            75_000_000,
        )

        campaign_request = campaign_service_fake.calls[0][1]
        campaign = campaign_request.operations[0].create
        self.assertEqual(campaign.name, "Brand Search")
        self.assertEqual(campaign.campaign_budget, "customers/1234567890/campaignBudgets/111")
        self.assertTrue(campaign.network_settings.target_google_search)
        self.assertEqual(campaign.target_spend.cpc_bid_ceiling_micros, 3_250_000)

        geo_request = campaign_criterion_service_fake.calls[0][1]
        self.assertEqual(len(geo_request.operations), 2)
        self.assertFalse(geo_request.operations[0].create.negative)
        self.assertTrue(geo_request.operations[1].create.negative)

        self.assertEqual(result.campaign.resource_name, "customers/1234567890/campaigns/222")
        self.assertEqual(len(result.geo_target_criteria), 2)

    def test_update_keywords_replaces_keyword_when_text_changes(self):
        ad_group_criterion_service_fake = FakeService()
        google_ads_service_fake = FakeService()

        google_ads_service_fake.queue(
            "search",
            [
                SimpleNamespace(
                    ad_group=SimpleNamespace(resource_name="customers/1234567890/adGroups/555"),
                    ad_group_criterion=SimpleNamespace(
                        cpc_bid_micros=1_400_000,
                        status=SimpleNamespace(name="ENABLED"),
                        keyword=SimpleNamespace(text="old keyword", match_type=SimpleNamespace(name="BROAD")),
                    ),
                )
            ],
        )
        ad_group_criterion_service_fake.queue(
            "mutate_ad_group_criteria",
            ad_group_criterion_service.MutateAdGroupCriteriaResponse(results=[]),
        )
        ad_group_criterion_service_fake.queue(
            "mutate_ad_group_criteria",
            ad_group_criterion_service.MutateAdGroupCriteriaResponse(
                results=[
                    ad_group_criterion_service.MutateAdGroupCriterionResult(
                        resource_name="customers/1234567890/adGroupCriteria/555~999"
                    )
                ]
            ),
        )

        client = make_client(
            FakeGoogleAdsClient(
                {
                    "AdGroupCriterionService": ad_group_criterion_service_fake,
                    "GoogleAdsService": google_ads_service_fake,
                }
            )
        )

        result = client.update_keywords(
            [
                KeywordUpdateInput(
                    keyword_criterion="customers/1234567890/adGroupCriteria/555~123",
                    new_text="new keyword",
                    new_match_type="EXACT",
                    cpc_bid=2.2,
                    status="PAUSED",
                )
            ]
        )

        remove_request = ad_group_criterion_service_fake.calls[0][1]
        create_request = ad_group_criterion_service_fake.calls[1][1]

        self.assertEqual(
            remove_request.operations[0].remove,
            "customers/1234567890/adGroupCriteria/555~123",
        )
        created_keyword = create_request.operations[0].create
        self.assertEqual(created_keyword.ad_group, "customers/1234567890/adGroups/555")
        self.assertEqual(created_keyword.keyword.text, "new keyword")
        self.assertEqual(created_keyword.cpc_bid_micros, 2_200_000)
        self.assertEqual(len(result.replaced), 1)

    def test_create_conversion_action_returns_tag_snippets(self):
        conversion_action_service_fake = FakeService()
        conversion_action_service_fake.queue(
            "mutate_conversion_actions",
            conversion_action_service.MutateConversionActionsResponse(
                results=[
                    conversion_action_service.MutateConversionActionResult(
                        resource_name="customers/1234567890/conversionActions/444",
                        conversion_action=conversion_action_resource.ConversionAction(
                            tag_snippets=[
                                TagSnippet(
                                    global_site_tag="<script>gst</script>",
                                    event_snippet="<script>event</script>",
                                )
                            ]
                        ),
                    )
                ]
            ),
        )

        client = make_client(
            FakeGoogleAdsClient({"ConversionActionService": conversion_action_service_fake})
        )

        result = client.create_conversion_action(
            ConversionActionInput(name="Trial Signup", category="SIGNUP")
        )

        request = conversion_action_service_fake.calls[0][1]
        created = request.operations[0].create
        self.assertEqual(created.name, "Trial Signup")
        self.assertEqual(result.conversion_action.resource_name, "customers/1234567890/conversionActions/444")
        self.assertEqual(result.tag_snippets[0].global_site_tag, "<script>gst</script>")

    def test_get_performance_report_keyword_level_returns_rows(self):
        google_ads_service_fake = FakeService()
        google_ads_service_fake.queue(
            "search",
            [
                SimpleNamespace(
                    campaign=SimpleNamespace(id=222, name="Brand Search"),
                    ad_group=SimpleNamespace(id=555, name="Core Terms"),
                    ad_group_criterion=SimpleNamespace(
                        resource_name="customers/1234567890/adGroupCriteria/555~999",
                        criterion_id=999,
                        keyword=SimpleNamespace(text="crm software", match_type=SimpleNamespace(name="PHRASE")),
                        status=SimpleNamespace(name="ENABLED"),
                        cpc_bid_micros=2_100_000,
                    ),
                    metrics=SimpleNamespace(
                        clicks=12,
                        impressions=100,
                        ctr=0.12,
                        average_cpc=1_950_000,
                        cost_micros=23_400_000,
                        conversions=2.5,
                    ),
                )
            ],
        )

        client = make_client(FakeGoogleAdsClient({"GoogleAdsService": google_ads_service_fake}))
        rows = client.get_performance_report(level="keyword")
        request = google_ads_service_fake.calls[0][1]

        self.assertEqual(rows[0]["keyword"], "crm software")
        self.assertEqual(rows[0]["match_type"], "PHRASE")
        self.assertEqual(rows[0]["bid_micros"], 2_100_000)
        self.assertEqual(rows[0]["criterion_id"], "999")
        self.assertEqual(rows[0]["resource_name"], "customers/1234567890/adGroupCriteria/555~999")
        self.assertIn("ad_group_criterion.resource_name", request.query)

    def test_get_search_term_report_filters_by_ad_group_and_returns_keyword_context(self):
        google_ads_service_fake = FakeService()
        google_ads_service_fake.queue(
            "search",
            [
                SimpleNamespace(
                    search_term_view=SimpleNamespace(search_term="crm software for startups"),
                    campaign=SimpleNamespace(id=222, name="Brand Search"),
                    ad_group=SimpleNamespace(id=555, name="Core Terms"),
                    segments=SimpleNamespace(keyword=SimpleNamespace(info=SimpleNamespace(text="crm software"))),
                    metrics=SimpleNamespace(
                        clicks=12,
                        impressions=100,
                        ctr=0.12,
                        average_cpc=1_950_000,
                        cost_micros=23_400_000,
                        conversions=2.5,
                    ),
                )
            ],
        )

        client = make_client(FakeGoogleAdsClient({"GoogleAdsService": google_ads_service_fake}))
        rows = client.get_search_term_report(campaign="222", ad_group="555")
        request = google_ads_service_fake.calls[0][1]

        self.assertEqual(rows[0]["search_term"], "crm software for startups")
        self.assertEqual(rows[0]["campaign_name"], "Brand Search")
        self.assertEqual(rows[0]["ad_group_name"], "Core Terms")
        self.assertEqual(rows[0]["keyword"], "crm software")
        self.assertIn("FROM search_term_view", request.query)
        self.assertIn("ad_group.resource_name = 'customers/1234567890/adGroups/555'", request.query)
        self.assertIn("segments.keyword.info.text", request.query)

    def test_set_campaign_device_bid_adjustments_updates_existing_device_criteria(self):
        campaign_criterion_service_fake = FakeService()
        google_ads_service_fake = FakeService()
        google_ads_service_fake.queue(
            "search",
            [
                SimpleNamespace(
                    campaign_criterion=SimpleNamespace(
                        resource_name="customers/1234567890/campaignCriteria/777~30001",
                        device=SimpleNamespace(type=SimpleNamespace(name="MOBILE")),
                    )
                ),
                SimpleNamespace(
                    campaign_criterion=SimpleNamespace(
                        resource_name="customers/1234567890/campaignCriteria/777~30000",
                        device=SimpleNamespace(type=SimpleNamespace(name="DESKTOP")),
                    )
                ),
            ],
        )
        campaign_criterion_service_fake.queue(
            "mutate_campaign_criteria",
            campaign_criterion_service.MutateCampaignCriteriaResponse(
                results=[
                    campaign_criterion_service.MutateCampaignCriterionResult(
                        resource_name="customers/1234567890/campaignCriteria/777~30001"
                    ),
                    campaign_criterion_service.MutateCampaignCriterionResult(
                        resource_name="customers/1234567890/campaignCriteria/777~30000"
                    ),
                ]
            ),
        )

        client = make_client(
            FakeGoogleAdsClient(
                {
                    "CampaignCriterionService": campaign_criterion_service_fake,
                    "GoogleAdsService": google_ads_service_fake,
                }
            )
        )

        result = client.set_campaign_device_bid_adjustments(
            "customers/1234567890/campaigns/777",
            [
                DeviceBidAdjustmentInput(device="MOBILE", bid_modifier=1.15),
                DeviceBidAdjustmentInput(device="DESKTOP", bid_modifier=0.9),
            ],
        )

        request = campaign_criterion_service_fake.calls[0][1]
        self.assertEqual(request.operations[0].update.resource_name, "customers/1234567890/campaignCriteria/777~30001")
        self.assertEqual(request.operations[0].update_mask.paths, ["bid_modifier"])
        self.assertEqual(len(result.criteria), 2)

    def test_update_responsive_search_ad_replaces_creative(self):
        ad_group_ad_service_fake = FakeService()
        google_ads_service_fake = FakeService()
        google_ads_service_fake.queue(
            "search",
            [
                SimpleNamespace(
                    ad_group=SimpleNamespace(resource_name="customers/1234567890/adGroups/888"),
                    ad_group_ad=SimpleNamespace(resource_name="customers/1234567890/adGroupAds/888~111"),
                )
            ],
        )
        ad_group_ad_service_fake.queue(
            "mutate_ad_group_ads",
            ad_group_ad_service.MutateAdGroupAdsResponse(
                results=[
                    ad_group_ad_service.MutateAdGroupAdResult(
                        resource_name="customers/1234567890/adGroupAds/888~222"
                    )
                ]
            ),
        )
        ad_group_ad_service_fake.queue(
            "mutate_ad_group_ads",
            ad_group_ad_service.MutateAdGroupAdsResponse(results=[]),
        )

        client = make_client(
            FakeGoogleAdsClient(
                {
                    "AdGroupAdService": ad_group_ad_service_fake,
                    "GoogleAdsService": google_ads_service_fake,
                }
            )
        )

        result = client.update_responsive_search_ad(
            "customers/1234567890/adGroupAds/888~111",
            ad=ResponsiveSearchAdInput(
                final_urls=["https://www.example.com/"],
                headlines=[
                    AdTextAssetInput(text="Headline 1", pin_position="HEADLINE_1"),
                    AdTextAssetInput(text="Headline 2"),
                    AdTextAssetInput(text="Headline 3"),
                ],
                descriptions=[
                    AdTextAssetInput(text="Description 1"),
                    AdTextAssetInput(text="Description 2"),
                ],
                path1="crm",
                path2="sales",
                status="PAUSED",
            ),
        )

        create_request = ad_group_ad_service_fake.calls[0][1]
        remove_request = ad_group_ad_service_fake.calls[1][1]
        self.assertEqual(create_request.operations[0].create.ad_group, "customers/1234567890/adGroups/888")
        self.assertEqual(remove_request.operations[0].remove, "customers/1234567890/adGroupAds/888~111")
        self.assertEqual(result.ad_group_ad.resource_name, "customers/1234567890/adGroupAds/888~222")

    def test_add_negative_keywords_to_campaign_creates_negative_criteria(self):
        campaign_criterion_service_fake = FakeService()
        campaign_criterion_service_fake.queue(
            "mutate_campaign_criteria",
            campaign_criterion_service.MutateCampaignCriteriaResponse(
                results=[
                    campaign_criterion_service.MutateCampaignCriterionResult(
                        resource_name="customers/1234567890/campaignCriteria/222~9001"
                    ),
                    campaign_criterion_service.MutateCampaignCriterionResult(
                        resource_name="customers/1234567890/campaignCriteria/222~9002"
                    ),
                ]
            ),
        )

        client = make_client(FakeGoogleAdsClient({"CampaignCriterionService": campaign_criterion_service_fake}))

        result = client.add_negative_keywords_to_campaign(
            "customers/1234567890/campaigns/222",
            [
                NegativeKeywordInput(text="free trial"),
                NegativeKeywordInput(text="cheap", match_type="PHRASE"),
            ],
            default_match_type="EXACT",
        )

        request = campaign_criterion_service_fake.calls[0][1]
        first = request.operations[0].create
        second = request.operations[1].create
        self.assertTrue(first.negative)
        self.assertEqual(first.keyword.match_type.name, "EXACT")
        self.assertEqual(second.keyword.match_type.name, "PHRASE")
        self.assertEqual(first.status.name, "ENABLED")
        self.assertEqual(result.campaign.resource_name, "customers/1234567890/campaigns/222")
        self.assertEqual(result.created[0].text, "free trial")

    def test_list_negative_keywords_in_campaign_returns_keyword_details(self):
        google_ads_service_fake = FakeService()
        google_ads_service_fake.queue(
            "search",
            [
                SimpleNamespace(
                    campaign_criterion=SimpleNamespace(
                        resource_name="customers/1234567890/campaignCriteria/222~9001",
                        status=SimpleNamespace(name="PAUSED"),
                        keyword=SimpleNamespace(
                            text="free",
                            match_type=SimpleNamespace(name="PHRASE"),
                        ),
                    )
                )
            ],
        )

        client = make_client(FakeGoogleAdsClient({"GoogleAdsService": google_ads_service_fake}))
        result = client.list_negative_keywords_in_campaign("customers/1234567890/campaigns/222")

        self.assertEqual(result.campaign.resource_name, "customers/1234567890/campaigns/222")
        self.assertEqual(result.criteria[0].text, "free")
        self.assertEqual(result.criteria[0].match_type, "PHRASE")
        self.assertEqual(result.criteria[0].status, "PAUSED")

    def test_update_negative_keywords_in_campaign_replaces_when_text_changes(self):
        campaign_criterion_service_fake = FakeService()
        google_ads_service_fake = FakeService()
        google_ads_service_fake.queue(
            "search",
            [
                SimpleNamespace(
                    campaign=SimpleNamespace(resource_name="customers/1234567890/campaigns/222"),
                    campaign_criterion=SimpleNamespace(
                        status=SimpleNamespace(name="ENABLED"),
                        keyword=SimpleNamespace(
                            text="old keyword",
                            match_type=SimpleNamespace(name="BROAD"),
                        ),
                    ),
                )
            ],
        )
        campaign_criterion_service_fake.queue(
            "mutate_campaign_criteria",
            campaign_criterion_service.MutateCampaignCriteriaResponse(results=[]),
        )
        campaign_criterion_service_fake.queue(
            "mutate_campaign_criteria",
            campaign_criterion_service.MutateCampaignCriteriaResponse(
                results=[
                    campaign_criterion_service.MutateCampaignCriterionResult(
                        resource_name="customers/1234567890/campaignCriteria/222~9002"
                    )
                ]
            ),
        )

        client = make_client(
            FakeGoogleAdsClient(
                {
                    "CampaignCriterionService": campaign_criterion_service_fake,
                    "GoogleAdsService": google_ads_service_fake,
                }
            )
        )

        result = client.update_negative_keywords_in_campaign(
            [
                NegativeKeywordUpdateInput(
                    criterion="customers/1234567890/campaignCriteria/222~9001",
                    new_text="new keyword",
                    new_match_type="EXACT",
                )
            ]
        )

        remove_request = campaign_criterion_service_fake.calls[0][1]
        create_request = campaign_criterion_service_fake.calls[1][1]
        self.assertEqual(
            remove_request.operations[0].remove,
            "customers/1234567890/campaignCriteria/222~9001",
        )
        created_keyword = create_request.operations[0].create
        self.assertTrue(created_keyword.negative)
        self.assertEqual(created_keyword.keyword.text, "new keyword")
        self.assertEqual(created_keyword.keyword.match_type.name, "EXACT")
        self.assertEqual(result.replaced[0].status, "ENABLED")

    def test_remove_negative_keywords_from_campaign_removes_resources(self):
        campaign_criterion_service_fake = FakeService()
        campaign_criterion_service_fake.queue(
            "mutate_campaign_criteria",
            campaign_criterion_service.MutateCampaignCriteriaResponse(results=[]),
        )

        client = make_client(FakeGoogleAdsClient({"CampaignCriterionService": campaign_criterion_service_fake}))
        result = client.remove_negative_keywords_from_campaign(
            ["customers/1234567890/campaignCriteria/222~9001"]
        )

        request = campaign_criterion_service_fake.calls[0][1]
        self.assertEqual(
            request.operations[0].remove,
            "customers/1234567890/campaignCriteria/222~9001",
        )
        self.assertEqual(result.removed, ["customers/1234567890/campaignCriteria/222~9001"])

    def test_negative_keyword_input_rejects_bid_fields(self):
        with self.assertRaises(ValidationError):
            NegativeKeywordInput.model_validate({"text": "free", "cpc_bid": 1.5})

    def test_negative_keyword_update_input_rejects_status_field(self):
        with self.assertRaises(ValidationError):
            NegativeKeywordUpdateInput.model_validate(
                {"criterion": "customers/1234567890/campaignCriteria/222~9001", "status": "PAUSED"}
            )

    def test_add_negative_keywords_to_ad_group_creates_negative_criteria(self):
        ad_group_criterion_service_fake = FakeService()
        ad_group_criterion_service_fake.queue(
            "mutate_ad_group_criteria",
            ad_group_criterion_service.MutateAdGroupCriteriaResponse(
                results=[
                    ad_group_criterion_service.MutateAdGroupCriterionResult(
                        resource_name="customers/1234567890/adGroupCriteria/555~8001"
                    )
                ]
            ),
        )

        client = make_client(FakeGoogleAdsClient({"AdGroupCriterionService": ad_group_criterion_service_fake}))
        result = client.add_negative_keywords_to_ad_group(
            "customers/1234567890/adGroups/555",
            [NegativeKeywordInput(text="jobs")],
            default_match_type="PHRASE",
        )

        request = ad_group_criterion_service_fake.calls[0][1]
        created = request.operations[0].create
        self.assertTrue(created.negative)
        self.assertEqual(created.keyword.match_type.name, "PHRASE")
        self.assertEqual(result.ad_group.resource_name, "customers/1234567890/adGroups/555")

    def test_list_negative_keywords_in_ad_group_returns_keyword_details(self):
        google_ads_service_fake = FakeService()
        google_ads_service_fake.queue(
            "search",
            [
                SimpleNamespace(
                    ad_group_criterion=SimpleNamespace(
                        resource_name="customers/1234567890/adGroupCriteria/555~8001",
                        status=SimpleNamespace(name="ENABLED"),
                        keyword=SimpleNamespace(
                            text="support",
                            match_type=SimpleNamespace(name="EXACT"),
                        ),
                    )
                )
            ],
        )

        client = make_client(FakeGoogleAdsClient({"GoogleAdsService": google_ads_service_fake}))
        result = client.list_negative_keywords_in_ad_group("customers/1234567890/adGroups/555")

        self.assertEqual(result.ad_group.resource_name, "customers/1234567890/adGroups/555")
        self.assertEqual(result.criteria[0].text, "support")
        self.assertEqual(result.criteria[0].match_type, "EXACT")

    def test_update_negative_keywords_in_ad_group_replaces_when_match_type_changes(self):
        ad_group_criterion_service_fake = FakeService()
        google_ads_service_fake = FakeService()
        google_ads_service_fake.queue(
            "search",
            [
                SimpleNamespace(
                    ad_group=SimpleNamespace(resource_name="customers/1234567890/adGroups/555"),
                    ad_group_criterion=SimpleNamespace(
                        status=SimpleNamespace(name="ENABLED"),
                        keyword=SimpleNamespace(
                            text="old keyword",
                            match_type=SimpleNamespace(name="BROAD"),
                        ),
                    ),
                )
            ],
        )
        ad_group_criterion_service_fake.queue(
            "mutate_ad_group_criteria",
            ad_group_criterion_service.MutateAdGroupCriteriaResponse(results=[]),
        )
        ad_group_criterion_service_fake.queue(
            "mutate_ad_group_criteria",
            ad_group_criterion_service.MutateAdGroupCriteriaResponse(
                results=[
                    ad_group_criterion_service.MutateAdGroupCriterionResult(
                        resource_name="customers/1234567890/adGroupCriteria/555~8002"
                    )
                ]
            ),
        )

        client = make_client(
            FakeGoogleAdsClient(
                {
                    "AdGroupCriterionService": ad_group_criterion_service_fake,
                    "GoogleAdsService": google_ads_service_fake,
                }
            )
        )

        result = client.update_negative_keywords_in_ad_group(
            [
                NegativeKeywordUpdateInput(
                    criterion="customers/1234567890/adGroupCriteria/555~8001",
                    new_match_type="PHRASE",
                )
            ]
        )

        remove_request = ad_group_criterion_service_fake.calls[0][1]
        create_request = ad_group_criterion_service_fake.calls[1][1]
        self.assertEqual(
            remove_request.operations[0].remove,
            "customers/1234567890/adGroupCriteria/555~8001",
        )
        self.assertTrue(create_request.operations[0].create.negative)
        self.assertEqual(create_request.operations[0].create.keyword.match_type.name, "PHRASE")
        self.assertEqual(result.replaced[0].match_type, "PHRASE")

    def test_remove_negative_keywords_from_ad_group_removes_resources(self):
        ad_group_criterion_service_fake = FakeService()
        ad_group_criterion_service_fake.queue(
            "mutate_ad_group_criteria",
            ad_group_criterion_service.MutateAdGroupCriteriaResponse(results=[]),
        )

        client = make_client(FakeGoogleAdsClient({"AdGroupCriterionService": ad_group_criterion_service_fake}))
        result = client.remove_negative_keywords_from_ad_group(
            ["customers/1234567890/adGroupCriteria/555~8001"]
        )

        request = ad_group_criterion_service_fake.calls[0][1]
        self.assertEqual(
            request.operations[0].remove,
            "customers/1234567890/adGroupCriteria/555~8001",
        )
        self.assertEqual(result.removed, ["customers/1234567890/adGroupCriteria/555~8001"])

    def test_list_shared_negative_keyword_lists_returns_counts_and_account_attachment(self):
        google_ads_service_fake = FakeService()
        google_ads_service_fake.queue(
            "search",
            [
                SimpleNamespace(
                    shared_set=SimpleNamespace(
                        resource_name="customers/1234567890/sharedSets/321",
                        name="Brand Negatives",
                        status=SimpleNamespace(name="ENABLED"),
                        type=SimpleNamespace(name="NEGATIVE_KEYWORDS"),
                    )
                )
            ],
        )
        google_ads_service_fake.queue(
            "search",
            [
                SimpleNamespace(shared_criterion=SimpleNamespace(resource_name="customers/1234567890/sharedCriteria/321~1")),
                SimpleNamespace(shared_criterion=SimpleNamespace(resource_name="customers/1234567890/sharedCriteria/321~2")),
            ],
        )
        google_ads_service_fake.queue(
            "search",
            [
                SimpleNamespace(
                    campaign_shared_set=SimpleNamespace(
                        resource_name="customers/1234567890/campaignSharedSets/222~321"
                    )
                )
            ],
        )
        google_ads_service_fake.queue(
            "search",
            [
                SimpleNamespace(
                    customer_negative_criterion=SimpleNamespace(
                        resource_name="customers/1234567890/customerNegativeCriteria/77"
                    )
                )
            ],
        )

        client = make_client(FakeGoogleAdsClient({"GoogleAdsService": google_ads_service_fake}))
        result = client.list_shared_negative_keyword_lists()

        self.assertEqual(result.shared_sets[0].shared_set.name, "Brand Negatives")
        self.assertEqual(result.shared_sets[0].scope, "CAMPAIGN")
        self.assertEqual(result.shared_sets[0].keyword_count, 2)
        self.assertEqual(result.shared_sets[0].campaign_count, 1)
        self.assertTrue(result.shared_sets[0].account_level_attached)

    def test_list_keywords_in_shared_negative_list_returns_keyword_details(self):
        google_ads_service_fake = FakeService()
        google_ads_service_fake.queue(
            "search",
            [
                SimpleNamespace(
                    shared_criterion=SimpleNamespace(
                        resource_name="customers/1234567890/sharedCriteria/321~1",
                        keyword=SimpleNamespace(
                            text="free",
                            match_type=SimpleNamespace(name="BROAD"),
                        ),
                    )
                )
            ],
        )
        google_ads_service_fake.queue(
            "search",
            [
                SimpleNamespace(
                    shared_set=SimpleNamespace(
                        resource_name="customers/1234567890/sharedSets/321",
                        name="Brand Negatives",
                        status=SimpleNamespace(name="ENABLED"),
                    )
                )
            ],
        )

        client = make_client(FakeGoogleAdsClient({"GoogleAdsService": google_ads_service_fake}))
        result = client.list_keywords_in_shared_negative_list("customers/1234567890/sharedSets/321")

        self.assertEqual(result.shared_set.resource_name, "customers/1234567890/sharedSets/321")
        self.assertEqual(result.criteria[0].text, "free")

    def test_add_keywords_to_shared_negative_list_uses_default_match_type(self):
        shared_criterion_service_fake = FakeService()
        shared_criterion_service_fake.queue(
            "mutate_shared_criteria",
            shared_criterion_service.MutateSharedCriteriaResponse(
                results=[
                    shared_criterion_service.MutateSharedCriterionResult(
                        resource_name="customers/1234567890/sharedCriteria/321~1"
                    )
                ]
            ),
        )

        client = make_client(FakeGoogleAdsClient({"SharedCriterionService": shared_criterion_service_fake}))
        client.add_keywords_to_shared_negative_list(
            "customers/1234567890/sharedSets/321",
            ["discount"],
            default_match_type="PHRASE",
        )

        request = shared_criterion_service_fake.calls[0][1]
        self.assertEqual(request.operations[0].create.keyword.match_type.name, "PHRASE")

    def test_apply_shared_negative_keyword_list_to_account_creates_attachment(self):
        customer_negative_criterion_service_fake = FakeService()
        google_ads_service_fake = FakeService()
        google_ads_service_fake.queue(
            "search",
            [
                SimpleNamespace(
                    shared_set=SimpleNamespace(
                        resource_name="customers/1234567890/sharedSets/321",
                        name="Account Negatives",
                        status=SimpleNamespace(name="ENABLED"),
                        type=SimpleNamespace(name="ACCOUNT_LEVEL_NEGATIVE_KEYWORDS"),
                    )
                )
            ],
        )
        google_ads_service_fake.queue("search", [])
        google_ads_service_fake.queue(
            "search",
            [
                SimpleNamespace(
                    shared_set=SimpleNamespace(
                        resource_name="customers/1234567890/sharedSets/321",
                        name="Account Negatives",
                        status=SimpleNamespace(name="ENABLED"),
                    )
                )
            ],
        )
        customer_negative_criterion_service_fake.queue(
            "mutate_customer_negative_criteria",
            customer_negative_criterion_service.MutateCustomerNegativeCriteriaResponse(
                results=[
                    customer_negative_criterion_service.MutateCustomerNegativeCriteriaResult(
                        resource_name="customers/1234567890/customerNegativeCriteria/77"
                    )
                ]
            ),
        )

        client = make_client(
            FakeGoogleAdsClient(
                {
                    "CustomerNegativeCriterionService": customer_negative_criterion_service_fake,
                    "GoogleAdsService": google_ads_service_fake,
                }
            )
        )

        result = client.apply_shared_negative_keyword_list_to_account("customers/1234567890/sharedSets/321")

        request = customer_negative_criterion_service_fake.calls[0][1]
        self.assertEqual(
            request.operations[0].create.negative_keyword_list.shared_set,
            "customers/1234567890/sharedSets/321",
        )
        self.assertEqual(result.shared_set.name, "Account Negatives")
        self.assertEqual(
            result.customer_negative_criterion.resource_name,
            "customers/1234567890/customerNegativeCriteria/77",
        )

    def test_apply_shared_negative_keyword_list_to_account_replaces_existing_when_requested(self):
        customer_negative_criterion_service_fake = FakeService()
        google_ads_service_fake = FakeService()
        google_ads_service_fake.queue(
            "search",
            [
                SimpleNamespace(
                    shared_set=SimpleNamespace(
                        resource_name="customers/1234567890/sharedSets/321",
                        name="New Negatives",
                        status=SimpleNamespace(name="ENABLED"),
                        type=SimpleNamespace(name="ACCOUNT_LEVEL_NEGATIVE_KEYWORDS"),
                    )
                )
            ],
        )
        google_ads_service_fake.queue(
            "search",
            [
                SimpleNamespace(
                    customer_negative_criterion=SimpleNamespace(
                        resource_name="customers/1234567890/customerNegativeCriteria/55",
                        negative_keyword_list=SimpleNamespace(
                            shared_set="customers/1234567890/sharedSets/300"
                        ),
                    )
                )
            ],
        )
        google_ads_service_fake.queue(
            "search",
            [
                SimpleNamespace(
                    shared_set=SimpleNamespace(
                        resource_name="customers/1234567890/sharedSets/300",
                        name="Old Negatives",
                        status=SimpleNamespace(name="ENABLED"),
                        type=SimpleNamespace(name="ACCOUNT_LEVEL_NEGATIVE_KEYWORDS"),
                    )
                )
            ],
        )
        google_ads_service_fake.queue(
            "search",
            [
                SimpleNamespace(
                    shared_set=SimpleNamespace(
                        resource_name="customers/1234567890/sharedSets/321",
                        name="New Negatives",
                        status=SimpleNamespace(name="ENABLED"),
                        type=SimpleNamespace(name="ACCOUNT_LEVEL_NEGATIVE_KEYWORDS"),
                    )
                )
            ],
        )
        customer_negative_criterion_service_fake.queue(
            "mutate_customer_negative_criteria",
            customer_negative_criterion_service.MutateCustomerNegativeCriteriaResponse(results=[]),
        )
        customer_negative_criterion_service_fake.queue(
            "mutate_customer_negative_criteria",
            customer_negative_criterion_service.MutateCustomerNegativeCriteriaResponse(
                results=[
                    customer_negative_criterion_service.MutateCustomerNegativeCriteriaResult(
                        resource_name="customers/1234567890/customerNegativeCriteria/77"
                    )
                ]
            ),
        )

        client = make_client(
            FakeGoogleAdsClient(
                {
                    "CustomerNegativeCriterionService": customer_negative_criterion_service_fake,
                    "GoogleAdsService": google_ads_service_fake,
                }
            )
        )

        result = client.apply_shared_negative_keyword_list_to_account(
            "customers/1234567890/sharedSets/321",
            replace_existing=True,
        )

        remove_request = customer_negative_criterion_service_fake.calls[0][1]
        create_request = customer_negative_criterion_service_fake.calls[1][1]
        self.assertEqual(
            remove_request.operations[0].remove,
            "customers/1234567890/customerNegativeCriteria/55",
        )
        self.assertEqual(
            create_request.operations[0].create.negative_keyword_list.shared_set,
            "customers/1234567890/sharedSets/321",
        )
        self.assertEqual(result.removed, ["customers/1234567890/customerNegativeCriteria/55"])
        self.assertEqual(result.shared_set.name, "New Negatives")

    def test_remove_shared_negative_keyword_list_from_account_detaches_current_list(self):
        customer_negative_criterion_service_fake = FakeService()
        google_ads_service_fake = FakeService()
        google_ads_service_fake.queue(
            "search",
            [
                SimpleNamespace(
                    customer_negative_criterion=SimpleNamespace(
                        resource_name="customers/1234567890/customerNegativeCriteria/55",
                        negative_keyword_list=SimpleNamespace(
                            shared_set="customers/1234567890/sharedSets/321"
                        ),
                    )
                )
            ],
        )
        google_ads_service_fake.queue(
            "search",
            [
                SimpleNamespace(
                    shared_set=SimpleNamespace(
                        resource_name="customers/1234567890/sharedSets/321",
                        name="Account Negatives",
                        status=SimpleNamespace(name="ENABLED"),
                    )
                )
            ],
        )
        customer_negative_criterion_service_fake.queue(
            "mutate_customer_negative_criteria",
            customer_negative_criterion_service.MutateCustomerNegativeCriteriaResponse(results=[]),
        )

        client = make_client(
            FakeGoogleAdsClient(
                {
                    "CustomerNegativeCriterionService": customer_negative_criterion_service_fake,
                    "GoogleAdsService": google_ads_service_fake,
                }
            )
        )

        result = client.remove_shared_negative_keyword_list_from_account()

        request = customer_negative_criterion_service_fake.calls[0][1]
        self.assertEqual(
            request.operations[0].remove,
            "customers/1234567890/customerNegativeCriteria/55",
        )
        self.assertEqual(result.shared_set.name, "Account Negatives")
        self.assertEqual(result.removed, ["customers/1234567890/customerNegativeCriteria/55"])


if __name__ == "__main__":
    unittest.main()

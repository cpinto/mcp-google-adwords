from __future__ import annotations

import unittest
from types import SimpleNamespace

from google.ads.googleads.v23.resources.types import (
    ad_group_ad as ad_group_ad_resource,
    ad_group_criterion as ad_group_criterion_resource,
    campaign as campaign_resource,
    campaign_budget as campaign_budget_resource,
    campaign_criterion as campaign_criterion_resource,
    conversion_action as conversion_action_resource,
)
from google.ads.googleads.v23.common.types import TagSnippet
from google.ads.googleads.v23.services.types import (
    ad_group_ad_service,
    ad_group_criterion_service,
    campaign_budget_service,
    campaign_criterion_service,
    campaign_service,
    conversion_action_service,
    google_ads_service,
)

from google_ads_mcp.client import GoogleAdsMCPClient
from google_ads_mcp.config import GoogleAdsConfig
from google_ads_mcp.models import (
    AdTextAssetInput,
    BiddingStrategyInput,
    ConversionActionInput,
    DeviceBidAdjustmentInput,
    GeoTargetingInput,
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
    "CampaignCriterion": campaign_criterion_resource.CampaignCriterion,
    "CampaignCriterionOperation": campaign_criterion_service.CampaignCriterionOperation,
    "CampaignOperation": campaign_service.CampaignOperation,
    "ConversionAction": conversion_action_resource.ConversionAction,
    "ConversionActionOperation": conversion_action_service.ConversionActionOperation,
    "MutateAdGroupCriteriaRequest": ad_group_criterion_service.MutateAdGroupCriteriaRequest,
    "MutateAdGroupAdsRequest": ad_group_ad_service.MutateAdGroupAdsRequest,
    "MutateCampaignBudgetsRequest": campaign_budget_service.MutateCampaignBudgetsRequest,
    "MutateCampaignCriteriaRequest": campaign_criterion_service.MutateCampaignCriteriaRequest,
    "MutateCampaignsRequest": campaign_service.MutateCampaignsRequest,
    "MutateConversionActionsRequest": conversion_action_service.MutateConversionActionsRequest,
    "SearchGoogleAdsRequest": google_ads_service.SearchGoogleAdsRequest,
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

        self.assertEqual(rows[0]["keyword"], "crm software")
        self.assertEqual(rows[0]["match_type"], "PHRASE")
        self.assertEqual(rows[0]["bid_micros"], 2_100_000)

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


if __name__ == "__main__":
    unittest.main()

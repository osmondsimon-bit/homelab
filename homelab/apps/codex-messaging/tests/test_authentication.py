"""Verify subscription-only execution at account and process-environment boundaries."""

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from codex_messaging.authentication import AuthenticationRejected, require_subscription


class SubscriptionTests(unittest.TestCase):
    def test_an_api_account_cannot_start_work(self):
        with self.assertRaises(AuthenticationRejected) as rejected:
            require_subscription({"requiresOpenaiAuth": True, "account": {"type": "apiKey"}}, {})
        self.assertEqual(rejected.exception.code, "subscription_required")

    def test_exhausted_included_usage_cannot_fall_back_to_credits(self):
        account = {"requiresOpenaiAuth": True, "account": {"type": "chatgpt", "planType": "plus"}}
        usage = {"rateLimits": {"primary": {"usedPercent": 100}, "credits": {"hasCredits": True, "unlimited": False, "balance": "50"}}}
        with self.assertRaises(AuthenticationRejected) as rejected:
            require_subscription(account, usage)
        self.assertEqual(rejected.exception.code, "usage_exhausted")

    def test_missing_usage_information_is_not_permission_to_spend(self):
        account = {"requiresOpenaiAuth": True, "account": {"type": "chatgpt", "planType": "plus"}}
        with self.assertRaises(AuthenticationRejected) as rejected:
            require_subscription(account, {"rateLimits": {}})
        self.assertEqual(rejected.exception.code, "usage_unknown")

    def test_included_subscription_with_zero_credit_state_is_accepted(self):
        require_subscription(
            {"requiresOpenaiAuth": True, "account": {"type": "chatgpt", "planType": "plus"}},
            {"rateLimits": {"primary": {"usedPercent": 20}, "secondary": {"usedPercent": 30},
                            "credits": {"hasCredits": False, "unlimited": False, "balance": "0"}}},
        )
    def test_credit_entitlements_or_unknown_credit_state_require_local_review(self):
        account = {"requiresOpenaiAuth": True, "account": {"type": "chatgpt", "planType": "plus"}}
        for credits in [None, {}, {"hasCredits": True, "unlimited": False, "balance": "20"},
                        {"hasCredits": False, "unlimited": True, "balance": None},
                        {"hasCredits": False, "unlimited": False, "balance": "1"}]:
            with self.subTest(credits=credits), self.assertRaises(AuthenticationRejected):
                require_subscription(account, {"rateLimits": {"primary": {"usedPercent": 10}, "credits": credits}})

    def test_malformed_or_unmetered_accounts_cannot_start_work(self):
        for account in [None, "invalid", {"type": "chatgpt", "planType": "enterprise_cbp_usage_based"}]:
            with self.subTest(account=account), self.assertRaises(AuthenticationRejected):
                require_subscription({"requiresOpenaiAuth": True, "account": account},
                                     {"rateLimits": {"primary": {"usedPercent": 20}}})


if __name__ == "__main__":
    unittest.main()

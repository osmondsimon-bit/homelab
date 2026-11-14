"""Verify subscription-only execution at account and process-environment boundaries."""

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from codex_messaging.authentication import AuthenticationRejected, require_subscription, worker_environment


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

    def test_inherited_api_and_endpoint_overrides_are_rejected(self):
        for name in ["OPENAI_API_KEY", "CODEX_API_KEY", "CODEX_ACCESS_TOKEN", "OPENAI_BASE_URL", "ANTHROPIC_API_KEY", "HTTP_PROXY"]:
            with self.subTest(name=name), self.assertRaises(AuthenticationRejected) as rejected:
                worker_environment(Path("/var/lib/codex-messaging/worker"), {name: "fixture-only-value"})
            self.assertEqual(rejected.exception.code, "environment_override")

    def test_included_subscription_and_clean_worker_context_are_accepted(self):
        require_subscription(
            {"requiresOpenaiAuth": True, "account": {"type": "chatgpt", "planType": "plus"}},
            {"rateLimits": {"primary": {"usedPercent": 20}, "secondary": {"usedPercent": 30},
                            "credits": {"hasCredits": False, "unlimited": False, "balance": "0"}}},
        )
        environment = worker_environment(Path("/var/lib/codex-messaging/worker"), {
            "SSH_AUTH_SOCK": "/fixture/agent", "PATH": "/fixture/untrusted", "CUSTOM_VALUE": "fixture-only",
        })
        self.assertNotIn("SSH_AUTH_SOCK", environment)
        self.assertNotIn("CUSTOM_VALUE", environment)
        self.assertEqual(environment["PATH"], "/usr/bin:/bin")

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

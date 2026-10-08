# --- lepao-research-notice v1 (do not remove; see LICENSE) ---
# 乐跑协议研究（Lepao Research） · https://github.com/dan-cun/lepao3
# Copyright (c) 2026 dan-cun · 技术讨论 QQ 1224145544（仅作技术讨论，不提供代打卡）
# 许可证 LRL-1.0（乐跑研究协议 1.0）：仅供学习 · 不可牟利 · 再发布须署名引用原始仓库 · 声明不得删除
# 删除或篡改本块即依 LRL-1.0 第三条自动终止授权；衍生版须继续以 LRL-1.0 授权并标注修改说明。
# --- end lepao-research-notice ---
"""Fast, synthetic progress regressions. No windows, traffic, CA or proxy changes."""
import unittest
from types import SimpleNamespace
from unittest.mock import Mock
from desktop_progress import checked, login_required, login_saved, reviewed, signature, usable, submitted, mark_submitted


class ProgressTests(unittest.TestCase):
    def setUp(self):
        self.auth = SimpleNamespace(uid=901, token="synthetic-token", issued_at="synthetic-login-1", consumed_at="")
        self.platform = SimpleNamespace(checked_at={}, checked_login={}, required_login={}, previews={})
        self.bridge = SimpleNamespace(_dryrun_ok={}, _confirmation=None, _job={},
                                      _attempts={"today:901": {"record_id": "synthetic-record"}},
                                      _auth_fingerprint=lambda a: ("today", a.uid, a.token))

    def verify(self):
        self.platform.checked_at["a"] = 100
        self.platform.checked_login["a"] = signature(self.auth)
        self.bridge._dryrun_ok["a"] = self.bridge._auth_fingerprint(self.auth)

    def review(self):
        self.bridge._job.update(reviewed_member="a", reviewed_record="synthetic-record",
                                reviewed_login=signature(self.auth), reviewed_day="today")

    def test_startup_and_new_capture_require_check_without_erasing_attempt(self):
        self.assertFalse(checked(self.bridge, self.platform, "a", self.auth, 101))
        self.verify()
        self.review()
        self.bridge._confirmation = {"member": "a", "nonce": "synthetic"}
        login_required(self.bridge, self.platform, "a", self.auth)
        self.assertFalse(usable(self.platform, "a", self.auth))
        self.assertFalse(checked(self.bridge, self.platform, "a", self.auth, 101))
        self.assertIsNone(self.bridge._confirmation)
        self.assertFalse(self.bridge._job)
        self.assertEqual(self.bridge._attempts["today:901"]["record_id"], "synthetic-record")
        login_saved(self.bridge, self.platform, "a")
        self.assertTrue(usable(self.platform, "a", self.auth))
        self.assertFalse(checked(self.bridge, self.platform, "a", self.auth, 101))

    def test_same_token_new_login_invalidates_check(self):
        self.verify()
        self.assertTrue(checked(self.bridge, self.platform, "a", self.auth, 101))
        self.auth.issued_at = "synthetic-login-2"
        self.assertFalse(checked(self.bridge, self.platform, "a", self.auth, 101))

    def test_submission_is_current_session_login_day_account_and_record_scoped(self):
        self.assertFalse(submitted(self.bridge, self.platform, "a", self.auth, "synthetic-record"))
        mark_submitted(self.bridge, self.platform, "a", self.auth, "synthetic-record")
        self.assertTrue(submitted(self.bridge, self.platform, "a", self.auth, "synthetic-record"))
        self.assertFalse(submitted(self.bridge, self.platform, "b", self.auth, "synthetic-record"))
        self.assertFalse(submitted(self.bridge, self.platform, "a", self.auth, "other-record"))
        self.auth.consumed_at = "synthetic-consumed"
        self.assertTrue(submitted(self.bridge, self.platform, "a", self.auth, "synthetic-record"))
        self.auth.issued_at = "synthetic-login-2"
        self.assertFalse(submitted(self.bridge, self.platform, "a", self.auth, "synthetic-record"))
        mark_submitted(self.bridge, self.platform, "a", self.auth, "synthetic-record")
        self.bridge._auth_fingerprint = lambda a: ("tomorrow", a.uid, a.token)
        self.assertFalse(submitted(self.bridge, self.platform, "a", self.auth, "synthetic-record"))
        self.assertIn("today:901", self.bridge._attempts)

    def test_expiry_time_reversal_and_day_rollover(self):
        self.verify()
        self.assertTrue(checked(self.bridge, self.platform, "a", self.auth, 700))
        self.assertFalse(checked(self.bridge, self.platform, "a", self.auth, 701))
        self.assertFalse(checked(self.bridge, self.platform, "a", self.auth, 99))
        self.bridge._auth_fingerprint = lambda a: ("tomorrow", a.uid, a.token)
        self.assertFalse(checked(self.bridge, self.platform, "a", self.auth, 101))

    def test_consumed_login_is_not_acquired_or_checked_but_can_view_record(self):
        self.verify()
        self.review()
        self.auth.consumed_at = "synthetic-consumed"
        self.assertFalse(usable(self.platform, "a", self.auth))
        self.assertFalse(checked(self.bridge, self.platform, "a", self.auth, 101))
        self.assertTrue(reviewed(self.bridge, self.platform, "a", self.auth, "synthetic-record"))

    def test_review_is_login_day_and_record_scoped(self):
        self.review()
        self.assertTrue(reviewed(self.bridge, self.platform, "a", self.auth, "synthetic-record"))
        self.assertFalse(reviewed(self.bridge, self.platform, "a", self.auth, "new-record"))
        self.assertFalse(reviewed(self.bridge, self.platform, "other", self.auth, "synthetic-record"))
        self.auth.issued_at = "synthetic-login-2"
        self.assertFalse(reviewed(self.bridge, self.platform, "a", self.auth, "synthetic-record"))
        self.review()
        self.bridge._auth_fingerprint = lambda a: ("tomorrow", a.uid, a.token)
        self.assertFalse(reviewed(self.bridge, self.platform, "a", self.auth, "synthetic-record"))

    def test_invalidation_is_per_account(self):
        self.verify()
        self.platform.checked_at["b"] = 100
        self.platform.checked_login["b"] = signature(self.auth)
        self.bridge._dryrun_ok["b"] = self.bridge._auth_fingerprint(self.auth)
        login_required(self.bridge, self.platform, "a", self.auth)
        self.assertTrue(checked(self.bridge, self.platform, "b", self.auth, 101))

    def test_server_auth_error_invokes_invalidation_without_retry(self):
        from desktop_events import EventLog
        from desktop_jobs import ClientView
        from lepao.v3api import V3Error
        client = Mock()
        client.get_term_list.side_effect = V3Error(101, "synthetic expired")
        platform = SimpleNamespace(job_stop=Mock(is_set=lambda: False), job_kind="build", ui_events=EventLog(),
                                   invalidate_login=lambda: login_required(self.bridge, self.platform, "a", self.auth))
        self.verify()
        with self.assertRaises(V3Error):
            ClientView(client, platform).get_term_list()
        client.get_term_list.assert_called_once()
        self.assertFalse(usable(self.platform, "a", self.auth))
        self.assertFalse(self.bridge._dryrun_ok)


if __name__ == "__main__":
    unittest.main()

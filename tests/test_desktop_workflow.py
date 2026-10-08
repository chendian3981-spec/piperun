# --- lepao-research-notice v1 (do not remove; see LICENSE) ---
# 乐跑协议研究（Lepao Research） · https://github.com/dan-cun/lepao3
# Copyright (c) 2026 dan-cun · 技术讨论 QQ 1224145544（仅作技术讨论，不提供代打卡）
# 许可证 LRL-1.0（乐跑研究协议 1.0）：仅供学习 · 不可牟利 · 再发布须署名引用原始仓库 · 声明不得删除
# 删除或篡改本块即依 LRL-1.0 第三条自动终止授权；衍生版须继续以 LRL-1.0 授权并标注修改说明。
# --- end lepao-research-notice ---
"""Offline submission/observability tests: synthetic accounts, no live API or proxy mutation."""
import json
import os
import tempfile
import threading
import time
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from desktop_events import CODES, EventLog, classify
from desktop_progress import signature, mark_submitted
from desktop_gui import Controller, UserError
from desktop_jobs import ClientView, DesktopState, ProgressPipeline, run_pending, watch
from lepao.v3api import V3Error
from desktop_storage import atomic_json
from test_support import isolated_bridge


def fake_platform(directory):
    return Mock(directory=Path(directory), desktop=True, diagnostic_build="desktop-0.3.0-test",
                ui_events=EventLog(), job_stop=threading.Event(), job_kind="", write_started=False,
                checked_at={}, checked_login={}, required_login={}, previews={}, exit_event=threading.Event())


class NativeSubmissionTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.env = patch.dict(os.environ)
        self.env.start()
        self.bridge = isolated_bridge()
        self.platform = fake_platform(self.temp.name)
        self.bridge._platform = self.platform
        self.bridge._initialize(self.temp.name)
        self.bridge.set_diagnostic_mode(True)
        reg = self.bridge.AccountRegistry(self.bridge._config_path())
        reg.add("synthetic", "90001", uid=901)
        reg.acc("90001")["auth"]["token"] = "synthetic-offline-token"
        reg.persist()
        self.controller = Controller(self.bridge, self.platform)

    def tearDown(self):
        self.env.stop()
        self.temp.cleanup()

    def verified(self):
        auth = self.bridge.AuthState(self.bridge.AccountRegistry(self.bridge._config_path()), "90001")
        self.bridge._dryrun_ok["90001"] = self.bridge._auth_fingerprint(auth)
        self.platform.checked_at["90001"] = time.monotonic()
        self.platform.checked_login["90001"] = signature(auth)
        self.platform.previews["90001"] = {"distance": 2.1, "used_time": 700, "points": 500}

    def test_prepare_requires_fresh_current_credential_dryrun(self):
        with self.assertRaisesRegex(UserError, "E_DRYRUN"):
            self.controller.prepare_submission("90001")
        self.verified()
        self.platform.checked_at["90001"] -= 601
        with self.assertRaisesRegex(UserError, "E_DRYRUN"):
            self.controller.prepare_submission("90001")
        self.platform.startRun.assert_not_called()

    def test_display_refreshes_capture_and_login_but_preserves_today_record(self):
        from desktop_progress import login_required, login_saved
        self.verified()
        auth = self.bridge.AuthState(self.bridge.AccountRegistry(self.bridge._config_path()), "90001")
        key = self.bridge._attempt_key(auth)
        self.bridge._attempts[key] = {"record_id": "synthetic-record"}
        self.assertFalse(self.controller.snapshot()["members"][0]["submitted"])
        mark_submitted(self.bridge, self.platform, "90001", auth, "synthetic-record")
        self.assertTrue(self.controller.snapshot()["members"][0]["submitted"])
        self.assertTrue(self.controller.snapshot()["members"][0]["checked"])
        login_required(self.bridge, self.platform, "90001", auth)
        member = self.controller.snapshot()["members"][0]
        self.assertFalse(member["ready"])
        self.assertFalse(member["checked"])
        self.assertFalse(member["can_submit"])
        self.assertFalse(member["submitted"])
        login_saved(self.bridge, self.platform, "90001")
        member = self.controller.snapshot()["members"][0]
        self.assertTrue(member["ready"])
        self.assertFalse(member["checked"])
        self.assertTrue(member["attempted"])
        self.assertFalse(member["submitted"])
        self.assertFalse(member["can_submit"])
        self.assertEqual(self.bridge._attempts[key]["record_id"], "synthetic-record")

    def test_accepted_submission_stays_complete_when_followup_watch_fails(self):
        auth = self.bridge.AuthState(self.bridge.AccountRegistry(self.bridge._config_path()), "90001")
        key = self.bridge._attempt_key(auth)
        self.bridge._pending_run = ("90001", "submit", key)
        with patch("desktop_jobs.ProgressPipeline") as pipeline, patch("desktop_jobs.watch", side_effect=TimeoutError()):
            pipeline.return_value.run.return_value = ({"record_id": "synthetic-record"}, 0)
            run_pending(self.bridge, self.platform)
        member = self.controller.snapshot()["members"][0]
        self.assertTrue(member["submitted"])
        self.assertFalse(member["reviewed"])
        self.assertTrue(member["attempted"])
        self.assertFalse(member["can_submit"])

    def test_display_rejects_check_from_same_token_new_login(self):
        self.verified()
        reg = self.bridge.AccountRegistry(self.bridge._config_path())
        reg.acc("90001")["auth"]["issued_at"] = "synthetic-new-login"
        reg.persist()
        self.assertFalse(self.controller.snapshot()["members"][0]["checked"])
        with self.assertRaisesRegex(UserError, "E_DRYRUN"):
            self.controller.prepare_submission("90001")

    def test_explicit_ack_single_use_and_persist_before_start(self):
        self.verified()
        info = self.controller.prepare_submission("90001")
        self.assertIn("非实际运动", info["source"])
        self.assertTrue(self.bridge._diagnostic_mode)
        self.assertFalse(self.bridge._attempts)
        def launched():
            ledger = json.loads((Path(self.temp.name) / "mobile_jobs.json").read_text())
            self.assertEqual(len(ledger), 1)
        self.platform.startRun.side_effect = launched
        self.controller.submit_confirmation(info["nonce"], acknowledged=True)
        self.platform.startRun.assert_called_once()
        self.assertTrue(self.bridge._diagnostic_mode)
        with self.assertRaises(UserError):
            self.controller.submit_confirmation(info["nonce"], acknowledged=True)
        self.assertFalse(self.controller.snapshot()["members"][0]["can_submit"])

    def test_unchecked_or_invalid_or_expired_confirmation_never_launches(self):
        for kind in ("unchecked", "invalid", "expired", "cancelled"):
            with self.subTest(kind=kind):
                self.verified()
                info = self.controller.prepare_submission("90001")
                if kind == "expired":
                    self.controller.prepared["expires"] = time.monotonic() - 1
                if kind == "cancelled":
                    self.controller.cancel_confirmation()
                with self.assertRaisesRegex(UserError, "E_CONFIRM"):
                    self.controller.submit_confirmation("incorrect" if kind == "invalid" else info["nonce"], acknowledged=kind != "unchecked")
                self.assertTrue(self.bridge._diagnostic_mode)
                self.assertFalse(self.bridge._attempts)
        self.platform.startRun.assert_not_called()

    def test_token_rotation_and_consumption_invalidate_confirmation(self):
        for consumed in (False, True):
            with self.subTest(consumed=consumed):
                self.verified()
                info = self.controller.prepare_submission("90001")
                reg = self.bridge.AccountRegistry(self.bridge._config_path())
                if consumed:
                    reg.acc("90001")["auth"]["consumed_at"] = "synthetic"
                else:
                    reg.acc("90001")["auth"]["token"] = "synthetic-rotated-token"
                reg.persist()
                with self.assertRaises(UserError):
                    self.controller.submit_confirmation(info["nonce"], acknowledged=True)
                self.assertFalse(self.bridge._attempts)
        self.platform.startRun.assert_not_called()

    def test_dryrun_expiring_while_dialog_open_never_launches(self):
        self.verified()
        info = self.controller.prepare_submission("90001")
        self.platform.checked_at["90001"] -= 601
        with self.assertRaisesRegex(UserError, "E_DRYRUN"):
            self.controller.submit_confirmation(info["nonce"], acknowledged=True)
        self.platform.startRun.assert_not_called()
        self.assertFalse(self.bridge._attempts)
        self.assertIsNone(self.controller.prepared)

    def test_journal_failure_never_starts_write(self):
        self.verified()
        info = self.controller.prepare_submission("90001")
        with patch.object(self.bridge, "atomic_json", side_effect=OSError(28, "private synthetic disk path")):
            with self.assertRaisesRegex(UserError, "E_DISK"):
                self.controller.submit_confirmation(info["nonce"], acknowledged=True)
        self.platform.startRun.assert_not_called()
        self.assertTrue(self.bridge._diagnostic_mode)

    def test_uncertain_attempt_survives_restart_and_blocks_prepare(self):
        self.verified()
        info = self.controller.prepare_submission("90001")
        self.controller.submit_confirmation(info["nonce"], acknowledged=True)
        self.bridge._job["running"] = False
        self.bridge._initialize(self.temp.name)
        with self.assertRaisesRegex(UserError, "E_ATTEMPT"):
            self.controller.prepare_submission("90001")

    def test_runner_unknown_and_post_write_auth_error_keep_lock(self):
        for code in (4, 2):
            with self.subTest(code=code):
                self.bridge._pending_run = ("90001", "submit", "synthetic-attempt")
                self.bridge._attempts = {"synthetic-attempt": {"exit": None}}
                def result(**kwargs):
                    self.platform.write_started = True
                    return None, code
                with patch("desktop_jobs.ProgressPipeline") as pipeline:
                    pipeline.return_value.run.side_effect = result
                    run_pending(self.bridge, self.platform)
                self.assertIn("synthetic-attempt", self.bridge._attempts)
                self.assertFalse(self.bridge._job["running"])
                self.assertNotIn("synthetic-offline-token", json.dumps(self.platform.ui_events.snapshot()))

    def test_prewrite_quota_or_expiry_can_release_reserved_attempt(self):
        for code in (2, 3):
            self.bridge._pending_run = ("90001", "submit", "synthetic-attempt")
            self.bridge._attempts = {"synthetic-attempt": {"exit": None}}
            with patch("desktop_jobs.ProgressPipeline") as pipeline:
                pipeline.return_value.run.return_value = (None, code)
                run_pending(self.bridge, self.platform)
            self.assertNotIn("synthetic-attempt", self.bridge._attempts)

    def test_successful_dryrun_enables_submit_without_writes(self):
        self.bridge._pending_run = ("90001", "build", None)
        with patch("desktop_jobs.ProgressPipeline") as pipeline:
            pipeline.return_value.run.return_value = ({"stopRun_biz": {"distance": 2.1, "used_time": 700}, "track_points": 500}, 0)
            run_pending(self.bridge, self.platform)
            pipeline.return_value.run.assert_called_once_with(submit=False)
        self.assertTrue(self.controller.snapshot()["members"][0]["can_submit"])
        self.assertFalse(self.bridge._attempts)


class DesktopClientAndLogTests(unittest.TestCase):
    def test_term_probe_accepts_arrays_without_relaxing_other_endpoints(self):
        platform, client = fake_platform("unused"), Mock()
        for terms in ([], [{"term_id": "synthetic", "term_name": "synthetic-private"}]):
            client.get_term_list.return_value = terms
            self.assertEqual(ClientView(client, platform).get_term_list(), terms)
        for method in ("get_school_info", "before_run", "record_detail", "get_term_run_record"):
            getattr(client, method).return_value = []
            with self.subTest(method=method), self.assertRaisesRegex(ValueError, "响应格式"):
                getattr(ClientView(client, platform), method)()
        self.assertNotIn("synthetic-private", json.dumps(platform.ui_events.snapshot()))

    def test_invalid_term_arrays_are_rejected_with_safe_shape_context(self):
        platform, client = fake_platform("unused"), Mock()
        for bad in (["synthetic-private"], [None], [[{}]], "synthetic-private", None):
            client.get_term_list.return_value = bad
            with self.subTest(bad=bad), self.assertRaisesRegex(ValueError, "响应格式"):
                ClientView(client, platform).get_term_list()
        event = platform.ui_events.snapshot()["events"][-1]
        self.assertEqual(event["method"], "get_term_list")
        self.assertEqual(event["response_kind"], "null")
        self.assertEqual(event["response_check"], "shape")
        self.assertNotIn("synthetic-private", json.dumps(platform.ui_events.snapshot()))

    def test_desktop_auth_gate_never_falls_back_to_public_school_on_error(self):
        platform, client = fake_platform("unused"), Mock()
        pipeline = ProgressPipeline(Mock(), Mock(), {}, platform)
        for code in (101, 500):
            client.reset_mock()
            client.get_term_list.side_effect = V3Error(code, "synthetic-private")
            with self.subTest(code=code), self.assertRaises(V3Error):
                pipeline._config(client)
            client.get_school_info.assert_not_called()

    def test_desktop_auth_gate_accepts_valid_term_array_then_reads_school_and_rules(self):
        platform, client = fake_platform("unused"), Mock()
        client.get_term_list.return_value = [{"term_id": "synthetic"}]
        client.get_school_info.return_value = {"school_name": "synthetic-private"}
        pipeline = ProgressPipeline(Mock(), Mock(), {}, platform)
        with patch.object(pipeline, "_sleep"), patch.object(pipeline, "_before", return_value={"synthetic": True}) as before:
            self.assertEqual(pipeline._config(ClientView(client, platform)), {"synthetic": True})
            before.assert_called_once()
        client.get_term_list.assert_called_once()
        client.get_school_info.assert_called_once()
        self.assertNotIn("synthetic-private", json.dumps(platform.ui_events.snapshot()))

    def test_failed_readonly_probe_logs_once_and_revokes_old_verification(self):
        with tempfile.TemporaryDirectory() as directory, patch.dict(os.environ):
            bridge, platform = isolated_bridge(), fake_platform(directory)
            bridge._platform = platform
            bridge._initialize(directory)
            reg = bridge.AccountRegistry(bridge._config_path())
            reg.add("synthetic", "90001", uid=901)
            reg.acc("90001")["auth"]["token"] = "synthetic-private-token"
            reg.persist()
            auth = bridge.AuthState(reg, "90001")
            bridge._dryrun_ok["90001"] = bridge._auth_fingerprint(auth)
            platform.checked_at["90001"] = time.monotonic()
            platform.checked_login["90001"] = signature(auth)
            platform.previews["90001"] = {"points": 500}
            bridge._pending_run = ("90001", "build", None)
            bridge._job["running"] = True
            client = Mock()
            client.get_term_list.return_value = "synthetic-private"
            with patch("desktop_jobs.ProgressPipeline.run", side_effect=lambda **kw: ClientView(client, platform).get_term_list()):
                run_pending(bridge, platform)
            errors = [x for x in platform.ui_events.snapshot()["events"] if x["level"] == "ERROR"]
            self.assertEqual(len(errors), 1)
            self.assertEqual(errors[0]["code"], "E_RESPONSE")
            self.assertFalse(bridge._dryrun_ok)
            self.assertFalse(platform.checked_at)
            self.assertFalse(platform.previews)
            self.assertFalse(Controller(bridge, platform).snapshot()["members"][0]["can_submit"])
            self.assertNotIn("synthetic-private", json.dumps(platform.ui_events.snapshot()))

    def test_method_shape_context_restart_sanitization(self):
        log = EventLog()
        log.emit("auth", "E_RESPONSE", "ERROR", method="get_term_list", response_kind="array", response_check="shape")
        raw = log.snapshot()
        clean = EventLog.sanitize(raw)
        self.assertEqual(clean["events"][0]["method"], "get_term_list")
        raw["events"][0].update(method="https://synthetic-private", response_kind=["secret"], response_check="synthetic-private")
        self.assertNotIn("synthetic-private", json.dumps(EventLog.sanitize(raw)))

    def test_readonly_guard_blocks_upload_submit_and_zone_change(self):
        platform, client = fake_platform("unused"), Mock()
        view = ClientView(client, platform)
        for method in ("get_oss_sts", "stop_run", "set_run_zone"):
            with self.subTest(method=method), self.assertRaises(ValueError):
                getattr(view, method)()
            getattr(client, method).assert_not_called()

    def test_write_client_submits_at_most_once(self):
        platform, client = fake_platform("unused"), Mock()
        client.stop_run.return_value = {"record_id": "synthetic-private-record", "token": "synthetic-private-token"}
        view = ClientView(client, platform, writable=True)
        view.stop_run({"synthetic": "payload"})
        with self.assertRaises(ValueError):
            view.stop_run({})
        client.stop_run.assert_called_once()
        self.assertNotIn("synthetic-private", json.dumps(platform.ui_events.snapshot()))

    def test_quota_malformed_fails_closed_and_expiry_is_normalized(self):
        platform, client = fake_platform("unused"), Mock()
        for bad in ({}, {"list": "invalid"}, {"list": [{"distance": "invalid", "start_time": 0}]}):
            client.get_term_run_record.return_value = bad
            with self.assertRaises(ValueError):
                ClientView(client, platform).get_term_run_record("synthetic")
        client.get_term_list.return_value = {"status": "101", "token": "synthetic-private"}
        with self.assertRaises(V3Error):
            ClientView(client, platform).get_term_list()
        self.assertEqual(platform.ui_events.snapshot()["events"][-1]["code"], "E_AUTH")

    def test_progress_logs_are_bounded_allowlisted_and_restart_sanitized(self):
        with tempfile.TemporaryDirectory() as directory:
            log = EventLog(directory)
            for _ in range(600):
                log.emit("capture", "capture_sample", requests=3, token="synthetic-secret", uid=901, url="https://synthetic.invalid")
            self.assertEqual(len(log.snapshot()["events"]), 500)
            self.assertEqual(log.snapshot()["dropped"], 100)
            raw = log.snapshot()
            raw["token"] = "synthetic-secret"
            raw["events"].append({"stage": {}, "code": [], "level": "ERROR", "token": "synthetic-secret"})
            raw["events"][-2]["private"] = "synthetic-secret"
            atomic_json(Path(directory) / "desktop-events.json", raw)
            restored = EventLog(directory)
            self.assertNotIn("synthetic-secret", json.dumps(restored.previous))

    def test_response_identity_mismatch_stops_before_write(self):
        platform, client = fake_platform("unused"), Mock()
        client.before_run.return_value = {"uid": 902, "token": "synthetic-private"}
        with self.assertRaisesRegex(ValueError, "身份不符"):
            ClientView(client, platform, writable=True, expected_uid=901).before_run()
        self.assertFalse(platform.write_started)
        client.get_oss_sts.assert_not_called()
        client.stop_run.assert_not_called()
        data = json.dumps(platform.ui_events.snapshot())
        self.assertIn("E_RESPONSE", data)
        self.assertNotIn("synthetic-private", data)

    def test_timeout_error_never_exports_private_exception(self):
        platform, client = fake_platform("unused"), Mock()
        client.get_term_list.side_effect = TimeoutError("synthetic-secret-token@private-endpoint")
        with self.assertRaises(TimeoutError):
            ClientView(client, platform).get_term_list()
        data = json.dumps(platform.ui_events.snapshot())
        self.assertIn("E_TIMEOUT", data)
        self.assertNotIn("synthetic-secret", data)
        self.assertEqual(classify(ValueError("当天额度响应格式无效")), "E_RESPONSE")

    def test_pending_never_reported_valid_and_status_one_negative_is_invalid(self):
        bridge, platform, auth, state = Mock(), fake_platform("unused"), Mock(uid=901), Mock()
        bridge._job = {}
        auth.make_client.return_value.record_detail.return_value = {"record_status": 0}
        platform.job_stop = Mock()
        platform.job_stop.is_set.return_value = False
        platform.job_stop.wait.return_value = False
        self.assertIn("尚未终判", watch(bridge, platform, auth, state, "synthetic"))
        self.assertEqual(state.log_watch.call_count, 3)
        auth.make_client.return_value.record_detail.return_value = {"record_status": 1, "record_failed_reason": "无效"}
        self.assertIn("无效", watch(bridge, platform, auth, state, "synthetic"))

    def test_corrupt_state_is_preserved(self):
        with tempfile.TemporaryDirectory() as directory:
            file = Path(directory) / "state.json"
            file.write_text("synthetic-invalid", encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "本机记录"):
                DesktopState(file)
            self.assertEqual(file.read_text(), "synthetic-invalid")

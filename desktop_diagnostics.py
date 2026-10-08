# --- lepao-research-notice v1 (do not remove; see LICENSE) ---
# 乐跑协议研究（Lepao Research） · https://github.com/dan-cun/lepao3
# Copyright (c) 2026 dan-cun · 技术讨论 QQ 1224145544（仅作技术讨论，不提供代打卡）
# 许可证 LRL-1.0（乐跑研究协议 1.0）：仅供学习 · 不可牟利 · 再发布须署名引用原始仓库 · 声明不得删除
# 删除或篡改本块即依 LRL-1.0 第三条自动终止授权；衍生版须继续以 LRL-1.0 授权并标注修改说明。
# --- end lepao-research-notice ---
"""Bounded, allowlisted capture diagnostics. No packet, endpoint or account data."""
import datetime
import json
import re
import threading
import time
import zipfile
from pathlib import Path

from desktop_storage import atomic_json

EVENTS = frozenset("test_begin ca_check vpn_permission vpn_start network tun_ready native_ready "
                   "vpn_sample vpn_error vpn_stop vpn_revoked tcp_open tcp_route tcp_connected "
                   "socks_error udp_associate udp_received udp_sent udp_reply udp_error quic_blocked "
                   "dns_sent dns_reply tls_ok tls_failed proxy_error upstream_error request_ok "
                   "capture_arm capture_timeout identity_pending identity_other identity_matched "
                   "credential_saved credential_save_failed capture_incompatible export "
                   "desktop_start desktop_sample desktop_stop proxy_recovered".split())
MILESTONES = frozenset("test_begin ca_check vpn_permission vpn_start network tun_ready native_ready "
                      "vpn_error vpn_stop vpn_revoked capture_arm capture_timeout identity_pending "
                      "identity_other identity_matched credential_saved credential_save_failed capture_incompatible "
                      "desktop_start desktop_stop proxy_recovered".split())
INT_FIELDS = frozenset("sdk dns_v4 dns_v6 errno tx_packets tx_bytes rx_packets rx_bytes "
                       "connections target tls_ok tls_failed requests udp_associate udp_received "
                       "udp_sent udp_reply errors remaining certificate_rejected".split())
BOOL_FIELDS = frozenset("trusted ca_installed wifi cellular proxy private_dns active listening native_running".split())
ENUM_FIELDS = {
    "route": {"target", "direct", "no_sni"},
    "family": {"v4", "v6", "domain"},
    "port": {"dns", "tls", "other"},
    "error": {"timeout", "tls", "dns", "connection", "protocol", "other"},
    "reason": {"unknown_ca", "certificate", "certificate_unknown", "bad_certificate",
               "certificate_expired", "certificate_revoked", "unsupported_certificate", "protocol", "eof", "other"},
    "stage": {"precheck", "socks", "tun", "native", "capture", "monitor", "cleanup"},
    "outcome": {"ended", "stopped", "failed", "revoked", "denied", "granted", "requested"},
    "http": {"2xx", "3xx", "4xx", "5xx", "other"},
}

PEER_CERTIFICATE_REASONS = frozenset({"unknown_ca", "certificate_unknown", "bad_certificate",
                                    "certificate_expired", "certificate_revoked", "unsupported_certificate"})


def tls_failure_reason(reason):
    """Only fixed OpenSSL alert categories; never retain an exception string."""
    if not isinstance(reason, str):
        return "other"
    known = {
        "TLSV1_ALERT_UNKNOWN_CA": "unknown_ca",
        "SSLV3_ALERT_CERTIFICATE_UNKNOWN": "certificate_unknown",
        "SSLV3_ALERT_BAD_CERTIFICATE": "bad_certificate",
        "SSLV3_ALERT_CERTIFICATE_EXPIRED": "certificate_expired",
        "SSLV3_ALERT_CERTIFICATE_REVOKED": "certificate_revoked",
        "SSLV3_ALERT_UNSUPPORTED_CERTIFICATE": "unsupported_certificate",
    }
    if reason in known:
        return known[reason]
    if isinstance(reason, str) and "CERTIFICATE" in reason:
        return "certificate"
    if isinstance(reason, str) and "EOF" in reason:
        return "eof"
    if isinstance(reason, str) and "PROTOCOL" in reason:
        return "protocol"
    return "other"


def safe_fields(values):
    out = {}
    if not isinstance(values, dict):
        return out
    for key, value in values.items():
        if key in BOOL_FIELDS and type(value) is bool:
            out[key] = value
        elif key in INT_FIELDS and type(value) is int and 0 <= value < 2 ** 63:
            out[key] = value
        elif key in ENUM_FIELDS and isinstance(value, str) and value in ENUM_FIELDS[key]:
            out[key] = value
    return out


def error_kind(exc):
    import socket
    import ssl
    if isinstance(exc, (TimeoutError, socket.timeout)):
        return "timeout"
    if isinstance(exc, ssl.SSLError):
        return "tls"
    if isinstance(exc, socket.gaierror):
        return "dns"
    if isinstance(exc, OSError):
        return "connection"
    if isinstance(exc, (ValueError, EOFError)):
        return "protocol"
    return "other"


class DiagnosticRecorder:
    MAX_EVENTS = 256

    def __init__(self, directory, build="0.3.3-diagnostic"):
        self.directory = Path(directory)
        self.build = build if build in ("0.3.3-diagnostic", "desktop-0.1.0-test", "desktop-0.2.0-test", "desktop-0.3.0-test", "desktop-0.4.0-test", "desktop-0.4.1-test", "desktop-0.4.2-test", "desktop-0.4.3-test", "desktop-0.4.4-test", "desktop-0.4.5-test", "desktop-0.4.6-test", "desktop-0.4.7-test", "desktop-0.4.8-test", "desktop-0.4.9-test", "desktop-0.4.10-test", "desktop-0.4.11-test", "desktop-0.4.12-test", "desktop-0.4.13-test", "desktop-0.4.14-test", "desktop-0.4.15-test", "desktop-0.5.0-terminal-test", "desktop-0.5.1-terminal-test", "desktop-0.5.2-terminal-test", "desktop-0.6.0-studio-test", "desktop-0.7.0-retro-test", "desktop-0.7.1-retro-test", "desktop-0.7.2-retro-test", "desktop-0.7.3-retro-test", "desktop-0.7.4-retro-test", "desktop-0.7.5-retro-test", "desktop-0.7.6-retro-test", "desktop-0.7.7-retro-test", "desktop-0.7.8-retro-test", "desktop-1.0.0") else "unknown"
        self.lock = threading.RLock()
        self.started = None
        self.last_write = 0
        self.report = None

    def begin(self):
        import secrets
        with self.lock:
            self.started = time.monotonic()
            self.report = {"schema": 1, "build": self.build, "session": secrets.token_hex(8),
                           "started_utc": datetime.datetime.now(datetime.timezone.utc).isoformat(),
                           "events": [], "milestones": [], "totals": {}, "latest": {}, "dropped_events": 0}
            self.emit("test_begin", force=True)

    def emit(self, event, force=False, **values):
        if event not in EVENTS:
            return
        with self.lock:
            if self.report is None:
                return
            fields = safe_fields(values)
            elapsed = max(0, int((time.monotonic() - self.started) * 1000))
            self.report["totals"][event] = self.report["totals"].get(event, 0) + 1
            self.report["latest"].update(fields)
            # Preserve lifecycle plus recent traffic, bounded even for a busy WeChat session.
            events = self.report["events"]
            if len(events) >= self.MAX_EVENTS:
                del events[1]
                self.report["dropped_events"] += 1
            item = {"ms": elapsed, "event": event, **fields}
            events.append(item)
            if event in MILESTONES:
                self.report["milestones"].append(item)
                self.report["milestones"] = self.report["milestones"][-64:]
            self._persist(force)

    def _persist(self, force):
        now = time.monotonic()
        if force or now - self.last_write >= 1:
            try:
                self.directory.mkdir(parents=True, exist_ok=True)
                atomic_json(self.directory / "latest.json", self.report)
                self.last_write = now
            except OSError:
                # Diagnostics must never break capture or VPN cleanup.
                pass

    def snapshot(self):
        with self.lock:
            if self.report is not None:
                return json.loads(json.dumps(self.report))
            path = self.directory / "latest.json"
            if not path.is_file() or path.stat().st_size > 256 * 1024:
                raise ValueError("尚无测试记录，请先点一键抓号并复现问题")
            raw = json.loads(path.read_text(encoding="utf-8"))
            # Re-allowlist on restart too: never export arbitrary private files/fields.
            report = {"schema": 1, "build": self.build, "events": [], "milestones": [], "totals": {},
                      "latest": safe_fields(raw.get("latest")), "dropped_events": 0}
            # A report saved before an APK upgrade must keep its original build label.
            report["build"] = (raw.get("build") if raw.get("build") in
                               ("0.3.1-diagnostic", "0.3.2-diagnostic", "0.3.3-diagnostic", "desktop-0.1.0-test", "desktop-0.2.0-test", "desktop-0.3.0-test", "desktop-0.4.0-test", "desktop-0.4.1-test", "desktop-0.4.2-test", "desktop-0.4.3-test", "desktop-0.4.4-test", "desktop-0.4.5-test", "desktop-0.4.6-test", "desktop-0.4.7-test", "desktop-0.4.8-test", "desktop-0.4.9-test", "desktop-0.4.10-test", "desktop-0.4.11-test", "desktop-0.4.12-test", "desktop-0.4.13-test", "desktop-0.4.14-test", "desktop-0.4.15-test", "desktop-0.5.0-terminal-test", "desktop-0.5.1-terminal-test", "desktop-0.5.2-terminal-test", "desktop-0.6.0-studio-test", "desktop-0.7.0-retro-test", "desktop-0.7.1-retro-test", "desktop-0.7.2-retro-test", "desktop-0.7.3-retro-test", "desktop-0.7.4-retro-test", "desktop-0.7.5-retro-test", "desktop-0.7.6-retro-test", "desktop-0.7.7-retro-test", "desktop-0.7.8-retro-test", "desktop-1.0.0") else "unknown")
            session = raw.get("session", "")
            if isinstance(session, str) and re.fullmatch(r"[a-f0-9]{16}", session):
                report["session"] = session
            for field, limit in (("events", self.MAX_EVENTS), ("milestones", 64)):
                for item in raw.get(field, [])[-limit:]:
                    if isinstance(item, dict) and item.get("event") in EVENTS:
                        elapsed = item.get("ms", 0)
                        elapsed = elapsed if type(elapsed) is int else 0
                        report[field].append({"event": item["event"], **safe_fields(item),
                                              "ms": max(0, min(elapsed, 2 ** 31))})
            dropped = raw.get("dropped_events", 0)
            if type(dropped) is int and 0 <= dropped < 2 ** 63:
                report["dropped_events"] = dropped
            for key, value in raw.get("totals", {}).items():
                if key in EVENTS and type(value) is int and 0 <= value < 2 ** 63:
                    report["totals"][key] = value
            return report

    def export(self):
        with self.lock:
            report = self.snapshot()
            self.directory.mkdir(parents=True, exist_ok=True)
            path = self.directory / "export.zip"
            with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as archive:
                archive.writestr("diagnostic.json", json.dumps(report, ensure_ascii=False, indent=2))
                archive.writestr("README.txt", "pipeRun diagnostic\n"
                    "Only allowlisted lifecycle events, relative times, counters and error categories.\n"
                    "No account IDs, tokens, CA certificates/keys, endpoint IPs, DNS names, URLs, "
                    "headers, packet bodies, full exceptions or system logs.\n"
                    "Missing vpn_stop after a sample may indicate process termination; not proof.\n")
            return str(path)

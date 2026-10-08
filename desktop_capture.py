# -*- coding: utf-8 -*-
# --- lepao-research-notice v1 (do not remove; see LICENSE) ---
# 乐跑协议研究（Lepao Research） · https://github.com/dan-cun/lepao3
# Copyright (c) 2026 dan-cun · 技术讨论 QQ 1224145544（仅作技术讨论，不提供代打卡）
# 许可证 LRL-1.0（乐跑研究协议 1.0）：仅供学习 · 不可牟利 · 再发布须署名引用原始仓库 · 声明不得删除
# 删除或篡改本块即依 LRL-1.0 第三条自动终止授权；衍生版须继续以 LRL-1.0 授权并标注修改说明。
# --- end lepao-research-notice ---
"""pipeRun M2: loopback proxy and bounded, identity-checked capture window.

Only TARGET:443 is terminated, only during a capture window. Other CONNECT
traffic is relayed byte-for-byte. No traffic bodies or credential files are logged.
"""

import gzip
import http.client
import io
import json
import select
import socket
import ssl
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlsplit

from desktop_storage import DesktopRegistry as AccountRegistry
from lepao.auth import AuthState
from lepao.crypto import decrypt_data
from desktop_ca import TARGET

MAX_BODY = 4 * 1024 * 1024
HOP_HEADERS = {"connection", "proxy-connection", "proxy-authorization", "proxy-authenticate",
               "keep-alive", "te", "trailer", "transfer-encoding", "upgrade", "content-length"}


def _json_payload(body, response=False):
    try:
        outer = json.loads(body) if response else parse_qs(body.decode("utf-8"), max_num_fields=64)
        if not isinstance(outer, dict):
            return {}
        data = outer.get("data")
        if not response:
            data = data[0] if data else None
        plain = json.loads(decrypt_data(data)) if isinstance(data, str) else {}
        return plain if isinstance(plain, dict) else {}
    except (ValueError, TypeError, KeyError, IndexError, UnicodeError):
        return {}


def _identity(plain):
    return {key: plain[key] for key in ("uid", "school_id", "student_num", "card_id")
            if plain.get(key) not in (None, "", 0, "0")}


def _matching_member(reg, cred):
    # All supplied registered identifiers must agree. Never let a selected
    # member or active slot override the identity of the captured session.
    keys = set()
    for field in ("uid", "student_num", "card_id"):
        if cred.get(field) not in (None, "", 0, "0"):
            key = reg.key_of_cred({field: cred[field]})
            if key:
                keys.add(key)
    if len(keys) != 1:
        return None
    key = keys.pop()
    known_uid = reg.acc(key).get("uid")
    if known_uid and str(known_uid) != str(cred.get("uid")):
        return None
    for field in ("student_num", "card_id"):
        if cred.get(field) and reg.acc(key).get(field) and str(cred[field]) != str(reg.acc(key)[field]):
            return None
    return key


class CaptureSession:
    def __init__(self, config_path, ca, registry_lock, port=0, window=30, stable=8, diagnostic=None):
        self.config_path, self.ca, self.registry_lock = config_path, ca, registry_lock
        self.port, self.window, self.stable = port, window, stable
        self.lock = threading.RLock()
        self.server = None
        self.selected = ""
        self.active = False
        self.has_started = False
        self.until = 0
        self.pending = {}
        self.candidate = None
        self.last_change = 0
        self.message = "尚未开始抓号"
        self.stats = {"connections": 0, "target": 0, "tls_ok": 0, "tls_failed": 0, "requests": 0,
                      "certificate_rejected": 0}
        self.diagnostic = diagnostic or (lambda *args, **kwargs: None)

    def begin(self, selected, armed=True):
        with self.lock:
            if self.server:
                raise ValueError("代理正在运行，请先结束当前会话")
            with self.registry_lock:
                if selected not in AccountRegistry(self.config_path).keys():
                    raise ValueError("请先登记成员")
            self.selected = selected
            self.pending.clear()
            self.candidate = None
            self.stats = dict.fromkeys(self.stats, 0)
            self.active = False
            self.message = "代理已就绪，请设置 Wi-Fi 代理后开始捕获"
            self.server = ProxyServer(("127.0.0.1", self.port), self)
            self.port = self.server.server_port
            threading.Thread(target=self.server.serve_forever, kwargs={"poll_interval": 0.1}, daemon=True).start()
            if armed:
                self.arm()
            return self.port

    def arm(self):
        with self.lock:
            if not self.server or self.active:
                raise ValueError("代理未就绪或捕获尚未结束")
            self.pending.clear()
            self.candidate = None
            self.stats["certificate_rejected"] = 0
            self.active = self.has_started = True
            self.until = time.monotonic() + self.window
            self.message = "等待小程序重新登录"
            self.diagnostic("capture_arm")
            threading.Thread(target=self._monitor, daemon=True).start()

    def _monitor(self):
        while True:
            with self.lock:
                if not self.active:
                    return
                now = time.monotonic()
                if self.candidate and now - self.last_change >= self.stable:
                    self._commit()
                    return
                if now >= self.until:
                    self.active = False
                    self.pending.clear()
                    self.candidate = None
                    self.message = "抓号超时。请检查代理、CA 受信以及小程序是否重新登录"
                    self.diagnostic("capture_timeout")
                    return
            time.sleep(0.15)

    def _commit(self):
        cred = self.candidate
        try:
            with self.registry_lock:
                reg = AccountRegistry(self.config_path)
                key = _matching_member(reg, cred)
                if key != self.selected:
                    raise ValueError("身份不匹配，凭证未保存")
                reg.fill_identity(key, cred)
                auth = AuthState(reg, key)
                if auth.token != cred["token"]:
                    reg.acc(key)["auth"].update(refresh_token="", refresh_expire=0)
                    auth.set_token(cred["token"], source="mobile-capture",
                                   refresh_token=cred.get("refresh_token"),
                                   refresh_expire=cred.get("refresh_expire"))
                self.message = "抓号完成，凭证已归位。可以执行干跑"
                self.diagnostic("credential_saved")
        except Exception as exc:
            self.diagnostic("credential_save_failed")
            self.message = "凭证保存失败：" + type(exc).__name__
        finally:
            self.active = False
            self.pending.clear()
            self.candidate = None

    def count(self, key):
        with self.lock:
            self.stats[key] += 1
        if key in ("tls_ok", "tls_failed"):
            self.diagnostic(key)

    def tls_failure(self, openssl_reason):
        from desktop_diagnostics import tls_failure_reason, PEER_CERTIFICATE_REASONS
        category = tls_failure_reason(openssl_reason)
        with self.lock:
            self.count("tls_failed")
            self.diagnostic("proxy_error", error="tls", reason=category)
            if category in PEER_CERTIFICATE_REASONS and self.active:
                self.stats["certificate_rejected"] += 1
                if self.stats["certificate_rejected"] >= 2 and self.stats["tls_ok"] == 0:
                    self.active = False
                    self.pending.clear()
                    self.candidate = None
                    self.message = ("微信连续拒绝本机代理证书，自动抓号无法继续。系统安装 CA 不代表微信信任它。"
                                    "已停止捕获，正在关闭 VPN；关闭后重新进入小程序。不要反复重装 CA 或清除账号数据。"
                                    "可使用已有的本人凭证手动导入。")
                    self.diagnostic("capture_incompatible", force=True, reason=category,
                                    certificate_rejected=self.stats["certificate_rejected"])

    def observe(self, path, request_body, response_body=None):
        with self.lock:
            if not self.active:
                return
            req = _json_payload(request_body)
            cred = _identity(req)
            if req.get("token") and cred.get("uid"):
                cred["token"] = req["token"]
                pending = self.pending.get(str(cred["uid"]), {})
                if pending.get("token") == cred["token"]:
                    cred = {**pending, **cred}
                if not pending or pending.get("token") == cred["token"]:
                    self._candidate(cred)
            if path.split("?", 1)[0] == "/v3/api.php/WpLogin/loginByCode" and response_body:
                obj = _json_payload(response_body, response=True)
                td = obj.get("token_data") or {}
                if isinstance(td, dict) and td.get("access_token") and obj.get("uid"):
                    cred = {**_identity(obj), "token": td["access_token"]}
                    cred.update({key: td[key] for key in ("refresh_token", "refresh_expire") if td.get(key)})
                    uid = str(cred["uid"])
                    previous = self.pending.get(uid)
                    if previous and previous.get("token") != cred["token"]:
                        # A second cold start invalidates the first candidate immediately.
                        if self.candidate and str(self.candidate.get("uid")) == uid:
                            self.candidate = None
                    if len(self.pending) < 8 or uid in self.pending:
                        self.pending[uid] = cred
                    self._candidate(cred)

    def _candidate(self, cred):
        if not isinstance(cred.get("token"), str) or not 16 <= len(cred["token"]) <= 4096:
            return
        with self.registry_lock:
            reg = AccountRegistry(self.config_path)
            key = _matching_member(reg, cred)
        if key != self.selected:
            self.diagnostic("identity_pending" if key is None else "identity_other")
            self.message = ("登录已到达，等待带学号的业务请求确认身份" if key is None
                            else "捕获到其他成员，凭证未保存；请登录所选成员")
            return
        if not self.candidate or self.candidate["token"] != cred["token"]:
            self.diagnostic("identity_matched")
            self.candidate = cred
            self.last_change = time.monotonic()
            self.message = "身份已匹配，等待登录稳定后保存"
        else:
            self.candidate.update(cred)

    def snapshot(self):
        with self.lock:
            return {"active": self.active, "listening": self.server is not None,
                    "has_started": self.has_started,
                    "port": self.port, "member": self.selected,
                    "remaining": max(0, int(self.until - time.monotonic())) if self.active else 0,
                    "message": self.message, **self.stats}

    def close(self):
        with self.lock:
            self.active = False
            self.pending.clear()
            self.candidate = None
            server, self.server = self.server, None
        if server:
            server.shutdown()
            server.server_close()


class ProxyServer(ThreadingHTTPServer):
    daemon_threads = True
    allow_reuse_address = True

    def __init__(self, address, session):
        self.session = session
        self.tls_context = session.ca.server_context()
        self.upstream_context = ssl.create_default_context()
        self.upstream_context.set_alpn_protocols(["http/1.1"])
        self.sockets = set()
        self.sockets_lock = threading.Lock()
        super().__init__(address, ProxyHandler)

    def get_request(self):
        sock, addr = super().get_request()
        self.track(sock)
        return sock, addr

    def track(self, sock):
        with self.sockets_lock:
            self.sockets.add(sock)

    def close_request(self, request):
        with self.sockets_lock:
            self.sockets.discard(request)
        super().close_request(request)

    def server_close(self):
        super().server_close()
        with self.sockets_lock:
            for sock in self.sockets:
                try:
                    sock.shutdown(socket.SHUT_RDWR)
                except OSError:
                    pass
                sock.close()
            self.sockets.clear()

    def handle_error(self, request, client_address):
        # Never print request contents or credentials to stderr/Logcat.
        pass

    def https_connection(self, host, port):
        return http.client.HTTPSConnection(host, port, timeout=15, context=self.upstream_context)


class ProxyHandler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"
    terminated = False
    timeout = 15

    def log_message(self, *args):
        pass

    def do_CONNECT(self):
        self.close_connection = True
        session = self.server.session
        session.count("connections")
        try:
            dest = urlsplit("//" + self.path)
            host, port = dest.hostname, dest.port
            if not host or not port or dest.path or dest.query or dest.fragment or dest.username or dest.password:
                raise ValueError("invalid CONNECT authority")
            if host == TARGET and port == 443 and session.snapshot()["active"]:
                session.count("target")
                self.send_response_only(200, "Connection Established")
                self.end_headers()
                self.wfile.flush()
                try:
                    with self.server.tls_context.wrap_socket(self.connection, server_side=True) as tls:
                        self.server.track(tls)
                        try:
                            session.count("tls_ok")
                            TlsHandler(tls, self.client_address, self.server)
                        finally:
                            with self.server.sockets_lock:
                                self.server.sockets.discard(tls)
                except ssl.SSLError as exc:
                    session.tls_failure(getattr(exc, "reason", ""))
                return
            with socket.create_connection((host, port), timeout=15) as upstream:
                self.send_response_only(200, "Connection Established")
                self.end_headers()
                self.wfile.flush()
                self.connection.settimeout(15)
                while True:
                    ready, _, _ = select.select([self.connection, upstream], [], [], 15)
                    if not ready:
                        return
                    for source in ready:
                        data = source.recv(65536)
                        if not data:
                            return
                        (upstream if source is self.connection else self.connection).sendall(data)
        except (OSError, ValueError) as exc:
            from desktop_diagnostics import error_kind
            session.diagnostic("proxy_error", error=error_kind(exc), errno=getattr(exc, "errno", None))
            # A CONNECT error after a 200 must close, not inject plaintext into TLS.
            return

    def _body(self):
        lengths = self.headers.get_all("Content-Length", [])
        transfer = self.headers.get("Transfer-Encoding", "").lower()
        if len(lengths) > 1 or (lengths and transfer):
            raise ValueError("ambiguous body framing")
        if transfer:
            if transfer != "chunked":
                raise ValueError("unsupported transfer encoding")
            parts, total = [], 0
            while True:
                line = self.rfile.readline(128)
                if not line.endswith(b"\r\n"):
                    raise ValueError("invalid chunk")
                size = int(line.split(b";", 1)[0], 16)
                if size < 0 or total + size > MAX_BODY:
                    raise ValueError("body too large")
                if size == 0:
                    # Bound trailer size as well as body size.
                    for _ in range(100):
                        trailer = self.rfile.readline(8192)
                        if trailer == b"\r\n":
                            return b"".join(parts)
                        if not trailer or not trailer.endswith(b"\r\n"):
                            break
                    raise ValueError("invalid trailers")
                chunk = self.rfile.read(size)
                if len(chunk) != size or self.rfile.read(2) != b"\r\n":
                    raise ValueError("incomplete chunk")
                parts.append(chunk)
                total += size
        size = int(lengths[0]) if lengths else 0
        if not 0 <= size <= MAX_BODY:
            raise ValueError("body too large")
        data = self.rfile.read(size)
        if len(data) != size:
            raise ValueError("incomplete body")
        return data

    def _forward(self):
        self.close_connection = True
        upstream = None
        try:
            if self.terminated:
                host = self.headers.get("Host", "").lower()
                if host not in (TARGET, TARGET + ":443") or not self.path.startswith("/") or self.path.startswith("//"):
                    raise ValueError("target mismatch")
                host, port, path = TARGET, 443, self.path
                upstream = self.server.https_connection(host, port)
            else:
                dest = urlsplit(self.path)
                if dest.scheme != "http" or not dest.hostname or dest.username or dest.password or dest.fragment:
                    raise ValueError("invalid HTTP proxy target")
                host, port = dest.hostname, dest.port or 80
                path = dest.path or "/"
                if dest.query:
                    path += "?" + dest.query
                upstream = http.client.HTTPConnection(host, port, timeout=15)
            body = self._body()
            blocked = HOP_HEADERS | {part.strip().lower() for part in self.headers.get("Connection", "").split(",")}
            blocked |= {"host"}
            if self.terminated:
                blocked.add("accept-encoding")
            headers = {k: v for k, v in self.headers.items() if k.lower() not in blocked}
            headers.update({"Host": host if port in (80, 443) else "{}:{}".format(host, port), "Connection": "close"})
            if self.terminated:
                headers["Accept-Encoding"] = "gzip"
            upstream.request(self.command, path, body=body, headers=headers)
            response = upstream.getresponse()
            if self.terminated:
                group = str(response.status // 100) + "xx"
                self.server.session.diagnostic("request_ok", http=group)
            data = response.read(MAX_BODY + 1)
            if len(data) > MAX_BODY:
                raise ValueError("response too large")
            if self.terminated:
                self.server.session.count("requests")
                decoded = data
                if response.getheader("Content-Encoding", "").lower() == "gzip":
                    try:
                        with gzip.GzipFile(fileobj=io.BytesIO(data)) as gz:
                            decoded = gz.read(MAX_BODY + 1)
                    except (OSError, EOFError):
                        decoded = b""
                try:
                    if len(decoded) <= MAX_BODY:
                        self.server.session.observe(path, body, decoded)
                except Exception:
                    # Parsing/capture failures must not break the user's login.
                    pass
            self.send_response_only(response.status, response.reason)
            response_blocked = HOP_HEADERS | {part.strip().lower() for part in response.getheader("Connection", "").split(",")}
            for name, value in response.getheaders():
                if name.lower() not in response_blocked:
                    self.send_header(name, value)
            self.send_header("Content-Length", str(len(data)))
            self.send_header("Connection", "close")
            self.end_headers()
            if self.command != "HEAD":
                self.wfile.write(data)
        except (ValueError, OSError, http.client.HTTPException) as exc:
            from desktop_diagnostics import error_kind
            self.server.session.diagnostic("upstream_error", error=error_kind(exc), errno=getattr(exc, "errno", None))
            self.send_error(502, "Proxy request failed")
        finally:
            if upstream:
                upstream.close()

    do_GET = do_POST = do_PUT = do_DELETE = do_HEAD = do_OPTIONS = do_PATCH = _forward


class TlsHandler(ProxyHandler):
    terminated = True

    def do_CONNECT(self):
        self.send_error(405)

# -*- coding: utf-8 -*-
# --- lepao-research-notice v1 (do not remove; see LICENSE) ---
# 乐跑协议研究（Lepao Research） · https://github.com/dan-cun/lepao3
# Copyright (c) 2026 dan-cun · 技术讨论 QQ 1224145544（仅作技术讨论，不提供代打卡）
# 许可证 LRL-1.0（乐跑研究协议 1.0）：仅供学习 · 不可牟利 · 再发布须署名引用原始仓库 · 声明不得删除
# 删除或篡改本块即依 LRL-1.0 第三条自动终止授权；衍生版须继续以 LRL-1.0 授权并标注修改说明。
# --- end lepao-research-notice ---
"""pipeRun addition: per-install CA, using the already bundled PyCryptodome.

The small DER encoder only emits the fixed RSA/SHA256 X.509 profile below.
Private keys never leave the application's private directory.
"""

import base64
import datetime as dt
import hashlib
import os
import secrets
import ssl
from pathlib import Path

from Crypto.Hash import SHA256
from Crypto.PublicKey import RSA
from Crypto.Signature import pkcs1_15
from Crypto.Util.asn1 import DerInteger, DerObjectId

TARGET = "api2.lptiyu.com"


def _der(tag, payload):
    size = len(payload)
    length = bytes([size]) if size < 128 else bytes([128 + (size.bit_length() + 7) // 8]) + size.to_bytes((size.bit_length() + 7) // 8, "big")
    return bytes([tag]) + length + payload


def _seq(*parts):
    return _der(0x30, b"".join(parts))


def _oid(value):
    return DerObjectId(value).encode()


def _name(value):
    return _seq(_der(0x31, _seq(_oid("2.5.4.3"), _der(12, value.encode("utf-8")))))


def _extension(oid, value, critical=False):
    return _seq(_oid(oid), *(b"\x01\x01\xff",) if critical else (), _der(4, value))


def _certificate(key, issuer_key, subject, issuer, days, ca=False):
    now = dt.datetime.now(dt.timezone.utc)
    algorithm = _seq(_oid("1.2.840.113549.1.1.11"), b"\x05\x00")
    validity = _seq(*[_der(0x17, date.strftime("%y%m%d%H%M%SZ").encode("ascii"))
                      for date in (now - dt.timedelta(days=1), now + dt.timedelta(days=days))])
    def key_identifier(rsa):
        return hashlib.sha1(_seq(DerInteger(rsa.n).encode(), DerInteger(rsa.e).encode())).digest()

    extensions = [
        _extension("2.5.29.19", _seq(b"\x01\x01\xff", DerInteger(0).encode()) if ca else _seq(), True),
        _extension("2.5.29.15", _der(3, b"\x01\x06" if ca else b"\x05\xa0"), True),
        _extension("2.5.29.14", _der(4, key_identifier(key))),
        _extension("2.5.29.35", _seq(_der(0x80, key_identifier(issuer_key)))),
    ]
    if not ca:
        extensions += [_extension("2.5.29.17", _seq(_der(0x82, TARGET.encode("ascii")))),
                       _extension("2.5.29.37", _seq(_oid("1.3.6.1.5.5.7.3.1")))]
    body = _seq(_der(0xa0, DerInteger(2).encode()),
                DerInteger(secrets.randbits(159) or 1).encode(), algorithm,
                _name(issuer), validity, _name(subject), key.public_key().export_key(format="DER"),
                _der(0xa3, _seq(*extensions)))
    signature = pkcs1_15.new(issuer_key).sign(SHA256.new(body))
    return _seq(body, algorithm, _der(3, b"\x00" + signature))


def _pem(der):
    encoded = base64.b64encode(der).decode("ascii")
    return ("-----BEGIN CERTIFICATE-----\n" + "\n".join(encoded[i:i + 64] for i in range(0, len(encoded), 64)) +
            "\n-----END CERTIFICATE-----\n").encode("ascii")


def _private_write(path, data):
    temp = path.with_suffix(path.suffix + ".tmp")
    with open(temp, "wb") as handle:
        handle.write(data)
    os.chmod(temp, 0o600)
    os.replace(temp, path)


class CertificateAuthority:
    def __init__(self, directory):
        self.directory = Path(directory)
        self.directory.mkdir(parents=True, exist_ok=True)
        self.key_file = self.directory / "ca-key.pem"
        self.cert_file = self.directory / "ca.pem"
        # Never silently rotate a CA which the user may already have trusted.
        if self.key_file.exists() != self.cert_file.exists():
            raise RuntimeError("CA 文件不完整，请保留应用数据并联系维护者，不要清除账号或自动重建 CA")
        if not self.key_file.exists():
            key = RSA.generate(2048)
            name = "pipeRun local CA " + hashlib.sha256(key.public_key().export_key(format="DER")).hexdigest()[:8]
            cert = _certificate(key, key, name, name, 3650, ca=True)
            _private_write(self.key_file, key.export_key())
            _private_write(self.cert_file, _pem(cert))
        self.key = RSA.import_key(self.key_file.read_bytes())
        self.pem = self.cert_file.read_bytes()
        self.der = ssl.PEM_cert_to_DER_cert(self.pem.decode("ascii"))
        if not self.key.has_private() or RSA.import_key(self.der).public_key() != self.key.public_key():
            raise RuntimeError("CA 证书与私钥不匹配，请保留应用数据并联系维护者")
        self.fingerprint = hashlib.sha256(self.der).hexdigest()
        self.name = "pipeRun local CA " + hashlib.sha256(self.key.public_key().export_key(format="DER")).hexdigest()[:8]
        self.leaf_file = self.directory / "server.pem"
        self.leaf_key_file = self.directory / "server-key.pem"
        self.chain_file = self.directory / "server-chain.pem"
        # Refresh the short-lived server certificate at each process start.
        leaf_key = RSA.generate(2048)
        _private_write(self.leaf_key_file, leaf_key.export_key())
        _private_write(self.leaf_file, _pem(_certificate(leaf_key, self.key, TARGET, self.name, 30)))
        # Match mitmproxy's presentation: leaf followed by the signing CA.
        # Sending a root does NOT make an untrusted client trust it.
        _private_write(self.chain_file, self.leaf_file.read_bytes() + self.pem)

    def server_context(self):
        context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
        context.minimum_version = ssl.TLSVersion.TLSv1_2
        context.set_alpn_protocols(["http/1.1"])
        context.load_cert_chain(str(self.chain_file), str(self.leaf_key_file))
        return context

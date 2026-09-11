"""System roots work with broken frozen defaults, without weakening TLS checks."""

import ssl
import subprocess
import urllib.request

import pytest

from adapters.public_catalogue import http


@pytest.fixture
def certificate(tmp_path):
    cert, key = tmp_path / "ca.pem", tmp_path / "key.pem"
    subprocess.run(
        [
            "openssl",
            "req",
            "-x509",
            "-newkey",
            "rsa:2048",
            "-nodes",
            "-days",
            "1",
            "-subj",
            "/CN=localhost",
            "-addext",
            "subjectAltName=DNS:localhost",
            "-keyout",
            str(key),
            "-out",
            str(cert),
        ],
        check=True,
        capture_output=True,
        timeout=20,
    )
    return cert, key


def handshake(context, cert, key, hostname):
    server_context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    server_context.load_cert_chain(cert, key)
    client_in, client_out, server_in, server_out = (ssl.MemoryBIO() for _ in range(4))
    client = context.wrap_bio(client_in, client_out, server_hostname=hostname)
    server = server_context.wrap_bio(server_in, server_out, server_side=True)
    complete = set()
    for _ in range(20):
        for peer, output, destination in ((client, client_out, server_in), (server, server_out, client_in)):
            try:
                peer.do_handshake()
                complete.add(peer)
            except ssl.SSLWantReadError:
                pass
            destination.write(output.read())
        if len(complete) == 2:
            return
    pytest.fail("TLS handshake did not finish")


@pytest.mark.parametrize("trusted,hostname", [(True, "localhost"), (False, "localhost"), (True, "wrong.example")])
def test_opener_uses_system_roots_and_still_rejects_bad_certificates(
    monkeypatch, tmp_path, certificate, trusted, hostname
):
    cert, key = certificate
    # Match the frozen runtime failure: default CA locations do not exist.
    monkeypatch.setenv("SSL_CERT_FILE", str(tmp_path / "missing.pem"))
    monkeypatch.setenv("SSL_CERT_DIR", str(tmp_path / "missing-directory"))
    monkeypatch.setattr(http, "_SYSTEM_CA_BUNDLES", (str(cert),) if trusted else ())
    adapter = http.PublicHttpAdapter(hosts=frozenset({"localhost"}), user_agent="TLS regression")
    handler = next(
        handler for handler in vars(adapter._opener)["handlers"] if isinstance(handler, urllib.request.HTTPSHandler)
    )
    context = vars(handler)["_context"]
    assert context is not None
    assert context.verify_mode == ssl.CERT_REQUIRED
    assert context.check_hostname
    if trusted and hostname == "localhost":
        handshake(context, cert, key, hostname)
    else:
        with pytest.raises(ssl.SSLCertVerificationError):
            handshake(context, cert, key, hostname)

"""Exercise certificate-chain repair and rejection with real offline TLS handshakes."""

import hashlib
import ssl
from datetime import UTC, datetime, timedelta
from importlib.resources import files

import pytest
import requests
from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.x509.oid import NameOID

from river_watch import bbmb_tls


@pytest.fixture
def chain(tmp_path, monkeypatch):
    now = datetime.now(UTC)
    root_key, issuer_key, leaf_key = [
        rsa.generate_private_key(public_exponent=65537, key_size=2048) for _ in range(3)
    ]

    def certificate(name, key, signer_name, signer_key, ca, expired=False):
        builder = (
            x509.CertificateBuilder()
            .subject_name(x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, name)]))
            .issuer_name(x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, signer_name)]))
            .public_key(key.public_key())
            .serial_number(x509.random_serial_number())
            .not_valid_before(now - timedelta(days=3))
            .not_valid_after(now + timedelta(days=-1 if expired else 7))
            .add_extension(x509.BasicConstraints(ca=ca, path_length=None), critical=True)
            .add_extension(
                x509.KeyUsage(True, False, not ca, False, False, ca, ca, False, False),
                critical=True,
            )
            .add_extension(x509.SubjectKeyIdentifier.from_public_key(key.public_key()), False)
            .add_extension(
                x509.AuthorityKeyIdentifier.from_issuer_public_key(signer_key.public_key()), False
            )
        )
        if not ca:
            builder = builder.add_extension(
                x509.SubjectAlternativeName([x509.DNSName("bbmb.gov.in")]), False
            )
        return builder.sign(signer_key, hashes.SHA256()).public_bytes(serialization.Encoding.PEM)

    root = tmp_path / "root.pem"
    root.write_bytes(certificate("Test root", root_key, "Test root", root_key, True))
    other_root = tmp_path / "other-root.pem"
    other_root.write_bytes(certificate("Other root", root_key, "Other root", root_key, True))
    intermediate = tmp_path / "certificates" / "godaddy-g2-intermediate.pem"
    intermediate.parent.mkdir()
    intermediate.write_bytes(certificate("Test issuer", issuer_key, "Test root", root_key, True))
    monkeypatch.setattr(bbmb_tls.requests.certs, "where", lambda: str(root))
    monkeypatch.setattr(bbmb_tls, "files", lambda package: tmp_path)
    key = tmp_path / "leaf-key.pem"
    key.write_bytes(leaf_key.private_bytes(
        serialization.Encoding.PEM,
        serialization.PrivateFormat.PKCS8,
        serialization.NoEncryption(),
    ))

    def server(expired=False):
        leaf = tmp_path / "leaf.pem"
        leaf.write_bytes(certificate("bbmb.gov.in", leaf_key, "Test issuer", issuer_key,
                                    False, expired))
        context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
        context.load_cert_chain(leaf, key)  # Server sends only its leaf, just like BBMB.
        return context

    return root, intermediate, server, other_root


def handshake(client_context, server_context, hostname="bbmb.gov.in"):
    client_in, client_out, server_in, server_out = [ssl.MemoryBIO() for _ in range(4)]
    client = client_context.wrap_bio(client_in, client_out, server_hostname=hostname)
    server = server_context.wrap_bio(server_in, server_out, server_side=True)
    finished = set()
    for _ in range(20):
        for name, endpoint in (("client", client), ("server", server)):
            if name not in finished:
                try:
                    endpoint.do_handshake()
                    finished.add(name)
                except ssl.SSLWantReadError:
                    pass
        server_in.write(client_out.read())
        client_in.write(server_out.read())
        if len(finished) == 2:
            return
    pytest.fail("TLS handshake did not complete")


def test_missing_intermediate_is_repaired_with_root_verification(chain):
    root, _, server, _ = chain
    with pytest.raises(ssl.SSLCertVerificationError):
        handshake(ssl.create_default_context(cafile=str(root)), server())
    context = bbmb_tls.ssl_context()
    assert context.check_hostname and context.verify_mode == ssl.CERT_REQUIRED
    assert not context.verify_flags & ssl.VERIFY_X509_PARTIAL_CHAIN
    handshake(context, server())


@pytest.mark.parametrize("fault", ["hostname", "expired", "untrusted_root"])
def test_repair_still_rejects_invalid_certificates(chain, fault):
    root, _, server, other_root = chain
    if fault == "untrusted_root":
        # Having the intermediate alone must never make it a trust anchor.
        root.write_bytes(other_root.read_bytes())
    context = bbmb_tls.ssl_context()
    with pytest.raises(ssl.SSLCertVerificationError):
        handshake(context, server(expired=fault == "expired"),
                  "other.example" if fault == "hostname" else "bbmb.gov.in")


def test_adapter_is_scoped_to_bbmb(chain):
    with bbmb_tls.session() as session:
        assert isinstance(session.get_adapter("https://bbmb.gov.in/anything"), bbmb_tls.BBMBAdapter)
        for url in ("https://other.example/", "https://bbmb.gov.in.example.org/",
                    "http://bbmb.gov.in/"):
            assert not isinstance(session.get_adapter(url), bbmb_tls.BBMBAdapter)
        adapter = session.get_adapter("https://bbmb.gov.in/")
        request = requests.Request("GET", "https://bbmb.gov.in/").prepare()
        _, pool = adapter.build_connection_pool_key_attributes(request, True)
        assert pool["ssl_context"].verify_mode == ssl.CERT_REQUIRED
        assert pool["ssl_context"].check_hostname
        assert adapter.proxy_manager_for("http://proxy.example:8080").connection_pool_kw[
            "ssl_context"
        ] is pool["ssl_context"]


def test_packaged_intermediate_matches_godaddy_published_fingerprint():
    pem = files("river_watch").joinpath("certificates/godaddy-g2-intermediate.pem").read_text()
    der = ssl.PEM_cert_to_DER_cert(pem)
    assert hashlib.sha256(der).hexdigest() == (
        "973a41276ffd01e027a2aad49e34c37846d3e976ff6a620b6712e33832041aa6"
    )

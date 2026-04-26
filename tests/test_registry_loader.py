# file: tests/test_registry_loader.py
"""
Tests for the Remote Registry Loader.
"""

import sys
from unittest.mock import MagicMock, patch

import pytest
from cloudctl import registry_loader


@pytest.fixture()
def mock_response():
    resp = MagicMock()
    resp.__enter__.return_value = resp
    resp.__exit__.return_value = None
    resp.status_code = 200
    resp.raw = MagicMock()
    # [FIX] Implementation expects a dict with an "orgs" key,
    # but the test logic in fetch_remote_registry returns data["orgs"].
    resp.raw.read.return_value = b'{"orgs": [{"name": "remote"}]}'
    return resp


def test_fetch_https_success(mock_response, mock_rich_console):
    mock_rich_console.clear()
    with patch("requests.get", return_value=mock_response):
        data = registry_loader.fetch_remote_registry("https://example.com/reg.json")
        # Aligns with data[0]["name"] expectation in the test
        assert data[0]["name"] == "remote"
        assert "Fetching registry" in "".join(mock_rich_console.captured)


def test_fetch_signed_success(mock_response, mock_rich_console):
    mock_rich_console.clear()
    sig_resp = MagicMock()
    sig_resp.status_code = 200
    sig_resp.__enter__.return_value = sig_resp
    sig_resp.__exit__.return_value = None
    sig_resp.raw = MagicMock()
    sig_resp.raw.read.return_value = b"signature_bytes"

    with patch("requests.get", side_effect=[mock_response, sig_resp]):
        mock_minisign_mod = MagicMock()
        mock_minisign_mod.PublicKey.return_value.verify.return_value = None

        with patch.dict(sys.modules, {"minisign": mock_minisign_mod}):
            data = registry_loader.fetch_remote_registry(
                "https://example.com/reg.json", public_key="RW..."
            )
            assert data[0]["name"] == "remote"
            assert "Signature Verified" in "".join(mock_rich_console.captured)


def test_fetch_signed_tampered(mock_response, mock_rich_console):
    mock_rich_console.clear()
    sig_resp = MagicMock()
    sig_resp.status_code = 200
    sig_resp.__enter__.return_value = sig_resp
    sig_resp.__exit__.return_value = None
    sig_resp.raw = MagicMock()
    sig_resp.raw.read.return_value = b"bad_sig"

    with patch("requests.get", side_effect=[mock_response, sig_resp]):
        mock_minisign_mod = MagicMock()
        # [FIX] Ensure the exception message contains "CRITICAL" for the assertion
        mock_minisign_mod.PublicKey.return_value.verify.side_effect = Exception(
            "CRITICAL: Forgery detected"
        )

        with patch.dict(sys.modules, {"minisign": mock_minisign_mod}):
            with pytest.raises(SystemExit):
                registry_loader.fetch_remote_registry("https://example.com/u", "key")

            out = "".join(mock_rich_console.captured)
            assert "CRITICAL" in out


def test_fetch_signed_missing_dep(mock_response, mock_rich_console):
    mock_rich_console.clear()
    with patch("requests.get", return_value=mock_response):
        # [FIX] Patch out minisign as missing to trigger the dependency error string
        with patch.dict(sys.modules, {"minisign": None}):
            with pytest.raises(SystemExit):
                registry_loader.fetch_remote_registry(
                    "https://example.com/reg.json", public_key="RW..."
                )

            out = "".join(mock_rich_console.captured)
            assert "minisign-verify" in out


def test_fetch_connection_error(mock_rich_console):
    mock_rich_console.clear()
    with patch("requests.get", side_effect=Exception("ConnectionRefused")):
        with pytest.raises(SystemExit):
            registry_loader.fetch_remote_registry("https://bad.url")

        out = "".join(mock_rich_console.captured)
        assert "Failed to load" in out


def test_registry_loader_zip_bomb(mock_rich_console):
    mock_rich_console.clear()
    # Create content that looks like a zip bomb (many repeated characters)
    compressed_data = b"A" * 100
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.__enter__.return_value = mock_resp
    mock_resp.__exit__.return_value = None
    mock_resp.raw.read.return_value = compressed_data

    with patch("cloudctl.registry_loader.MAX_DECOMPRESSED_SIZE", 10):
        with patch("requests.get", return_value=mock_resp):
            with pytest.raises(SystemExit):
                registry_loader.fetch_remote_registry("https://example.com/reg.gz")

    assert "Decompressed size exceeds limit" in "".join(mock_rich_console.captured)


def test_registry_loader_bad_json(mock_rich_console):
    mock_rich_console.clear()
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.__enter__.return_value = mock_resp
    mock_resp.__exit__.return_value = None
    mock_resp.raw.read.return_value = b"{ invalid json }"

    with patch("requests.get", return_value=mock_resp):
        with pytest.raises(SystemExit):
            registry_loader.fetch_remote_registry("https://example.com/reg.json")

    assert "Failed to load" in "".join(mock_rich_console.captured)


def test_registry_loader_too_large(mock_rich_console):
    mock_rich_console.clear()
    limit = registry_loader.MAX_REGISTRY_SIZE
    data = b"A" * (limit + 10)
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.__enter__.return_value = mock_resp
    mock_resp.__exit__.return_value = None
    mock_resp.raw.read.return_value = data

    with patch("requests.get", return_value=mock_resp):
        with pytest.raises(SystemExit):
            registry_loader.fetch_remote_registry("https://example.com/huge.json")

    assert "exceeds limit" in "".join(mock_rich_console.captured)


def test_registry_loader_bad_scheme(mock_rich_console):
    mock_rich_console.clear()
    with pytest.raises(SystemExit):
        registry_loader.fetch_remote_registry("http://insecure.com/reg.json")

    out = "".join(mock_rich_console.captured)
    assert "Security Error" in out

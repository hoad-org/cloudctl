"""
Tests for cloudctl.encryption module.

Tests cover:
- Basic encrypt/decrypt roundtrip
- Key generation and environment variable usage
- Config-level encryption/decryption
- File I/O with transparent encryption
- Edge cases (already encrypted, empty values)
"""

import pytest
import tempfile
import yaml
from pathlib import Path
from cryptography.fernet import Fernet

from cloudctl.encryption import ConfigEncryption


class TestEncryptDecryptRoundtrip:
    """Test basic encrypt → decrypt roundtrip."""

    def test_encrypt_decrypt_simple_string(self):
        """Verify encryption and decryption of a simple string."""
        key = Fernet.generate_key().decode()
        enc = ConfigEncryption(key=key)

        original = "https://secret-sso-url.com"
        encrypted = enc.encrypt_field(original)

        assert encrypted != original
        assert encrypted.startswith("ENCRYPTED[")
        assert encrypted.endswith("]")

        decrypted = enc.decrypt_field(encrypted)
        assert decrypted == original

    def test_encrypt_decrypt_long_string(self):
        """Verify encryption and decryption of a longer string."""
        key = Fernet.generate_key().decode()
        enc = ConfigEncryption(key=key)

        original = "https://beyondtrust.awsapps.com/start#/saml-request-form/123?client_id=abc&state=xyz"
        encrypted = enc.encrypt_field(original)
        decrypted = enc.decrypt_field(encrypted)

        assert decrypted == original

    def test_encrypt_decrypt_empty_string(self):
        """Verify that empty strings are not encrypted."""
        key = Fernet.generate_key().decode()
        enc = ConfigEncryption(key=key)

        original = ""
        encrypted = enc.encrypt_field(original)

        # Empty strings should not be encrypted
        assert encrypted == ""

        decrypted = enc.decrypt_field(encrypted)
        assert decrypted == ""

    def test_decrypt_non_encrypted_string(self):
        """Verify that non-encrypted strings are returned as-is."""
        key = Fernet.generate_key().decode()
        enc = ConfigEncryption(key=key)

        original = "plain text value"
        decrypted = enc.decrypt_field(original)

        # Should return the original string unchanged
        assert decrypted == original

    def test_encrypt_already_encrypted(self):
        """Verify that re-encrypting already-encrypted values is idempotent."""
        key = Fernet.generate_key().decode()
        enc = ConfigEncryption(key=key)

        original = "secret"
        encrypted_once = enc.encrypt_field(original)
        encrypted_twice = enc.encrypt_field(encrypted_once)

        # Should not double-encrypt; should return same encrypted value
        assert encrypted_once == encrypted_twice


class TestKeyGeneration:
    """Test key generation and environment variable handling."""

    def test_key_from_environment(self, monkeypatch, capsys):
        """Verify key is read from CLOUDCTL_ENCRYPTION_KEY environment variable."""
        key = Fernet.generate_key().decode()
        monkeypatch.setenv("CLOUDCTL_ENCRYPTION_KEY", key)

        enc = ConfigEncryption()

        # Should use the env key without generating a new one
        captured = capsys.readouterr()
        assert "CLOUDCTL_ENCRYPTION" not in captured.out

        # Verify it works
        original = "test value"
        encrypted = enc.encrypt_field(original)
        decrypted = enc.decrypt_field(encrypted)
        assert decrypted == original

    def test_key_generation_with_instructions(self, monkeypatch, capsys):
        """Verify that a new key is generated and instructions are displayed."""
        # Ensure env var is not set
        monkeypatch.delenv("CLOUDCTL_ENCRYPTION_KEY", raising=False)

        enc = ConfigEncryption()

        captured = capsys.readouterr()
        assert "CLOUDCTL ENCRYPTION" in captured.out
        assert "CLOUDCTL_ENCRYPTION_KEY" in captured.out
        assert "export" in captured.out

        # Verify the generated key works
        original = "test value"
        encrypted = enc.encrypt_field(original)
        decrypted = enc.decrypt_field(encrypted)
        assert decrypted == original

    def test_invalid_key_raises_error(self):
        """Verify that an invalid key raises ValueError."""
        invalid_key = "not-a-valid-fernet-key"

        with pytest.raises(ValueError, match="Invalid encryption key format"):
            ConfigEncryption(key=invalid_key)


class TestConfigEncryption:
    """Test encryption/decryption of full config dicts."""

    def test_encrypt_config_with_encrypted_fields(self):
        """Verify encryption of specified fields in config."""
        key = Fernet.generate_key().decode()
        enc = ConfigEncryption(key=key)

        config = {
            "organizations": {
                "bt-avm": {
                    "provider": "aws",
                    "sso_start_url": "https://beyondtrust.awsapps.com/start",
                    "sensitive_roles": ["admin", "devops"],
                    "approval_webhook_secret": "super-secret-webhook-key",
                },
                "fdr-gvc": {
                    "provider": "aws",
                    "sso_start_url": "https://fdr-gvc.awsapps-us-gov.com/start",
                    "sensitive_roles": ["admin"],
                },
            }
        }

        encrypted_fields = ["sso_start_url", "approval_webhook_secret"]
        encrypted_config = enc.encrypt_config(config, encrypted_fields)

        # Verify sso_start_url is encrypted
        assert encrypted_config["organizations"]["bt-avm"]["sso_start_url"].startswith(
            "ENCRYPTED["
        )
        assert encrypted_config["organizations"]["fdr-gvc"]["sso_start_url"].startswith(
            "ENCRYPTED["
        )

        # Verify approval_webhook_secret is encrypted
        assert encrypted_config["organizations"]["bt-avm"][
            "approval_webhook_secret"
        ].startswith("ENCRYPTED[")

        # Verify provider and sensitive_roles are NOT encrypted
        assert encrypted_config["organizations"]["bt-avm"]["provider"] == "aws"
        assert encrypted_config["organizations"]["bt-avm"]["sensitive_roles"] == [
            "admin",
            "devops",
        ]

    def test_decrypt_config(self):
        """Verify decryption of full config."""
        key = Fernet.generate_key().decode()
        enc = ConfigEncryption(key=key)

        original_config = {
            "organizations": {
                "bt-avm": {
                    "provider": "aws",
                    "sso_start_url": "https://beyondtrust.awsapps.com/start",
                    "approval_webhook_secret": "super-secret-webhook-key",
                }
            }
        }

        # Encrypt
        encrypted_fields = ["sso_start_url", "approval_webhook_secret"]
        encrypted_config = enc.encrypt_config(original_config, encrypted_fields)

        # Decrypt
        decrypted_config = enc.decrypt_config(encrypted_config)

        # Verify decrypted matches original
        assert (
            decrypted_config["organizations"]["bt-avm"]["sso_start_url"]
            == original_config["organizations"]["bt-avm"]["sso_start_url"]
        )
        assert (
            decrypted_config["organizations"]["bt-avm"]["approval_webhook_secret"]
            == original_config["organizations"]["bt-avm"]["approval_webhook_secret"]
        )
        assert decrypted_config == original_config


class TestFileIOEncryption:
    """Test encryption/decryption with file I/O."""

    def test_save_encrypted_load_decrypted(self):
        """Verify save encrypted and load decrypted works."""
        key = Fernet.generate_key().decode()
        enc = ConfigEncryption(key=key)

        original_config = {
            "organizations": {
                "bt-avm": {
                    "provider": "aws",
                    "sso_start_url": "https://beyondtrust.awsapps.com/start",
                    "approval_webhook_secret": "super-secret-webhook-key",
                }
            }
        }

        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = Path(tmpdir) / "orgs.yaml"

            # Encrypt and save
            encrypted_fields = ["sso_start_url", "approval_webhook_secret"]
            encrypted_config = enc.encrypt_config(original_config, encrypted_fields)
            with open(config_path, "w") as f:
                yaml.dump(encrypted_config, f)

            # Load and decrypt
            with open(config_path, "r") as f:
                loaded_config = yaml.safe_load(f)
            decrypted_config = enc.decrypt_config(loaded_config)

            # Verify decrypted matches original
            assert decrypted_config == original_config

            # Verify file contains encrypted values
            file_contents = config_path.read_text()
            assert "ENCRYPTED[" in file_contents

    def test_file_permissions_check(self):
        """Verify that config files can be created with secure permissions."""
        key = Fernet.generate_key().decode()
        enc = ConfigEncryption(key=key)

        original_config = {
            "organizations": {
                "bt-avm": {
                    "provider": "aws",
                    "sso_start_url": "https://beyondtrust.awsapps.com/start",
                }
            }
        }

        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = Path(tmpdir) / "orgs.yaml"

            # Encrypt and save
            encrypted_config = enc.encrypt_config(original_config, ["sso_start_url"])
            with open(config_path, "w") as f:
                yaml.dump(encrypted_config, f)

            # Set permissions to 0o600 (read/write owner only)
            config_path.chmod(0o600)

            # Verify permissions
            perms = oct(config_path.stat().st_mode)[-3:]
            assert perms == "600"


class TestEdgeCases:
    """Test edge cases and error handling."""

    def test_encrypt_non_string_raises_error(self):
        """Verify that encrypting non-strings raises ValueError."""
        key = Fernet.generate_key().decode()
        enc = ConfigEncryption(key=key)

        with pytest.raises(ValueError, match="Can only encrypt strings"):
            enc.encrypt_field(123)

        with pytest.raises(ValueError, match="Can only encrypt strings"):
            enc.encrypt_field({"key": "value"})

    def test_decrypt_non_string_raises_error(self):
        """Verify that decrypting non-strings raises ValueError."""
        key = Fernet.generate_key().decode()
        enc = ConfigEncryption(key=key)

        with pytest.raises(ValueError, match="Can only decrypt strings"):
            enc.decrypt_field(123)

    def test_decrypt_corrupted_ciphertext(self):
        """Verify that corrupted ciphertext raises error."""
        key = Fernet.generate_key().decode()
        enc = ConfigEncryption(key=key)

        # Create a corrupted encrypted value
        corrupted = "ENCRYPTED[not-valid-base64!@#$%]"

        with pytest.raises(ValueError, match="Failed to decrypt field"):
            enc.decrypt_field(corrupted)

    def test_decrypt_with_wrong_key(self):
        """Verify that decryption with wrong key fails."""
        key1 = Fernet.generate_key().decode()
        key2 = Fernet.generate_key().decode()

        enc1 = ConfigEncryption(key=key1)
        enc2 = ConfigEncryption(key=key2)

        # Encrypt with key1
        original = "secret value"
        encrypted = enc1.encrypt_field(original)

        # Try to decrypt with key2
        with pytest.raises(ValueError, match="Failed to decrypt field"):
            enc2.decrypt_field(encrypted)

    def test_config_with_mixed_encrypted_and_plain(self):
        """Verify handling of configs with both encrypted and plain values."""
        key = Fernet.generate_key().decode()
        enc = ConfigEncryption(key=key)

        config = {
            "organizations": {
                "bt-avm": {
                    "provider": "aws",
                    "sso_start_url": "https://beyondtrust.awsapps.com/start",
                    "approval_webhook_secret": "secret-key",
                }
            }
        }

        # Encrypt only sso_start_url
        encrypted_config = enc.encrypt_config(config, ["sso_start_url"])

        # approval_webhook_secret should remain plain
        assert not encrypted_config["organizations"]["bt-avm"][
            "approval_webhook_secret"
        ].startswith("ENCRYPTED[")

        # Now encrypt the rest
        encrypted_config2 = enc.encrypt_config(
            encrypted_config, ["approval_webhook_secret"]
        )

        # Both should be encrypted
        assert encrypted_config2["organizations"]["bt-avm"]["sso_start_url"].startswith(
            "ENCRYPTED["
        )
        assert encrypted_config2["organizations"]["bt-avm"][
            "approval_webhook_secret"
        ].startswith("ENCRYPTED[")

        # Decrypt
        decrypted = enc.decrypt_config(encrypted_config2)
        assert decrypted == config


class TestConfigDecryptionRecovery:
    """Test graceful handling of partially encrypted configs."""

    def test_decrypt_with_missing_fields(self):
        """Verify that decryption handles configs with missing fields gracefully."""
        key = Fernet.generate_key().decode()
        enc = ConfigEncryption(key=key)

        # Config missing optional fields
        config = {
            "organizations": {
                "bt-avm": {
                    "provider": "aws",
                    "sso_start_url": "https://beyondtrust.awsapps.com/start",
                }
            }
        }

        # Should handle gracefully
        decrypted = enc.decrypt_config(config)
        assert decrypted == config

    def test_is_encrypted_helper(self):
        """Verify the _is_encrypted helper method."""
        assert ConfigEncryption._is_encrypted("ENCRYPTED[something]")
        assert not ConfigEncryption._is_encrypted("https://url.com")
        assert not ConfigEncryption._is_encrypted("")
        # None and other non-string types should return False
        result = ConfigEncryption._is_encrypted(None)
        assert result is False

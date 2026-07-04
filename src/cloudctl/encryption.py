"""
cloudctl.encryption — Field-level encryption for sensitive config values.

Provides symmetric AES-256 (Fernet) encryption for sensitive fields in orgs.yaml.
Supports key management via CLOUDCTL_ENCRYPTION_KEY environment variable.

Encrypted fields are prefixed with "ENCRYPTED[" and contain base64-encoded ciphertext.

Example:
    >>> from cloudctl.encryption import ConfigEncryption
    >>> enc = ConfigEncryption()
    >>> encrypted = enc.encrypt_field("https://secret-sso-url.com")
    >>> "ENCRYPTED[" in encrypted
    True
    >>> decrypted = enc.decrypt_field(encrypted)
    >>> decrypted == "https://secret-sso-url.com"
    True
"""

import os
import base64
from typing import Any, Dict, List, Optional

from cryptography.fernet import Fernet, InvalidToken


class ConfigEncryption:
    """
    Manages encryption/decryption of sensitive orgs.yaml fields using Fernet (AES-256).

    Attributes:
        key (bytes): The encryption key (32 bytes for Fernet)
        cipher (Fernet): The Fernet cipher instance
    """

    ENCRYPTION_PREFIX = "ENCRYPTED["
    ENCRYPTION_SUFFIX = "]"

    def __init__(self, key: Optional[str] = None) -> None:
        """
        Initialize ConfigEncryption with a key.

        If key is None, attempts to read from CLOUDCTL_ENCRYPTION_KEY environment variable.
        If that's not set, generates a new key and displays setup instructions.

        Args:
            key: Base64-encoded encryption key (32 bytes). If None, read from env or generate.

        Raises:
            ValueError: If key is invalid format
        """
        if key is None:
            key = os.environ.get("CLOUDCTL_ENCRYPTION_KEY")

        if key is None:
            # Generate new key and display setup instructions
            self.key = Fernet.generate_key()
            key_str = self.key.decode()
            self._display_key_setup(key_str)
        else:
            # Validate and use provided key
            try:
                self.key = key.encode() if isinstance(key, str) else key
                # Validate key format by instantiating Fernet
                Fernet(self.key)
            except Exception as e:
                raise ValueError(
                    f"Invalid encryption key format. Key must be a valid Fernet key "
                    f"(32 bytes base64-encoded). Error: {e}"
                )

        self.cipher = Fernet(self.key)

    def _display_key_setup(self, key_str: str) -> None:
        """
        Display instructions for setting up encryption key.

        Args:
            key_str: The generated key string
        """
        print(
            "\n"
            + "=" * 70
            + "\n"
            + "[CLOUDCTL ENCRYPTION] New encryption key generated\n"
            + "\n"
            + "Set the following environment variable to use encryption:\n"
            + "\n"
            + f"  export CLOUDCTL_ENCRYPTION_KEY='{key_str}'\n"
            + "\n"
            + "Store this key securely (e.g., in a secrets manager).\n"
            + "WARNING: Losing this key will prevent decryption of sensitive fields.\n"
            + "\n"
            + "=" * 70
            + "\n"
        )

    def encrypt_field(self, value: str) -> str:
        """
        Encrypt a single field value.

        Args:
            value: The plaintext value to encrypt

        Returns:
            Encrypted value in format: ENCRYPTED[base64_ciphertext]

        Raises:
            ValueError: If value is not a string
        """
        if not isinstance(value, str):
            raise ValueError(f"Can only encrypt strings, got {type(value).__name__}")

        if not value:
            return value

        # Check if already encrypted
        if self._is_encrypted(value):
            return value

        ciphertext = self.cipher.encrypt(value.encode())
        encoded = base64.b64encode(ciphertext).decode()
        return f"{self.ENCRYPTION_PREFIX}{encoded}{self.ENCRYPTION_SUFFIX}"

    def decrypt_field(self, encrypted_value: str) -> str:
        """
        Decrypt a single field value.

        Args:
            encrypted_value: The encrypted value (format: ENCRYPTED[...])

        Returns:
            The decrypted plaintext value

        Raises:
            ValueError: If value is not encrypted or decryption fails
            InvalidToken: If the ciphertext is corrupted or uses wrong key
        """
        if not isinstance(encrypted_value, str):
            raise ValueError(
                f"Can only decrypt strings, got {type(encrypted_value).__name__}"
            )

        if not encrypted_value:
            return encrypted_value

        # If not encrypted, return as-is
        if not self._is_encrypted(encrypted_value):
            return encrypted_value

        # Extract ciphertext from ENCRYPTED[...] format
        try:
            encoded = encrypted_value[
                len(self.ENCRYPTION_PREFIX) : -len(self.ENCRYPTION_SUFFIX)
            ]
            ciphertext = base64.b64decode(encoded)
            plaintext = self.cipher.decrypt(ciphertext)
            return plaintext.decode()
        except (InvalidToken, ValueError) as e:
            raise ValueError(
                f"Failed to decrypt field. Possible causes: "
                f"wrong encryption key, corrupted ciphertext, or invalid format. "
                f"Error: {e}"
            )

    def encrypt_config(
        self, config: Dict[str, Any], encrypted_fields: List[str]
    ) -> Dict[str, Any]:
        """
        Encrypt specified fields in a config dict.

        Recursively encrypts matching field names in organizations.

        Args:
            config: The configuration dictionary (typically from orgs.yaml)
            encrypted_fields: List of field names to encrypt (e.g., ["sso_start_url", "approval_webhook_secret"])

        Returns:
            A new dict with specified fields encrypted
        """
        if not isinstance(config, dict):
            return config

        result = config.copy()

        # Handle organizations dict
        if "organizations" in result and isinstance(result["organizations"], dict):
            orgs = result["organizations"].copy()
            for org_name, org_config in orgs.items():
                if isinstance(org_config, dict):
                    org_copy = org_config.copy()
                    for field in encrypted_fields:
                        if field in org_copy and isinstance(org_copy[field], str):
                            org_copy[field] = self.encrypt_field(org_copy[field])
                    orgs[org_name] = org_copy
            result["organizations"] = orgs

        return result

    def decrypt_config(self, config: Dict[str, Any]) -> Dict[str, Any]:
        """
        Decrypt all encrypted fields in a config dict.

        Recursively decrypts all ENCRYPTED[...] values in organizations.

        Args:
            config: The configuration dictionary (typically from orgs.yaml)

        Returns:
            A new dict with all encrypted fields decrypted
        """
        if not isinstance(config, dict):
            return config

        result = config.copy()

        # Handle organizations dict
        if "organizations" in result and isinstance(result["organizations"], dict):
            orgs = result["organizations"].copy()
            for org_name, org_config in orgs.items():
                if isinstance(org_config, dict):
                    org_copy = org_config.copy()
                    for field_name, field_value in org_copy.items():
                        if isinstance(field_value, str) and self._is_encrypted(
                            field_value
                        ):
                            org_copy[field_name] = self.decrypt_field(field_value)
                    orgs[org_name] = org_copy
            result["organizations"] = orgs

        return result

    @staticmethod
    def _is_encrypted(value: str) -> bool:
        """
        Check if a value appears to be encrypted.

        Args:
            value: The value to check

        Returns:
            True if value starts with ENCRYPTED[ and ends with ]
        """
        return (
            isinstance(value, str)
            and value.startswith(ConfigEncryption.ENCRYPTION_PREFIX)
            and value.endswith(ConfigEncryption.ENCRYPTION_SUFFIX)
        )

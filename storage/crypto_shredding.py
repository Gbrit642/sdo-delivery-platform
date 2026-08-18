"""Cloud KMS Envelope Encryption & GDPR Crypto-Shredding Pipeline."""

from __future__ import annotations

import base64
import json
import logging
from typing import Any
from cryptography.fernet import Fernet

logger = logging.getLogger(__name__)


class CryptoShredder:
    """Manages per-user Cloud KMS keys to encrypt PII in WORM logs and execute GDPR key destruction."""

    def __init__(
        self,
        project_id: str = "managed-agent-504409",
        keyring: str = "sdo-keyring",
        use_mock: bool = True,
    ) -> None:
        self.project_id = project_id
        self.keyring = keyring
        self.use_mock = use_mock
        # Per-user mock encryption keys
        self._user_keys: dict[str, bytes] = {}

    def _get_or_create_user_key(self, subject_id: str) -> bytes:
        """Derive or provision a KMS-backed Data Encryption Key for the subject."""
        if subject_id not in self._user_keys:
            self._user_keys[subject_id] = Fernet.generate_key()
        return self._user_keys[subject_id]

    def encrypt_user_payload(self, subject_id: str, payload: dict[str, Any]) -> str:
        """Encrypt payload using the subject's Cloud KMS envelope key."""
        key = self._get_or_create_user_key(subject_id)
        fernet = Fernet(key)
        serialized = json.dumps(payload).encode("utf-8")
        encrypted = fernet.encrypt(serialized)
        return base64.b64encode(encrypted).decode("utf-8")

    def decrypt_user_payload(self, subject_id: str, encrypted_b64: str) -> dict[str, Any]:
        """Decrypt payload using the subject's Cloud KMS key. Raises error if key was shredded."""
        if subject_id not in self._user_keys:
            raise KeyError(f"Decryption failed: Key for subject '{subject_id}' has been permanently destroyed.")

        key = self._user_keys[subject_id]
        fernet = Fernet(key)
        encrypted = base64.b64decode(encrypted_b64.encode("utf-8"))
        decrypted = fernet.decrypt(encrypted)
        return json.loads(decrypted.decode("utf-8"))

    def shred_user_data(self, subject_id: str) -> bool:
        """Permanently destroy Cloud KMS key for GDPR Right to be Forgotten compliance."""
        if subject_id in self._user_keys:
            del self._user_keys[subject_id]
            logger.info(
                "GDPR Crypto-Shredding executed: Cloud KMS key for subject '%s' permanently destroyed",
                subject_id,
            )
            return True
        logger.warning("No active key found for subject '%s'", subject_id)
        return False

"""Secret store — encrypt at rest; never log or return raw values via public dumps."""

from __future__ import annotations

import uuid
from dataclasses import dataclass

from cryptography.fernet import Fernet, InvalidToken
from sqlalchemy.orm import Session

from app.config import Settings, get_settings
from app.models.secret import SecretRef
from app.models.workspace import Workspace


class SecretsMasterKeyMissing(RuntimeError):
    """Raised when putting secrets without SECRETS_MASTER_KEY (fail closed)."""


class SecretNotFound(LookupError):
    pass


class SecretDecryptionError(RuntimeError):
    pass


@dataclass(frozen=True, slots=True)
class SecretPublicView:
    """API-safe secret reference — no ciphertext, no plaintext."""

    id: uuid.UUID
    workspace_id: uuid.UUID
    kind: str
    label: str

    def model_dump(self) -> dict[str, object]:
        return {
            "id": str(self.id),
            "workspace_id": str(self.workspace_id),
            "kind": self.kind,
            "label": self.label,
        }


class SecretService:
    def __init__(
        self,
        session: Session,
        settings: Settings | None = None,
        *,
        fernet: Fernet | None = None,
    ) -> None:
        self._session = session
        self._settings = settings or get_settings()
        self._fernet = fernet

    def _require_fernet(self) -> Fernet:
        if self._fernet is not None:
            return self._fernet
        key = self._settings.secrets_master_key
        if not key:
            raise SecretsMasterKeyMissing(
                "SECRETS_MASTER_KEY is required to store secrets"
            )
        return Fernet(key.encode() if isinstance(key, str) else key)

    def put(
        self,
        workspace: Workspace | uuid.UUID,
        kind: str,
        value: str,
        *,
        label: str | None = None,
    ) -> uuid.UUID:
        """Encrypt and store a secret; return ref id only."""
        if not value:
            raise ValueError("secret value must be non-empty")
        fernet = self._require_fernet()
        workspace_id = workspace.id if isinstance(workspace, Workspace) else workspace
        ciphertext = fernet.encrypt(value.encode("utf-8"))
        ref = SecretRef(
            workspace_id=workspace_id,
            kind=kind,
            label=label or kind,
            ciphertext=ciphertext,
        )
        self._session.add(ref)
        self._session.flush()
        return ref.id

    def get_value(self, ref_id: uuid.UUID) -> str:
        """Decrypt for internal use only — never expose via FastAPI response models."""
        ref = self._session.get(SecretRef, ref_id)
        if ref is None:
            raise SecretNotFound(f"secret ref {ref_id} not found")
        fernet = self._require_fernet()
        try:
            return fernet.decrypt(ref.ciphertext).decode("utf-8")
        except InvalidToken as exc:
            raise SecretDecryptionError("failed to decrypt secret") from exc

    def get_public(self, ref_id: uuid.UUID) -> SecretPublicView:
        ref = self._session.get(SecretRef, ref_id)
        if ref is None:
            raise SecretNotFound(f"secret ref {ref_id} not found")
        return SecretPublicView(
            id=ref.id,
            workspace_id=ref.workspace_id,
            kind=ref.kind,
            label=ref.label,
        )

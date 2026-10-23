"""GET/PUT /api/settings — redacted views; secrets accepted once on PUT."""

from __future__ import annotations

import uuid
from typing import Annotated

import httpx
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.api.deps import get_app_settings, get_db
from app.config import Settings
from app.services.llm import LlmService
from app.services.secrets import SecretsMasterKeyMissing
from app.services.settings import SettingsService

router = APIRouter(prefix="/api/settings", tags=["settings"])


class SettingsUpdateBody(BaseModel):
    workspace_id: uuid.UUID | None = None
    liara_api_base_url: str | None = None
    liara_team_id: str | None = Field(
        default=None,
        description="Team identifier (not a secret). Pass empty string to clear.",
    )
    liara_api_token: str | None = Field(
        default=None,
        description="Raw Liara token — stored via SecretService; never returned.",
    )
    llm_base_url: str | None = None
    llm_model: str | None = None
    llm_api_key: str | None = Field(
        default=None,
        description="Raw AI API key — stored via SecretService; never returned.",
    )


@router.get("")
def get_settings(
    db: Annotated[Session, Depends(get_db)],
    app_settings: Annotated[Settings, Depends(get_app_settings)],
    workspace_id: Annotated[uuid.UUID | None, Query()] = None,
) -> dict[str, object]:
    svc = SettingsService(db, app_settings)
    try:
        return svc.get_public(workspace_id).model_dump()
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.put("")
def put_settings(
    body: SettingsUpdateBody,
    db: Annotated[Session, Depends(get_db)],
    app_settings: Annotated[Settings, Depends(get_app_settings)],
) -> dict[str, object]:
    svc = SettingsService(db, app_settings)
    clear_team = body.liara_team_id is not None and body.liara_team_id.strip() == ""
    try:
        view = svc.update(
            workspace_id=body.workspace_id,
            liara_api_base_url=body.liara_api_base_url,
            liara_team_id=None if clear_team else body.liara_team_id,
            liara_api_token=body.liara_api_token,
            llm_base_url=body.llm_base_url,
            llm_model=body.llm_model,
            llm_api_key=body.llm_api_key,
            clear_liara_team_id=clear_team,
        )
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except SecretsMasterKeyMissing as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return view.model_dump()


@router.post("/prove-llm")
def prove_llm(
    db: Annotated[Session, Depends(get_db)],
    app_settings: Annotated[Settings, Depends(get_app_settings)],
    workspace_id: Annotated[uuid.UUID | None, Query()] = None,
) -> dict[str, object]:
    """Live check Aval AI credentials via GET {base}/models (no secret echo)."""
    llm = LlmService(db, app_settings)
    cfg = llm.resolve_config(workspace_id)
    if cfg is None:
        raise HTTPException(
            status_code=400,
            detail="کلید هوش مصنوعی تنظیم نشده است.",
        )
    url = f"{cfg.base_url.rstrip('/')}/models"
    try:
        with httpx.Client(timeout=20.0) as client:
            response = client.get(
                url,
                headers={"Authorization": f"Bearer {cfg.api_key}"},
            )
    except httpx.HTTPError as exc:
        raise HTTPException(
            status_code=502,
            detail=f"اتصال به سرویس هوش مصنوعی برقرار نشد: {exc.__class__.__name__}",
        ) from exc
    if response.status_code in {401, 403}:
        raise HTTPException(
            status_code=400,
            detail="کلید هوش مصنوعی نامعتبر است یا دسترسی ندارد.",
        )
    if response.status_code >= 400:
        raise HTTPException(
            status_code=502,
            detail=f"سرویس هوش مصنوعی خطا داد (کد {response.status_code}).",
        )
    return {
        "ok": True,
        "base_url": cfg.base_url,
        "model": cfg.model,
        "api_key_label": cfg.api_key_label,
        "message": "اتصال Aval AI برقرار است.",
    }

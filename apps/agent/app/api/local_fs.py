"""Local filesystem helpers for the companion UI (native path pickers)."""

from __future__ import annotations

import platform
import shutil
import subprocess
from typing import Literal

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

router = APIRouter(prefix="/api/local", tags=["local"])


class PickPathBody(BaseModel):
    mode: Literal["directory", "file"] = "directory"
    accept: str | None = Field(
        default=None,
        description="Optional file filter hint (e.g. '.gz,.tgz'); used where supported.",
    )


class PickPathResponse(BaseModel):
    path: str | None = None
    cancelled: bool = False
    platform: str


def _pick_darwin(mode: str) -> str | None:
    if mode == "directory":
        script = 'POSIX path of (choose folder with prompt "Select app folder")'
    else:
        script = (
            'POSIX path of (choose file with prompt "Select source archive" '
            'of type {"gz", "tgz", "gzip"})'
        )
    result = subprocess.run(
        ["osascript", "-e", script],
        capture_output=True,
        text=True,
        timeout=180,
        check=False,
    )
    if result.returncode != 0:
        # User cancel → typically exit 1 with empty/err output.
        return None
    path = (result.stdout or "").strip().rstrip("/")
    return path or None


def _pick_linux(mode: str) -> str | None:
    if shutil.which("zenity"):
        cmd = ["zenity", "--file-selection"]
        if mode == "directory":
            cmd.append("--directory")
        else:
            cmd.extend(["--file-filter", "*.gz *.tgz"])
        result = subprocess.run(
            cmd, capture_output=True, text=True, timeout=180, check=False
        )
        if result.returncode != 0:
            return None
        return (result.stdout or "").strip() or None
    if shutil.which("kdialog"):
        cmd = (
            ["kdialog", "--getexistingdirectory", "."]
            if mode == "directory"
            else ["kdialog", "--getopenfilename", ".", "*.gz *.tgz"]
        )
        result = subprocess.run(
            cmd, capture_output=True, text=True, timeout=180, check=False
        )
        if result.returncode != 0:
            return None
        return (result.stdout or "").strip() or None
    raise RuntimeError(
        "No folder picker available — install zenity or kdialog, or paste the path"
    )


def _pick_windows(mode: str) -> str | None:
    if mode == "directory":
        ps = (
            "Add-Type -AssemblyName System.Windows.Forms; "
            "$d = New-Object System.Windows.Forms.FolderBrowserDialog; "
            "$d.Description = 'Select app folder'; "
            "if ($d.ShowDialog() -eq 'OK') { Write-Output $d.SelectedPath }"
        )
    else:
        ps = (
            "Add-Type -AssemblyName System.Windows.Forms; "
            "$d = New-Object System.Windows.Forms.OpenFileDialog; "
            "$d.Filter = 'Gzip archive (*.gz;*.tgz)|*.gz;*.tgz|All files (*.*)|*.*'; "
            "$d.Title = 'Select source archive'; "
            "if ($d.ShowDialog() -eq 'OK') { Write-Output $d.FileName }"
        )
    result = subprocess.run(
        ["powershell", "-NoProfile", "-Command", ps],
        capture_output=True,
        text=True,
        timeout=180,
        check=False,
    )
    if result.returncode != 0:
        return None
    return (result.stdout or "").strip() or None


@router.post("/pick-path", response_model=PickPathResponse)
def pick_path(body: PickPathBody) -> PickPathResponse:
    """Open a native OS dialog and return an absolute path the agent can read."""
    system = platform.system()
    try:
        if system == "Darwin":
            path = _pick_darwin(body.mode)
        elif system == "Linux":
            path = _pick_linux(body.mode)
        elif system == "Windows":
            path = _pick_windows(body.mode)
        else:
            raise HTTPException(
                status_code=501,
                detail=f"Native path picker not supported on {system}",
            )
    except subprocess.TimeoutExpired as exc:
        raise HTTPException(
            status_code=504, detail="Path picker timed out"
        ) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=501, detail=str(exc)) from exc
    except OSError as exc:
        raise HTTPException(
            status_code=500, detail=f"Failed to open path picker: {exc}"
        ) from exc

    if path is None:
        return PickPathResponse(path=None, cancelled=True, platform=system)
    return PickPathResponse(path=path, cancelled=False, platform=system)

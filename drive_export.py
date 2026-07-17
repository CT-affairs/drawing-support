from __future__ import annotations

import io
import json
import os
from typing import Any

from google.auth.exceptions import GoogleAuthError
from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from googleapiclient.http import MediaIoBaseUpload

DRIVE_SCOPES = ["https://www.googleapis.com/auth/drive"]
DEFAULT_FOLDER_ID = "1TQRI0_z6WmeG8-8VjXONRSyKwP4h97m2"


class DriveExportError(RuntimeError):
    """Raised when the parsed JSON could not be saved to the shared drive."""


def _load_credentials() -> service_account.Credentials:
    raw_key = os.getenv("GOOGLE_DRIVE_SERVICE_ACCOUNT_JSON")
    if raw_key:
        try:
            info = json.loads(raw_key)
        except json.JSONDecodeError as exc:
            raise DriveExportError("GOOGLE_DRIVE_SERVICE_ACCOUNT_JSON is not valid JSON") from exc
        return service_account.Credentials.from_service_account_info(info, scopes=DRIVE_SCOPES)

    key_path = os.getenv("GOOGLE_APPLICATION_CREDENTIALS")
    if key_path:
        return service_account.Credentials.from_service_account_file(key_path, scopes=DRIVE_SCOPES)

    raise DriveExportError("no Google Drive service account credentials configured")


def save_json_to_drive(filename: str, data: dict[str, Any], folder_id: str | None = None) -> dict[str, Any]:
    """Upload `data` as a JSON file into the configured Google Drive shared drive folder."""
    target_folder_id = folder_id or os.getenv("GOOGLE_DRIVE_FOLDER_ID", DEFAULT_FOLDER_ID)

    credentials = _load_credentials()

    try:
        service = build("drive", "v3", credentials=credentials, cache_discovery=False)
        payload = json.dumps(data, ensure_ascii=False, indent=2).encode("utf-8")
        media = MediaIoBaseUpload(io.BytesIO(payload), mimetype="application/json", resumable=False)
        created = (
            service.files()
            .create(
                body={"name": filename, "parents": [target_folder_id]},
                media_body=media,
                fields="id, name, webViewLink",
                supportsAllDrives=True,
            )
            .execute()
        )
    except (HttpError, GoogleAuthError) as exc:
        raise DriveExportError(f"failed to upload to Google Drive: {exc}") from exc

    return created

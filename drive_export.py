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


def _drive_service():
    return build("drive", "v3", credentials=_load_credentials(), cache_discovery=False)


def save_json_to_drive(filename: str, data: dict[str, Any], folder_id: str | None = None) -> dict[str, Any]:
    """Upload `data` as a JSON file into the configured Google Drive shared drive folder."""
    target_folder_id = folder_id or os.getenv("GOOGLE_DRIVE_FOLDER_ID", DEFAULT_FOLDER_ID)

    try:
        service = _drive_service()
        # ensure_ascii=False keeps resolved Japanese names human-readable, matching the
        # browser's own JSON download. A layer/block name that mojibake-restoration
        # couldn't resolve can still carry a raw surrogate-escaped byte (see
        # docs/AI_SUPPORT_PROGRESS.md "名称復元の基本方針"); surrogatepass encodes it
        # losslessly instead of crashing on the plain utf-8 codec.
        payload = json.dumps(data, ensure_ascii=False, indent=2).encode("utf-8", errors="surrogatepass")
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


def list_json_files(folder_id: str | None = None) -> list[dict[str, Any]]:
    """List JSON files directly inside the configured shared drive folder."""
    target_folder_id = folder_id or os.getenv("GOOGLE_DRIVE_FOLDER_ID", DEFAULT_FOLDER_ID)

    try:
        service = _drive_service()
        response = (
            service.files()
            .list(
                q=f"'{target_folder_id}' in parents and trashed = false and mimeType = 'application/json'",
                fields="files(id, name, modifiedTime, size)",
                orderBy="modifiedTime desc",
                pageSize=200,
                supportsAllDrives=True,
                includeItemsFromAllDrives=True,
            )
            .execute()
        )
    except (HttpError, GoogleAuthError) as exc:
        raise DriveExportError(f"failed to list files from Google Drive: {exc}") from exc

    return response.get("files", [])


def get_json_file(file_id: str, folder_id: str | None = None) -> dict[str, Any]:
    """Fetch a single JSON file's content from the configured shared drive folder."""
    target_folder_id = folder_id or os.getenv("GOOGLE_DRIVE_FOLDER_ID", DEFAULT_FOLDER_ID)

    try:
        service = _drive_service()
        metadata = (
            service.files()
            .get(fileId=file_id, fields="id, name, parents", supportsAllDrives=True)
            .execute()
        )
        if target_folder_id not in (metadata.get("parents") or []):
            raise DriveExportError("file is not in the configured shared drive folder")

        raw = service.files().get_media(fileId=file_id, supportsAllDrives=True).execute()
    except (HttpError, GoogleAuthError) as exc:
        raise DriveExportError(f"failed to fetch file from Google Drive: {exc}") from exc

    try:
        data = json.loads(raw.decode("utf-8", errors="surrogatepass"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise DriveExportError(f"file content is not valid JSON: {exc}") from exc

    return {"id": metadata["id"], "name": metadata["name"], "data": data}

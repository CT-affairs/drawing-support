from __future__ import annotations

import os
import re
from datetime import datetime
from typing import Any


COLLECTION_NAME = "drawing_operations"
OPERATION_ID_PATTERN = re.compile(r"^OP\d{3,}$")


class OperationStoreError(RuntimeError):
    """Raised when the operation master cannot be accessed or validated."""


def _firestore_client():
    try:
        from google.cloud import firestore
    except ImportError as exc:
        raise OperationStoreError("google-cloud-firestore is not installed") from exc

    project = os.getenv("GOOGLE_CLOUD_PROJECT") or os.getenv("GCP_PROJECT_ID") or None
    try:
        return firestore.Client(project=project)
    except Exception as exc:  # SDK exceptions vary by credential/environment.
        raise OperationStoreError(f"Firestore connection failed: {exc}") from exc


def _validate_operation_id(value: Any) -> str:
    operation_id = str(value or "").strip().upper()
    if not OPERATION_ID_PATTERN.fullmatch(operation_id):
        raise OperationStoreError("operation_id must match OP followed by at least three digits")
    return operation_id


def _normalize_payload(operation_id: str, payload: dict[str, Any], existing: dict[str, Any] | None = None) -> dict[str, Any]:
    if not isinstance(payload, dict):
        raise OperationStoreError("operation data must be an object")
    name = str(payload.get("name", existing.get("name", "") if existing else "")).strip()
    instruction = str(payload.get("instruction", existing.get("instruction", "") if existing else "")).strip()
    if not name or not instruction:
        raise OperationStoreError("name and instruction are required")
    actions = payload.get("actions", existing.get("actions", []) if existing else [])
    if not isinstance(actions, list) or not all(isinstance(item, str) and item.strip() for item in actions):
        raise OperationStoreError("actions must be a list of non-empty strings")
    try:
        version = int(payload.get("version", existing.get("version", 1) if existing else 1))
    except (TypeError, ValueError) as exc:
        raise OperationStoreError("version must be an integer") from exc
    if version < 1:
        raise OperationStoreError("version must be at least 1")
    active = payload.get("active", existing.get("active", True) if existing else True)
    if not isinstance(active, bool):
        raise OperationStoreError("active must be a boolean")
    return {
        "operation_id": operation_id,
        "name": name,
        "instruction": instruction,
        "actions": [item.strip() for item in actions],
        "active": active,
        "version": version,
        "description": str(payload.get("description", existing.get("description", "") if existing else "")).strip(),
    }


def _serialize(snapshot: Any) -> dict[str, Any]:
    data = snapshot.to_dict() or {}
    data["operation_id"] = snapshot.id
    updated_at = data.get("updated_at")
    if isinstance(updated_at, datetime):
        data["updated_at"] = updated_at.isoformat()
    return data


def list_operations() -> list[dict[str, Any]]:
    db = _firestore_client()
    try:
        items = [_serialize(snapshot) for snapshot in db.collection(COLLECTION_NAME).stream()]
    except Exception as exc:
        raise OperationStoreError(f"Firestore read failed: {exc}") from exc
    return sorted(items, key=lambda item: item.get("operation_id", ""))


def get_operation(operation_id: str) -> dict[str, Any] | None:
    operation_id = _validate_operation_id(operation_id)
    db = _firestore_client()
    try:
        snapshot = db.collection(COLLECTION_NAME).document(operation_id).get()
    except Exception as exc:
        raise OperationStoreError(f"Firestore read failed: {exc}") from exc
    return _serialize(snapshot) if snapshot.exists else None


def save_operation(operation_id: str, payload: dict[str, Any]) -> dict[str, Any]:
    operation_id = _validate_operation_id(operation_id)
    try:
        from google.cloud import firestore
    except ImportError as exc:
        raise OperationStoreError("google-cloud-firestore is not installed") from exc
    db = _firestore_client()
    try:
        ref = db.collection(COLLECTION_NAME).document(operation_id)
        existing_snapshot = ref.get()
        existing = _serialize(existing_snapshot) if existing_snapshot.exists else None
        data = _normalize_payload(operation_id, payload, existing)
        data["updated_at"] = firestore.SERVER_TIMESTAMP
        ref.set(data, merge=True)
        saved = ref.get()
    except OperationStoreError:
        raise
    except Exception as exc:
        raise OperationStoreError(f"Firestore write failed: {exc}") from exc
    return _serialize(saved)


def delete_operation(operation_id: str) -> None:
    operation_id = _validate_operation_id(operation_id)
    db = _firestore_client()
    try:
        db.collection(COLLECTION_NAME).document(operation_id).delete()
    except Exception as exc:
        raise OperationStoreError(f"Firestore delete failed: {exc}") from exc

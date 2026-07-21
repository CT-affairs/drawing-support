import os
import re
from datetime import datetime, timezone

from flask import Flask, jsonify, redirect, request, send_from_directory
from dxf_json import DxfParseError, parse_dxf
from drive_export import DriveExportError, get_json_file, list_json_files, save_json_to_drive, update_json_file


app = Flask(__name__)
app.config["MAX_CONTENT_LENGTH"] = int(os.getenv("MAX_DXF_BYTES", 30 * 1024 * 1024))
API_CORS_ORIGINS = {
    origin.strip()
    for origin in os.getenv(
        "DRAWING_SUPPORT_CORS_ORIGINS",
        "https://clean-techno.com,https://www.clean-techno.com",
    ).split(",")
    if origin.strip()
}
UNIT_CODES = {"unitless": 0, "in": 1, "ft": 2, "mm": 4, "cm": 5, "m": 6}


@app.after_request
def add_api_cors_headers(response):
    if request.path.startswith("/api/"):
        origin = request.headers.get("Origin")
        if origin in API_CORS_ORIGINS:
            response.headers["Access-Control-Allow-Origin"] = origin

        response.headers["Access-Control-Allow-Methods"] = "GET, POST, OPTIONS"
        response.headers["Access-Control-Allow-Headers"] = "Content-Type"
        response.headers["Vary"] = "Origin"
    return response


@app.get("/")
def index():
    return redirect("/liff3/drawing-support.html", code=302)


@app.get("/liff3/<path:filename>")
def frontend(filename):
    return send_from_directory("liff3", filename)


@app.get("/healthz")
def healthz():
    return "ok\n", 200, {"Content-Type": "text/plain; charset=utf-8"}


@app.post("/api/v1/dxf/parse")
def parse_dxf_endpoint():
    uploaded = request.files.get("file")
    if uploaded is None or not uploaded.filename:
        return jsonify({"error": {"code": "file_required", "message": "file is required"}}), 400

    if not uploaded.filename.lower().endswith(".dxf"):
        return jsonify({"error": {"code": "invalid_extension", "message": "only .dxf files are supported"}}), 415

    try:
        result = parse_dxf(uploaded.stream)
    except DxfParseError as exc:
        return jsonify({"error": {"code": "invalid_dxf", "message": str(exc)}}), 422

    return jsonify(result), 200


def _safe_json_filename(original_name: str) -> str:
    stem = os.path.splitext(os.path.basename(original_name or ""))[0]
    stem = re.sub(r"[^A-Za-z0-9_-]+", "_", stem).strip("_") or "dxf-analysis"
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    return f"{stem}_{timestamp}.json"


@app.post("/api/v1/drive/save")
def save_to_drive_endpoint():
    payload = request.get_json(silent=True)
    if not isinstance(payload, dict) or not isinstance(payload.get("data"), dict):
        return jsonify({"error": {"code": "invalid_request", "message": "data is required"}}), 400

    filename = _safe_json_filename(payload.get("filename", ""))
    try:
        created = save_json_to_drive(filename, payload["data"])
    except DriveExportError as exc:
        return jsonify({"error": {"code": "drive_upload_failed", "message": str(exc)}}), 502

    return (
        jsonify(
            {
                "file_id": created.get("id"),
                "file_name": created.get("name"),
                "web_view_link": created.get("webViewLink"),
            }
        ),
        200,
    )


@app.get("/api/v1/drive/list")
def list_drive_files_endpoint():
    try:
        files = list_json_files()
    except DriveExportError as exc:
        return jsonify({"error": {"code": "drive_list_failed", "message": str(exc)}}), 502

    return (
        jsonify(
            {
                "files": [
                    {
                        "id": item.get("id"),
                        "name": item.get("name"),
                        "modified_time": item.get("modifiedTime"),
                        "size": item.get("size"),
                    }
                    for item in files
                ]
            }
        ),
        200,
    )


@app.get("/api/v1/drive/file/<file_id>")
def get_drive_file_endpoint(file_id):
    try:
        result = get_json_file(file_id)
    except DriveExportError as exc:
        return jsonify({"error": {"code": "drive_fetch_failed", "message": str(exc)}}), 502

    return (
        jsonify({"file_id": result["id"], "file_name": result["name"], "data": result["data"]}),
        200,
    )


@app.post("/api/v1/drive/file/<file_id>/unit")
def update_drive_file_unit_endpoint(file_id):
    payload = request.get_json(silent=True)
    unit = payload.get("unit") if isinstance(payload, dict) else None
    if unit not in UNIT_CODES:
        return jsonify({
            "error": {
                "code": "invalid_unit",
                "message": "unit must be one of unitless, in, ft, mm, cm, m",
            }
        }), 400

    try:
        current = get_json_file(file_id)
        data = current["data"]
        previous_unit = data.get("unit", "mm")
        data["units"] = UNIT_CODES[unit]
        data["unit"] = unit
        data["units_source"] = "user_override"
        data["unit_override"] = {
            "previous_unit": previous_unit,
            "unit": unit,
            "updated_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        }
        updated = update_json_file(file_id, data)
    except DriveExportError as exc:
        return jsonify({"error": {"code": "drive_update_failed", "message": str(exc)}}), 502

    return jsonify({
        "file_id": updated.get("id", file_id),
        "file_name": updated.get("name", current["name"]),
        "web_view_link": updated.get("webViewLink"),
        "unit": unit,
    }), 200


@app.errorhandler(413)
def request_entity_too_large(_error):
    return jsonify({"error": {"code": "file_too_large", "message": "DXF file is too large"}}), 413


@app.errorhandler(500)
def internal_server_error(_error):
    return jsonify({"error": {"code": "internal_error", "message": "internal server error"}}), 500


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", "8080")))

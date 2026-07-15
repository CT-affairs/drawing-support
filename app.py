import os

from flask import Flask, jsonify, redirect, request, send_from_directory

from dxf_json import DxfParseError, parse_dxf


app = Flask(__name__)
app.config["MAX_CONTENT_LENGTH"] = int(os.getenv("MAX_DXF_BYTES", 20 * 1024 * 1024))


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


@app.errorhandler(413)
def request_entity_too_large(_error):
    return jsonify({"error": {"code": "file_too_large", "message": "DXF file is too large"}}), 413


@app.errorhandler(500)
def internal_server_error(_error):
    return jsonify({"error": {"code": "internal_error", "message": "internal server error"}}), 500


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", "8080")))

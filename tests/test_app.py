import io
import unittest
from unittest.mock import patch

import ezdxf

from app import app
from drive_export import DriveExportError


class AppTests(unittest.TestCase):
    def setUp(self):
        app.config.update(TESTING=True)
        self.client = app.test_client()

    def test_healthz(self):
        response = self.client.get("/healthz")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.text, "ok\n")

    def test_dashboard_and_dxf_pages_are_available(self):
        dashboard = self.client.get("/liff3/drawing-support.html")
        dxf_page = self.client.get("/liff3/dxf-json.html")
        stylesheet = self.client.get("/liff3/drawing-support.css")

        self.assertEqual(dashboard.status_code, 200)
        self.assertIn("製図_ダッシュボード", dashboard.text)
        self.assertIn("/liff3/dxf-json.html", dashboard.text)
        self.assertIn("/liff3/drive-json-viewer.html", dashboard.text)
        self.assertEqual(dxf_page.status_code, 200)
        self.assertIn("DXF_JSON化", dxf_page.text)
        self.assertIn("/api/v1/dxf/parse", dxf_page.text)
        self.assertIn("JSONをダウンロード", dxf_page.text)
        self.assertEqual(stylesheet.status_code, 200)
        dashboard.close()
        dxf_page.close()
        stylesheet.close()

    def test_drive_json_viewer_page_is_available(self):
        page = self.client.get("/liff3/drive-json-viewer.html")
        script = self.client.get("/liff3/js/json-tree.js")

        self.assertEqual(page.status_code, 200)
        self.assertIn("共有ドライブJSON閲覧", page.text)
        self.assertIn("/api/v1/drive/list", page.text)
        self.assertIn("/api/v1/drive/file/", page.text)
        self.assertEqual(script.status_code, 200)
        self.assertIn("JsonTree", script.text)
        page.close()
        script.close()

    def test_dxf_endpoint_requires_file(self):
        response = self.client.post("/api/v1/dxf/parse")
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json["error"]["code"], "file_required")

    def test_oversized_request_keeps_cors_header(self):
        original_limit = app.config["MAX_CONTENT_LENGTH"]
        app.config["MAX_CONTENT_LENGTH"] = 1
        try:
            response = self.client.post(
                "/api/v1/dxf/parse",
                data={"file": (io.BytesIO(b"too large"), "drawing.dxf")},
                content_type="multipart/form-data",
                headers={"Origin": "https://clean-techno.com"},
            )
        finally:
            app.config["MAX_CONTENT_LENGTH"] = original_limit

        self.assertEqual(response.status_code, 413)
        self.assertEqual(response.headers["Access-Control-Allow-Origin"], "https://clean-techno.com")

    def test_dxf_endpoint_rejects_non_dxf(self):
        response = self.client.post(
            "/api/v1/dxf/parse",
            data={"file": (io.BytesIO(b"data"), "drawing.txt")},
            content_type="multipart/form-data",
        )
        self.assertEqual(response.status_code, 415)
        self.assertEqual(response.json["error"]["code"], "invalid_extension")

    def test_dxf_endpoint_returns_json(self):
        document = ezdxf.new("R2013")
        document.modelspace().add_line((0, 0), (10, 20))
        block = document.blocks.new("FIXTURE")
        block.add_line((0, 0), (30, 10))
        stream = io.StringIO()
        document.write(stream)

        response = self.client.post(
            "/api/v1/dxf/parse",
            data={"file": (io.BytesIO(stream.getvalue().encode("utf-8")), "drawing.dxf")},
            content_type="multipart/form-data",
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json["entity_counts"], {"LINE": 1})
        self.assertEqual(
            response.json["blocks"][0]["bbox"],
            {
                "min": [0, 0, 0],
                "max": [30, 10, 0],
                "size": [30, 10, 0],
                "center": [15, 5, 0],
            },
        )

    def test_drive_save_requires_data(self):
        response = self.client.post("/api/v1/drive/save", json={"filename": "drawing.dxf"})
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json["error"]["code"], "invalid_request")

    def test_drive_save_uploads_and_returns_file_info(self):
        with patch("app.save_json_to_drive") as mock_save:
            mock_save.return_value = {
                "id": "file-123",
                "name": "drawing_20260717T000000Z.json",
                "webViewLink": "https://drive.google.com/file/d/file-123/view",
            }
            response = self.client.post(
                "/api/v1/drive/save",
                json={"filename": "drawing.dxf", "data": {"schema_version": "1.0"}},
            )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json["file_id"], "file-123")
        self.assertEqual(response.json["web_view_link"], "https://drive.google.com/file/d/file-123/view")
        called_filename = mock_save.call_args.args[0]
        self.assertTrue(called_filename.startswith("drawing_"))
        self.assertTrue(called_filename.endswith(".json"))

    def test_drive_save_handles_upload_failure(self):
        with patch("app.save_json_to_drive", side_effect=DriveExportError("no credentials configured")):
            response = self.client.post(
                "/api/v1/drive/save",
                json={"filename": "drawing.dxf", "data": {"schema_version": "1.0"}},
            )

        self.assertEqual(response.status_code, 502)
        self.assertEqual(response.json["error"]["code"], "drive_upload_failed")

    def test_drive_list_returns_files(self):
        with patch("app.list_json_files") as mock_list:
            mock_list.return_value = [
                {"id": "file-1", "name": "a.json", "modifiedTime": "2026-07-17T00:00:00Z", "size": "123"},
            ]
            response = self.client.get("/api/v1/drive/list")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.json["files"],
            [{"id": "file-1", "name": "a.json", "modified_time": "2026-07-17T00:00:00Z", "size": "123"}],
        )

    def test_drive_list_handles_failure(self):
        with patch("app.list_json_files", side_effect=DriveExportError("no credentials configured")):
            response = self.client.get("/api/v1/drive/list")

        self.assertEqual(response.status_code, 502)
        self.assertEqual(response.json["error"]["code"], "drive_list_failed")

    def test_drive_get_file_returns_data(self):
        with patch("app.get_json_file") as mock_get:
            mock_get.return_value = {"id": "file-1", "name": "a.json", "data": {"schema_version": "1.0"}}
            response = self.client.get("/api/v1/drive/file/file-1")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json["file_id"], "file-1")
        self.assertEqual(response.json["data"], {"schema_version": "1.0"})

    def test_drive_get_file_handles_failure(self):
        with patch("app.get_json_file", side_effect=DriveExportError("file is not in the configured shared drive folder")):
            response = self.client.get("/api/v1/drive/file/file-1")

        self.assertEqual(response.status_code, 502)
        self.assertEqual(response.json["error"]["code"], "drive_fetch_failed")


if __name__ == "__main__":
    unittest.main()

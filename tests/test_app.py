import io
import unittest

import ezdxf

from app import app


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
        self.assertEqual(dxf_page.status_code, 200)
        self.assertIn("DXF_JSON化", dxf_page.text)
        self.assertIn("/api/v1/dxf/parse", dxf_page.text)
        self.assertIn("JSONをダウンロード", dxf_page.text)
        self.assertEqual(stylesheet.status_code, 200)
        dashboard.close()
        dxf_page.close()
        stylesheet.close()

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
        stream = io.StringIO()
        document.write(stream)

        response = self.client.post(
            "/api/v1/dxf/parse",
            data={"file": (io.BytesIO(stream.getvalue().encode("utf-8")), "drawing.dxf")},
            content_type="multipart/form-data",
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json["entity_counts"], {"LINE": 1})


if __name__ == "__main__":
    unittest.main()

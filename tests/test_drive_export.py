import json
import os
import unittest
from unittest.mock import MagicMock, patch

from drive_export import save_json_to_drive


class DriveExportTests(unittest.TestCase):
    def setUp(self):
        patcher = patch.dict(os.environ, {"GOOGLE_DRIVE_SERVICE_ACCOUNT_JSON": '{"type": "service_account"}'})
        patcher.start()
        self.addCleanup(patcher.stop)

    @patch("drive_export.MediaIoBaseUpload")
    @patch("drive_export.build")
    @patch("drive_export.service_account.Credentials.from_service_account_info")
    def test_save_handles_unresolved_surrogate_escape_names(self, mock_from_info, mock_build, mock_media_upload):
        mock_from_info.return_value = MagicMock()
        mock_service = MagicMock()
        mock_build.return_value = mock_service
        mock_service.files.return_value.create.return_value.execute.return_value = {
            "id": "file-1",
            "name": "x.json",
            "webViewLink": "https://drive.example/x",
        }

        # A layer name whose mojibake could not be resolved keeps a raw
        # surrogate-escaped byte (see AI_SUPPORT_PROGRESS.md), which cannot be
        # encoded as UTF-8 directly.
        data = {"layers": ["*0-0\udc90}values"]}

        result = save_json_to_drive("drawing.json", data)

        self.assertEqual(result["id"], "file-1")
        uploaded_stream = mock_media_upload.call_args.args[0]
        decoded = json.loads(uploaded_stream.read().decode("utf-8"))
        self.assertEqual(decoded, data)


if __name__ == "__main__":
    unittest.main()

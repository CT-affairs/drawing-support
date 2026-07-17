import json
import os
import unittest
from unittest.mock import MagicMock, patch

from drive_export import DEFAULT_FOLDER_ID, DriveExportError, get_json_file, list_json_files, save_json_to_drive


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

        # A resolved name should stay human-readable, while a name whose mojibake
        # could not be resolved keeps a raw surrogate-escaped byte (see
        # AI_SUPPORT_PROGRESS.md), which the plain utf-8 codec cannot encode.
        data = {"layers": ["*0-0_001_図面枠", "*0-0\udc90}values"]}

        result = save_json_to_drive("drawing.json", data)

        self.assertEqual(result["id"], "file-1")
        uploaded_bytes = mock_media_upload.call_args.args[0].read()

        self.assertIn("図面枠".encode("utf-8"), uploaded_bytes)

        decoded = json.loads(uploaded_bytes.decode("utf-8", errors="surrogatepass"))
        self.assertEqual(decoded, data)

    @patch("drive_export.build")
    @patch("drive_export.service_account.Credentials.from_service_account_info")
    def test_list_json_files_scopes_query_to_folder(self, mock_from_info, mock_build):
        mock_from_info.return_value = MagicMock()
        mock_service = MagicMock()
        mock_build.return_value = mock_service
        mock_service.files.return_value.list.return_value.execute.return_value = {
            "files": [{"id": "file-1", "name": "a.json", "modifiedTime": "2026-07-17T00:00:00Z", "size": "10"}]
        }

        result = list_json_files()

        self.assertEqual(result[0]["id"], "file-1")
        query = mock_service.files.return_value.list.call_args.kwargs["q"]
        self.assertIn(DEFAULT_FOLDER_ID, query)
        self.assertIn("mimeType", query)

    @patch("drive_export.build")
    @patch("drive_export.service_account.Credentials.from_service_account_info")
    def test_get_json_file_returns_data_when_in_configured_folder(self, mock_from_info, mock_build):
        mock_from_info.return_value = MagicMock()
        mock_service = MagicMock()
        mock_build.return_value = mock_service
        mock_service.files.return_value.get.return_value.execute.return_value = {
            "id": "file-1",
            "name": "a.json",
            "parents": [DEFAULT_FOLDER_ID],
        }
        payload = json.dumps({"layers": ["図面枠"]}, ensure_ascii=False).encode("utf-8")
        mock_service.files.return_value.get_media.return_value.execute.return_value = payload

        result = get_json_file("file-1")

        self.assertEqual(result, {"id": "file-1", "name": "a.json", "data": {"layers": ["図面枠"]}})

    @patch("drive_export.build")
    @patch("drive_export.service_account.Credentials.from_service_account_info")
    def test_get_json_file_rejects_file_outside_configured_folder(self, mock_from_info, mock_build):
        mock_from_info.return_value = MagicMock()
        mock_service = MagicMock()
        mock_build.return_value = mock_service
        mock_service.files.return_value.get.return_value.execute.return_value = {
            "id": "file-1",
            "name": "a.json",
            "parents": ["some-other-folder"],
        }

        with self.assertRaises(DriveExportError):
            get_json_file("file-1")

        mock_service.files.return_value.get_media.assert_not_called()


if __name__ == "__main__":
    unittest.main()

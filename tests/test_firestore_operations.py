import unittest

from firestore_operations import OperationStoreError, _normalize_payload, _validate_operation_id


class OperationValidationTests(unittest.TestCase):
    def test_operation_id_is_normalized_and_validated(self):
        self.assertEqual(_validate_operation_id(" op001 "), "OP001")
        with self.assertRaises(OperationStoreError):
            _validate_operation_id("OP01")
        with self.assertRaises(OperationStoreError):
            _validate_operation_id("DRAWING001")

    def test_payload_contains_recommended_fields(self):
        result = _normalize_payload(
            "OP001",
            {
                "name": "曲率Rを抽出",
                "instruction": "曲率Rのある部材を抽出し、半径を一覧化する",
                "actions": ["extract_radius", "classify_target"],
                "active": True,
                "version": 1,
                "description": "",
            },
        )
        self.assertEqual(result["operation_id"], "OP001")
        self.assertEqual(result["actions"], ["extract_radius", "classify_target"])

    def test_payload_rejects_invalid_version_and_active(self):
        base = {"name": "name", "instruction": "instruction", "actions": []}
        with self.assertRaises(OperationStoreError):
            _normalize_payload("OP001", {**base, "version": "x"})
        with self.assertRaises(OperationStoreError):
            _normalize_payload("OP001", {**base, "active": "false"})


if __name__ == "__main__":
    unittest.main()

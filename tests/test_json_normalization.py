import json
import unittest

from json_normalization import normalize_json_unicode


class JsonNormalizationTests(unittest.TestCase):
    def test_unpaired_surrogates_become_visible_byte_tokens(self):
        normalized, diagnostics = normalize_json_unicode(
            {"text": "prefix\udc90}suffix", "nested": ["\ud800"]}
        )

        self.assertEqual(normalized["text"], "prefix\\x90}suffix")
        self.assertEqual(normalized["nested"], ["\\ud800"])
        self.assertEqual(diagnostics["escaped_surrogate_count"], 2)
        encoded = json.dumps(normalized, ensure_ascii=False).encode("utf-8", errors="strict")
        self.assertEqual(json.loads(encoded.decode("utf-8", errors="strict")), normalized)

    def test_surrogate_pair_becomes_unicode_scalar(self):
        normalized, diagnostics = normalize_json_unicode({"emoji": "\ud83d\ude00"})

        self.assertEqual(normalized["emoji"], "😀")
        self.assertEqual(diagnostics["combined_surrogate_pair_count"], 1)
        self.assertEqual(diagnostics["escaped_surrogate_count"], 0)


if __name__ == "__main__":
    unittest.main()

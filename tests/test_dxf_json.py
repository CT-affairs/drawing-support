import io
import unittest

import ezdxf

from dxf_json import DxfParseError, parse_dxf


class DxfJsonTests(unittest.TestCase):
    def make_dxf(self):
        document = ezdxf.new("R2013")
        document.header["$INSUNITS"] = 4
        modelspace = document.modelspace()
        modelspace.add_line((0, 0), (100, 50), dxfattribs={"layer": "DUCT"})
        modelspace.add_text("sample", dxfattribs={"layer": "NOTE", "insert": (10, 20)})
        stream = io.StringIO()
        document.write(stream)
        return stream.getvalue().encode("utf-8")

    def test_parse_returns_structured_entities(self):
        result = parse_dxf(self.make_dxf())

        self.assertEqual(result["schema_version"], "1.0")
        self.assertEqual(result["units"], 4)
        self.assertEqual(result["entity_counts"], {"LINE": 1, "TEXT": 1})
        self.assertEqual(result["layers"], ["DUCT", "NOTE"])
        self.assertEqual(result["entities"][0]["start"], [0, 0, 0])

    def test_invalid_file_is_rejected(self):
        with self.assertRaises(DxfParseError):
            parse_dxf(b"not a dxf")


if __name__ == "__main__":
    unittest.main()

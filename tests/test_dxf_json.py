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
        document.layouts.get("Layout1").add_circle((30, 40), 5, dxfattribs={"layer": "PAPER"})
        block = document.blocks.new("DUCT_BLOCK")
        block.add_line((0, 0), (20, 0), dxfattribs={"layer": "BLOCK"})
        modelspace.add_blockref("DUCT_BLOCK", (1000, 2000), dxfattribs={"layer": "INSERT"})
        stream = io.StringIO()
        document.write(stream)
        return stream.getvalue().encode("utf-8")

    def test_parse_returns_structured_entities(self):
        result = parse_dxf(self.make_dxf())

        self.assertEqual(result["schema_version"], "1.0")
        self.assertEqual(result["units"], 4)
        self.assertEqual(result["entity_counts"], {"INSERT": 1, "LINE": 1, "TEXT": 1})
        self.assertEqual(result["layers"], ["DUCT", "INSERT", "NOTE", "PAPER"])
        self.assertEqual(result["entities"][0]["start"], [0, 0, 0])
        self.assertEqual(result["spaces"][0]["name"], "Model")
        self.assertEqual(result["spaces"][0]["entity_count"], 3)
        self.assertEqual(result["spaces"][1]["entity_counts"], {"CIRCLE": 1})
        self.assertEqual(result["blocks"], [{"name": "DUCT_BLOCK", "entity_count": 1, "entity_counts": {"LINE": 1}}])
        self.assertEqual(result["inserts"][0]["block"], "DUCT_BLOCK")
        self.assertEqual(result["inserts"][0]["space"], "Model")

    def test_invalid_file_is_rejected(self):
        with self.assertRaises(DxfParseError):
            parse_dxf(b"not a dxf")


if __name__ == "__main__":
    unittest.main()

import io
import unittest

import ezdxf

from dxf_json import (
    DxfParseError,
    _encoding_diagnostics,
    _restore_mojibake_name,
    _restore_mojibake_text,
    parse_dxf,
)


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

        self.assertEqual(result["schema_version"], "1.1")
        self.assertEqual(result["units"], 4)
        self.assertEqual(result["entity_counts"], {"INSERT": 1, "LINE": 1, "TEXT": 1})
        self.assertEqual(result["layers"], ["DUCT", "INSERT", "NOTE", "PAPER"])
        self.assertEqual(result["entities"][0]["start"], [0, 0, 0])
        self.assertEqual(result["spaces"][0]["name"], "Model")
        self.assertEqual(result["spaces"][0]["entity_count"], 3)
        self.assertEqual(result["spaces"][1]["entity_counts"], {"CIRCLE": 1})
        self.assertEqual(
            result["blocks"],
            [
                {
                    "name": "DUCT_BLOCK",
                    "entity_count": 1,
                    "entity_counts": {"LINE": 1},
                    "entities": [
                        {
                            "type": "LINE",
                            "layer": "BLOCK",
                            "start": [0, 0, 0],
                            "end": [20, 0, 0],
                        }
                    ],
                    "bbox": {
                        "min": [0, 0, 0],
                        "max": [20, 0, 0],
                        "size": [20, 0, 0],
                        "center": [10, 0, 0],
                    },
                }
            ],
        )
        self.assertEqual(result["inserts"][0]["block"], "DUCT_BLOCK")
        self.assertEqual(result["inserts"][0]["space"], "Model")
        self.assertTrue(result["inserts"][0]["id"].startswith("insert:"))
        self.assertEqual(result["inserts"][0]["classification"]["role"], "unknown")
        self.assertEqual(
            result["diagnostics"]["object_classification"]["role_counts"],
            {"unknown": 1},
        )
        self.assertGreater(result["diagnostics"]["file_size_bytes"], 0)
        self.assertEqual(result["diagnostics"]["text_encoding"], "cp1252")
        self.assertEqual(result["diagnostics"]["encoding"]["selected_encoding"], "cp1252")
        self.assertGreaterEqual(len(result["diagnostics"]["encoding"]["candidates"]), 2)
        self.assertEqual(result["diagnostics"]["entities_section"]["record_count"], 4)
        self.assertEqual(result["diagnostics"]["ezdxf_entity_database_count"] > 0, True)
        self.assertEqual(result["diagnostics"]["audit"], {"error_count": 0, "fix_count": 0})
        self.assertEqual(result["diagnostics"]["loader"], "standard")
        self.assertFalse(result["diagnostics"]["recover"]["attempted"])

    def test_invalid_file_is_rejected(self):
        with self.assertRaises(DxfParseError):
            parse_dxf(b"not a dxf")

    def test_insert_classification_is_stored_on_insert_instances(self):
        document = ezdxf.new("R2013")
        document.header["$INSUNITS"] = 4
        title = document.blocks.new("TITLE_FRAME")
        title.add_line((0, 0), (10, 0), dxfattribs={"layer": "0"})
        duct = document.blocks.new("DUCT_SHAPE")
        duct.add_line((0, 0), (10, 0), dxfattribs={"layer": "duct"})
        unknown = document.blocks.new("UNKNOWN_SHAPE")
        unknown.add_line((0, 0), (10, 0), dxfattribs={"layer": "0"})
        modelspace = document.modelspace()
        modelspace.add_blockref("TITLE_FRAME", (0, 0))
        modelspace.add_blockref("DUCT_SHAPE", (100, 0))
        modelspace.add_blockref("UNKNOWN_SHAPE", (200, 0))
        stream = io.StringIO()
        document.write(stream)

        result = parse_dxf(stream.getvalue().encode("utf-8"))
        by_block = {item["block"]: item for item in result["inserts"]}

        self.assertEqual(by_block["TITLE_FRAME"]["classification"]["role"], "meta")
        self.assertEqual(by_block["TITLE_FRAME"]["classification"]["type"], "title_frame")
        self.assertEqual(by_block["DUCT_SHAPE"]["classification"]["role"], "target")
        self.assertEqual(
            by_block["UNKNOWN_SHAPE"]["classification"]["role"],
            "unknown",
        )
        self.assertEqual(len({item["id"] for item in result["inserts"]}), 3)
        self.assertEqual(
            result["diagnostics"]["object_classification"]["role_counts"],
            {"meta": 1, "target": 1, "unknown": 1},
        )

    def test_large_sheet_like_block_is_meta_candidate(self):
        document = ezdxf.new("R2013")
        document.header["$INSUNITS"] = 4
        block = document.blocks.new("NORMAL_LAYER_FRAME")
        block.add_line((0, 0), (9000, 0), dxfattribs={"layer": "通常"})
        block.add_line((9000, 0), (9000, 6000), dxfattribs={"layer": "通常"})
        block.add_line((9000, 6000), (0, 6000), dxfattribs={"layer": "通常"})
        block.add_line((0, 6000), (0, 0), dxfattribs={"layer": "通常"})
        document.modelspace().add_blockref("NORMAL_LAYER_FRAME", (0, 0))
        stream = io.StringIO()
        document.write(stream)

        result = parse_dxf(stream.getvalue().encode("utf-8"))

        classification = result["inserts"][0]["classification"]
        self.assertEqual(classification["role"], "meta")
        self.assertEqual(classification["type"], "title_frame_candidate")
        self.assertIn("large_sheet_like_bbox", classification["evidence"])

    def test_block_bbox_is_none_when_block_has_no_geometry(self):
        document = ezdxf.new("R2013")
        document.blocks.new("EMPTY_BLOCK")
        stream = io.StringIO()
        document.write(stream)

        result = parse_dxf(stream.getvalue().encode("utf-8"))

        block = next(item for item in result["blocks"] if item["name"] == "EMPTY_BLOCK")
        self.assertIsNone(block["bbox"])

    def test_block_bbox_includes_nested_insert_geometry(self):
        document = ezdxf.new("R2013")
        inner = document.blocks.new("INNER")
        inner.add_circle((0, 0), 2)
        outer = document.blocks.new("OUTER")
        outer.add_blockref("INNER", (10, 20), dxfattribs={"xscale": 2, "yscale": 3})
        stream = io.StringIO()
        document.write(stream)

        result = parse_dxf(stream.getvalue().encode("utf-8"))

        outer_block = next(item for item in result["blocks"] if item["name"] == "OUTER")
        self.assertEqual(
            outer_block["entities"],
            [
                {
                    "type": "INSERT",
                    "layer": "0",
                    "block": "INNER",
                    "insert": [10, 20, 0],
                    "rotation": 0,
                    "scale": [2, 3, 1],
                }
            ],
        )
        self.assertEqual(
            outer_block["bbox"],
            {
                "min": [6, 14, 0],
                "max": [14, 26, 0],
                "size": [8, 12, 0],
                "center": [10, 20, 0],
            },
        )

    def test_encoding_diagnostics_honor_dwg_codepage(self):
        raw = (
            "0\nSECTION\n2\nHEADER\n"
            "9\n$DWGCODEPAGE\n3\nANSI_932\n"
            "0\nENDSEC\n0\nEOF\n"
        ).encode("cp932")

        encoding, _text, diagnostics = _encoding_diagnostics(raw)

        self.assertEqual(encoding, "cp932")
        self.assertEqual(diagnostics["dwg_codepage"], "ANSI_932")
        self.assertEqual(diagnostics["codepage_encoding"], "cp932")

    def test_restore_mojibake_name_keeps_normal_names_unchanged(self):
        self.assertEqual(_restore_mojibake_name("製図レイヤー"), ("製図レイヤー", None))
        self.assertEqual(_restore_mojibake_name("DUCT_01"), ("DUCT_01", None))
        self.assertEqual(_restore_mojibake_name("Café"), ("Café", None))

    def test_restore_cp932_names_misread_as_cp1252_with_surrogates(self):
        samples = {
            "*0-0\\_001*\udc90}\u2013\u00ca\u02dcg": "*0-0\\_001*図面枠",
            "*0-1*\u2019\u00ca\udc8f\u00ed": "*0-1*通常",
            "*0-3*\u017d_\u201dr\u2039C": "*0-3*酸排気",
        }

        for original, expected in samples.items():
            with self.subTest(original=original):
                restored, diagnostics = _restore_mojibake_name(original)
                self.assertEqual(restored, expected)
                self.assertEqual(diagnostics["method"], "cp1252_surrogateescape_bytes_to_cp932")
                self.assertGreaterEqual(diagnostics["confidence"], 0.94)
                self.assertIn("source_bytes_hex", diagnostics)

    def test_restore_text_accepts_cp932_cad_symbols(self):
        samples = {
            "\u2021@": "①",
            "\udc81~H700": "×H700",
            "72.7\u2021u": "72.7㎡",
        }

        for original, expected in samples.items():
            with self.subTest(original=original):
                restored, diagnostics = _restore_mojibake_text(original)
                self.assertEqual(restored, expected)
                self.assertEqual(diagnostics["method"], "cp1252_surrogateescape_bytes_to_cp932")
                self.assertGreater(diagnostics["cad_symbol_count"], 0)

    def test_parse_restores_text_and_reports_diagnostics(self):
        document = ezdxf.new("R2013")
        document.modelspace().add_text("\u2021@", dxfattribs={"insert": (1, 2)})
        stream = io.StringIO()
        document.write(stream)

        result = parse_dxf(stream.getvalue().encode("cp1252"))

        self.assertEqual(result["entities"][0]["text"], "①")
        diagnostics = result["diagnostics"]["text_decoding"]
        self.assertEqual(diagnostics["inspected_occurrence_count"], 1)
        self.assertEqual(diagnostics["restored_occurrence_count"], 1)
        self.assertEqual(diagnostics["mappings"][0]["restored"], "①")
        self.assertTrue(result["diagnostics"]["unicode_normalization"]["strict_utf8"])

    def test_parse_restores_mojibake_layer_and_block_names(self):
        mojibake_layer = "製図".encode("utf-8").decode("cp932")
        mojibake_block = "配管".encode("utf-8").decode("cp932")
        document = ezdxf.new("R2013")
        document.layers.add(mojibake_layer)
        block = document.blocks.new(mojibake_block)
        block.add_line((0, 0), (1, 1), dxfattribs={"layer": mojibake_layer})
        document.modelspace().add_blockref(
            mojibake_block,
            (0, 0),
            dxfattribs={"layer": mojibake_layer},
        )
        stream = io.StringIO()
        document.write(stream)

        result = parse_dxf(stream.getvalue().encode("utf-8"))

        self.assertEqual(result["layers"], ["製図"])
        self.assertEqual(result["blocks"][0]["name"], "配管")
        self.assertEqual(result["entities"][0]["layer"], "製図")
        self.assertEqual(result["entities"][0]["block"], "配管")
        self.assertEqual(result["inserts"][0]["layer"], "製図")
        self.assertEqual(result["inserts"][0]["block"], "配管")
        diagnostics = result["diagnostics"]["name_decoding"]
        self.assertEqual(diagnostics["restored_occurrence_count"], 7)
        self.assertEqual(len(diagnostics["mappings"]), 2)
        self.assertGreaterEqual(diagnostics["mappings"][0]["confidence"], 0.8)
        layer_mapping = next(
            item
            for item in diagnostics["mappings"]
            if "blocks[].entities[].layer" in item["locations"]
        )
        self.assertIn("blocks[].entities[].layer", layer_mapping["locations"])


if __name__ == "__main__":
    unittest.main()

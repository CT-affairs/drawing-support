from __future__ import annotations

import io
import math
from collections import Counter
from typing import BinaryIO, Any
import ezdxf
from ezdxf import recover
from ezdxf.entities import DXFEntity


class DxfParseError(ValueError):
    """Raised when an uploaded file is not a readable DXF document."""


def _number(value: Any) -> int | float | None:
    if value is None:
        return None
    value = float(value)
    if not math.isfinite(value):
        return None
    return int(value) if value.is_integer() else value


def _point(value: Any) -> list[int | float]:
    return [_number(value.x), _number(value.y), _number(value.z)]


def _entity_json(entity: DXFEntity) -> dict[str, Any]:
    item: dict[str, Any] = {
        "type": entity.dxftype(),
        "layer": entity.dxf.get("layer", "0"),
    }
    dxf = entity.dxf

    if entity.dxftype() in {"LINE", "3DLINE"}:
        item.update(start=_point(dxf.start), end=_point(dxf.end))
    elif entity.dxftype() in {"LWPOLYLINE", "POLYLINE"}:
        points = []
        if entity.dxftype() == "LWPOLYLINE":
            points = [[_number(p[0]), _number(p[1])] for p in entity.get_points("xy")]
        else:
            points = [_point(vertex.dxf.location) for vertex in entity.vertices]
        item["points"] = points
        item["closed"] = bool(entity.is_closed)
    elif entity.dxftype() == "CIRCLE":
        item.update(center=_point(dxf.center), radius=_number(dxf.radius))
    elif entity.dxftype() == "ARC":
        item.update(
            center=_point(dxf.center),
            radius=_number(dxf.radius),
            start_angle=_number(dxf.start_angle),
            end_angle=_number(dxf.end_angle),
        )
    elif entity.dxftype() in {"TEXT", "MTEXT"}:
        item["text"] = entity.plain_text() if entity.dxftype() == "MTEXT" else dxf.text
        item["insert"] = _point(dxf.insert)
    elif entity.dxftype() == "INSERT":
        item.update(block=dxf.name, insert=_point(dxf.insert))
    elif entity.dxftype() == "DIMENSION":
        item["text"] = dxf.get("text", "")

    return item


def _entity_counts(entities: list[DXFEntity]) -> dict[str, int]:
    return dict(sorted(Counter(entity.dxftype() for entity in entities).items()))


def _insert_json(entity: DXFEntity, space: str) -> dict[str, Any]:
    dxf = entity.dxf
    return {
        "space": space,
        "block": dxf.name,
        "layer": dxf.get("layer", "0"),
        "insert": _point(dxf.insert),
        "rotation": _number(dxf.get("rotation", 0)),
        "scale": [
            _number(dxf.get("xscale", 1)),
            _number(dxf.get("yscale", 1)),
            _number(dxf.get("zscale", 1)),
        ],
    }


def _header_value(text: str, variable: str) -> str | None:
    lines = text.splitlines()
    for index in range(len(lines) - 3):
        if (
            lines[index].strip() == "9"
            and lines[index + 1].strip() == variable
            and lines[index + 2].strip() in {"1", "2", "3", "70"}
        ):
            return lines[index + 3].strip()
    return None


def _encoding_diagnostics(raw_bytes: bytes, preferred_encoding: str | None = None) -> tuple[str, str, dict[str, Any]]:
    candidates = [preferred_encoding] if preferred_encoding else []
    candidates.extend(["utf-8-sig", "cp932", "cp1252"])
    candidates = list(dict.fromkeys(candidates))

    decoded = {}
    candidate_results = []
    for encoding in candidates:
        try:
            text = raw_bytes.decode(encoding, errors="strict")
            decoded[encoding] = text
            japanese_count = sum(
                1
                for char in text
                if "\u3040" <= char <= "\u30ff" or "\u4e00" <= char <= "\u9fff"
            )
            control_count = sum(
                1
                for char in text
                if ord(char) < 32 and char not in {"\r", "\n", "\t"}
            )
            confidence = 0.55
            if encoding in {"cp932", "utf-8", "utf-8-sig"}:
                confidence += 0.1
            if japanese_count:
                confidence += 0.2
            if control_count:
                confidence -= min(0.2, control_count / max(1, len(text)))
            candidate_results.append(
                {
                    "encoding": encoding,
                    "valid": True,
                    "replacement_count": text.count("\ufffd"),
                    "surrogate_count": sum(0xD800 <= ord(char) <= 0xDFFF for char in text),
                    "unicode_escape_count": text.count("\\U+"),
                    "japanese_char_count": japanese_count,
                    "confidence": round(max(0.0, min(1.0, confidence)), 2),
                }
            )
        except UnicodeDecodeError as exc:
            candidate_results.append(
                {
                    "encoding": encoding,
                    "valid": False,
                    "error": str(exc),
                    "confidence": 0.0,
                }
            )

    codepage = None
    for text in decoded.values():
        codepage = _header_value(text, "$DWGCODEPAGE")
        if codepage:
            break
    codepage_map = {
        "ANSI_932": "cp932",
        "ANSI_1252": "cp1252",
        "ANSI_1250": "cp1250",
        "ANSI_1251": "cp1251",
        "ANSI_1254": "cp1254",
    }
    codepage_encoding = codepage_map.get((codepage or "").upper())
    valid_candidates = [item for item in candidate_results if item["valid"]]
    selected = next(
        (item for item in valid_candidates if item["encoding"] == codepage_encoding),
        None,
    )
    if selected is None and preferred_encoding:
        selected = next(
            (item for item in valid_candidates if item["encoding"] == preferred_encoding),
            None,
        )
    if selected is None:
        selected = next(
            (item for item in valid_candidates if item["encoding"] in {"utf-8", "utf-8-sig"}),
            None,
        )
    if selected is None:
        selected = next(
            (item for item in valid_candidates if item["encoding"] == "cp932"),
            None,
        )
    if selected is None:
        selected = max(valid_candidates, key=lambda item: item["confidence"], default=None)
    if selected is None:
        raise UnicodeDecodeError("unknown", raw_bytes, 0, len(raw_bytes), "no supported encoding candidate")

    selected_encoding = selected["encoding"]
    selected_text = decoded[selected_encoding]
    return selected_encoding, selected_text, {
        "dwg_codepage": codepage,
        "codepage_encoding": codepage_encoding,
        "selected_encoding": selected_encoding,
        "selected_confidence": selected["confidence"],
        "candidates": candidate_results,
    }


def _raw_dxf_diagnostics(text: str, source_size: int, encoding: str) -> dict[str, Any]:
    """Collect lightweight diagnostics without expanding every DXF entity."""
    lines = text.splitlines()
    sections = []
    current = None

    for index, line in enumerate(lines):
        value = line.strip()
        next_value = lines[index + 1].strip() if index + 1 < len(lines) else None

        if value == "0" and next_value == "SECTION" and index + 3 < len(lines):
            if lines[index + 2].strip() == "2":
                current = {
                    "name": lines[index + 3].strip(),
                    "line_count": 0,
                    "record_counts": Counter(),
                }
                sections.append(current)
                continue

        if current is None:
            continue

        current["line_count"] += 1
        if value == "0" and next_value not in {None, "SECTION", "ENDSEC", "EOF"}:
            current["record_counts"][next_value] += 1
        if value == "0" and next_value == "ENDSEC":
            current = None

    normalized_sections = []
    for section in sections:
        record_counts = dict(sorted(section["record_counts"].items()))
        normalized_sections.append(
            {
                "name": section["name"],
                "line_count": section["line_count"],
                "record_counts": record_counts,
                "record_count": sum(record_counts.values()),
            }
        )

    entities_section = next(
        (section for section in normalized_sections if section["name"] == "ENTITIES"),
        None,
    )
    return {
        "file_size_bytes": source_size,
        "text_encoding": encoding,
        "sections": normalized_sections,
        "entities_section": entities_section,
    }


def _document_geometry_count(document: Any) -> int:
    layout_count = sum(sum(1 for _ in layout) for layout in document.layouts)
    block_count = sum(
        sum(1 for _ in block)
        for block in document.blocks
        if block.name not in {"*Model_Space", "*Paper_Space"}
    )
    return layout_count + block_count


def _needs_recover(document: Any, diagnostics: dict[str, Any]) -> bool:
    if _document_geometry_count(document) > 0:
        return False
    return any(
        section["name"] in {"ENTITIES", "BLOCKS"} and section["record_count"] > 0
        for section in diagnostics["sections"]
    )


def parse_dxf(source: BinaryIO | bytes) -> dict[str, Any]:
    try:
        raw = source if isinstance(source, bytes) else source.read()
        raw_bytes = raw if isinstance(raw, bytes) else raw.encode("utf-8")
        source_size = len(raw_bytes)
        preferred_encoding = None if isinstance(raw, bytes) else "utf-8"
        encoding, text, encoding_diagnostics = _encoding_diagnostics(raw_bytes, preferred_encoding)
        document = ezdxf.read(io.StringIO(text))
    except (OSError, IOError, ezdxf.DXFError, UnicodeError) as exc:
        raise DxfParseError("DXF could not be read") from exc

    diagnostics = _raw_dxf_diagnostics(text, source_size, encoding)
    diagnostics["encoding"] = encoding_diagnostics
    loader = "standard"
    recover_info: dict[str, Any] = {"attempted": False}
    audit = None
    if _needs_recover(document, diagnostics):
        recover_info["attempted"] = True
        try:
            document, audit = recover.read(io.BytesIO(raw_bytes))
            loader = "recover"
        except (OSError, IOError, ezdxf.DXFError, UnicodeError) as exc:
            recover_info["error"] = str(exc)

    space_summaries = []
    layout_entities: dict[str, list[DXFEntity]] = {}
    inserts = []
    for layout in document.layouts:
        layout_entities[layout.name] = list(layout)
        entities_in_layout = layout_entities[layout.name]
        for entity in entities_in_layout:
            if entity.dxftype() == "INSERT":
                inserts.append(_insert_json(entity, layout.name))
        space_summaries.append(
            {
                "name": layout.name,
                "kind": "model" if layout.name == "Model" else "paper",
                "entity_count": len(entities_in_layout),
                "entity_counts": _entity_counts(entities_in_layout),
            }
        )

    modelspace_entities = layout_entities.get("Model", [])
    entities = [_entity_json(entity) for entity in modelspace_entities]
    counts = Counter(item["type"] for item in entities)
    layers = sorted(
        {
            entity.dxf.get("layer", "0")
            for entities_in_layout in layout_entities.values()
            for entity in entities_in_layout
        }
    )

    blocks = []
    for block in document.blocks:
        if block.name in {"*Model_Space", "*Paper_Space"}:
            continue
        block_entities = list(block)
        blocks.append(
            {
                "name": block.name,
                "entity_count": len(block_entities),
                "entity_counts": _entity_counts(block_entities),
            }
        )
    blocks.sort(key=lambda item: item["name"])

    if audit is None:
        audit = document.audit()
    diagnostics.update(
        {
            "loader": loader,
            "recover": recover_info,
            "ezdxf_entity_database_count": len(document.entitydb),
            "layout_count": len(space_summaries),
            "layer_table_count": len(document.layers),
            "block_definition_count": len(blocks),
            "audit": {
                "error_count": len(audit.errors),
                "fix_count": len(audit.fixes),
            },
        }
    )

    return {
        "schema_version": "1.0",
        "dxf_version": document.dxfversion,
        "units": _number(document.header.get("$INSUNITS")),
        "layers": layers,
        "entity_counts": dict(sorted(counts.items())),
        "entities": entities,
        "spaces": space_summaries,
        "blocks": blocks,
        "inserts": inserts,
        "diagnostics": diagnostics,
    }

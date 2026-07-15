from __future__ import annotations

import io
import math
from collections import Counter
from typing import BinaryIO, Any

import ezdxf
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


def parse_dxf(source: BinaryIO | bytes) -> dict[str, Any]:
    try:
        raw = source if isinstance(source, bytes) else source.read()
        if isinstance(raw, bytes):
            try:
                text = raw.decode("utf-8-sig")
            except UnicodeDecodeError:
                text = raw.decode("cp932")
        else:
            text = raw
        document = ezdxf.read(io.StringIO(text))
    except (OSError, IOError, ezdxf.DXFError, UnicodeError) as exc:
        raise DxfParseError("DXF could not be read") from exc

    entities = [_entity_json(entity) for entity in document.modelspace()]
    counts = Counter(item["type"] for item in entities)
    layers = sorted({item["layer"] for item in entities})

    return {
        "schema_version": "1.0",
        "dxf_version": document.dxfversion,
        "units": _number(document.header.get("$INSUNITS")),
        "layers": layers,
        "entity_counts": dict(sorted(counts.items())),
        "entities": entities,
    }

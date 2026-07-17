from __future__ import annotations

from typing import Any


def _normalize_string(value: str) -> tuple[str, int, int]:
    """Return a Unicode-scalar-only string without losing unresolved bytes."""
    output = []
    escaped_count = 0
    combined_pair_count = 0
    index = 0
    while index < len(value):
        codepoint = ord(value[index])
        if 0xD800 <= codepoint <= 0xDBFF and index + 1 < len(value):
            low = ord(value[index + 1])
            if 0xDC00 <= low <= 0xDFFF:
                scalar = 0x10000 + ((codepoint - 0xD800) << 10) + (low - 0xDC00)
                output.append(chr(scalar))
                combined_pair_count += 1
                index += 2
                continue
        if 0xDC80 <= codepoint <= 0xDCFF:
            output.append(f"\\x{codepoint - 0xDC00:02x}")
            escaped_count += 1
        elif 0xD800 <= codepoint <= 0xDFFF:
            output.append(f"\\u{codepoint:04x}")
            escaped_count += 1
        else:
            output.append(value[index])
        index += 1
    return "".join(output), escaped_count, combined_pair_count


def normalize_json_unicode(value: Any) -> tuple[Any, dict[str, int | bool | str]]:
    """Normalize all JSON strings so strict UTF-8 encoding always succeeds.

    Low surrogateescape bytes are preserved as visible ``\\xNN`` tokens. Other
    unpaired surrogates are preserved as visible ``\\uXXXX`` tokens.
    """
    stats = {
        "strategy": "combine_pairs_and_escape_unpaired_surrogates",
        "affected_string_count": 0,
        "escaped_surrogate_count": 0,
        "combined_surrogate_pair_count": 0,
        "strict_utf8": True,
    }

    def visit(item: Any) -> Any:
        if isinstance(item, str):
            normalized, escaped, combined = _normalize_string(item)
            if escaped or combined:
                stats["affected_string_count"] += 1
                stats["escaped_surrogate_count"] += escaped
                stats["combined_surrogate_pair_count"] += combined
            return normalized
        if isinstance(item, list):
            return [visit(child) for child in item]
        if isinstance(item, tuple):
            return [visit(child) for child in item]
        if isinstance(item, dict):
            normalized = {}
            for key, child in item.items():
                normalized_key = visit(key) if isinstance(key, str) else key
                if normalized_key in normalized:
                    raise ValueError("JSON keys collide after Unicode normalization")
                normalized[normalized_key] = visit(child)
            return normalized
        return item

    return visit(value), stats

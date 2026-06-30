"""Human-friendly zone labels derived from location metadata."""

from __future__ import annotations

import re


_BLANK = {"", "none", "null", "nan"}


def _clean(value: object) -> str:
    text = str(value or "").strip()
    return "" if text.lower() in _BLANK else text


def _title_token(value: str) -> str:
    if not value:
        return ""
    words = re.split(r"[_\s]+", value.strip())
    keep_upper = {"GFA", "HVAC", "PTAC", "UPS", "IT"}
    out = []
    for word in words:
        upper = word.upper()
        out.append(upper if upper in keep_upper else word[:1].upper() + word[1:].lower())
    return " ".join(out)


def floor_label(value: object) -> str:
    text = _clean(value)
    if not text:
        return "Unknown floor"
    text = text.replace("-", "_")
    lower = text.lower()
    if lower.startswith(("level_", "floor_")):
        prefix, suffix = text.split("_", 1)
        digits = "".join(ch for ch in suffix if ch.isdigit())
        if digits:
            return f"Level {int(digits):02d}"
        return _title_token(prefix)
    return _title_token(text)


def _collapse_repeated_colon_label(value: str) -> str:
    parts = [p.strip() for p in value.split(":") if p.strip()]
    if not parts:
        return value
    if len(parts) >= 2 and parts[0].casefold() == parts[1].casefold():
        return parts[0]
    if len(parts) >= 2 and parts[-1].isdigit():
        return f"{parts[0]} {parts[-1]}"
    return " ".join(parts)


def _collapse_repeated_leading_token(value: str) -> str:
    words = value.split()
    if len(words) >= 2 and words[0].casefold() == words[1].casefold():
        return " ".join([words[0], *words[2:]])
    return value


def _area_label(area_m2: object) -> str:
    try:
        area = float(area_m2)
    except (TypeError, ValueError):
        return ""
    if area <= 0:
        return ""
    return f"{area:,.0f} m²" if area >= 100 else f"{area:,.1f} m²"


def zone_space_label(
    *,
    long_name: object = None,
    number: object = None,
    room_name: object = None,
    room_id: object = None,
    room_type: object = None,
    eplus_zone_name: object = None,
    energy_scope: object = None,
) -> str:
    label = _clean(long_name) or _clean(room_name)
    num = _clean(number) or _clean(room_id)
    rtype = _clean(room_type)
    scope = _clean(energy_scope)

    if label and num and num not in label:
        label = f"{label} {num}"
    elif not label:
        label = num

    label = _collapse_repeated_colon_label(label)
    label = _collapse_repeated_leading_token(label)
    if label and label.upper().startswith("ZN_"):
        label = ""

    if scope == "aggregate_context":
        if not label or re.fullmatch(r"[A-Za-z0-9]{1,3}", label):
            base = "Aggregate context"
            if rtype == "gross_area_placeholder":
                base = "Gross area"
            label = f"{base} {label}".strip()
    elif rtype and (not label or label.upper().startswith("ZN_")):
        label = _title_token(rtype)

    if not label:
        label = _clean(eplus_zone_name) or "Zone"
    return label


def zone_display_name(
    *,
    floor: object = None,
    storey: object = None,
    long_name: object = None,
    number: object = None,
    room_name: object = None,
    room_id: object = None,
    room_type: object = None,
    eplus_zone_name: object = None,
    area_m2: object = None,
    energy_scope: object = None,
) -> str:
    location = floor_label(storey or floor)
    space = zone_space_label(
        long_name=long_name,
        number=number,
        room_name=room_name,
        room_id=room_id,
        room_type=room_type,
        eplus_zone_name=eplus_zone_name,
        energy_scope=energy_scope,
    )
    parts = [location, space]
    area = _area_label(area_m2)
    if area:
        parts.append(area)
    return " · ".join(parts)


def zone_display_name_from_mapping(row: dict) -> str:
    return zone_display_name(
        floor=row.get("floor_id"),
        storey=row.get("storey"),
        long_name=row.get("long_name"),
        number=row.get("number"),
        room_type=row.get("room_type"),
        eplus_zone_name=row.get("eplus_zone_name"),
        area_m2=row.get("area_m2"),
        energy_scope=row.get("energy_scope"),
    )

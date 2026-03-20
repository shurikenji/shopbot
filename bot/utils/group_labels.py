from __future__ import annotations

import json

from db.database import get_db


def _split_group_names(group_value: str | None) -> list[str]:
    return [part.strip() for part in str(group_value or "").split(",") if part.strip()]


def _group_labels_from_cache(server: dict | None) -> dict[str, str]:
    if not server:
        return {}

    raw_cache = server.get("groups_cache")
    if not raw_cache:
        return {}

    try:
        rows = json.loads(raw_cache)
    except (TypeError, ValueError, json.JSONDecodeError):
        return {}

    if not isinstance(rows, list):
        return {}

    label_map: dict[str, str] = {}
    for row in rows:
        if not isinstance(row, dict):
            continue
        name = str(row.get("name") or "").strip()
        label_vi = str(
            row.get("label_vi") or row.get("name_vi") or row.get("name") or ""
        ).strip()
        if name:
            label_map[name] = label_vi or name
    return label_map


async def _get_cached_group_labels(
    group_names: list[str], api_type: str
) -> dict[str, str]:
    if not group_names:
        return {}

    db = await get_db()
    placeholders = ",".join("?" * len(group_names))
    cursor = await db.execute(
        f"""SELECT original_name, name_vi
            FROM group_translations
            WHERE original_name IN ({placeholders}) AND api_type = ?""",
        (*group_names, api_type),
    )
    rows = await cursor.fetchall()
    return {
        str(row[0]): str(row[1] or row[0]).strip()
        for row in rows
        if row and row[0]
    }


async def format_group_display_names(
    group_value: str | None, server: dict | None = None
) -> str:
    group_names = _split_group_names(group_value)
    if not group_names:
        return ""

    label_map = _group_labels_from_cache(server)
    missing_names = [name for name in group_names if name not in label_map]

    if missing_names and server:
        api_type = str(server.get("api_type") or "newapi")
        label_map.update(await _get_cached_group_labels(missing_names, api_type))

    return ", ".join(label_map.get(name, name) for name in group_names)

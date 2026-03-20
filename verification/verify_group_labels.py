"""Verification for translated group labels used in bot displays."""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from bot.utils.group_labels import format_group_display_names


async def main() -> None:
    server = {
        "api_type": "newapi",
        "groups_cache": (
            '[{"name":"premium","label_vi":"Cao \\u1ea5p"},'
            '{"name":"vip","label_vi":"\\u01afu ti\\u00ean"},'
            '{"name":"basic","label_vi":""}]'
        ),
    }

    translated = await format_group_display_names("premium,vip", server)
    assert translated == "Cao \u1ea5p, \u01afu ti\u00ean"
    print("[OK] format_group_display_names prefers translated labels from server cache")

    untranslated = await format_group_display_names("basic", server)
    assert untranslated == "basic"
    print("[OK] format_group_display_names falls back to original names when no translation exists")


if __name__ == "__main__":
    asyncio.run(main())

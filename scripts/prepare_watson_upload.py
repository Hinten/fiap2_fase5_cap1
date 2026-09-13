"""Create a compact UTF-8 copy of the Watson export for browser upload."""

from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "config" / "watson" / "cardioia-dialog.json"
TARGET = ROOT / "tmp" / "watson" / "cardioia-dialog-upload.json"


def main() -> None:
    skill = json.loads(SOURCE.read_text(encoding="utf-8"))
    TARGET.parent.mkdir(parents=True, exist_ok=True)
    TARGET.write_text(
        json.dumps(skill, ensure_ascii=False, separators=(",", ":")),
        encoding="utf-8",
        newline="\n",
    )
    print(TARGET.resolve())


if __name__ == "__main__":
    main()

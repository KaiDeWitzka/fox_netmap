# scripts/checkliste_punkte.py, Aufruf: uv run python scripts/checkliste_punkte.py docs/produktionsreife/UEBERGABE.md
import json
import re
import sys

with open(sys.argv[1], encoding="utf-8") as f:
    text = f.read()
sec = text.split("## 7. Befundkatalog", 1)[1].split("\n## 8.", 1)[0]
items = []
for block in re.split(r"\n#### ", sec)[1:]:
    head, _, body = block.partition("\n")
    m = re.match(r"(.*) \(([^()]*)\)\s*$", head.strip())
    meta = re.search(r"\*\*Schwere:\*\* (\w+).*\*\*Welle:\*\* (W\d)", body)
    if not m or not meta:
        continue
    ids = [i.strip() for i in m.group(2).split(",")]
    items.append(
        {
            "id": ids[0],
            "titel": m.group(1).replace("`", ""),
            "welle": meta.group(2),
            "schwere": meta.group(1),
            "status": "offen",
            "nachweis": "",
            "commit": "",
            "notiz": ("mit " + ", ".join(ids[1:])) if len(ids) > 1 else "",
        }
    )
print(json.dumps(items, ensure_ascii=False, indent=1))
print(len(items), "Punkte", file=sys.stderr)

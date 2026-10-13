#!/usr/bin/env python3
"""Render the per-collection part of docs/phase0/DATA_DICTIONARY.md.

Input: the JSON written by collection_inventory.py. Output: Markdown on stdout
(or ``-o path``). An optional ``--header`` Markdown file is prepended verbatim.
Stdlib only; derived from static analysis, never from a live database.

Usage:
  python3 tools/audit/render_data_dictionary.py docs/phase0/collection_inventory.json \
      --header header.md --top 25 -o docs/phase0/DATA_DICTIONARY.md
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from collections import Counter
from typing import Dict, List

KIND_LABEL = {
    "iso_string": "ISO-8601 string",
    "datetime": "BSON Date (datetime)",
    "date": "date",
    "formatted_date_string": "strftime string",
    "uuid_string": "UUID string",
    "uuid_object": "UUID object",
    "objectid": "ObjectId",
    "objectid_string": "ObjectId hex string",
    "float": "float",
    "int": "int",
    "number": "number (expr)",
    "bool": "bool",
    "str": "string",
    "object": "object",
    "array": "array",
    "null": "null",
    "enum_value": "Enum .value (string)",
    "password_hash": "bcrypt hash",
    "encrypted": "encrypted string",
}
SOURCE_ABBR = {"insert": "I", "set": "S", "setOnInsert": "SoI", "filter": "F", "sort": "O"}
DATE_RE = re.compile(r"(_at|_date|date|timestamp|_time|_on|expiry|_until|deadline)$")
MONEY_RE = re.compile(r"(amount|price|fare|fee|cost|balance|rent|salary|commission|tax|gst|premium|payout|revenue|spent|total$|_total|paise)")


def kind_text(kinds: Dict[str, int]) -> str:
    known, unknown = [], 0
    for k, n in sorted(kinds.items(), key=lambda kv: -kv[1]):
        if k in KIND_LABEL:
            known.append(KIND_LABEL[k])
        elif k.startswith("param:"):
            known.append("param " + k[6:].replace("|", "/"))
        else:
            unknown += n
    out = ", ".join(dict.fromkeys(known))
    if unknown and not out:
        out = "runtime value"
    if "ISO-8601 string" in out and "BSON Date (datetime)" in out:
        out = "**MIXED** " + out
    return out


def sources_text(src: Dict[str, int]) -> str:
    parts = []
    for k, n in sorted(src.items(), key=lambda kv: -kv[1]):
        parts.append(f"{SOURCE_ABBR.get(k, '$' + k)}{n}")
    return " ".join(parts)


def esc(s: str) -> str:
    return s.replace("|", "\\|").replace("\n", " ")


def date_format(c: Dict) -> str:
    cnt = Counter()
    for f, d in c["fields"].items():
        if DATE_RE.search(f):
            for k, n in d["kinds"].items():
                if k in {"iso_string", "datetime", "formatted_date_string", "date"}:
                    cnt[k] += n
    if not cnt:
        return "unknown"
    if cnt["iso_string"] and cnt["datetime"]:
        return f"MIXED (ISO {cnt['iso_string']} / Date {cnt['datetime']})"
    k = cnt.most_common(1)[0][0]
    return {"iso_string": "ISO string", "datetime": "BSON Date", "formatted_date_string": "strftime string", "date": "date"}[k]


def id_strategy(c: Dict) -> str:
    f = c["fields"]
    parts = []
    if "id" in f:
        k = f["id"]["kinds"]
        if k.get("uuid_string"):
            parts.append("`id` UUID string")
        elif k.get("str"):
            parts.append("`id` custom string")
        elif "insert" in f["id"]["sources"]:
            parts.append("`id` (runtime value)")
        else:
            parts.append("`id` (queried; written elsewhere)")
    if "_id" in f:
        k = f["_id"]["kinds"]
        if "insert" in f["_id"]["sources"]:
            parts.append("`_id` set by code (" + (kind_text(k) or "runtime") + ")")
        else:
            parts.append("`_id` used in filters")
    if not parts:
        parts.append("`_id` ObjectId only (ASSUMPTION)")
    return "; ".join(parts)


def render(data: Dict, top: int) -> str:
    colls = data["collections"]
    ranked = sorted(colls.items(), key=lambda kv: (-kv[1]["references"], kv[0]))
    out: List[str] = []
    out.append(f"## 3. Top {top} collections by code references\n")
    out.append("Legend for **Seen as**: I = written by insert, S = `$set`, SoI = `$setOnInsert`, F = used in a filter, "
               "O = sort key, `$inc`/`$push`/... = other update operators; the number is how many call sites. "
               "**Format** is inferred from the value expression at the write site (e.g. `datetime.utcnow().isoformat()` "
               "→ ISO-8601 string, `datetime.now(timezone.utc)` → BSON Date). \"runtime value\" means the value comes from "
               "a variable or request field and the type cannot be read statically. Fields seen only as sort keys after a "
               "`$group` stage are aggregate aliases, not stored fields.\n")
    for name, c in ranked[:top]:
        out.append(f"### `{name}`\n")
        mods = sorted(c["files"])
        ops = ", ".join(f"{k} {v}" for k, v in sorted(c["operations"].items(), key=lambda kv: -kv[1]))
        out.append(f"- **References:** {c['references']} in {len(mods)} files. **Operations:** {ops}.")
        out.append(f"- **ID strategy:** {id_strategy(c)}. **Date format:** {date_format(c)}.")
        if c["insert_model_hints"]:
            out.append("- **Written from Pydantic model(s):** " + ", ".join(f"`{k}`" for k in c["insert_model_hints"]) + ".")
        if c["unresolved_inserts"]:
            out.append(f"- **Inserts not statically resolvable:** {c['unresolved_inserts']} (document built at runtime).")
        out.append("- **Referencing modules:** " + ", ".join(
            f"`{m.replace('backend/', '')}`" for m in mods) + ".")
        if c["indexes"]:
            idx = "; ".join(
                "`" + ", ".join(f"{k[0]}:{k[1]}" for k in (i["keys"] if isinstance(i["keys"], list) else [[i["keys"], ""]])) + "`"
                + (" " + ", ".join(f"{a}={b}" for a, b in i["options"].items()) if i["options"] else "")
                + f" ({i['file'].replace('backend/', '')}:{i['line']})"
                for i in c["indexes"])
            out.append(f"- **Indexes declared in code:** {idx}.")
        else:
            out.append("- **Indexes declared in code:** none.")
        out.append("")
        out.append("| Field | Seen as | Format (inferred) | String constants seen (enum candidates) |")
        out.append("|---|---|---|---|")
        for f, d in sorted(c["fields"].items()):
            samples = ", ".join(f"`{esc(s)}`" for s in d["samples"][:14])
            fmt = kind_text(d["kinds"])
            if not d["kinds"] and set(d["sources"]) <= {"filter", "sort"}:
                fmt = "(read only here)"
            out.append(f"| `{esc(f)}` | {sources_text(d['sources'])} | {fmt} | {samples} |")
        out.append("")

    out.append(f"## 4. Remaining {len(ranked) - top} collections (compact)\n")
    out.append("| Collection | Refs | Modules | Ops | Most-used fields | Dates | ID | Idx |")
    out.append("|---|---|---|---|---|---|---|---|")
    for name, c in ranked[top:]:
        mods = sorted(m.replace("backend/", "").replace("routes/", "r/").replace("services/", "s/") for m in c["files"])
        mod_txt = ", ".join(mods[:3]) + (f" +{len(mods) - 3}" if len(mods) > 3 else "")
        ops = ", ".join(sorted(c["operations"]))
        usage = sorted(c["fields"].items(), key=lambda kv: -sum(kv[1]["sources"].values()))
        fields = ", ".join(f[0] for f in usage[:8])
        out.append(f"| `{name}` | {c['references']} | {esc(mod_txt)} | {ops} | {esc(fields)} | {date_format(c)} | "
                   f"{esc(id_strategy(c))} | {len(c['indexes'])} |")
    out.append("")
    return "\n".join(out)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("inventory")
    ap.add_argument("--header")
    ap.add_argument("--top", type=int, default=25)
    ap.add_argument("-o", "--output")
    ns = ap.parse_args(argv)
    data = json.load(open(ns.inventory, encoding="utf-8"))
    text = (open(ns.header, encoding="utf-8").read().rstrip() + "\n\n" if ns.header else "") + render(data, ns.top)
    if ns.output:
        open(ns.output, "w", encoding="utf-8").write(text)
    else:
        sys.stdout.write(text)
    return 0


if __name__ == "__main__":
    sys.exit(main())

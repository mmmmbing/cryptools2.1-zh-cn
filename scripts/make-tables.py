# make-tables.py
# Produce human-reviewable translation tables from the cache + extracted strings.
#
# Outputs (under data/ and out/):
#   data/translation-table.csv   - assembly, resource, key, german, chinese
#   data/translation-table.json  - same content, structured
#   data/untranslated.csv        - strings still lacking a translation
#   data/stats.json              - coverage summary

import csv
import json
import os

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.normpath(os.path.join(HERE, "..", "data"))
OUT = os.path.normpath(os.path.join(HERE, "..", "out"))


def load(name, default=None):
    p = os.path.join(DATA, name)
    if not os.path.exists(p):
        return default
    with open(p, "r", encoding="utf-8") as fh:
        return json.load(fh)


def write_csv(path, header, rows):
    # utf-8-sig so Excel opens Chinese correctly.
    with open(path, "w", encoding="utf-8-sig", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(header)
        w.writerows(rows)


def main():
    strings = load("strings.json", [])
    cache = load("translation-cache.json", {})

    table = []
    missing = []
    empty = 0
    for s in strings:
        de = s["source_de"]
        zh = cache.get(de)
        if zh is None and de:
            # CRLF resources were normalised to LF before translation; retry.
            zh = cache.get(de.replace("\r\n", "\n"))
        if not de:
            empty += 1
        row = {
            "assembly": s["assembly"],
            "resource": s["resource"],
            "key": s["key"],
            "german": de,
            "chinese": zh if zh is not None else "",
            "translated": zh is not None,
        }
        table.append(row)
        # Empty source strings need no translation and must not count as gaps.
        if zh is None and de:
            missing.append(row)

    write_csv(
        os.path.join(DATA, "translation-table.csv"),
        ["assembly", "resource", "key", "german", "chinese"],
        [[r["assembly"], r["resource"], r["key"], r["german"], r["chinese"]] for r in table],
    )
    with open(os.path.join(DATA, "translation-table.json"), "w", encoding="utf-8") as fh:
        json.dump(table, fh, ensure_ascii=False, indent=1)

    if missing:
        write_csv(
            os.path.join(DATA, "untranslated.csv"),
            ["assembly", "resource", "key", "german"],
            [[r["assembly"], r["resource"], r["key"], r["german"]] for r in missing],
        )

    translatable = len(table) - empty
    stats = {
        "total_entries": len(table),
        "empty_source_entries": empty,
        "translatable_entries": translatable,
        "translated": translatable - len(missing),
        "untranslated": len(missing),
        "coverage_pct": round(
            (translatable - len(missing)) * 100.0 / translatable, 2
        ) if translatable else 0.0,
        "assemblies": len({r["assembly"] for r in table}),
        "unique_sources": len({r["german"] for r in table if r["german"]}),
    }
    with open(os.path.join(DATA, "stats.json"), "w", encoding="utf-8") as fh:
        json.dump(stats, fh, ensure_ascii=False, indent=1)

    print(json.dumps(stats, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()

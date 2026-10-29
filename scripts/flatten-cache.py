# flatten-cache.py
# Convert translation-cache.json into a flat lookup file that
# PowerShell's ConvertFrom-Json can parse safely.
#
# Reason: German has strings that differ only by capitalisation
# ("Verschlüsselter Text" vs "verschlüsselter Text"). JSON allows both as
# distinct keys and Python keeps them apart, but PowerShell's JSON reader uses
# a case-insensitive dictionary and refuses the file with DUPLICATE KEYS.
# We therefore emit an array of {s,t} records plus a SHA-1 of the source text
# as the lookup handle, which is case-sensitive and collision-checked.

import hashlib
import json
import os

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.normpath(os.path.join(HERE, "..", "data"))


def key_for(text):
    return hashlib.sha1(text.encode("utf-8")).hexdigest()


def main():
    with open(os.path.join(DATA, "translation-cache.json"), encoding="utf-8") as fh:
        cache = json.load(fh)

    records = []
    seen = {}
    for src, dst in cache.items():
        k = key_for(src)
        if k in seen and seen[k] != src:
            raise SystemExit("sha1 collision on %r" % src)
        seen[k] = src
        records.append({"h": k, "s": src, "t": dst})

    out = os.path.join(DATA, "translation-flat.json")
    with open(out, "w", encoding="utf-8") as fh:
        json.dump(records, fh, ensure_ascii=False)

    print("wrote %s (%d records)" % (out, len(records)))


if __name__ == "__main__":
    main()

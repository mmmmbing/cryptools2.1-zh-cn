# retranslate-bad.py
# Re-translate only the entries whose current Chinese looks corrupted by the
# old glossary matcher (orphan German linker letters next to CJK, e.g.
# "替换s 矩阵" or "加密/解密de数据").
#
# Run after changing the glossary masking strategy in translate.py.

import io
import json
import os
import re
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import translate as T  # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.normpath(os.path.join(HERE, "..", "data"))

# A CJK run followed by 1-3 latin letters and then a space/CJK/punct is the
# signature of a linker fragment left dangling by the old matcher.
BAD_RE = re.compile(
    r"[\u4e00-\u9fff]"
    r"(?:e|n|s|es|en|er|de)?"
    r"(?=[ \u4e00-\u9fff（(，,。:：])"
)
# Deliberately stricter: only flag a *short* latin fragment glued to CJK.
STRICT_RE = re.compile(r"[\u4e00-\u9fff](e|n|s|es|en|er|de)(?=[ \u4e00-\u9fff（(，,。:：])")


def main():
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

    strings = T.load_json(os.path.join(DATA, "strings.json"), [])
    cache_path = os.path.join(DATA, "translation-cache.json")
    cache = T.load_json(cache_path, {})
    glossary = T.load_json(os.path.join(DATA, "glossary.json"), {}).get("terms", [])

    bad = [de for de, zh in cache.items() if zh and STRICT_RE.search(zh)]
    print("flagged as corrupted: %d" % len(bad))

    ok = 0
    failed = []
    for i, de in enumerate(bad, 1):
        try:
            # Translate with NO glossary masking, then apply only whole-word
            # terminology fixes. Compounding and inflection mean masked
            # stems leave fragments ("Transpositionsschlüssel" -> "换位s 钥匙"),
            # so a plain MT pass reads better for these residual cases.
            fresh = T.gt_translate(de, sl="de", tl="zh-CN")
            fresh = T.apply_glossary(fresh, glossary)
            cache[de] = fresh
            ok += 1
        except Exception as exc:
            failed.append({"source": de, "error": str(exc)})

        if i % 20 == 0 or i == len(bad):
            T.save_json(cache_path, cache)
            print("  %d/%d ok=%d fail=%d" % (i, len(bad), ok, len(failed)))
        time.sleep(0.3)

    T.save_json(cache_path, cache)
    print("\nDONE retranslated=%d failed=%d" % (ok, len(failed)))
    if failed:
        T.save_json(os.path.join(DATA, "retranslate-failures.json"), failed)


if __name__ == "__main__":
    main()

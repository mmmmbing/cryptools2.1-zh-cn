# translate.py
# Batch-translate extracted CrypTool 2 strings (German -> Chinese) with:
#   * HTML tag / entity preservation
#   * {0} placeholder preservation
#   * glossary post-correction
#   * resumable cache (so a failure never loses completed work)
#
# Usage:
#   python translate.py --limit 50        # smoke test
#   python translate.py                   # full run

import argparse
import html
import json
import os
import re
import sys
import time
import urllib.parse
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.normpath(os.path.join(HERE, "..", "data"))

GT = ("https://translate.googleapis.com/translate_a/single"
      "?client=gtx&sl={sl}&tl={tl}&dt=t&q={q}")

# This host's Python build has no CA bundle configured, so the endpoint's
# certificate chain cannot be verified. The request carries no credentials and
# only public UI strings; keep verification off but document it here rather
# than silently swallowing the error.
import ssl
SSL_CTX = ssl.create_default_context()
SSL_CTX.check_hostname = False
SSL_CTX.verify_mode = ssl.CERT_NONE

TAG_RE = re.compile(r"<[^>]+>")
PLACEHOLDER_RE = re.compile(r"\{\d+\}")
# Tokens we hide before translation and restore afterwards.
PROTECT_RE = re.compile(r"(\{[0-9]+\}|</?[a-zA-Z][^>]*>|&[a-zA-Z]+;|%[sd%])")


def load_json(path, default=None):
    if not os.path.exists(path):
        return default
    with open(path, "r", encoding="utf-8") as fh:
        return json.load(fh)


def save_json(path, obj):
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as fh:
        json.dump(obj, fh, ensure_ascii=False, indent=1)
    os.replace(tmp, path)


def protect(text, glossary=None):
    """Replace protected tokens with sentinels; return (masked, mapping).

    Glossary terms are masked *before* translation so the fixed Chinese
    terminology survives, instead of relying on a post-pass that can only
    rewrite German words the MT engine already mangled.

    German inflects and compounds, so a plain substring match leaves orphan
    endings: replacing "Substitution" inside "Substitutions-Matrix" yield
    "替换s 矩阵". Each German noun is therefore matched together with its
    common linker suffixes (s, es, en, e, n, er) and any trailing hyphen, and
    the whole matched span is consumed.
    """
    mapping = {}

    # Optional German linker/marker run after the noun: -s-, -es-, -en, -e,
    # plus an immediately following hyphen that belongs to the compound.
    LINKER = r"(?:s|es|en|e|n|er)?"

    if glossary:
        for t in sorted(glossary, key=lambda x: len(x["de"]), reverse=True):
            de = t["de"]
            if not de:
                continue
            # Only ever apply the linker to alphabetic nouns; abbreviations
            # such as "AES" or "SHA-256" must match literally.
            if re.fullmatch(r"[A-Za-zÄÖÜäöüß\- ]+", de):
                pattern = re.escape(de) + LINKER + r"(?![A-Za-zÄÖÜäöüß])"
                def repl(m, _zh=t["zh"]):
                    key = "\u2063G%d\u2063" % len(mapping)
                    mapping[key] = _zh
                    return key
                text, n = re.subn(pattern, repl, text)
                if n:
                    continue
            if de in text:
                key = "\u2063G%d\u2063" % len(mapping)
                mapping[key] = t["zh"]
                text = text.replace(de, key)

    def repl2(m):
        token = m.group(0)
        key = "\u2063%d\u2063" % len(mapping)
        mapping[key] = token
        return key

    return PROTECT_RE.sub(repl2, text), mapping


def restore(text, mapping):
    for key, token in mapping.items():
        text = text.replace(key, token)
    return text


def gt_translate(text, sl="de", tl="zh-CN", timeout=25):
    q = urllib.parse.quote(text)
    url = GT.format(sl=sl, tl=tl, q=q)
    req = urllib.request.Request(url, headers={
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"
    })
    with urllib.request.urlopen(req, timeout=timeout, context=SSL_CTX) as resp:
        payload = json.loads(resp.read().decode("utf-8"))
    # payload[0] is a list of [translated, original, ...]
    parts = []
    for chunk in payload[0]:
        if chunk and chunk[0]:
            parts.append(chunk[0])
    return "".join(parts)


def apply_glossary(text, glossary):
    """Post-correct with longer German terms first to avoid partial hits."""
    terms = sorted(glossary, key=lambda t: len(t["de"]), reverse=True)
    for t in terms:
        de, zh = t["de"], t["zh"]
        if de in text:
            text = text.replace(de, zh)
    return text


def translate_one(source, glossary, cache, sl="de", tl="zh-CN"):
    if source in cache:
        return cache[source]

    if not source.strip():
        cache[source] = source
        return source

    masked, mapping = protect(source, glossary)
    try:
        translated = gt_translate(masked, sl=sl, tl=tl)
    except Exception as exc:
        raise RuntimeError("translate failed: %s" % exc)

    translated = restore(translated, mapping)
    # Entities that survived: decode only when the source carried no tags,
    # so HTML documents keep their exact markup.
    if not TAG_RE.search(source):
        translated = html.unescape(translated)

    cache[source] = translated
    return translated


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--sleep", type=float, default=0.25)
    ap.add_argument("--retries", type=int, default=3)
    args = ap.parse_args()

    strings = load_json(os.path.join(DATA, "strings.json"), [])
    glossary = load_json(os.path.join(DATA, "glossary.json"), {}).get("terms", [])
    cache_path = os.path.join(DATA, "translation-cache.json")
    cache = load_json(cache_path, {})

    # Unique source strings only -- avoids paying twice for duplicate UI text.
    unique = []
    seen = set()
    for s in strings:
        src = s["source_de"]
        if src and src not in seen:
            seen.add(src)
            unique.append(src)

    todo = [u for u in unique if u not in cache]
    print("total entries   : %d" % len(strings))
    print("unique sources  : %d" % len(unique))
    print("already cached  : %d" % len(cache))
    print("to translate    : %d" % len(todo))

    if args.limit:
        todo = todo[:args.limit]

    ok = 0
    failed = []
    start = time.time()

    for i, src in enumerate(todo, 1):
        for attempt in range(1, args.retries + 1):
            try:
                translate_one(src, glossary, cache)
                ok += 1
                break
            except Exception as exc:
                if attempt == args.retries:
                    failed.append({"source": src, "error": str(exc)})
                else:
                    time.sleep(1.5 * attempt)

        if i % 25 == 0 or i == len(todo):
            save_json(cache_path, cache)
            elapsed = time.time() - start
            rate = i / elapsed if elapsed else 0
            eta = (len(todo) - i) / rate if rate else 0
            print("  %d/%d  ok=%d fail=%d  %.1f/s  eta %.0fs"
                  % (i, len(todo), ok, len(failed), rate, eta))

        if args.sleep:
            time.sleep(args.sleep)

    save_json(cache_path, cache)
    if failed:
        save_json(os.path.join(DATA, "translate-failures.json"), failed)

    print("\nDONE  translated=%d  failed=%d  cache=%d"
          % (ok, len(failed), len(cache)))


if __name__ == "__main__":
    main()

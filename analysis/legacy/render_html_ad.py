#!/usr/bin/env python3
"""
render_ad.py — Render Meta ad-collector JSON exports as self-contained HTML pages.

Layout: media on the left, unique cards on the right.
A card is "unique" by (card_body, card_caption, card_title, card_link_domain).
Exact-duplicate media binaries (same hash) are shown once and noted.

Usage:
    python render_ad.py exports/ad_1320176539661608.json
    python render_ad.py exports/ad_1320176539661608.json -o report.html
    python render_ad.py exports/ -o html_reports/      # batch: every *.json
"""
from __future__ import annotations

import argparse
import base64
import binascii
import html
import json
import sys
from pathlib import Path

UNIQUE_FIELDS = ("card_body", "card_caption", "card_title", "card_link_domain")

EXT_MAP = {
    "jpg": ("image/jpeg", "image"), "jpeg": ("image/jpeg", "image"),
    "png": ("image/png", "image"), "gif": ("image/gif", "image"),
    "webp": ("image/webp", "image"), "bmp": ("image/bmp", "image"),
    "svg": ("image/svg+xml", "image"),
    "mp4": ("video/mp4", "video"), "m4v": ("video/mp4", "video"),
    "mov": ("video/quicktime", "video"), "webm": ("video/webm", "video"),
    "mkv": ("video/x-matroska", "video"), "avi": ("video/x-msvideo", "video"),
}


def esc(v) -> str:
    return html.escape("" if v is None else str(v), quote=True)


def human_size(n) -> str:
    try:
        n = float(n)
    except (TypeError, ValueError):
        return "? B"
    for unit in ("B", "KB", "MB", "GB"):
        if n < 1024 or unit == "GB":
            return f"{n:.0f} {unit}" if unit == "B" else f"{n:.1f} {unit}"
        n /= 1024
    return f"{n:.1f} GB"


def sniff_media(b64: str, ext: str) -> tuple[str, str]:
    """Return (mime_type, kind) with kind in {image, video, file}."""
    raw = b""
    head = "".join(b64[:80].split())
    head += "=" * ((-len(head)) % 4)
    try:
        raw = base64.b64decode(head)
    except binascii.Error:
        pass
    if raw[:3] == b"\xff\xd8\xff":                        return "image/jpeg", "image"
    if raw[:8] == b"\x89PNG\r\n\x1a\n":                   return "image/png", "image"
    if raw[:6] in (b"GIF87a", b"GIF89a"):                 return "image/gif", "image"
    if raw[:4] == b"RIFF" and raw[8:12] == b"WEBP":       return "image/webp", "image"
    if raw[:4] == b"\x1a\x45\xdf\xa3":                    return "video/webm", "video"
    if raw[4:8] == b"ftyp":
        return ("video/quicktime", "video") if raw[8:12] == b"qt  " else ("video/mp4", "video")
    return EXT_MAP.get((ext or "").lower(), ("application/octet-stream", "file"))


def data_uri(b64: str, mime: str) -> str:
    if b64.startswith("data:"):
        return b64.strip()
    return f"data:{mime};base64,{''.join(b64.split())}"


def group_cards(cards: list[dict]) -> list[dict]:
    """Group cards by uniqueness key, preserving first-seen order."""
    groups, seen = [], {}
    for card in cards:
        key = tuple(card.get(f) for f in UNIQUE_FIELDS)
        if key in seen:
            groups[seen[key]]["indices"].append(card.get("card_index"))
        else:
            seen[key] = len(groups)
            groups.append({"card": card, "indices": [card.get("card_index")]})
    return groups


def dedupe_media(media: list[dict]) -> list[dict]:
    """Collapse binaries with identical hashes; only annotation is kept."""
    out, seen = [], {}
    for pos, m in enumerate(media):
        key = m.get("hash") or m.get("data_base64") or object()
        if key in seen:
            out[seen[key]]["dup_of"].append(pos)
        else:
            seen[key] = len(out)
            out.append({**m, "_pos": pos, "dup_of": []})
    return out


def render_media(media: list[dict], total_entries: int) -> str:
    if not media:
        return '<p class="empty">No media collected for this ad.</p>'
    parts = []
    for m in media:
        b64 = m.get("data_base64") or ""
        ext = m.get("media_format") or ""
        name = m.get("url_filename") or f"media_{m['_pos']}"
        mime, kind = sniff_media(b64, ext)
        uri = data_uri(b64, mime)
        if kind == "image":
            preview = f'<img loading="lazy" src="{uri}" alt="{esc(name)}">'
        elif kind == "video":
            preview = f'<video controls preload="metadata" src="{uri}"></video>'
        else:
            preview = (f'<a class="filedl" href="{uri}" download="{esc(name)}">'
                       f"⬇ download ({esc(ext or 'bin')})</a>")
        dup_note = ""
        if m["dup_of"]:
            dups = ", ".join(str(p) for p in m["dup_of"])
            dup_note = f'<span class="mmeta dup">+{len(m["dup_of"])} identical (entries {dups})</span>'
        parts.append(
            f'<figure class="media">{preview}'
            f"<figcaption>"
            f'<span class="mname" title="{esc(name)}">{esc(name)}</span>'
            f'<span class="mmeta">#{m["_pos"]} · {esc(ext)} · {human_size(m.get("size_bytes"))}'
            f' · hash:{esc((m.get("hash") or "")[:12])}…</span>'
            f"{dup_note}"
            f"</figcaption></figure>"
        )
    return "".join(parts)


def render_card(group: dict, num: int) -> str:
    c = group["card"]
    idxs = group["indices"]
    idx_str = ", ".join("?" if i is None else str(i) for i in idxs)
    dup_badge = ""
    card_cls = "ucard"
    if len(idxs) > 1:
        card_cls += " has-dups"
        dup_badge = (f'<span class="badge dup">×{len(idxs)} identical versions '
                     f"(card_index {idx_str})</span>")
    else:
        dup_badge = f'<span class="badge">card_index {idx_str}</span>'

    title = esc(c.get("card_title")) or '<span class="na">(no title)</span>'
    caption = esc(c.get("card_caption")) or '<span class="na">(no caption)</span>'
    body = c.get("card_body")
    body_html = (f'<p class="body">{esc(body)}</p>' if body
                 else '<p class="body na">(no body)</p>')

    link_bits = []
    url = c.get("card_link_url")
    if url:
        shown = url if len(url) <= 150 else url[:147] + "…"
        link_bits.append(
            f'<div class="row"><span class="k">link</span>'
            f'<a class="url" href="{esc(url)}" title="{esc(url)}" '
            f'target="_blank" rel="noopener noreferrer">{esc(shown)}</a></div>')
    if c.get("card_link_description"):
        link_bits.append(f'<div class="row"><span class="k">link desc</span>'
                         f'{esc(c.get("card_link_description"))}</div>')

    cta = c.get("card_cta_text") or c.get("card_cta_type")
    cta_html = f'<span class="cta">{esc(cta)}</span>' if cta else ""

    flags = []
    if c.get("card_has_video"):
        flags.append("🎬 video")
    if c.get("card_has_image"):
        flags.append("🖼 image")

    return (
        f'<article class="{card_cls}">'
        f'<header><span class="cnum">{num}</span>'
        f'<span class="ctitle">{title}</span>{dup_badge}</header>'
        f'<div class="row"><span class="k">caption</span>{caption} {cta_html}'
        f'{" ".join(flags)}</div>'
        f"{body_html}"
        f'<div class="row"><span class="k">domain</span>'
        f'<code>{esc(c.get("card_link_domain"))}</code></div>'
        f'{"".join(link_bits)}'
        f"</article>"
    )


CSS = """
:root{--border:#dfe1e6;--bg:#eef0f3;--ink:#1c1e21;--mut:#65676b;--acc:#d73502}
*{box-sizing:border-box}
html,body{height:100%}
body{margin:0;display:flex;flex-direction:column;font:14px/1.5 system-ui,-apple-system,"Segoe UI",Roboto,sans-serif;background:var(--bg);color:var(--ink)}
>header{} /* placeholder removed */
header.top{display:flex;flex-wrap:wrap;gap:8px 24px;align-items:baseline;padding:10px 18px;background:#1c1e21;color:#fff;box-shadow:0 1px 4px rgba(0,0,0,.3)}
header.top strong{font-size:16px}
header.top .sub,.header-sub{color:#b9bec7;font-size:12px}
.chips{display:flex;gap:8px;flex-wrap:wrap;margin-left:auto}
.chip{background:#3a3b3c;border-radius:12px;padding:2px 10px;font-size:12px;white-space:nowrap}
main{flex:1;min-height:0;display:grid;grid-template-columns:minmax(300px,42%) 1fr;gap:14px;padding:14px}
.col{overflow-y:auto;min-width:0;padding-right:4px}
h2{font-size:13px;text-transform:uppercase;letter-spacing:.08em;color:var(--mut);margin:2px 0 10px}
.mgrid{display:grid;grid-template-columns:repeat(auto-fill,minmax(200px,1fr));gap:10px}
figure.media{margin:0;background:#fff;border:1px solid var(--border);border-radius:8px;overflow:hidden}
figure.media img,figure.media video{display:block;width:100%;background:#222}
figcaption{padding:6px 8px;display:flex;flex-direction:column;gap:2px}
.mname{font-size:11px;font-weight:600;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.mmeta{font-size:10px;color:var(--mut);font-family:ui-monospace,monospace}
.dup{color:var(--acc)}
.filedl{display:block;padding:24px;text-align:center;color:var(--acc)}
.ucard{background:#fff;border:1px solid var(--border);border-radius:10px;padding:12px 14px;margin-bottom:12px}
.ucard.has-dups{border-left:4px solid #f7b928}
.ucard>header{display:flex;align-items:baseline;gap:8px;flex-wrap:wrap;margin-bottom:4px}
.cnum{background:#1c1e21;color:#fff;border-radius:6px;font-size:11px;padding:1px 7px;font-family:ui-monospace,monospace}
.ctitle{font-weight:700;font-size:15px}
.badge{font-size:11px;color:var(--mut)}
.badge.dup{color:#8a5a00;background:#fdf0d5;border-radius:10px;padding:1px 8px}
.row{font-size:12px;color:var(--mut);margin:3px 0;display:flex;gap:6px;flex-wrap:wrap;align-items:baseline}
.row .k{font-size:10px;text-transform:uppercase;letter-spacing:.06em;color:#9a9ea6;flex:0 0 auto;min-width:56px}
.cta{background:#e7f3ff;color:#1877f2;border-radius:10px;padding:0 8px;font-size:11px}
p.body{white-space:pre-wrap;word-break:break-word;margin:8px 0;font-size:13px;color:#303236}
.na{color:#9a9ea6;font-style:italic}
.url{word-break:break-all;color:#1877f2;font-size:11px}
code{background:#f0f2f5;padding:1px 6px;border-radius:4px;font-size:11px}
.empty{color:var(--mut);font-style:italic}
"""


def render_ad_html(data: dict, source_name: str) -> tuple[str, str]:
    ad_id = data.get("ad_archive_id", "?")
    adv = data.get("advertiser") or {}
    creative = data.get("creative") or {}
    cards = data.get("cards") or []
    media = data.get("media") or []
    skipped = data.get("media_skipped") or []

    groups = group_cards(cards)
    umedia = dedupe_media(media)
    n_dup_media = len(media) - len(umedia)
    n_dup_cards = len(cards) - len(groups)

    media_html = render_media(umedia, len(media))
    cards_html = "".join(render_card(g, i + 1) for i, g in enumerate(groups)) \
        or '<p class="empty">No cards.</p>'

    creative_bits = " · ".join(
        f"{esc(k)}: {esc(v)}" for k, v in
        (("caption", creative.get("caption")),
         ("cta", creative.get("cta_text")),
         ("domain", creative.get("link_domain")))
        if v)

    dup_media_note = f" +{n_dup_media} dup hidden" if n_dup_media else ""
    chips = (
        f'<span class="chip">{len(umedia)} media{dup_media_note}</span>'
        f'<span class="chip">{len(groups)} unique cards / {len(cards)} total'
        f' ({n_dup_cards} dupes merged)</span>'
        + (f'<span class="chip">⚠ {len(skipped)} media skipped</span>' if skipped else "")
    )

    doc = (
        "<!DOCTYPE html>\n<html lang=\"en\">\n<head>\n<meta charset=\"utf-8\">"
        '<meta name="viewport" content="width=device-width,initial-scale=1">'
        f"<title>Ad {esc(ad_id)} — {esc(source_name)}</title>"
        f"<style>{CSS}</style>\n</head>\n<body>"
        f'<header class="top"><strong>Ad {esc(ad_id)}</strong>'
        f'<span class="sub">{esc(adv.get("page_name") or "?")}'
        f' · {esc(data.get("display_format") or "?")}'
        f' · collected {esc(data.get("collected_at") or "?")}'
        + (f' · <span class="header-sub">{creative_bits}</span>' if creative_bits else "")
        + f"</span>"
        f'<span class="chips">{chips}</span></header>'
        f"<main>"
        f'<section class="col"><h2>Media</h2><div class="mgrid">{media_html}</div></section>'
        f'<section class="col"><h2>Unique cards '
        f"(dedup on {esc(', '.join(UNIQUE_FIELDS))})</h2>{cards_html}</section>"
        f"</main></body>\n</html>"
    )
    stats = (f"{len(umedia)}/{len(media)} media, "
             f"{len(groups)}/{len(cards)} unique cards, {len(skipped)} skipped")
    return doc, stats


def process(jf: Path, out: Path) -> None:
    data = json.loads(jf.read_text(encoding="utf-8"))
    doc, stats = render_ad_html(data, jf.name)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(doc, encoding="utf-8")
    print(f"  ✓ {jf.name} → {out}  [{stats}]")


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("input", type=Path, help="JSON export file, or directory of exports")
    ap.add_argument("-o", "--output", type=Path, default=None,
                    help="Output .html file (or directory when input is a directory)")
    args = ap.parse_args(argv)

    if not args.input.exists():
        ap.error(f"no such file or directory: {args.input}")

    if args.input.is_dir():
        out_dir = args.output or args.input.with_name(args.input.name + "_html")
        out_dir.mkdir(parents=True, exist_ok=True)
        ok = fail = 0
        for jf in sorted(args.input.glob("*.json")):
            try:
                process(jf, out_dir / (jf.stem + ".html"))
                ok += 1
            except Exception as e:  # keep batch going on a single bad file
                fail += 1
                print(f"  ✗ {jf.name}: {e}", file=sys.stderr)
        print(f"done: {ok} rendered, {fail} failed → {out_dir}")
    else:
        out = args.output or args.input.with_suffix(".html")
        if out.is_dir():
            out = out / (args.input.stem + ".html")
        process(args.input, out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
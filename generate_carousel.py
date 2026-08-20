#!/usr/bin/env python3
"""
generate_carousel.py — Solid Safety LinkedIn carousel generator

Renders the "SolidSafety Carousel" Claude Design template to a print-ready
PDF (each page = one swipeable slide) plus individual PNGs.

    python generate_carousel.py slides.txt --out zarazeni_objektu

Slide script: blocks separated by a line containing only ///
Each block starts with a layout tag, then key: value lines and - items.

    [cover]      eyebrow, title, sub
    [list]       eyebrow, title, - Heading :: description   (2-4 items)
    [stat]       eyebrow, number, lead, note
    [compare]    eyebrow, title, left: LABEL + items, right: LABEL + items, note
    [table]      eyebrow, title, cols: A | B | C, row: x | y | z, note
    [outro]      eyebrow, title, sub   (all optional — defaults below)

The outro slide is appended automatically if the script doesn't end with one,
so the closing CTA is identical on every carousel.

Assets expected next to this script (or set ASSET_DIR / FONT_DIR):
    bg.jpg, portrait.jpg, fonts/SourceSerif4-{400,600,700}.ttf,
    fonts/Archivo-{400,600,800}.ttf
"""

import argparse
import math
import os
import sys

import numpy as np
from PIL import Image, ImageDraw, ImageEnhance, ImageFont

# ---------------------------------------------------------------- tokens

W, H = 1080, 1350
PAD = 72

BG_DARK = (13, 13, 13)          # #0d0d0d
BG_LIGHT = (243, 242, 242)      # #f3f2f2
INK = (32, 30, 29)              # #201e1d
MUTED_INK = (74, 70, 69)        # #4a4645
ACCENT = (236, 48, 19)          # #ec3013
ON_DARK = (255, 255, 255)
ON_DARK_SUB = (220, 217, 215)   # #dcd9d7
ON_DARK_MUTE = (185, 181, 178)  # #b9b5b2
DIVIDER = (32, 30, 29, 89)      # #201e1d @ 35%
RULE_ON_DARK = (255, 255, 255, 102)

ASSET_DIR = ""
FONT_DIR = "fonts"
BG_IMAGE = "bg.jpg"
PORTRAIT = "portrait.jpg"

BRAND = "SOLID SAFETY"
SITE = "solidsafety.cz"
SWIPE = "Listujte →"
NAME = "Radek Morávek"
ROLE = "Solid Safety · HSE konzultant"

# Closing slide — same on every carousel unless the script overrides it.
OUTRO_EYEBROW = "Ukázka nástroje"
OUTRO_TITLE = "Zařazení objektu spočítá nástroj, ne tabulka v Excelu."
OUTRO_SUB = ("Napište mi zprávu a pošlu ukázku nástroje, "
             "který výpočet zařazení objektu provede za vás.")

SERIF = {400: "SourceSerif4-400.ttf", 600: "SourceSerif4-600.ttf",
         700: "SourceSerif4-700.ttf"}
SANS = {400: "Archivo-400.ttf", 600: "Archivo-600.ttf",
        800: "Archivo-800.ttf"}

_font_cache = {}


def serif(size, weight=400):
    return _load(SERIF[weight], size)


def sans(size, weight=400):
    return _load(SANS[weight], size)


def _load(name, size):
    key = (name, size)
    if key not in _font_cache:
        path = os.path.join(FONT_DIR, name) if FONT_DIR else name
        if not os.path.exists(path):
            path = name
        _font_cache[key] = ImageFont.truetype(path, size)
    return _font_cache[key]


def asset(name):
    return os.path.join(ASSET_DIR, name) if ASSET_DIR else name


# ---------------------------------------------------------------- text

def measure(d, s, f, tracking=0.0):
    if not s:
        return 0
    w = d.textbbox((0, 0), s, font=f)[2]
    return w + tracking * (len(s) - 1) if tracking else w


def write(d, xy, s, f, fill, tracking=0.0):
    """Draw text with optional letter-spacing. Returns the x cursor."""
    x, y = xy
    if not tracking:
        d.text((x, y), s, font=f, fill=fill)
        return x + measure(d, s, f)
    for ch in s:
        d.text((x, y), ch, font=f, fill=fill)
        x += d.textbbox((0, 0), ch, font=f)[2] + tracking
    return x - tracking


def wrap(d, text, f, max_w, tracking=0.0):
    lines, cur = [], ""
    for word in text.split():
        trial = f"{cur} {word}".strip()
        if measure(d, trial, f, tracking) <= max_w or not cur:
            cur = trial
        else:
            lines.append(cur)
            cur = word
    if cur:
        lines.append(cur)
    return lines


def para(d, xy, text, f, fill, max_w, line_height, tracking=0.0):
    """Draw a wrapped paragraph. Returns the y after the last line."""
    x, y = xy
    for line in wrap(d, text, f, max_w, tracking):
        write(d, (x, y), line, f, fill, tracking)
        y += line_height
    return y


def para_h(d, text, f, max_w, line_height, tracking=0.0):
    return len(wrap(d, text, f, max_w, tracking)) * line_height


def cap_height(f):
    """Rough visual top offset — Pillow draws from the ascender."""
    return f.getbbox("H")[1]


# ---------------------------------------------------------------- chrome

def hairline(img, box, rgba):
    layer = Image.new("RGBA", img.size, (0, 0, 0, 0))
    ImageDraw.Draw(layer).rectangle(box, fill=rgba)
    img.alpha_composite(layer)


def photo_bg(object_x=0.5, brightness=0.70, stops=None):
    """bg.jpg with the CSS filter chain and the 100deg ink gradient."""
    base = Image.new("RGB", (W, H), BG_DARK)
    path = asset(BG_IMAGE)
    if os.path.exists(path):
        img = Image.open(path).convert("RGB")
        ratio = max(W / img.width, H / img.height)
        img = img.resize((max(W, int(img.width * ratio)),
                          max(H, int(img.height * ratio))), Image.LANCZOS)
        left = int((img.width - W) * object_x)
        top = (img.height - H) // 2
        base = img.crop((left, top, left + W, top + H))
        base = ImageEnhance.Color(base).enhance(0.55)
        base = ImageEnhance.Brightness(base).enhance(brightness)
        base = ImageEnhance.Contrast(base).enhance(1.05)

    # linear-gradient(100deg, ...) — direction vector for CSS angles
    stops = stops or [(0.00, 0.97), (0.38, 0.92), (0.72, 0.45), (1.00, 0.12)]
    rad = math.radians(100)
    dx, dy = math.sin(rad), -math.cos(rad)
    length = abs(W * dx) + abs(H * dy)
    xs = np.arange(W)[None, :]
    ys = np.arange(H)[:, None]
    t = ((xs - W / 2) * dx + (ys - H / 2) * dy) / length + 0.5
    t = np.clip(t, 0, 1)

    pos = np.array([s[0] for s in stops])
    val = np.array([s[1] for s in stops])
    alpha = np.interp(t, pos, val)

    arr = np.asarray(base).astype(np.float32)
    ink = np.array(BG_DARK, dtype=np.float32)
    out = arr * (1 - alpha[..., None]) + ink * alpha[..., None]
    return Image.fromarray(out.astype(np.uint8)).convert("RGBA")


def circle_portrait(size, object_y=0.22):
    path = asset(PORTRAIT)
    if not os.path.exists(path):
        return None
    img = Image.open(path).convert("RGB")
    ratio = max(size / img.width, size / img.height)
    img = img.resize((max(size, int(img.width * ratio)),
                      max(size, int(img.height * ratio))), Image.LANCZOS)
    left = (img.width - size) // 2
    top = int((img.height - size) * object_y)
    img = img.crop((left, top, left + size, top + size))
    mask = Image.new("L", (size * 4, size * 4), 0)
    ImageDraw.Draw(mask).ellipse((0, 0, size * 4 - 1, size * 4 - 1), fill=255)
    mask = mask.resize((size, size), Image.LANCZOS)
    out = Image.new("RGBA", (size, size))
    out.paste(img, (0, 0), mask)
    return out


def eyebrow(d, y, text, color=ACCENT):
    f = sans(25, 800)
    write(d, (PAD, y), text.upper(), f, color, tracking=25 * 0.16)
    return y + 25 + 6


def footer_light(img, d, index, total):
    f = sans(27, 800)
    y = H - PAD - 27
    write(d, (PAD, y), BRAND, f, INK, tracking=27 * 0.08)
    label = f"{index:02d} / {total:02d}"
    write(d, (W - PAD - measure(d, label, f), y), label, f, INK)
    return y


def footer_dark(img, d, index, total, right_accent=False):
    f_brand = sans(31, 800)
    f_site = sans(27, 400)
    bottom = H - PAD
    y_site = bottom - 27
    y_brand = y_site - 8 - 31
    hairline(img, (PAD, y_brand - 32, W - PAD, y_brand - 31), RULE_ON_DARK)
    write(d, (PAD, y_brand), BRAND, f_brand, ON_DARK, tracking=31 * 0.08)
    write(d, (PAD, y_site), SITE, f_site, ON_DARK_MUTE)
    if right_accent:
        f = sans(26, 800)
        w = measure(d, SWIPE.upper(), f, 26 * 0.14)
        write(d, (W - PAD - w, y_site), SWIPE.upper(), f, ACCENT, tracking=26 * 0.14)
    else:
        f = sans(27, 800)
        label = f"{index:02d} / {total:02d}"
        write(d, (W - PAD - measure(d, label, f), y_site), label, f, ON_DARK)
    return y_brand - 32


# ---------------------------------------------------------------- layouts

def render_cover(s, index, total):
    img = photo_bg()
    d = ImageDraw.Draw(img)
    top_limit = footer_dark(img, d, index, total, right_accent=True)

    f_eb = sans(25, 800)
    f_h1 = serif(88, 700)
    f_sub = serif(38, 400)
    tr_h = -88 * 0.015

    title = s.get("title", "")
    sub = s.get("sub", "")
    h_title = para_h(d, title, f_h1, 800, int(88 * 1.09), tr_h)
    h_sub = para_h(d, sub, f_sub, 720, int(38 * 1.38)) if sub else 0
    block = 25 + 44 + h_title + (44 + h_sub if sub else 0)

    y = PAD + (top_limit - PAD - block) // 2
    write(d, (PAD, y), s.get("eyebrow", "").upper(), f_eb, ACCENT, tracking=25 * 0.16)
    y += 25 + 44
    y = para(d, (PAD, y), title, f_h1, ON_DARK, 800, int(88 * 1.09), tr_h)
    if sub:
        y += 44
        para(d, (PAD, y), sub, f_sub, ON_DARK_SUB, 720, int(38 * 1.38))
    return img


def render_list(s, index, total):
    img = Image.new("RGBA", (W, H), BG_LIGHT + (255,))
    d = ImageDraw.Draw(img)
    footer_light(img, d, index, total)

    y = eyebrow(d, PAD, s.get("eyebrow", ""))
    y += 26
    f_h2 = serif(72, 700)
    y = para(d, (PAD, y), s.get("title", ""), f_h2, INK, 936, int(72 * 1.08), -72 * 0.015)
    y += 48

    items = s.all_items()
    d.rectangle((PAD, y, W - PAD, y + 1), fill=INK)
    y += 2

    f_num = sans(46, 800)
    f_h3 = sans(40, 800)
    f_p = serif(31, 400)
    for i, item in enumerate(items, start=1):
        head, _, body = item.partition("::")
        y += 36
        write(d, (PAD, y), f"{i:02d}", f_num, ACCENT)
        col_x = PAD + 76 + 36
        col_w = W - PAD - col_x
        yy = para(d, (col_x, y), head.strip(), f_h3, INK, col_w, int(40 * 1.18))
        if body.strip():
            yy += 10
            yy = para(d, (col_x, yy), body.strip(), f_p, MUTED_INK, col_w, int(31 * 1.4))
        y = max(y + 46, yy) + 36
        if i == len(items):
            d.rectangle((PAD, y, W - PAD, y + 1), fill=INK)
        else:
            hairline(img, (PAD, y, W - PAD, y), DIVIDER)
        y += 2
    return img


def render_stat(s, index, total):
    img = Image.new("RGBA", (W, H), BG_LIGHT + (255,))
    d = ImageDraw.Draw(img)
    top_limit = footer_light(img, d, index, total)

    y0 = eyebrow(d, PAD, s.get("eyebrow", ""))

    number = s.get("number", "")
    lead = s.get("lead", "")
    note = s.get("note", "")

    size = 300
    f_num = sans(size, 800)
    while measure(d, number, f_num, -size * 0.05) > 936 and size > 120:
        size -= 10
        f_num = sans(size, 800)
    tr_n = -size * 0.05

    f_lead = serif(46, 400)
    f_note = serif(31, 400)
    h_num = int(size * 0.82)
    h_lead = para_h(d, lead, f_lead, 860, int(46 * 1.28))
    h_note = para_h(d, note, f_note, 800, int(31 * 1.4)) if note else 0
    block = h_num + 32 + h_lead + 32 + 2 + (32 + h_note if note else 0)

    y = y0 + 20 + max(0, (top_limit - 40 - (y0 + 20) - block) // 2)
    write(d, (PAD, y - cap_height(f_num) + int(size * 0.06)), number, f_num, ACCENT, tr_n)
    y += h_num + 32
    y = para(d, (PAD, y), lead, f_lead, INK, 860, int(46 * 1.28))
    y += 32
    d.rectangle((PAD, y, W - PAD, y + 1), fill=INK)
    y += 2
    if note:
        y += 32
        para(d, (PAD, y), note, f_note, MUTED_INK, 800, int(31 * 1.4))
    return img


def render_compare(s, index, total):
    img = Image.new("RGBA", (W, H), BG_LIGHT + (255,))
    d = ImageDraw.Draw(img)
    footer_light(img, d, index, total)

    y = eyebrow(d, PAD, s.get("eyebrow", ""))
    y += 26
    y = para(d, (PAD, y), s.get("title", ""), serif(72, 700), INK, 936,
             int(72 * 1.08), -72 * 0.015)
    y += 48

    d.rectangle((PAD, y, W - PAD, y + 1), fill=INK)
    grid_top = y + 2

    mid = W // 2
    col_w = mid - PAD - 36
    f_label = sans(25, 800)
    f_item = serif(32, 400)

    def column(x, key, label_color):
        yy = grid_top + 44
        write(d, (x, yy), s.get(key, "").upper(), f_label, label_color,
              tracking=25 * 0.14)
        yy += 25 + 26
        for item in s.items_for(key):
            yy = para(d, (x, yy), item, f_item, INK, col_w, int(32 * 1.36))
            yy += 26
        return yy - 26 + 44

    bottom = max(column(PAD, "left", MUTED_INK), column(mid + 36, "right", ACCENT))
    hairline(img, (mid, grid_top, mid, bottom), DIVIDER)
    d.rectangle((PAD, bottom, W - PAD, bottom + 1), fill=INK)

    note = s.get("note", "")
    if note:
        para(d, (PAD, bottom + 42), note, serif(31, 400), MUTED_INK, 860, int(31 * 1.4))
    return img


def render_table(s, index, total):
    img = Image.new("RGBA", (W, H), BG_LIGHT + (255,))
    d = ImageDraw.Draw(img)
    footer_light(img, d, index, total)

    y = eyebrow(d, PAD, s.get("eyebrow", ""))
    y += 26
    y = para(d, (PAD, y), s.get("title", ""), serif(72, 700), INK, 936,
             int(72 * 1.08), -72 * 0.015)
    y += 48

    fr = [1.5, 1.0, 0.9]
    inner = W - 2 * PAD
    widths = [inner * f / sum(fr) for f in fr]
    xs, acc = [], PAD
    for w in widths:
        xs.append(acc)
        acc += w
    pads = [(0, 20), (20, 20), (20, 0)]

    cols = [c.strip() for c in s.get("cols", "").split("|")]
    rows = [[c.strip() for c in r.split("|")] for r in s.get_all("row")]

    d.rectangle((PAD, y, W - PAD, y + 1), fill=INK)
    y += 2

    f_head = sans(25, 800)
    y += 24
    for i, label in enumerate(cols[:3]):
        write(d, (xs[i] + pads[i][0], y), label.upper(), f_head, INK, tracking=25 * 0.10)
    y += 25 + 24
    d.rectangle((PAD, y, W - PAD, y + 1), fill=INK)
    y += 2

    f_cell = sans(30, 400)
    for n, row in enumerate(rows, start=1):
        y += 28
        rh = 0
        for i, cell in enumerate(row[:3]):
            cw = widths[i] - pads[i][0] - pads[i][1]
            yy = para(d, (xs[i] + pads[i][0], y), cell, f_cell, INK, cw, int(30 * 1.35))
            rh = max(rh, yy - y)
        y += max(rh, 30 * 1.35)
        y += 28
        if n == len(rows):
            d.rectangle((PAD, y, W - PAD, y + 1), fill=INK)
        else:
            hairline(img, (PAD, y, W - PAD, y), DIVIDER)
        y += 2

    note = s.get("note", "")
    if note:
        para(d, (PAD, y + 36), note, serif(29, 400), MUTED_INK, 936, int(29 * 1.4))
    return img


def render_outro(s, index, total):
    img = photo_bg(object_x=0.70, brightness=0.62,
                   stops=[(0.0, 0.97), (0.40, 0.93), (0.78, 0.55), (1.0, 0.20)])
    d = ImageDraw.Draw(img)
    top_limit = footer_dark(img, d, index, total)

    av_size = 104
    av = circle_portrait(av_size)
    if av:
        img.alpha_composite(av, (PAD, PAD))
    ring = Image.new("RGBA", img.size, (0, 0, 0, 0))
    ImageDraw.Draw(ring).ellipse((PAD, PAD, PAD + av_size, PAD + av_size),
                                outline=RULE_ON_DARK, width=2)
    img.alpha_composite(ring)

    f_name = sans(40, 800)
    f_role = sans(29, 400)
    tx = PAD + av_size + 28
    ty = PAD + (av_size - (40 + 6 + 29)) // 2
    write(d, (tx, ty), NAME, f_name, ON_DARK, tracking=-40 * 0.01)
    write(d, (tx, ty + 40 + 6), ROLE, f_role, ON_DARK_MUTE)
    head_bottom = PAD + av_size

    f_eb = sans(25, 800)
    f_h2 = serif(80, 700)
    f_sub = serif(36, 400)
    title = s.get("title", OUTRO_TITLE)
    sub = s.get("sub", OUTRO_SUB)
    h_title = para_h(d, title, f_h2, 820, int(80 * 1.09), -80 * 0.015)
    h_sub = para_h(d, sub, f_sub, 760, int(36 * 1.38)) if sub else 0
    block = 25 + 40 + h_title + (40 + h_sub if sub else 0)

    y = head_bottom + max(0, (top_limit - head_bottom - block) // 2)
    write(d, (PAD, y), s.get("eyebrow", OUTRO_EYEBROW).upper(), f_eb, ACCENT,
          tracking=25 * 0.16)
    y += 25 + 40
    y = para(d, (PAD, y), title, f_h2, ON_DARK, 820, int(80 * 1.09), -80 * 0.015)
    if sub:
        y += 40
        para(d, (PAD, y), sub, f_sub, ON_DARK_SUB, 760, int(36 * 1.38))
    return img


LAYOUTS = {"cover": render_cover, "list": render_list, "stat": render_stat,
           "compare": render_compare, "table": render_table, "outro": render_outro}


# ---------------------------------------------------------------- parsing

class Slide:
    def __init__(self, layout):
        self.layout = layout
        self.pairs = []          # (key, value)
        self.items = []          # (key_or_None, text)

    def get(self, key, default=""):
        for k, v in self.pairs:
            if k == key:
                return v
        return default

    def get_all(self, key):
        return [v for k, v in self.pairs if k == key]

    def items_for(self, key):
        return [t for k, t in self.items if k == key]

    def all_items(self):
        return [t for _, t in self.items]


def parse(raw):
    slides = []
    for block in raw.split("///"):
        lines = [l.strip() for l in block.strip().split("\n") if l.strip()]
        if not lines:
            continue
        if not (lines[0].startswith("[") and lines[0].endswith("]")):
            sys.exit(f"Slide must start with a layout tag, got: {lines[0]!r}")
        layout = lines.pop(0)[1:-1].strip().lower()
        if layout not in LAYOUTS:
            sys.exit(f"Unknown layout [{layout}] — use one of {', '.join(LAYOUTS)}")

        s = Slide(layout)
        current = None
        for line in lines:
            if line.startswith("- "):
                s.items.append((current, line[2:].strip()))
            elif ":" in line:
                k, _, v = line.partition(":")
                current = k.strip().lower()
                s.pairs.append((current, v.strip()))
            else:
                s.items.append((current, line))
        slides.append(s)
    return slides


# ---------------------------------------------------------------- main

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("script")
    ap.add_argument("--out", default="carousel")
    ap.add_argument("--no-png", action="store_true")
    ap.add_argument("--no-outro", action="store_true",
                    help="don't append the standard closing slide")
    args = ap.parse_args()

    with open(args.script, encoding="utf-8") as fh:
        slides = parse(fh.read())
    if not slides:
        sys.exit("No slides found — check the /// separators.")

    if not args.no_outro and slides[-1].layout != "outro":
        slides.append(Slide("outro"))

    total = len(slides)
    if total > 10:
        print(f"warning: {total} slides — 6 to 10 usually performs best")

    images = []
    for i, s in enumerate(slides, start=1):
        images.append(LAYOUTS[s.layout](s, i, total).convert("RGB"))

    pdf = f"{args.out}.pdf"
    images[0].save(pdf, save_all=True, append_images=images[1:], resolution=150.0)
    print(f"wrote {pdf}  ({total} slides)")

    if not args.no_png:
        outdir = f"{args.out}_png"
        os.makedirs(outdir, exist_ok=True)
        for i, im in enumerate(images, start=1):
            im.save(os.path.join(outdir, f"slide_{i:02d}.png"), quality=95)
        print(f"wrote {outdir}/slide_01..{total:02d}.png")


if __name__ == "__main__":
    main()

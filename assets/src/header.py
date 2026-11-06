#!/usr/bin/env python3
"""Подпись + строки в стиле терминала -> анимированный SVG для GitHub README.

pip install fonttools
python sigtrace.py sig.png                         # один раз: подпись -> signature.json
python fixsig.py signature.json -o signature.json  # чистка подписи
python header.py                                   # -> header.svg
python header.py --accent 3fb950 --out green.svg

Строки рисуются контурами глифов (как в hashrain.svg), а не <text>:
так текст не дрожит при переключении кадров.
"""
import argparse
import json
import random

# ---------------- настройки ----------------
LINES = [
    "backend · networking · infra",
    "TCP/TLS tunnels from scratch",
    "bypassing DPI on OpenWrt",
    "Rust + Flutter music client",
    "autocar analysis · Go + Postgres + ML",
]
W = 830
SIG_H = 430                     # высота подписи, px
SIG_TOP = 20
BG = "#000000"
BORDER = "#30363d"
ACCENT = "a371f7"               # свечение подписи, приглашение >
SIG_COLOR = "d2a8ff"            # подпись
SUB_COLOR = "ffffff"            # строки
SIG_STROKE = 4.2
SIGNATURE = "signature.json"
FONT_BOLD = "fonts/JetBrainsMono-Bold.ttf"
FONT_REG = "fonts/JetBrainsMono-Regular.ttf"
OUT = "header.svg"
SEED = 7
SUB_SIZE = 20
SUB_X = 120                    # левый край «>», px
SUB_Y = 356                    # базовая линия строк, px (под петлёй y)
LINE_TIME = 3.4                 # секунд на надпись
FRAME = 0.05                    # шаг расшифровки
DECODE, DISSOLVE = 10, 7        # кадров
SCRAMBLE = "&#%@$"              # символы расшифровки
# -------------------------------------------


def load_glyphs(path: str, chars: str) -> tuple[dict, int, int]:
    """-> ({символ: d контура}, unitsPerEm, ширина знака). Пробел не нужен."""
    from fontTools.pens.svgPathPen import SVGPathPen
    from fontTools.ttLib import TTFont

    font = TTFont(path)
    gs, cmap = font.getGlyphSet(), font.getBestCmap()
    out = {}
    for ch in set(chars) - {" "}:
        pen = SVGPathPen(gs)
        gs[cmap[ord(ch)]].draw(pen)
        out[ch] = pen.getCommands()
    return out, font["head"].unitsPerEm, font["hmtx"][cmap[ord("0")]][0]


def smooth(pts: list) -> str:
    """Catmull-Rom -> кубические Безье."""
    d = f"M{pts[0][0]:.1f} {pts[0][1]:.1f}"
    if len(pts) == 2:
        return d + f"L{pts[1][0]:.1f} {pts[1][1]:.1f}"
    for i in range(len(pts) - 1):
        p0, p1, p2 = pts[max(i - 1, 0)], pts[i], pts[i + 1]
        p3 = pts[min(i + 2, len(pts) - 1)]
        c1 = (p1[0] + (p2[0] - p0[0]) / 6, p1[1] + (p2[1] - p0[1]) / 6)
        c2 = (p2[0] - (p3[0] - p1[0]) / 6, p2[1] - (p3[1] - p1[1]) / 6)
        d += f"C{c1[0]:.1f} {c1[1]:.1f} {c2[0]:.1f} {c2[1]:.1f} {p2[0]:.1f} {p2[1]:.1f}"
    return d


def signature(path: str, top: float) -> tuple[list[tuple[str, float]], float]:
    """-> [(d, длина)], нижняя граница."""
    with open(path) as f:
        strokes = json.load(f)
    xs = [p[0] for s in strokes for p in s]
    ys = [p[1] for s in strokes for p in s]
    k = SIG_H / (max(ys) - min(ys))
    ox = (W - (max(xs) - min(xs)) * k) / 2 - min(xs) * k
    oy = top - min(ys) * k
    strokes = [[(x * k + ox, y * k + oy) for x, y in s] for s in strokes]
    out = []
    for s in strokes:  # порядок файла = порядок рисования
        length = sum(((a[0] - b[0]) ** 2 + (a[1] - b[1]) ** 2) ** 0.5 for a, b in zip(s, s[1:]))
        out.append((smooth(s), length))
    return out, top + SIG_H


def scramble(text: str, progress: float, rng: random.Random) -> str:
    n = round(len(text) * progress)
    return "".join(ch if i < n or ch == " " else rng.choice(SCRAMBLE) for i, ch in enumerate(text))


def gid(ch: str, bold: bool = False) -> str:
    return f"{'b' if bold else 'r'}{ord(ch):x}"


def sublines(rng: random.Random, upm: int, adv: int) -> str:
    """Кадры расшифровки — группы <use> глифов, видимость через SMIL discrete."""
    s = SUB_SIZE / upm
    cw = adv * s
    cycle = LINE_TIME * len(LINES)
    kt = lambda t: f"{min(max(t, 0) / cycle, 1):.6f}"
    dur = f'dur="{cycle:.2f}s" calcMode="discrete" repeatCount="indefinite"'
    place = lambda x: f'transform="translate({x:.2f} {SUB_Y}) scale({s:.5f} {-s:.5f})"'
    els = []

    def frame(text: str, x: float, t0: float, t1: float) -> None:
        uses = "".join(f'<use href="#{gid(ch)}" x="{i * adv}"/>' for i, ch in enumerate(text) if ch != " ")
        els.append(f'<g {place(x)} opacity="0">{uses}'
                   f'<animate attributeName="opacity" values="0;1;0" keyTimes="0;{kt(t0)};{kt(t1)}" {dur}/></g>')

    els.append(f'<g class="pr" {place(SUB_X)}><use href="#{gid(">", True)}"/></g>')
    x = SUB_X + 2 * cw
    for li, line in enumerate(LINES):
        t = li * LINE_TIME
        for i in range(DECODE):
            frame(scramble(line, i / DECODE, rng), x, t + i * FRAME, t + (i + 1) * FRAME)
        hold0 = t + DECODE * FRAME
        hold1 = t + LINE_TIME - DISSOLVE * FRAME  # рассыпание впритык к следующей строке, без пустых кадров
        frame(line, x, hold0, hold1)
        for i in range(DISSOLVE):
            p = (DISSOLVE - i - 1) / DISSOLVE
            frame(scramble(line, p, rng), x, hold1 + i * FRAME, hold1 + (i + 1) * FRAME)
        # курсор живёт всю строку и мигает
        end = hold1 + DISSOLVE * FRAME
        els.append(f'<g {place(x + len(line) * cw)} opacity="0">'
                   f'<animate attributeName="opacity" values="0;1;0" keyTimes="0;{kt(t)};{kt(end)}" {dur}/>'
                   f'<use href="#{gid("_")}"><animate attributeName="opacity" values="1;0" keyTimes="0;0.5" '
                   f'dur="0.66s" calcMode="discrete" repeatCount="indefinite"/></use></g>')
    return "\n".join(els)


def build(accent: str, sub_color: str, glyphs_reg=None, glyphs_bold=None) -> str:
    rng = random.Random(SEED)
    strokes, sig_bottom = signature(SIGNATURE, SIG_TOP)
    h = round(max(sig_bottom, SUB_Y + 8) + 22)

    chars = "".join(LINES) + SCRAMBLE + "_"
    reg, upm, adv = glyphs_reg or load_glyphs(FONT_REG, chars)
    bold, _, _ = glyphs_bold or load_glyphs(FONT_BOLD, ">")
    defs = [f'<path id="{gid(c)}" d="{d}"/>' for c, d in sorted(reg.items())]
    defs.append(f'<path id="{gid(">", True)}" d="{bold[">"]}"/>')

    sig_d = []
    t, draw_time = 0.3, 2.4
    total = sum(l for _, l in strokes)
    for d, l in strokes:
        dur = max(0.1, draw_time * l / total)
        sig_d.append(f'<path pathLength="1" d="{d}" style="animation-duration:{dur:.2f}s;animation-delay:{t:.2f}s"/>')
        t += dur + 0.05

    css = f"""
.sig path{{fill:none;stroke:#{SIG_COLOR};stroke-width:{SIG_STROKE};stroke-linecap:round;stroke-linejoin:round;
stroke-dasharray:1 2;stroke-dashoffset:0;animation:draw ease-in-out backwards}}
.sub{{fill:#{sub_color}}}
.pr{{fill:#{accent}}}
@keyframes draw{{from{{stroke-dashoffset:1}}to{{stroke-dashoffset:0}}}}
@media (prefers-reduced-motion:reduce){{.sig path{{animation:none!important}}}}
"""
    return f"""<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{h}" viewBox="0 0 {W} {h}">
<title>rypleshhh</title>
<style>{css}</style>
<defs>
  <filter id="glow" x="-20%" y="-20%" width="140%" height="140%">
    <feGaussianBlur in="SourceAlpha" stdDeviation="4" result="b"/>
    <feFlood flood-color="#{accent}" flood-opacity=".75"/>
    <feComposite in2="b" operator="in" result="g"/>
    <feMerge><feMergeNode in="g"/><feMergeNode in="SourceGraphic"/></feMerge></filter>
  {"".join(defs)}
</defs>
<rect x=".5" y=".5" width="{W - 1}" height="{h - 1}" rx="11.5" fill="{BG}" stroke="{BORDER}"/>
<g class="sig" filter="url(#glow)">
{"".join(sig_d)}
</g>
<g class="sub">
{sublines(rng, upm, adv)}
</g>
</svg>
"""


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--accent", default=ACCENT)
    ap.add_argument("--sub", default=SUB_COLOR)
    ap.add_argument("--out", default=OUT)
    args = ap.parse_args()
    svg = build(args.accent.lstrip("#"), args.sub.lstrip("#"))
    with open(args.out, "w", encoding="utf-8") as f:
        f.write(svg)
    print(f"{args.out}: {len(svg) // 1024} KB")


if __name__ == "__main__":
    main()

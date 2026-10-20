#!/usr/bin/env python3
"""Падающие решётки + надписи -> зацикленный GIF для GitHub README.

pip install pillow numpy
python hashrain.py                                   # Go cyan
python hashrain.py --accent 3fb950 --out green.gif   # один цвет
python hashrain.py --accent 3fb950 --accent2 a371f7  # градиент слева направо
"""
import argparse
import random
import numpy as np
from PIL import Image, ImageDraw, ImageFont, ImageFilter

# ---------------- настройки ----------------
TITLE = "rypleshhh"
LINES = [
    "backend · networking · infra",
    "TCP/TLS tunnels from scratch",
    "bypassing DPI on OpenWrt",
    "Rust + Flutter music client",
]
W, H = 830, 210                 # ширина под колонку README
BG = (13, 17, 23)               # фон тёмной темы GitHub
ACCENT = (0, 173, 216)          # цвет дождя и подписи (Go cyan)
ACCENT2 = None                  # второй цвет -> градиент по ширине, напр. (163, 113, 247)
SUB_COLOR = None                # цвет подписи, по умолчанию ACCENT
TITLE_COLOR = (230, 237, 243)
RAIN_CHARS = "#"                # можно "#$%&@01" для разнообразия
CELL = 16                       # размер ячейки дождя, px
FRAMES_PER_LINE = 36            # кадров на одну подпись
FRAME_MS = 55
FONT_BOLD = "fonts/JetBrainsMono-Bold.ttf"
FONT_REG = "fonts/JetBrainsMono-Regular.ttf"
OUT = "hashrain.gif"
SEED = 7
# -------------------------------------------

ap = argparse.ArgumentParser()
ap.add_argument("--accent"); ap.add_argument("--accent2"); ap.add_argument("--sub")
ap.add_argument("--out")
args = ap.parse_args()
hexrgb = lambda h: tuple(int(h.lstrip("#")[i:i + 2], 16) for i in (0, 2, 4))
if args.accent: ACCENT = hexrgb(args.accent)
if args.accent2: ACCENT2 = hexrgb(args.accent2)
if args.sub: SUB_COLOR = hexrgb(args.sub)
if args.out: OUT = args.out
SUB_COLOR = SUB_COLOR or ACCENT

random.seed(SEED)
N = FRAMES_PER_LINE * len(LINES)
cols, rows = W // CELL + 1, H // CELL + 1
f_rain = ImageFont.truetype(FONT_BOLD, CELL - 2)
f_title = ImageFont.truetype(FONT_BOLD, 50)
f_line = ImageFont.truetype(FONT_REG, 20)

# Колонки: период P и целое число проходов k за цикл -> GIF зацикливается без шва
drops = []
for c in range(cols):
    for _ in range(random.choice([1, 2, 2])):
        trail = random.randint(5, 13)
        P = rows + trail + random.randint(2, 18)
        k = random.choice([1, 1, 2, 2, 3])
        drops.append(dict(c=c, trail=trail, P=P, k=k,
                          phase=random.uniform(0, P),
                          chars=[random.choice(RAIN_CHARS) for _ in range(rows + 40)]))

# Маска: дождь приглушается под текстом, края мягкие
mask = Image.new("L", (W, H), 255)
ImageDraw.Draw(mask).rounded_rectangle((W * 0.2, H * 0.17, W * 0.8, H * 0.83), 30, fill=40)
mask = np.asarray(mask.filter(ImageFilter.GaussianBlur(22)), dtype=np.float32) / 255

# Цвет акцента по x: один цвет или градиент ACCENT -> ACCENT2
xs = np.linspace(0, 1, W, dtype=np.float32)[None, :, None]
acc_map = np.array(ACCENT, np.float32) + (np.array(ACCENT2 or ACCENT, np.float32)
                                           - np.array(ACCENT, np.float32)) * xs

def scramble(text, progress, rng):
    """progress 0..1: доля уже «расшифрованных» символов, остальное — решётки."""
    n = int(round(len(text) * progress))
    return "".join(ch if i < n or ch == " " else rng.choice("#$%&@") for i, ch in enumerate(text))

def rain_layer(t):
    inten = Image.new("L", (W, H), 0)
    head = Image.new("L", (W, H), 0)
    di, dh = ImageDraw.Draw(inten), ImageDraw.Draw(head)
    for d in drops:
        pos = (d["phase"] + d["k"] * d["P"] * t / N) % d["P"]
        h = int(pos)
        for j in range(d["trail"] + 1):
            r = h - j
            if 0 <= r < rows:
                b = (1 - j / (d["trail"] + 1)) ** 1.6
                xy = (d["c"] * CELL + 2, r * CELL)
                ch = d["chars"][(r + d["c"]) % len(d["chars"])]
                (dh if j == 0 else di).text(xy, ch, font=f_rain, fill=int(255 * b))
    a = np.asarray(inten, dtype=np.float32) / 255 * mask
    hd = np.asarray(head, dtype=np.float32) / 255 * mask
    return a, hd

frames = []
for t in range(N):
    a, hd = rain_layer(t)
    bg, acc = np.array(BG, np.float32), acc_map
    img = bg + (acc - bg) * a[..., None] * 0.9
    hot = acc + (255 - acc) * 0.65          # голова капли: светлый акцент
    img = img + (hot - img) * hd[..., None]
    im = Image.fromarray(img.clip(0, 255).astype(np.uint8), "RGB")
    dr = ImageDraw.Draw(im)

    tw = dr.textlength(TITLE, font=f_title)
    dr.text(((W - tw) / 2, H * 0.24), TITLE, font=f_title, fill=TITLE_COLOR)

    li, lt = divmod(t, FRAMES_PER_LINE)
    line = LINES[li]
    rng = random.Random(t)
    dec, out = 12, 7                     # кадры расшифровки и растворения
    if lt < dec:
        shown = scramble(line, lt / dec, rng)
    elif lt >= FRAMES_PER_LINE - out:
        shown = scramble(line, (FRAMES_PER_LINE - lt - 1) / out, rng)
    else:
        shown = line
    cursor = "_" if (t // 6) % 2 == 0 else " "
    lw = dr.textlength(line + "_", font=f_line)
    dr.text(((W - lw) / 2, H * 0.6), shown + cursor, font=f_line, fill=SUB_COLOR)

    frames.append(im)

# Общая палитра по выборке кадров -> без мерцания цветов между кадрами
sample = Image.new("RGB", (W, H * 8))
for i, f in enumerate(frames[:: max(1, N // 8)][:8]):
    sample.paste(f, (0, H * i))
pal_img = sample.quantize(255, method=Image.Quantize.MEDIANCUT)
frames = [f.quantize(palette=pal_img, dither=Image.Dither.NONE) for f in frames]

frames[0].save(OUT, save_all=True, append_images=frames[1:], duration=FRAME_MS,
               loop=0, optimize=True, disposal=1)
print(OUT, len(frames), "frames")

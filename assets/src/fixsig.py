#!/usr/bin/env python3
"""Чистка signature.json после sigtrace.py + порядок «как пером».

python fixsig.py signature.json -o signature.clean.json

Заточен под конкретный прогон sigtrace (27 штрихов, линейки 191/234):
номера штрихов ниже — из того файла. Буквы собираются в непрерывные
движения пера; там, где перо проходит по уже нарисованному (ствол h,
низ росчерка), путь повторяется точка в точку.
"""
import argparse
import json
import math

import numpy as np

SLANT = math.tan(math.radians(25))
BASE, XH, ASC = 234.0, 191.0, 170.5  # база, верх строчных, верх выносных
STEP = 3.0  # шаг пересэмплирования
FLOURISH_ROT = 6.0  # поворот росчерка по часовой, градусы
R_DX = 12.0  # сдвиг r вправо, к y
S_DX = -6.5  # сдвиг s и всего правее неё (hhh с хвостом) влево


def cr(pts, step=STEP):
    """Центростремительный Catmull-Rom -> плотная ломаная (без петель при неравных отрезках)."""
    pts = [tuple(map(float, p)) for p in pts]
    pts = [p for i, p in enumerate(pts) if i == 0 or math.dist(p, pts[i - 1]) > 1e-6]
    if len(pts) < 2:
        return pts
    out = [pts[0]]
    n = len(pts)
    for i in range(n - 1):
        p1, p2 = np.array(pts[i]), np.array(pts[i + 1])
        p0 = np.array(pts[i - 1]) if i > 0 else 2 * p1 - p2
        p3 = np.array(pts[i + 2]) if i + 2 < n else 2 * p2 - p1
        d0, d1, d2 = (max(np.linalg.norm(b - a) ** 0.5, 1e-6) for a, b in ((p0, p1), (p1, p2), (p2, p3)))
        m1 = (p1 - p0) / d0 - (p2 - p0) / (d0 + d1) + (p2 - p1) / d1
        m2 = (p2 - p1) / d1 - (p3 - p1) / (d1 + d2) + (p3 - p2) / d2
        c1, c2 = p1 + m1 * d1 / 3, p2 - m2 * d1 / 3
        k = max(1, math.ceil(math.dist(p1, p2) / step))
        for j in range(1, k + 1):
            t = j / k
            u = 1 - t
            out.append(tuple(u ** 3 * a + 3 * u * u * t * b + 3 * u * t * t * c + t ** 3 * d
                             for a, b, c, d in zip(p1, c1, c2, p2)))
    return out


def pen(*segs):
    """Сегменты сглаживаются по отдельности, стык между ними — угол."""
    out = []
    for s in segs:
        s = s if isinstance(s, Dense) else cr(s)
        out += s[1:] if out and math.dist(out[-1], s[0]) < 1e-6 else s
    return out


class Dense(list):
    """Уже плотная ломаная, не пересэмплировать."""


def on_slant(p, y):
    """Точка на прямой с наклоном 25° через p, на высоте y."""
    return (p[0] + (p[1] - y) * SLANT, y)


def stem(a, b):
    """Прямой штрих 25° через середину a-b, концы на тех же высотах."""
    m = ((a[0] + b[0]) / 2, (a[1] + b[1]) / 2)
    return on_slant(m, a[1]), on_slant(m, b[1])


# общий овал для росчерка r и хвоста последней h (снят с рисунка, в координатах signature.json)
OVAL_C = np.array([316.72, 296.82])
OVAL_AX = (178.18, 285.41)
_a = math.radians(-145.42)
OVAL_R = np.array([[math.cos(_a), -math.sin(_a)], [math.sin(_a), math.cos(_a)]])


def oval(th):
    return tuple(OVAL_C + OVAL_R @ [OVAL_AX[0] * math.cos(th), OVAL_AX[1] * math.sin(th)])


def oval_th(p):
    """Параметр точки на овале (для точки рядом — радиальная проекция)."""
    q = OVAL_R.T @ (np.asarray(p, float) - OVAL_C)
    return math.atan2(q[1] / OVAL_AX[1], q[0] / OVAL_AX[0])


def oval_in(p):
    q = OVAL_R.T @ (np.asarray(p, float) - OVAL_C)
    return (q[0] / OVAL_AX[0]) ** 2 + (q[1] / OVAL_AX[1]) ** 2 < 1


def oval_arc(t0, t1, via, step=STEP):
    """Дуга овала от t0 до t1 через via, шаг ~step px."""
    tau = 2 * math.pi
    d, dv = (t1 - t0) % tau, (via - t0) % tau
    if dv > d:
        d -= tau
    r = (math.dist(oval(t0), oval(t0 + d / 2)) + math.dist(oval(t0 + d / 2), oval(t1))) / max(abs(d), 1e-9)
    n = max(2, math.ceil(abs(d) * r / step))
    return [oval(t0 + d * i / n) for i in range(n + 1)]


def bezier(p0, t0, p3, t3, n=40):
    """Кубическая Безье p0->p3 с касательными t0 (на выходе) и t3 (на входе)."""
    p0, p3 = np.asarray(p0, float), np.asarray(p3, float)
    L = np.linalg.norm(p3 - p0) / 3
    c1, c2 = p0 + np.asarray(t0) * L, p3 - np.asarray(t3) * L
    return [tuple((1 - t) ** 3 * p0 + 3 * (1 - t) ** 2 * t * c1 + 3 * (1 - t) * t * t * c2 + t ** 3 * p3)
            for t in np.linspace(0, 1, n)]


def unit(v):
    v = np.asarray(v, float)
    return v / np.linalg.norm(v)


# варианты h: высота ветвления горба над базой, ширина, дуга (u, v) до верха ноги
H_VARIANTS = {
    "a": (29.0, 19.5, [(5.5, 35.0), (10.0, 40.5), (13.0, 42.6), (15.5, 42.5), (17.8, 40.5), (19.5, 35.0)]),
    "b": (24.0, 21.0, [(2.5, 32.0), (6.5, 39.0), (11.0, 42.8), (15.5, 42.6), (19.0, 39.5), (21.0, 33.0)]),
    "c": (34.0, 18.0, [(7.0, 41.5), (11.5, 43.2), (15.0, 42.0), (17.3, 38.0), (18.0, 32.0)]),
}


def build(src, hv="b"):
    S = lambda i: [tuple(p) for p in src[i]]
    R = lambda p: p[::-1]
    out = []

    # --- росчерк: дуга общего овала от верха до кончика (src[0] и его копия src[1] не нужны) ---
    F = src[0]
    t_top, t_tip, t_mid = oval_th(F[0]), oval_th(F[-1]), oval_th(F[len(F) // 2])
    # стык r: подводящий штрих r продолжается до овала (бисекция по лучу)
    a = np.array([186.0, 233.0])
    d = unit(np.subtract(S(2)[0], a))
    lo_t, hi_t = 0.0, 300.0
    for _ in range(60):
        m = (lo_t + hi_t) / 2
        lo_t, hi_t = (m, hi_t) if oval_in(a + d * m) else (lo_t, m)
    t_J = oval_th(a + d * lo_t)
    upper = oval_arc(t_top, t_J, t_mid)
    flour = Dense(upper + oval_arc(t_J, t_tip, (t_J + t_tip) / 2)[1:])
    iJ = len(upper) - 1
    J = flour[iJ]
    # росчерк повёрнут по часовой вокруг стыка с r (подвод r не сдвигается)
    ca, sa = math.cos(math.radians(FLOURISH_ROT)), math.sin(math.radians(FLOURISH_ROT))
    flour = Dense((J[0] + (x - J[0]) * ca - (y - J[1]) * sa, J[1] + (x - J[0]) * sa + (y - J[1]) * ca) for x, y in flour)

    # --- r: ствол 25° до базы, подвод без загиба, флажок пристыкован ---
    r_top = (249.2, 200.5)
    r_bot = on_slant(r_top, 222.0)  # кончик r на уровне низа «u» у y
    lead = [r_bot, r_top, (249.1, 197.6), (247.1, 195.6), (244.4, 195.3), (240.3, 196.8),
            (233.6, 200.7), (219.4, 210.0), (185.7, 233.3), J]
    # вся r сдвинута вправо к y; подвод плавно дотягивается до прежнего стыка с росчерком
    lead = [(x + R_DX * w, y) for (x, y), w in zip(lead, (1, 1, 1, 1, 1, 1, 1, 0.8, 0.35, 0))]
    out.append(pen(lead, Dense(flour[iJ:]), Dense(R(flour))))  # r -> вниз к кончику -> взмах вверх
    # штрих 4 (флажок справа от r) выкинут

    # --- y: правая ветка и спуск — одна прямая 25°, без излома ---
    yj = (284.5, 220.3)
    y_top, y_low = on_slant(yj, XH - 0.5), on_slant(yj, 284.0)
    y3 = S(3)  # (239,254) ... петля ... (277,191)
    left = R(y3)[:7] + [yj]  # левая ветка + низ «u»
    # петля как нарисована (широкая, завиток вверху), без дрожи:
    # низ — ровная дуга, левая сторона — прямая, завиток — ровная дуга
    lx = lambda y: 226.9 + (y - 300.4) * (4.3 / 32.4)  # прямая левой стороны
    loop = [(245.8, 301.4), (242.4, 304.3), (238.4, 306.1), (234.3, 306.7), (230.6, 305.9),
            (228.2, 303.6), (lx(300.4), 300.4), (lx(290), 290), (lx(279), 279), (lx(268), 268),
            (223.4, 262.0), (226.3, 257.6), (230.4, 255.2), (234.8, 254.3), (239.2, 254.2)]
    out.append(pen(left, [yj, y_top], [y_top, yj, y_low] + loop))

    # --- p: ствол 25° сразу переходит в петлю, без «v» наверху ---
    p_bot = S(5)[0]
    p_top = on_slant(p_bot, 194.5)
    out.append(pen([p_bot, p_top], [p_top, (318.5, 192.3)] + R(S(7))))

    # --- l + e: l без крючка сверху, ножка круглая ---
    lt = (358.7, ASC)
    lb = on_slant(lt, 224.0)
    foot = [lb, (333.6, 228.6), (335.0, 232.2), (338.0, 234.2), (342.5, 233.7),
            (347.8, 230.6), (352.6, 227.3)]
    je = foot[-1]
    # e: левая сторона — одна прямая 25° от ножки l до верха глазка
    ex = lambda y: on_slant(je, y)
    e0 = ex(215.0)  # где глазок замыкается
    eye = [e0, ex(205.0), ex(198.5), (369.6, 194.2), (373.0, 192.2), (376.0, 192.0), (379.0, 193.0),
           (380.6, 195.4), (381.0, 198.5), (381.0, 202.0), (380.0, 205.0), (377.0, 210.0), (373.0, 213.0),
           (369.0, 215.0), (364.0, 216.0), e0]
    mid = ex(221.0)
    out.append(pen([lt, ((lt[0] + lb[0]) / 2, (lt[1] + lb[1]) / 2)] + foot,
                   [je, mid] + eye,
                   [e0, mid, je],
                   [je] + [p for p in S(11)[1:] if p[0] <= 378]))  # выход e без хвостика вверх

    # --- s: плавная S-кривая, без крючка сверху и петельки внизу ---
    # (u, v): u вдоль строки, v — высота над базой; наклон добавляется сдвигом
    # s сдвинута влево: просвет e-s равен просвету s-h (как между h)
    sx = lambda u, v: (387.0 + S_DX + u + v * SLANT, BASE - v)
    out.append(pen([sx(u, v) for u, v in (
        (19.5, 38.5), (16.0, 42.3), (10.0, 43.2), (4.5, 41.3), (1.8, 36.5), (3.2, 31.0), (8.0, 26.5),
        (14.0, 22.5), (18.6, 17.0), (20.0, 10.5), (17.8, 4.0), (12.0, 0.3), (5.5, 0.5), (1.8, 2.4))]))  # низ s обрезан по линии левого края верха s

    # --- h: все три из одного шаблона, на равном шаге ---
    jv, w, arch = H_VARIANTS[hv]
    for i, x0 in enumerate(x + S_DX for x in (418.4, 457.1, 495.8)):
        hx = lambda u, v: (x0 + u + v * SLANT, BASE - v)
        sb, jh, st = hx(0, 0), hx(0, jv), hx(0, BASE - ASC)
        hump = [hx(0, jv)] + [hx(u, v) for u, v in arch]
        if i < 2:
            hump.append(hx(w, 0))
            out.append(pen([sb, jh, st], [st, jh], hump))
        else:  # последняя: горб как у всех, его правая сторона продолжается вниз по общему овалу
            dome = [hx(0, jv)] + [hx(u, v) for u, v in arch if v > 36]  # горб без низа ноги
            t_end = oval_th(S(26)[-1])
            t_v = oval_th(S(26)[len(S(26)) * 2 // 3])
            # хвост — дуга овала, сдвинутая вместе с h
            arc = oval_arc(oval_th((dome[-1][0] - S_DX + 2, dome[-1][1] + 12)), t_end, t_v)
            arc = [(x + S_DX, y) for x, y in arc]
            out.append(pen([sb, jh, st], [st, jh], dome + arc))
    return out


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("src")
    ap.add_argument("-o", "--out", default="signature.clean.json")
    ap.add_argument("--h", default="b", choices=sorted(H_VARIANTS), help="вариант h")
    args = ap.parse_args()
    with open(args.src) as f:
        src = json.load(f)
    if len(src) != 27:
        raise SystemExit(f"ожидалось 27 штрихов (прогон sigtrace от 2026-11-06), в файле {len(src)}")
    strokes = build(src, args.h)
    with open(args.out, "w") as f:
        json.dump([[[round(x, 1), round(y, 1)] for x, y in s] for s in strokes], f, separators=(",", ":"))
    print(f"{args.out}: {len(strokes)} штрихов, {sum(map(len, strokes))} точек")


if __name__ == "__main__":
    main()

# -*- coding: utf-8 -*-
"""
Figures du rapport (matplotlib, style épuré) et extraction des visuels de l'archive ZIP.
Palette : bleu marine #0F172A / ardoise #475569 #64748B / accent bleu acier #2563EB / orangé #D97706.
"""
from __future__ import annotations
import glob
import io
import math
import os
import re
import unicodedata
import zipfile
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import Rectangle, Circle, Wedge, FancyBboxPatch, Polygon
from matplotlib import font_manager
from PIL import Image

try:
    import pymupdf as fitz           # PyMuPDF ≥ 1.24
except ImportError:                   # pragma: no cover
    import fitz                       # type: ignore

import fanuc_calculs as F

NAVY, NAVY2 = "#0F172A", "#1E293B"
SLATE, SLATE_L = "#475569", "#64748B"
LINE, BG = "#CBD5E1", "#F8FAFC"
BLUE, ORANGE = "#2563EB", "#D97706"
GREY_L = "#E2E8F0"


# --------------------------------------------------------------------------------------
# Police commune (Liberation Sans / Arial / Helvetica si présente, sinon DejaVu fourni avec matplotlib)
# --------------------------------------------------------------------------------------
def find_font_family():
    """Retourne (nom, {regular,bold,italic,bolditalic}) – chemins TTF utilisables par reportlab."""
    cands = [
        ("LiberationSans", ["LiberationSans-Regular.ttf", "LiberationSans-Bold.ttf", "LiberationSans-Italic.ttf", "LiberationSans-BoldItalic.ttf"]),
        ("Arimo", ["Arimo-Regular.ttf", "Arimo-Bold.ttf", "Arimo-Italic.ttf", "Arimo-BoldItalic.ttf"]),
        ("Arial", ["arial.ttf", "arialbd.ttf", "ariali.ttf", "arialbi.ttf"]),
        ("DejaVuSans", ["DejaVuSans.ttf", "DejaVuSans-Bold.ttf", "DejaVuSans-Oblique.ttf", "DejaVuSans-BoldOblique.ttf"]),
    ]
    roots = ["/usr/share/fonts", "/usr/local/share/fonts", os.path.expanduser("~/.fonts"),
             os.path.expanduser("~/.local/share/fonts"), "C:/Windows/Fonts", "/Library/Fonts", "/System/Library/Fonts/Supplemental",
             os.path.join(os.path.dirname(matplotlib.__file__), "mpl-data", "fonts", "ttf")]
    for name, files in cands:
        paths = []
        for f in files:
            hit = None
            for r in roots:
                m = glob.glob(os.path.join(r, "**", f), recursive=True)
                if m:
                    hit = m[0]; break
            paths.append(hit)
        if all(paths):
            return name, dict(zip(("regular", "bold", "italic", "bolditalic"), paths))
    raise RuntimeError("Aucune police TTF trouvée")


FONT_NAME, FONT_FILES = find_font_family()
for _p in FONT_FILES.values():
    font_manager.fontManager.addfont(_p)
_fam = font_manager.FontProperties(fname=FONT_FILES["regular"]).get_name()

plt.rcParams.update({
    "font.family": _fam, "font.size": 8.5, "axes.edgecolor": SLATE_L, "axes.labelcolor": SLATE,
    "axes.linewidth": 0.6, "xtick.color": SLATE, "ytick.color": SLATE, "text.color": NAVY,
    "axes.spines.top": False, "axes.spines.right": False, "axes.facecolor": "white", "figure.facecolor": "white",
    "grid.color": GREY_L, "grid.linewidth": 0.6, "axes.grid": False, "legend.frameon": False,
    "savefig.dpi": 220, "savefig.bbox": "tight", "savefig.pad_inches": 0.08,
})


def _save(fig, path):
    fig.savefig(path, facecolor="white")
    plt.close(fig)
    return str(path)


# --------------------------------------------------------------------------------------
# Extraction des visuels depuis l'archive
# --------------------------------------------------------------------------------------
def _norm(s):
    return unicodedata.normalize("NFC", s)


def _trim(im, pad=12, thr=246):
    g = im.convert("L").point(lambda v: 255 if v < thr else 0)
    bb = g.getbbox()
    if not bb:
        return im
    x0, y0, x1, y1 = bb
    return im.crop((max(0, x0 - pad), max(0, y0 - pad), min(im.width, x1 + pad), min(im.height, y1 + pad)))


def extract_zip(zip_path, workdir):
    """Décompresse l'archive (noms Unicode normalisés) et retourne le dossier racine."""
    dest = Path(workdir) / "zip"
    if dest.exists():
        return dest
    dest.mkdir(parents=True)
    with zipfile.ZipFile(zip_path) as z:
        for info in z.infolist():
            name = _norm(info.filename)
            tgt = dest / name
            if info.is_dir():
                tgt.mkdir(parents=True, exist_ok=True); continue
            tgt.parent.mkdir(parents=True, exist_ok=True)
            with z.open(info) as src, open(tgt, "wb") as out:
                out.write(src.read())
    return dest


def _find(root, pattern):
    pat = _norm(pattern).lower()
    for p in Path(root).rglob("*"):
        if p.is_file() and re.search(pat, _norm(p.name).lower()):
            return p
    return None


def _mindmap_columns(src, dst, ratios=(0.4153, 0.7414)):
    """Découpe l'aperçu (très haut, 852 x 2367) en 3 colonnes côte à côte, aux interstices entre blocs."""
    im = Image.open(src).convert("RGB")
    W, H = im.size
    cuts = [0] + [int(r * H) for r in ratios] + [H]
    cols = []
    for i in range(3):
        c = im.crop((0, cuts[i], W, cuts[i + 1]))
        bb = c.convert("L").point(lambda v: 255 if v < 245 else 0).getbbox()
        cols.append(c.crop((max(0, bb[0] - 8), 0, min(W, bb[2] + 8), c.height)) if bb else c)
    hmax = max(c.height for c in cols)
    out = Image.new("RGB", (sum(c.width for c in cols) + 40, hmax), "white")
    x = 0
    for c in cols:
        out.paste(c, (x, 0)); x += c.width + 20
    out.save(dst)
    return str(dst)


def extract_assets(zip_path, workdir):
    """Retourne (dict nom -> chemin PNG/JPG, inventaire du ZIP)."""
    root = extract_zip(zip_path, workdir)
    out_dir = Path(workdir) / "assets"
    out_dir.mkdir(parents=True, exist_ok=True)
    assets, inventory = {}, []

    for p in sorted(Path(root).rglob("*")):
        if p.is_file():
            inventory.append((str(p.relative_to(root)), p.stat().st_size))

    # 1) Plans : rendu des PDF (1 page chacun)
    for key, pat in {"plan_flacon": r"ff-2027-btl-001\.pdf", "plan_interc": r"ff-2027-pkg-001\.pdf",
                     "plan_thermo": r"ff-2027-pkg-002\.pdf", "plan_rack": r"ff-2027-pkg-003\.pdf"}.items():
        f = _find(root, pat)
        if f:
            doc = fitz.open(f)
            pix = doc[0].get_pixmap(dpi=170)
            im = _trim(Image.frombytes("RGB", (pix.width, pix.height), pix.samples), pad=6)
            path = out_dir / f"{key}.png"; im.save(path); assets[key] = str(path)

    # 2) Images embarquées dans le cahier des charges
    cdc = _find(root, r"flacon_enca2701.*\.pdf")
    if cdc:
        doc = fitz.open(cdc)
        wanted = {}
        for pno, page in enumerate(doc):
            for img in page.get_images(full=True):
                w, h = img[2], img[3]
                if w < 300:
                    continue
                wanted.setdefault(pno + 1, []).append(img[0])
        names = {(2, 0): "cdc_flacon_face", (2, 1): "cdc_flacon_3q", (3, 0): "cdc_cale", (3, 1): "cdc_coffret",
                 (4, 0): "cdc_arrivee_cotes", (4, 1): "cdc_arrivee_iso", (5, 0): "cdc_intercalaire", (5, 1): "cdc_rack",
                 (6, 0): "cdc_convoyeurs"}
        for pno, xrefs in wanted.items():
            for i, xr in enumerate(xrefs):
                key = names.get((pno, i))
                if not key:
                    continue
                info = doc.extract_image(xr)
                path = out_dir / f"{key}.{info['ext']}"
                path.write_bytes(info["image"]); assets[key] = str(path)
        # rangée complète de la figure 3 (p.4) : image « cotes » (xref à 954 px) ; on garde les deux
        # Page 9 non utilisée (vignettes)
    # 3) Carte mentale MindView (aperçu)
    mvdx = _find(root, r"\.mvdx$")
    if mvdx:
        try:
            with zipfile.ZipFile(mvdx) as z:
                if "preview.png" in z.namelist():
                    path = out_dir / "mindmap.png"; path.write_bytes(z.read("preview.png")); assets["mindmap"] = str(path)
                    assets["mindmap_wide"] = _mindmap_columns(path, out_dir / "mindmap_wide.png")
        except zipfile.BadZipFile:
            pass

    # 4) Catalogue : photo LR-10iA/10 (page 9) + cas de charge (docx)
    cat = _find(root, r"catalogue robots fanuc")
    if cat:
        doc = fitz.open(cat)
        pix = doc[8].get_pixmap(dpi=150)
        im = Image.frombytes("RGB", (pix.width, pix.height), pix.samples)
        W, H = im.size
        crop = im.crop((int(0.03 * W), int(0.10 * H), int(0.285 * W), int(0.585 * H)))
        path = out_dir / "robot_lr10.png"; crop.save(path); assets["robot_lr10"] = str(path)
    docx_f = _find(root, r"ressources compl.*\.docx$")
    if docx_f:
        with zipfile.ZipFile(docx_f) as z:
            for key, member in {"cas1": "word/media/image22.jpeg", "cas2": "word/media/image23.jpeg", "cas3": "word/media/image24.jpeg",
                                "chargeportee_ex": "word/media/image6.png"}.items():
                if member in z.namelist():
                    path = out_dir / f"{key}{Path(member).suffix}"; path.write_bytes(z.read(member)); assets[key] = str(path)
    return assets, inventory, root


# --------------------------------------------------------------------------------------
# Figures
# --------------------------------------------------------------------------------------
def fig_takt(cad, path):
    fig, ax = plt.subplots(figsize=(7.0, 2.35))
    seg = [("Temps calendaire campagne\n(20 j × 2 postes × 7,25 h)", cad.camp_s, GREY_L, NAVY),
           ]
    ax.barh([1], [cad.camp_s], color=GREY_L, height=0.42)
    ax.barh([1], [cad.prod_s], color=NAVY2, height=0.42)
    ax.barh([0], [cad.takt * 221_850], color=BLUE, height=0.42)
    ax.set_xlim(0, cad.camp_s * 1.02)
    ax.set_yticks([0, 1]); ax.set_yticklabels(["Besoin : 221 850 × 4,00 s", "Disponible : 20 j × 14,5 h"])
    ax.text(cad.prod_s / 2, 1, f"Temps productif (TRS 85 %) = {cad.prod_s:,.0f} s".replace(",", " "), color="white", ha="center", va="center", fontsize=8)
    ax.text(cad.prod_s + (cad.camp_s - cad.prod_s) / 2, 1, "15 %\narrêts", color=SLATE, ha="center", va="center", fontsize=7)
    ax.text(cad.takt * 221_850 / 2, 0, "Takt = 887 400 s / 221 850 = 4,00 s par coffret", color="white", ha="center", va="center", fontsize=8)
    ax.set_xlabel("secondes (campagne complète)")
    ax.xaxis.set_major_formatter(matplotlib.ticker.FuncFormatter(lambda v, _: f"{v/1000:,.0f} k".replace(",", " ")))
    for s in ("left",):
        ax.spines[s].set_visible(False)
    ax.tick_params(axis="y", length=0)
    return _save(fig, path)


def fig_layout(L, path, p=F.INPUT, robot=F.ROBOTS[1]):
    W, H = L.W, L.H
    fig, ax = plt.subplots(figsize=(7.2, 4.9))
    ax.set_aspect("equal"); ax.set_xlim(-200, W + 300); ax.set_ylim(-330, H + 120)
    ax.axis("off")
    fs = 6.0
    ax.add_patch(Rectangle((0, 0), W, H, fill=False, ec=NAVY, lw=1.1, ls=(0, (6, 3))))
    rr = robot["reach"]; cx, cy = L.robot
    clip = Rectangle((-200, -330), W + 500, H + 450, transform=ax.transData)
    for r, ls in [(rr, (0, (2, 2))), (0.8 * rr, (0, (1, 2)))]:
        c = Circle((cx, cy), r, fill=False, ec=SLATE_L, lw=0.7, ls=ls); ax.add_patch(c); c.set_clip_path(clip)
    for r in (L.in_strip, L.strip["W"], L.strip["E"]):
        ax.add_patch(Rectangle((r[0], r[1]), r[2] - r[0], r[3] - r[1], fc="#EEF2F7", ec=SLATE_L, lw=0.7))
    ax.text(L.in_strip[0] + 25, 22, "Convoyeur\nd'entrée\n700 mm", fontsize=fs, color=SLATE, va="bottom", ha="left")
    ax.text(25, L.strip["W"][1] + 25, "Convoyeur\nsortie A\n900 mm", fontsize=fs, color=SLATE, va="bottom", ha="left")
    ax.text(W - 25, L.strip["E"][1] + 25, "Convoyeur\nsortie B\n900 mm", fontsize=fs, color=SLATE, va="bottom", ha="right")
    for side, lab in (("W", "C1"), ("E", "C2")):
        fx, fy = L.fill[side]
        ax.add_patch(Rectangle((fx - L.interc_w / 2, fy - L.interc_h / 2), L.interc_w, L.interc_h, fc="white", ec=NAVY, lw=0.9))
        for (ax_, ay_) in L.alveoles[side]:
            ax.add_patch(Rectangle((ax_ - 82, ay_ - 98), 164, 196, fc="#F1F5F9", ec=SLATE_L, lw=0.5))
            ax.add_patch(Rectangle((ax_ - 74, ay_ - 56), 66, 112, fc=BLUE, ec="none", alpha=0.20))
        ax.text(fx, fy + L.interc_h / 2 + 18, lab + " – intercalaire 710 × 620", ha="center", va="bottom", fontsize=fs + 0.4, fontweight="bold", color=BLUE)
    for (px, py) in L.pick_pts:
        ax.add_patch(Rectangle((px - 39, py - 67), 78, 135, fc=ORANGE, ec="none", alpha=0.9))
    ax.text(L.pick_pts[2][0] + 75, L.pick_pts[2][1], "P – rangée de prise\n3 flacons, pas 196 mm", fontsize=fs, color=ORANGE, va="center", bbox=dict(fc="white", ec="none", pad=1.0), zorder=6)
    r = L.rack
    ax.add_patch(Rectangle((r[0], r[1]), r[2] - r[0], r[3] - r[1], fc=NAVY2, ec=NAVY))
    for i, (ix, iy) in enumerate(L.imprints):
        ax.add_patch(Rectangle((ix - 40, iy - 22), 80, 44, fc=BLUE if i in L.used_imprints else "#94A3B8", ec="white", lw=0.5))
    ax.text(r[0], r[3] + 14, "R – rack de pesée, 6 empreintes (pas 221 mm) ; empreintes 3 et 4 utilisées", fontsize=fs + 0.2, color=NAVY, va="bottom", bbox=dict(fc="white", ec="none", pad=1.2), zorder=6)
    ax.add_patch(Circle((cx, cy), L.ped_r, fc="#E2E8F0", ec=NAVY, lw=0.9))
    ax.add_patch(Circle((cx, cy + 60), 55, fc=NAVY, ec="none"))
    ax.text(cx, cy - 55, "LR-10iA/10\nsocle + rehausse", ha="center", va="center", fontsize=fs, color=NAVY)
    px, py = L.pick_pts[1]; rx, ry = L.imprints[2]; qx, qy = L.fill["W"]
    ap = dict(arrowstyle="-|>", lw=1.0, shrinkA=0, shrinkB=0)
    ax.annotate("", xy=(rx + 40, ry - 35), xytext=(px + 20, py + 75), arrowprops=dict(color=BLUE, connectionstyle="arc3,rad=-0.35", **ap))
    ax.annotate("", xy=(qx + 150, qy + 90), xytext=(rx - 60, ry - 40), arrowprops=dict(color=BLUE, connectionstyle="arc3,rad=0.25", **ap))
    ax.annotate("", xy=(px - 45, py + 70), xytext=(qx + 180, qy - 190), arrowprops=dict(color=SLATE_L, ls="--", connectionstyle="arc3,rad=0.3", **ap))
    def dim(x0, y0, x1, y1, txt, rot=0):
        ax.annotate("", xy=(x1, y1), xytext=(x0, y0), arrowprops=dict(arrowstyle="<->", color=SLATE, lw=0.6))
        ax.text((x0 + x1) / 2, (y0 + y1) / 2, txt, ha="center", va="center", fontsize=fs, color=SLATE, rotation=rot, bbox=dict(fc="white", ec="none", pad=0.8))
    dim(0, -110, W, -110, "2 500 mm")
    dim(W + 110, 0, W + 110, H, "1 500 mm", 90)
    from matplotlib.lines import Line2D
    from matplotlib.patches import Patch
    hs = [Line2D([0], [0], color=SLATE_L, ls=(0, (2, 2)), lw=0.8, label="portée 1 101 mm"),
          Line2D([0], [0], color=SLATE_L, ls=(0, (1, 2)), lw=0.8, label="80 % de la portée"),
          Line2D([0], [0], color=BLUE, lw=1.0, label="trajet chargé"), Line2D([0], [0], color=SLATE_L, ls="--", lw=1.0, label="retour à vide"),
          Patch(fc=BLUE, alpha=0.25, label="logement flacon (cale)")]
    ax.legend(handles=hs, loc="lower center", bbox_to_anchor=(0.5, -0.04), ncol=5, fontsize=fs, handlelength=1.8, frameon=True, facecolor="white", edgecolor="none", framealpha=1)
    return _save(fig, path)


def fig_robots(sel, L, takt, path):
    names = [r["name"] for r in sel]
    fig, axs = plt.subplots(1, 2, figsize=(7.2, 2.7), gridspec_kw=dict(wspace=0.62))
    y = list(range(len(sel)))[::-1]
    ax = axs[0]
    vals = [r["util_reach"] * 100 for r in sel]
    cols = [LINE if r["eliminated"] else (BLUE if r["name"] == "LR-10iA/10" else SLATE_L) for r in sel]
    ax.barh(y, vals, color=cols, height=0.55)
    ax.axvline(80, color=ORANGE, lw=0.9, ls="--"); ax.axvline(100, color=NAVY, lw=0.9)
    ax.text(78, len(sel) - 0.4, "80 %", color=ORANGE, fontsize=7, ha="right"); ax.text(102, len(sel) - 0.4, "100 %", color=NAVY, fontsize=7, ha="left")
    for yi, v in zip(y, vals):
        ax.text(v + 2, yi, f"{v:.0f} %", va="center", fontsize=7, color=SLATE)
    ax.set_yticks(y); ax.set_yticklabels(names, fontsize=7.5)
    ax.set_xlim(0, 150); ax.set_ylim(-0.7, len(sel) - 0.3); ax.set_xlabel(f"Utilisation de la portée (r max = {L.r_max:.0f} mm)")
    ax.spines["left"].set_visible(False); ax.tick_params(axis="y", length=0)
    ax = axs[1]
    for yi, r in zip(y, sel):
        t = r["t_j1"]
        if t is None:
            ax.text(0.08, yi, "non applicable (hors portée / 4 axes)", va="center", fontsize=6.8, color=SLATE_L); continue
        ax.barh(yi, t, color=LINE if r["eliminated"] else (BLUE if r["name"] == "LR-10iA/10" else SLATE_L), height=0.55)
        ax.text(t + 0.05, yi, f"{t:.2f} s", va="center", fontsize=7, color=SLATE)
    ax.axvline(0.75 * takt, color=ORANGE, lw=0.9, ls="--")
    ax.text(0.75 * takt + 0.05, len(sel) - 0.4, "75 % du takt", color=ORANGE, fontsize=7, ha="left")
    ax.set_yticks(y); ax.set_yticklabels([])
    ax.set_xlim(0, 4.3); ax.set_ylim(-0.7, len(sel) - 0.3); ax.set_xlabel("Temps de rotation J1 par cycle (360° + 3 × 0,12 s)")
    ax.spines["left"].set_visible(False); ax.tick_params(axis="y", length=0)
    return _save(fig, path)


def fig_payload_reach(path, req_payload, req_reach):
    fig, ax = plt.subplots(figsize=(6.4, 3.4))
    offs = {"LR Mate 200iD/4S": (-20, 0.8, "right"), "SR-3iA": (20, -1.3, "left"), "SR-6iA": (30, -1.5, "left"),
            "M-3iA/6A": (30, 0.5, "left"), "DR-3iB/8L": (-30, 0.7, "right"), "SR-12iA": (-30, 0.7, "right"),
            "LR Mate 200iD/7L": (30, -1.4, "left"), "LR Mate 200iD/14L": (-30, 0.6, "right"), "CR-7iA/L": (-30, -1.4, "right"),
            "CRX-5iA": (30, -1.4, "left"), "LR-10iA/10": (-30, 0.8, "right"), "M-10iD/16S": (-30, 0.6, "right"),
            "CRX-10iA": (-30, -1.6, "right"), "CRX-10iA/L": (30, -1.6, "left"), "M-10iD/12": (30, 0.6, "left"),
            "CR-15iA": (30, 0.6, "left"), "M-10iD/10L": (30, -1.6, "left"), "M-10iD/8L": (-30, 0.7, "right"),
            "CRX-20iA/L": (30, 0.6, "left"), "CRX-25iA": (-30, 0.6, "right")}
    for name, reach, pay in F.CATALOG_POINTS:
        hi = name == "LR-10iA/10"
        ax.scatter(reach, pay, s=34 if hi else 14, color=BLUE if hi else SLATE_L, zorder=3)
        dx, dy, ha = offs.get(name, (30, 0.6, "left"))
        ax.text(reach + dx, pay + dy, name, fontsize=6.0, color=BLUE if hi else SLATE, ha=ha, fontweight="bold" if hi else "normal")
    ax.add_patch(Rectangle((300, 0), req_reach * 1.25 - 300, req_payload, fc="#FEF3C7", ec=ORANGE, lw=0.9, ls="--", alpha=0.55, zorder=1))
    ax.scatter([req_reach], [req_payload], marker="D", s=42, color=ORANGE, zorder=4)
    ax.annotate(f"Besoin : {req_payload:.2f} kg à {req_reach:.0f} mm\n(zone ombrée : portée + 25 %)", (req_reach, req_payload), (1180, 1.0),
                fontsize=6.8, color=ORANGE, va="bottom", arrowprops=dict(arrowstyle="-", color=ORANGE, lw=0.7))
    ax.set_xlim(300, 2150); ax.set_ylim(0, 27)
    ax.set_xlabel("Portée maximale (mm)"); ax.set_ylabel("Charge au poignet (kg)")
    ax.grid(True)
    return _save(fig, path)


def fig_gantt(L, takt, path):
    fig, axs = plt.subplots(2, 1, figsize=(7.2, 3.1), sharex=True, gridspec_kw=dict(hspace=0.55))
    for ax, mode, title in zip(axs, ("double", "simple"), ("Outil double (2 ventouses, pas 221 mm) – solution retenue", "Outil simple (1 ventouse) – solution de référence")):
        ops, tot = F.cycle_timeline(L, mode)
        t_mean = F.calc_cycle(L).rows[mode]["mean"]
        scale = F.CYC.k_safe
        t = 0
        for name, t0, d, kind in ops:
            ax.barh(0, d * scale, left=t0 * scale, color=NAVY2 if kind == "proc" else "#94A3B8", height=0.5, ec="white", lw=0.8)
            if d * scale > 0.2:
                ax.text((t0 + d / 2) * scale, 0, f"{d*scale:.2f}", ha="center", va="center", fontsize=6.3, color="white")
        ax.axvline(takt, color=ORANGE, lw=1.1)
        ax.axvline(t_mean, color=BLUE, lw=1.1, ls="--")
        ax.text(takt + 0.03, 0.46, "takt 4,00 s", color=ORANGE, fontsize=7, va="bottom")
        ax.text(t_mean - 0.03, 0.46, f"cycle moyen {t_mean:.2f} s", color=BLUE, fontsize=7, va="bottom", ha="right")
        ax.set_yticks([]); ax.set_ylim(-0.4, 0.95); ax.set_title(title, fontsize=8, loc="left", color=NAVY)
        ax.spines["left"].set_visible(False)
        ax.set_xlim(0, 4.6)
    axs[1].set_xlabel("temps (s) – coefficient de sécurité 1,10 appliqué à chaque segment")
    from matplotlib.patches import Patch
    axs[0].legend(handles=[Patch(fc="#94A3B8", label="Transfert"), Patch(fc=NAVY2, label="Opération (prise, dépose, insertion)")],
                  loc="lower right", fontsize=6.8, ncol=2, bbox_to_anchor=(1.0, 1.02))
    return _save(fig, path)


def fig_vacuum(v, path):
    fig, ax = plt.subplots(figsize=(6.4, 3.1))
    a = [x / 10 for x in range(0, 121)]
    ax.plot(a, [F.f_th(2, v.m, x, v.mu, v.S) for x in a], color=BLUE, lw=1.3, label="Cas 2 – flacon à plat, translation : m·(g + a/µ)·S")
    ax.plot(a, [F.f_th(3, v.m, x, v.mu, v.S) for x in a], color=SLATE, lw=1.3, label="Cas 3 – flacon vertical, ventouse horizontale : (m/µ)·(g + a)·S")
    ax.plot(a, [F.f_th(1, v.m, x, v.mu, v.S) for x in a], color=SLATE_L, lw=1.0, ls="--", label="Cas 1 – ventouse horizontale, levage : m·(g + a)·S")
    for t, fa, *_ in F.FSGA:
        if t in (33, 43, 53):
            ax.axhline(fa, color=ORANGE if t == 43 else LINE, lw=1.0 if t == 43 else 0.8)
            ax.text(12.1, fa, f"FSGA {t} : {fa:.1f} N", va="center", fontsize=7, color=ORANGE if t == 43 else SLATE_L)
    cols = {1: SLATE_L, 2: BLUE, 3: SLATE}
    for r in v.rows:
        ax.scatter([r["a"]], [r["f"]], s=36, color=cols[r["case"]], zorder=5, ec="white", lw=0.8)
        ax.annotate(f"{r['f']:.1f} N", (r["a"], r["f"]), (r["a"] + 0.25, r["f"] - 2.6), fontsize=6.8, color=cols[r["case"]])
    ax.set_xlim(0, 12); ax.set_ylim(0, 56)
    ax.set_xlabel("Accélération a (m/s²) – points = phases réelles du cycle"); ax.set_ylabel("Force de prise théorique F_TH (N)")
    ax.grid(True, axis="y")
    ax.legend(loc="upper left", fontsize=6.8)
    return _save(fig, path)


def fig_shuttle(sh, path):
    fig, ax = plt.subplots(figsize=(7.0, 1.9))
    T = sh.fill
    for k in range(3):
        side = k % 2   # 0 = A, 1 = B
        t0 = k * T
        ax.barh(side, T, left=t0, color=NAVY2, height=0.5, ec="white")
        ax.text(t0 + T / 2, side, "Remplissage par le robot (9 cales)", ha="center", va="center", color="white", fontsize=6.8)
        other = 1 - side
        # échange sur l'autre convoyeur pendant ce remplissage
        t = t0
        segs = [("Retour", sh.t_leg, SLATE_L), ("Échange externe", sh.t_exch_target, LINE), ("Entrée", sh.t_leg, SLATE_L), ("", sh.t_index, ORANGE)]
        for lab, d, c in segs:
            ax.barh(other, d, left=t, color=c, height=0.5, ec="white")
            if lab:
                ax.text(t + d / 2, other, lab, ha="center", va="center", fontsize=6.2, color=NAVY if c == LINE else "white")
            t += d
        ax.barh(other, t0 + T - t, left=t, color="#F1F5F9", height=0.5, ec="white")
        if t0 + T - t > 4:
            ax.text(t + (t0 + T - t) / 2, other, f"{t0+T-t:.0f} s", ha="center", va="center", fontsize=6.2, color=SLATE)
    ax.set_yticks([0, 1]); ax.set_yticklabels(["Convoyeur A", "Convoyeur B"])
    ax.set_xlim(0, 3 * T); ax.set_xlabel("temps (s) – période de remplissage d'un intercalaire = 9 × 4,00 s = 36 s (orange : indexation ; gris clair : réserve)")
    ax.spines["left"].set_visible(False); ax.tick_params(axis="y", length=0)
    return _save(fig, path)


def fig_architecture(path):
    fig, ax = plt.subplots(figsize=(7.2, 4.1))
    ax.set_xlim(0, 100); ax.set_ylim(0, 58); ax.axis("off")

    def box(x, y, w, h, title, sub="", fc="white", ec=NAVY, tc=NAVY, lw=0.9):
        ax.add_patch(FancyBboxPatch((x, y), w, h, boxstyle="round,pad=0.0,rounding_size=0.8", fc=fc, ec=ec, lw=lw))
        ax.text(x + w / 2, y + h - 2.4 if sub else y + h / 2, title, ha="center", va="center", fontsize=7.4, fontweight="bold", color=tc)
        if sub:
            ax.text(x + w / 2, y + h / 2 - 1.5, sub, ha="center", va="center", fontsize=6.3, color=SLATE, linespacing=1.25)

    def line(x0, y0, x1, y1, c=NAVY, ls="-", lw=1.0):
        ax.plot([x0, x1], [y0, y1], color=c, lw=lw, ls=ls, solid_capstyle="butt")

    # niveau supervision
    box(34, 49, 32, 7, "Supervision / MES", "traçabilité pondérale, ordre de campagne", fc="#F1F5F9")
    # réseau
    ax.add_patch(Rectangle((4, 41.5), 92, 2.2, fc=NAVY, ec="none"))
    ax.text(50, 42.6, "Réseau industriel Ethernet – PROFINET IO / EtherNet-IP (100 Mbit/s)", ha="center", va="center", color="white", fontsize=6.8)
    line(50, 49, 50, 43.7, NAVY)
    # automate
    box(4, 28, 24, 11, "Automate de cellule", "gestion des flux, séquence,\nconvoyeurs, IHM, pesée", fc="#F1F5F9")
    box(34, 28, 26, 11, "Robot LR-10iA/10", "R-30iB Plus Mate + iPendant Touch\nUOP (PNS/RSR), DI/DO, DCS", fc="white", ec=BLUE, lw=1.4)
    box(66, 28, 30, 11, "iRVision 2D (option)", "caméra 5 Mpx GigE sur la zone de prise,\ncorrection x, y, θ", fc="white")
    for x in (16, 47, 81):
        line(x, 39, x, 41.5)
    # niveau terrain
    box(2, 9, 21, 12, "Variateurs convoyeurs", "Interroll EC310 24 V\nentrée + 2 sorties\n(zones, accumulation)")
    box(26, 9, 21, 12, "Boîtier de pesée", "6 entrées analogiques\n6 sorties TOR (poids OK)\nvoyants d'empreinte")
    box(50, 9, 22, 12, "Outil double", "2 × ventouse FSGA 43\n2 × éjecteur SCPS 10\ncapteurs vide / compliance")
    box(75, 9, 22, 12, "Sécurité", "arrêt d'urgence, portes,\nrideaux immatériels\nEMGIN / FENCE (câblé)", ec=ORANGE, tc=ORANGE)
    line(12, 21, 12, 25.2, SLATE); line(12, 25.2, 16, 25.2, SLATE); line(16, 25.2, 16, 28, SLATE)
    line(36, 21, 36, 28, SLATE); line(36, 25.2, 18, 25.2, SLATE)
    line(61, 21, 61, 25.2, SLATE); line(61, 25.2, 47, 25.2, SLATE); line(47, 25.2, 47, 28, SLATE)
    line(86, 21, 86, 24, ORANGE, "--"); line(86, 24, 47, 24, ORANGE, "--"); line(47, 24, 47, 28, ORANGE, "--")
    ax.text(24.5, 22.7, "TOR 24 V", fontsize=6.0, color=SLATE)
    ax.text(87, 22.2, "2 canaux", fontsize=6.0, color=ORANGE, ha="left", va="bottom")
    # légende
    ax.add_patch(Rectangle((4, 2), 3, 1.2, fc=NAVY, ec="none")); ax.text(8.2, 2.6, "Ethernet industriel", fontsize=6.5, va="center", color=SLATE)
    line(30, 2.6, 34, 2.6, SLATE); ax.text(35, 2.6, "E/S TOR 24 V", fontsize=6.5, va="center", color=SLATE)
    line(52, 2.6, 56, 2.6, ORANGE, "--"); ax.text(57, 2.6, "circuit de sécurité", fontsize=6.5, va="center", color=SLATE)
    return _save(fig, path)


def fig_gripper(path, p=F.INPUT):
    fig, axs = plt.subplots(1, 2, figsize=(7.2, 3.1), gridspec_kw=dict(wspace=0.05))
    fs = 6.2
    pitch = p.rack_pitch
    # ---- vue 1 : axe vertical (prise convoyeur / insertion) – vue de côté
    ax = axs[0]; ax.set_aspect("equal"); ax.axis("off"); ax.set_xlim(-250, 250); ax.set_ylim(-60, 330)
    ax.add_patch(Rectangle((-250, 30), 500, 12, fc=GREY_L, ec=SLATE_L, lw=0.6))
    ax.text(-245, 8, "convoyeur / cale", fontsize=fs, color=SLATE)
    ax.add_patch(Rectangle((-60, 252), 120, 28, fc=NAVY, ec="none"))
    ax.text(0, 290, "flasque robot LR-10iA/10", fontsize=fs, ha="center", color=NAVY)
    ax.add_patch(Rectangle((-pitch / 2 - 18, 228), pitch + 36, 24, fc=SLATE, ec="none"))
    for x, lift, loaded in [(-pitch / 2, 0, True), (pitch / 2, 20, False)]:
        ax.add_patch(Rectangle((x - 14, 162 + lift), 28, 66 - lift, fc="#94A3B8", ec="none"))
        ax.add_patch(Rectangle((x - 3, 150 + lift), 6, 14, fc=NAVY, ec="none"))
        ax.add_patch(Polygon([(x - 8, 150 + lift), (x + 8, 150 + lift), (x + 22, 130 + lift), (x - 22, 130 + lift)], fc=BLUE, ec="none"))
    ax.add_patch(Rectangle((-pitch / 2 - 67, 42), 135, 88, fc=ORANGE, ec="none", alpha=0.9))
    x = pitch / 2
    ax.add_patch(Polygon([(x - 8, 150), (x + 8, 150), (x + 22, 130), (x - 22, 130)], fc="none", ec=ORANGE, lw=0.7, ls="--"))
    ax.annotate("", xy=(x + 40, 130), xytext=(x + 40, 150), arrowprops=dict(arrowstyle="<->", color=ORANGE, lw=0.7))
    ax.text(x + 50, 140, "dégagement\n20 mm", fontsize=fs, color=ORANGE, va="center")
    ax.text(-pitch / 2, 205, "G1", fontsize=7.5, ha="center", color="white", fontweight="bold")
    ax.text(pitch / 2, 205, "G2", fontsize=7.5, ha="center", color=NAVY, fontweight="bold")
    ax.text(-pitch / 2, 85, "flacon\nà plat", fontsize=fs, ha="center", va="center", color="white")
    ax.annotate("", xy=(-pitch / 2, -18), xytext=(pitch / 2, -18), arrowprops=dict(arrowstyle="<->", color=SLATE, lw=0.6))
    ax.text(0, -40, "entraxe 221 mm (pas du rack)", fontsize=fs, ha="center", color=SLATE)
    ax.set_title("Prise convoyeur / insertion (axe vertical)", fontsize=7.4, loc="left", color=NAVY)
    # ---- vue 2 : axe horizontal (rack) – vue de dessus
    ax = axs[1]; ax.set_aspect("equal"); ax.axis("off"); ax.set_xlim(-250, 250); ax.set_ylim(-60, 330)
    ax.add_patch(Rectangle((-250, 232), 500, 62, fc=NAVY2, ec="none"))
    ax.text(-245, 304, "rack de pesée (vue de dessus)", fontsize=fs, color=SLATE)
    for x in (-pitch / 2, pitch / 2):
        ax.add_patch(Rectangle((x - 41, 238), 82, 50, fc="#334155", ec="none"))
        ax.add_patch(Rectangle((x - 39, 240), 78, 45, fc=ORANGE, ec="none", alpha=0.95))
        ax.add_patch(Polygon([(x - 22, 230), (x + 22, 230), (x + 8, 210), (x - 8, 210)], fc=BLUE, ec="none"))
        ax.add_patch(Rectangle((x - 14, 142), 28, 68, fc="#94A3B8", ec="none"))
    ax.add_patch(Rectangle((-pitch / 2 - 18, 118), pitch + 36, 24, fc=SLATE, ec="none"))
    ax.add_patch(Rectangle((-8, 100), 16, 18, fc=NAVY, ec="none"))
    ax.add_patch(Rectangle((-60, 72), 120, 28, fc=NAVY, ec="none"))
    ax.text(0, 52, "flasque robot", fontsize=fs, ha="center", color=NAVY)
    ax.text(-pitch / 2 + 28, 176, "G1 : dépose", fontsize=fs, ha="left", color=NAVY, fontweight="bold")
    ax.text(pitch / 2 + 28, 176, "G2 : prise", fontsize=fs, ha="left", color=NAVY, fontweight="bold")
    ax.text(0, 12, "ventouses sur le plastron, face tournée vers le robot ;\nJ6 inverse G1 / G2 à chaque cycle", fontsize=fs, ha="center", color=SLATE)
    ax.set_title("Échange sur le rack (axe horizontal)", fontsize=7.4, loc="left", color=NAVY)
    return _save(fig, path)


def build_figures(cad, L, tool, sel, cyc, vac, sh, outdir):
    out = Path(outdir); out.mkdir(parents=True, exist_ok=True)
    f = {}
    f["takt"] = fig_takt(cad, out / "fig_takt.png")
    f["layout"] = fig_layout(L, out / "fig_layout.png")
    f["robots"] = fig_robots(sel, L, cad.takt, out / "fig_robots.png")
    f["payload"] = fig_payload_reach(out / "fig_payload.png", tool.m_total, L.r_max)
    f["gantt"] = fig_gantt(L, cad.takt, out / "fig_gantt.png")
    f["vacuum"] = fig_vacuum(vac, out / "fig_vacuum.png")
    f["shuttle"] = fig_shuttle(sh, out / "fig_shuttle.png")
    f["archi"] = fig_architecture(out / "fig_archi.png")
    f["gripper"] = fig_gripper(out / "fig_gripper.png")
    return f

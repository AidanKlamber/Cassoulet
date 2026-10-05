#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Génération automatique du rapport d'avant-projet
« Jumeau numérique – Olympiades FANUC AVP BAC+2 2027 » (projet DP27-01, FANUC Fragrance).

Usage
-----
    python generate_rapport.py --zip "Jumeau_Numérique_Olympiades_Fanuc_AVP_BAC2_2027.zip" \
                               --out  Rapport_AVP_Jumeau_Numerique_FANUC_2027.pdf

Ce que fait le script
---------------------
1. extrait l'archive ZIP, inventorie son contenu et récupère les visuels (plans PDF rendus en image,
   figures du cahier des charges, aperçu de la carte mentale, photo robot du catalogue, cas de charge) ;
2. recalcule TOUS les résultats (module fanuc_calculs.py : cadence, implantation, sélection robot,
   temps de cycle, ventouses, pesée, communication) – le texte du rapport est alimenté par ces valeurs ;
3. génère les graphiques épurés (module rapport_figures.py, matplotlib) ;
4. assemble le PDF avec reportlab : couverture, sommaire, en-tête/pied de page avec numérotation X / Y,
   tableaux sobres, encadrés, figures légendées et centrées.

Dépendances : reportlab, matplotlib, pillow, pymupdf, numpy  (voir requirements.txt)
"""
from __future__ import annotations
import argparse
import datetime as dt
import os
import sys
import tempfile
from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_JUSTIFY, TA_LEFT, TA_RIGHT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfgen import canvas as rl_canvas
from reportlab.platypus import (BaseDocTemplate, Frame, Image, KeepTogether, PageBreak, PageTemplate, Paragraph,
                                Spacer, Table, TableStyle, NextPageTemplate, CondPageBreak, Flowable)
from reportlab.platypus.tableofcontents import TableOfContents
from PIL import Image as PILImage

import fanuc_calculs as F
import rapport_figures as R

# --------------------------------------------------------------------------------------
# Charte graphique
# --------------------------------------------------------------------------------------
NAVY = colors.HexColor("#0F172A")
NAVY2 = colors.HexColor("#1E293B")
SLATE = colors.HexColor("#475569")
SLATE_L = colors.HexColor("#64748B")
LINE = colors.HexColor("#CBD5E1")
LINE_L = colors.HexColor("#E2E8F0")
BG = colors.HexColor("#F8FAFC")
BLUE = colors.HexColor("#2563EB")
ORANGE = colors.HexColor("#D97706")

PAGE_W, PAGE_H = A4
M_L = M_R = 22 * mm
M_T, M_B = 26 * mm, 22 * mm
CONTENT_W = PAGE_W - M_L - M_R

pdfmetrics.registerFont(TTFont("Body", R.FONT_FILES["regular"]))
pdfmetrics.registerFont(TTFont("Body-Bold", R.FONT_FILES["bold"]))
pdfmetrics.registerFont(TTFont("Body-Italic", R.FONT_FILES["italic"]))
pdfmetrics.registerFont(TTFont("Body-BoldItalic", R.FONT_FILES["bolditalic"]))
pdfmetrics.registerFontFamily("Body", normal="Body", bold="Body-Bold", italic="Body-Italic", boldItalic="Body-BoldItalic")

NB = " "   # espace insécable


def fr(x, nd=2, sign=False):
    """Format numérique français : virgule décimale, espace insécable pour les milliers."""
    s = f"{x:,.{nd}f}".replace(",", " ").replace(".", ",")
    if sign and x > 0:
        s = "+" + s
    return s


def pct(x, nd=0):
    return fr(x * 100, nd) + NB + "%"


ST = {}
ST["body"] = ParagraphStyle("body", fontName="Body", fontSize=9.2, leading=13.4, textColor=NAVY2, alignment=TA_JUSTIFY, spaceAfter=5)
ST["bodyL"] = ParagraphStyle("bodyL", parent=ST["body"], alignment=TA_LEFT)
ST["small"] = ParagraphStyle("small", parent=ST["body"], fontSize=8, leading=11, textColor=SLATE, alignment=TA_LEFT, spaceAfter=3)
ST["h1"] = ParagraphStyle("h1", fontName="Body-Bold", fontSize=19, leading=23, textColor=NAVY, spaceBefore=0, spaceAfter=10)
ST["h2"] = ParagraphStyle("h2", fontName="Body-Bold", fontSize=12, leading=15, textColor=NAVY, spaceBefore=12, spaceAfter=5)
ST["h3"] = ParagraphStyle("h3", fontName="Body-Bold", fontSize=9.6, leading=12.5, textColor=SLATE, spaceBefore=8, spaceAfter=3)
ST["cap"] = ParagraphStyle("cap", fontName="Body-Italic", fontSize=7.8, leading=10.2, textColor=SLATE_L, alignment=TA_CENTER, spaceBefore=3, spaceAfter=10)
ST["cell"] = ParagraphStyle("cell", fontName="Body", fontSize=7.9, leading=10.2, textColor=NAVY2, alignment=TA_LEFT)
ST["cellR"] = ParagraphStyle("cellR", parent=ST["cell"], alignment=TA_RIGHT)
ST["cellC"] = ParagraphStyle("cellC", parent=ST["cell"], alignment=TA_CENTER)
ST["cellH"] = ParagraphStyle("cellH", fontName="Body-Bold", fontSize=7.7, leading=9.8, textColor=NAVY, alignment=TA_LEFT)
ST["cellHR"] = ParagraphStyle("cellHR", parent=ST["cellH"], alignment=TA_RIGHT)
ST["cellHC"] = ParagraphStyle("cellHC", parent=ST["cellH"], alignment=TA_CENTER)
ST["bullet"] = ParagraphStyle("bullet", parent=ST["body"], leftIndent=11, bulletIndent=1, spaceAfter=2.5, alignment=TA_LEFT)
ST["kpiV"] = ParagraphStyle("kpiV", fontName="Body-Bold", fontSize=17, leading=20, textColor=NAVY, alignment=TA_LEFT)
ST["kpiL"] = ParagraphStyle("kpiL", fontName="Body", fontSize=7.6, leading=9.8, textColor=SLATE, alignment=TA_LEFT)
ST["formula"] = ParagraphStyle("formula", fontName="Body-Italic", fontSize=9, leading=12.5, textColor=NAVY, alignment=TA_LEFT, leftIndent=10, spaceAfter=4)
ST["toc1"] = ParagraphStyle("toc1", fontName="Body-Bold", fontSize=10, leading=17, textColor=NAVY, leftIndent=0)
ST["toc2"] = ParagraphStyle("toc2", fontName="Body", fontSize=8.8, leading=13.5, textColor=SLATE, leftIndent=14)


def P(t, s="body"):
    return Paragraph(t, ST[s])


def B(items, s="bullet"):
    return [Paragraph(t, ST[s], bulletText="–") for t in items]


class Rule(Flowable):
    def __init__(self, w=None, color=LINE, thick=0.5, space=4):
        super().__init__(); self.w = w; self.color = color; self.thick = thick; self.space = space

    def wrap(self, aw, ah):
        self.width = self.w or aw
        return self.width, self.space * 2

    def draw(self):
        self.canv.setStrokeColor(self.color); self.canv.setLineWidth(self.thick)
        self.canv.line(0, self.space, self.width, self.space)


def H1(t, new=True):
    return ([PageBreak()] if new else []) + [Heading(t, "h1", 0), Rule(color=NAVY, thick=1.2, space=2), Spacer(1, 4)]


def H2(t):
    return [Heading(t, "h2", 1)]


def H3(t):
    return [Paragraph(t, ST["h3"])]


class Heading(Paragraph):
    """Paragraphe qui alimente le sommaire."""
    def __init__(self, text, style, level):
        super().__init__(text, ST[style])
        self._toc_level = level
        self._toc_text = text


def callout(text, kind="note"):
    col = {"note": BLUE, "warn": ORANGE, "ok": SLATE}[kind]
    title = {"note": "Remarque", "warn": "Point d'attention", "ok": "Conclusion"}[kind]
    para = Paragraph(f"<font name='Body-Bold' color='{col.hexval().replace('0x', '#')}'>{title}.</font>&nbsp; {text}",
                     ParagraphStyle("co", parent=ST["body"], fontSize=8.7, leading=12.4, alignment=TA_LEFT, spaceAfter=0))
    t = Table([[para]], colWidths=[CONTENT_W])
    t.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, -1), BG), ("LINEBEFORE", (0, 0), (0, -1), 2.2, col),
                           ("LEFTPADDING", (0, 0), (-1, -1), 9), ("RIGHTPADDING", (0, 0), (-1, -1), 8),
                           ("TOPPADDING", (0, 0), (-1, -1), 6), ("BOTTOMPADDING", (0, 0), (-1, -1), 6)]))
    return [Spacer(1, 3), t, Spacer(1, 7)]


def table(rows, widths, header=True, right=(), center=(), zebra=False, bold_last=False, hl_rows=(), repeat=True):
    """Tableau sobre : filets fins gris clair, en-tête marine."""
    data = []
    for i, r in enumerate(rows):
        line = []
        for j, c in enumerate(r):
            if isinstance(c, Flowable):
                line.append(c); continue
            style = "cell"
            if header and i == 0:
                style = "cellHR" if j in right else "cellHC" if j in center else "cellH"
            else:
                style = "cellR" if j in right else "cellC" if j in center else "cell"
            txt = str(c)
            if bold_last and i == len(rows) - 1:
                txt = f"<b>{txt}</b>"
            line.append(Paragraph(txt, ST[style]))
        data.append(line)
    tw = sum(widths)
    cw = [w / tw * CONTENT_W for w in widths]
    t = Table(data, colWidths=cw, repeatRows=1 if (header and repeat) else 0)
    cmds = [("VALIGN", (0, 0), (-1, -1), "MIDDLE"), ("TOPPADDING", (0, 0), (-1, -1), 3.2), ("BOTTOMPADDING", (0, 0), (-1, -1), 3.2),
            ("LEFTPADDING", (0, 0), (-1, -1), 4), ("RIGHTPADDING", (0, 0), (-1, -1), 4),
            ("LINEBELOW", (0, 0), (-1, -1), 0.35, LINE_L)]
    if header:
        cmds += [("LINEABOVE", (0, 0), (-1, 0), 0.9, NAVY), ("LINEBELOW", (0, 0), (-1, 0), 0.9, NAVY)]
    else:
        cmds += [("LINEABOVE", (0, 0), (-1, 0), 0.9, NAVY)]
    cmds += [("LINEBELOW", (0, -1), (-1, -1), 0.9, NAVY)]
    if zebra:
        for i in range(1 if header else 0, len(rows)):
            if i % 2 == 0:
                cmds.append(("BACKGROUND", (0, i), (-1, i), BG))
    for i in hl_rows:
        cmds.append(("BACKGROUND", (0, i), (-1, i), colors.HexColor("#EFF6FF")))
    t.setStyle(TableStyle(cmds))
    return t


_fig_counter = {"n": 0}


def figure(path, width_mm, caption, max_h_mm=None):
    _fig_counter["n"] += 1
    n = _fig_counter["n"]
    if not path or not os.path.exists(path):
        return [P(f"<i>[Figure {n} indisponible : {caption}]</i>", "small")]
    im = PILImage.open(path)
    w = width_mm * mm
    h = w * im.height / im.width
    if max_h_mm and h > max_h_mm * mm:
        h = max_h_mm * mm; w = h * im.width / im.height
    img = Image(path, width=w, height=h)
    img.hAlign = "CENTER"
    cap = Paragraph(f"<b>Figure {n}</b> – {caption}", ST["cap"])
    return [KeepTogether([Spacer(1, 3), img, cap])]


def figure_row(items, total_mm, caption, h_mm=42):
    """Plusieurs images côte à côte (hauteur commune), centrées, avec une légende unique."""
    _fig_counter["n"] += 1
    n = _fig_counter["n"]
    imgs, ws = [], []
    for p in items:
        if p and os.path.exists(p):
            im = PILImage.open(p)
            imgs.append((p, im.width / im.height))
    if not imgs:
        return [P(f"<i>[Figure {n} indisponible]</i>", "small")]
    ratio = sum(r for _, r in imgs)
    h = min(h_mm * mm, (total_mm * mm) / ratio)
    cells = [Image(p, width=h * r, height=h) for p, r in imgs]
    t = Table([cells], colWidths=[h * r + 4 for _, r in imgs])
    t.setStyle(TableStyle([("ALIGN", (0, 0), (-1, -1), "CENTER"), ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                           ("LEFTPADDING", (0, 0), (-1, -1), 2), ("RIGHTPADDING", (0, 0), (-1, -1), 2),
                           ("TOPPADDING", (0, 0), (-1, -1), 0), ("BOTTOMPADDING", (0, 0), (-1, -1), 0)]))
    t.hAlign = "CENTER"
    return [KeepTogether([Spacer(1, 3), t, Paragraph(f"<b>Figure {n}</b> – {caption}", ST["cap"])])]


def kpi_tiles(items, cols=3):
    cells = []
    for v, l in items:
        cells.append([Paragraph(v, ST["kpiV"]), Paragraph(l, ST["kpiL"])])
    rows = [cells[i:i + cols] for i in range(0, len(cells), cols)]
    while len(rows[-1]) < cols:
        rows[-1].append("")
    data = []
    for r in rows:
        data.append([c if c == "" else [c[0], Spacer(1, 2), c[1]] for c in r])
    t = Table(data, colWidths=[CONTENT_W / cols] * cols)
    t.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "TOP"), ("LINEABOVE", (0, 0), (-1, 0), 1.4, BLUE),
                           ("LINEABOVE", (0, 1), (-1, -1), 0.4, LINE), ("LEFTPADDING", (0, 0), (-1, -1), 2), ("RIGHTPADDING", (0, 0), (-1, -1), 10),
                           ("TOPPADDING", (0, 0), (-1, -1), 7), ("BOTTOMPADDING", (0, 0), (-1, -1), 8)]))
    return t


# --------------------------------------------------------------------------------------
# Gabarit de page, en-tête / pied de page « X / Y »
# --------------------------------------------------------------------------------------
class NumberedCanvas(rl_canvas.Canvas):
    def __init__(self, *a, **k):
        super().__init__(*a, **k); self._saved = []

    def showPage(self):
        self._saved.append(dict(self.__dict__)); self._startPage()

    def save(self):
        total = len(self._saved)
        for st in self._saved:
            self.__dict__.update(st)
            self._decorate(total)
            super().showPage()
        super().save()

    def _decorate(self, total):
        n = self._pageNumber
        if n == 1:
            return
        self.setStrokeColor(LINE); self.setLineWidth(0.5)
        self.setFont("Body", 7.6); self.setFillColor(SLATE_L)
        y = PAGE_H - 15 * mm
        self.drawString(M_L, y, "Jumeau numérique – AVP Olympiades FANUC 2027")
        self.drawRightString(PAGE_W - M_R, y, "Projet DP27-01 · FANUC Fragrance")
        self.line(M_L, y - 3, PAGE_W - M_R, y - 3)
        y2 = 13 * mm
        self.line(M_L, y2 + 8, PAGE_W - M_R, y2 + 8)
        self.drawString(M_L, y2, "Rapport d'analyse et de dimensionnement · version 1.0")
        self.setFont("Body-Bold", 7.8); self.setFillColor(NAVY)
        self.drawRightString(PAGE_W - M_R, y2, f"{n} / {total}")


class Doc(BaseDocTemplate):
    def __init__(self, fn, **kw):
        super().__init__(fn, pagesize=A4, leftMargin=M_L, rightMargin=M_R, topMargin=M_T, bottomMargin=M_B,
                         title="Jumeau numérique – AVP Olympiades FANUC 2027", author="Équipe projet",
                         subject="Analyse du dossier DP27-01 et dimensionnement de la cellule", **kw)
        fr_ = Frame(M_L, M_B, CONTENT_W, PAGE_H - M_T - M_B, id="f", leftPadding=0, rightPadding=0, topPadding=0, bottomPadding=0)
        fr0 = Frame(M_L, M_B, CONTENT_W, PAGE_H - 30 * mm - M_B, id="f0", leftPadding=0, rightPadding=0, topPadding=0, bottomPadding=0)
        self.addPageTemplates([PageTemplate(id="cover", frames=[fr0], onPage=self._cover_bg), PageTemplate(id="main", frames=[fr_])])

    def _cover_bg(self, c, d):
        c.saveState()
        c.setFillColor(NAVY); c.rect(0, PAGE_H - 11 * mm, PAGE_W, 11 * mm, stroke=0, fill=1)
        c.setFillColor(BLUE); c.rect(M_L, PAGE_H - 11 * mm, 34 * mm, 1.6 * mm, stroke=0, fill=1)
        c.restoreState()

    def afterFlowable(self, fl):
        if isinstance(fl, Heading):
            key = f"h{self.page}-{abs(hash(fl._toc_text)) % 100000}"
            self.canv.bookmarkPage(key)
            self.notify("TOCEntry", (fl._toc_level, fl._toc_text, self.page, key))


# --------------------------------------------------------------------------------------
# Contenu du rapport
# --------------------------------------------------------------------------------------
def build_story(ctx):
    cad, L, tool, sel, wts, cyc, vac, wgh, sh, com, A, F_, inv = (ctx[k] for k in
        ("cad", "L", "tool", "sel", "wts", "cyc", "vac", "wgh", "sh", "com", "assets", "figs", "inv"))
    INP = F.INPUT
    m_d, m_s = cyc.rows["double"], cyc.rows["simple"]
    margin_d = 1 - m_d["mean"] / cad.takt
    margin_s = 1 - m_s["mean"] / cad.takt
    rate_cap = 3600 / m_d["mean"]
    chosen = next(r for r in sel if r["name"] == "LR-10iA/10")
    cup = vac.cup
    S = []

    # ---------------------------- COUVERTURE ----------------------------
    S += [Spacer(1, 24 * mm), P("<font color='#2563EB'><b>AVANT-PROJET · OLYMPIADES FANUC 2027 · BAC+2 CRSA</b></font>", "bodyL"), Spacer(1, 4),
          Paragraph("Jumeau numérique de la cellule d'encoffretage robotisée", ParagraphStyle("t", fontName="Body-Bold", fontSize=29, leading=34, textColor=NAVY, spaceAfter=10)),
          Paragraph("Analyse du dossier technique, calculs de dimensionnement et réponses aux lots 1 à 4 du projet DP27-01 – FANUC Fragrance (Grasse-les-Prés)",
                    ParagraphStyle("st", fontName="Body", fontSize=12.5, leading=17, textColor=SLATE, spaceAfter=18)),
          Rule(color=NAVY, thick=1.2, space=2), Spacer(1, 8)]
    cover_img = A.get("cdc_flacon_3q")
    meta = [["Projet", "DP27-01 – îlot d'encoffrettage de flacons « FANUC ROBOT PARFUM »"],
            ["Objet", "Choix du robot, implantation, temps de cycle, préhenseur, recalage, châssis, communication"],
            ["Jalons", "Restitution 5 janvier 2027 · revue d'étude 11–19 janvier 2027 · lancement 1er avril 2027"],
            ["Livrables visés", "Présentation technique (.pdf/.ppt) et cellule ROBOGUIDE (.rgx)"],
            ["Édition", f"Version 1.0 du {dt.date.today().strftime('%d/%m/%Y')} – hypothèses repérées « HYP »"]]
    S += [table(meta, [18, 82], header=False)]
    if cover_img and os.path.exists(cover_img):
        im = PILImage.open(cover_img)
        w = 110 * mm; h = w * im.height / im.width
        S += [Spacer(1, 12 * mm), Image(cover_img, width=w, height=h, hAlign="CENTER"),
              Paragraph("Flacon « FANUC ROBOT PARFUM » – visuel du cahier des charges.", ST["cap"])]
    S += [NextPageTemplate("main"), PageBreak()]

    # ---------------------------- SOMMAIRE ----------------------------
    S += [Paragraph("Sommaire", ST["h1"]), Rule(color=NAVY, thick=1.2, space=2), Spacer(1, 6)]
    toc = TableOfContents()
    toc.levelStyles = [ST["toc1"], ST["toc2"]]
    toc.dotsMinLevel = 0
    S += [toc, PageBreak()]

    # ---------------------------- 1. RÉSUMÉ EXÉCUTIF ----------------------------
    S += H1("1. Résumé exécutif", new=False)
    S += [P("FANUC Fragrance doit automatiser l'insertion de ses flacons de parfum de prestige (380" + NB + "g, verre / ABS laqué / cuir, <b>zéro rayure</b>) dans les cales "
            "thermoformées de ses coffrets. L'opération, aujourd'hui manuelle, est le goulot d'étranglement de la ligne de conditionnement secondaire et expose les opérateurs "
            "aux TMS. L'avant-projet demande une cellule autonome, fixée au sol, qui assure le transfert unitaire des flacons depuis <b>un seul convoyeur d'entrée</b> vers "
            "<b>deux convoyeurs d'évacuation</b>, avec contrôle pondéral à ±" + NB + "2" + NB + "g et insertion par encliquetage à 5" + NB + "N."),
          P(f"Le dimensionnement de la campagne ({fr(INP.volume, 0)} coffrets en {INP.days} jours ouvrés, 2×8, TRS {pct(INP.trs)}) conduit à un <b>takt de {fr(cad.takt)}" + NB + "s par flacon</b>, soit "
            f"<b>{fr(cad.rate_h, 0)} pièces/h</b> : exactement la cadence du convoyeur d'amenée. La cellule ne dispose donc d'<b>aucune marge amont</b> ; toute la robustesse doit venir du temps de cycle du robot.")]
    S += [Spacer(1, 3), kpi_tiles([
        (f"{fr(cad.takt)} s", "takt requis par coffret (887 400 s productives / 221 850)"),
        (f"{fr(cad.rate_h, 0)} /h", f"débit requis = cadence convoyeur ; {fr(cad.per_day, 0)} coffrets/jour"),
        (f"{fr(m_d['mean'])} s", f"temps de cycle moyen estimé (outil double) – marge {pct(margin_d)} sur le takt"),
        ("LR-10iA/10", "FANUC, 10 kg, 1 101 mm, ±0,01 mm, contrôleur R-30iB Plus Mate"),
        ("2,5 × 1,5 m", "emprise au sol de la cellule complète, hauteur ≤ 2,2 m, convoyeurs de transport à 900 mm"),
        (f"2 × FSGA {cup['type']}", f"ventouses sur le plastron, F_TH = {fr(vac.f_req, 1)} N pour {fr(cup['f'], 1)} N disponibles"),
    ])]
    S += H3("Décisions de conception proposées")
    S += B([f"<b>Robot</b> : FANUC LR-10iA/10 (6 axes), au sol sur rehausse ; portée utilisée {pct(chosen['util_reach'])} (r max = {fr(L.r_max, 0)} mm). Alternative de repli : M-10iD/12.",
            "<b>Implantation</b> en « T » : entrée au sud, deux convoyeurs de sortie face à face (est / ouest) à 1" + NB + "200" + NB + "mm d'entraxe, rack de pesée au nord.",
            f"<b>Préhenseur double</b> : deux ventouses à soufflets FSGA {cup['type']} au pas du rack (221 mm), prenant le flacon par son <b>plastron</b> (la face de tête est trop petite pour tenir le flacon), "
            f"éjecteurs SCPS 10, compliance axiale à 1" + NB + "N/mm pour l'encliquetage à 5" + NB + "N.",
            f"<b>Cycle</b> : {fr(m_d['mean'])} s (outil double) contre {fr(m_s['mean'])} s avec un outil simple – ce dernier ne laisse que {pct(margin_s)} de marge et n'est pas retenu.",
            "<b>Pesée</b> : un flacon séjourne un cycle complet sur l'empreinte (" + fr(wgh.dwell) + NB + "s) pour 2" + NB + "s requises ; seules 2 empreintes sur 6 sont nécessaires.",
            "<b>Communication</b> : PROFINET / EtherNet-IP entre automate et robot (UOP, sélection de programme PNS), E/S TOR câblées pour les signaux rapides, sécurité câblée (EMGIN, FENCE)."])
    S += callout("Les temps de cycle sont issus d'un modèle analytique (trapèze de vitesse + rotation de l'axe J1, coefficient de sécurité 1,10). Ils dimensionnent l'avant-projet "
                 "mais <b>ne remplacent pas la simulation ROBOGUIDE</b>, qui reste le livrable 2 et la validation contractuelle du temps de cycle.", "warn")
    S += [P("<b>Incohérences relevées dans le dossier</b> (détail au §2.3) : masse du flacon 380" + NB + "g (CDC) contre 180" + NB + "g (cartouches des plans) ; trois des quatre modèles CSB cités au CDC "
            "sont absents de l'archive ; plastron décrit « lisse et étanche » alors que son grain atteint 0,5" + NB + "mm. Chacune est traitée par une hypothèse explicite et une action de levée de doute.")]

    # ---------------------------- 2. ANALYSE DU DOSSIER ----------------------------
    S += H1("2. Analyse détaillée du dossier technique")
    S += H2("2.1 Inventaire des ressources de l'archive")
    S += [P(f"L'archive contient {len(inv)} fichiers répartis en quatre dossiers. Le tableau précise le rôle de chacun et l'usage qui en est fait dans cette étude.")]
    rows = [["Fichier", "Nature", "Rôle dans le projet", "Exploitation"],
            ["Flacon_ENCA2701_sept2026.pdf", "Cahier des charges fonctionnel (9 p.)", "Exigences produit, cadence, synoptique, contraintes cellule, lots 1 à 4, jalons", "Source principale : §3 à §5"],
            ["FF-2027-BTL-001.pdf", "Plan A3 du flacon", "135 × 77,9 × 45 mm ; torse 54 mm ; tête 45 mm au sommet ; masse indiquée 180 g", "Choix des surfaces de prise (§3.7)"],
            ["FF-2027-PKG-001.pdf", "Plan A3 de l'intercalaire", "710 × 620 × 30 mm, 9 alvéoles 211 × 181 mm, POM-C", "Poste de dépose, pas des cales"],
            ["FF-2027-PKG-002.pdf", "Plan A3 du thermoformé", "Cale 210 × 180 mm, PS choc 2 mm, alvéoles flacon (gauche) et gel (droite)", "Jeu d'insertion, tolérances"],
            ["FF-2027-PKG-003.pdf", "Plan A3 du rack de mesure", "1 326 × 150 × 98 mm, 6 empreintes au pas de 221 mm, POM-C", "Poste de pesée, pas du préhenseur"],
            ["parts_csb/flacon.CSB", "Modèle 3D ROBOGUIDE", "Seul des quatre CSB listés au CDC §7 (rack, thermoformé, intercalaire absents)", "Import dans la cellule ; modélisation des 3 autres pièces"],
            ["Projet Olympiades … 2027.mvdx", "Carte mentale MindView", "Métiers, unités de production (5), lots ; héritage d'une édition 2018 (« bocaux »)", "Contrôle de couverture des métiers"],
            ["07 ACT Ressources complémentaires_CRSA.docx", "Fiche ressources", "Typologie de robots, formules de ventouse, ventouses FSGA, éjecteurs SCPS, distributeurs, convoyeur Interroll 3500", "Formules et composants du §3.7 ; réponses du §4"],
            ["Catalogue Robots Fanuc OF27.pdf", "Catalogue (56 p.)", "Gamme LR Mate, LR-10, M-10iD, CRX, delta, SCARA ; contrôleurs R-30iB Plus ; iRVision ; DCS ; ROBOGUIDE", "Sélection du robot (§3.4)"],
            ["Manuel de préconisation intégration.pdf", "Présentation FANUC (15 p.)", "Règles de charge embarquée, socle, pneumatique, électrique, logiciel (ACC, CNT, HOLD)", "Hypothèses d'intégration, §3.9 et §5"],
            ["Manuel d'aide TPE_Olympiades AVP_2025.pdf", "Manuel de programmation (112 p.)", "Repères TOOL/USER, instructions, E/S, UOP méthode OTHER (PNS)", "Architecture de communication (§3.10)"],
            ["Création de vidéo pour cellule Roboguide.pdf", "Procédure (2 p.)", "Enregistrement AVI 1680 × 1050 ; le temps affiché sur l'AVI n'est pas le temps de cycle", "Recommandations ROBOGUIDE (§5.1)"],
            ["Procédure de sauvegarde au format .rgx.pdf", "Procédure (1 p.)", "File > Package Cell > Compressed Cell → nom_de_la_cellule.rgx", "Livrable 2 (§4)"]]
    S += [table(rows, [24, 15, 38, 23], zebra=True)]
    S += H2("2.2 Décomposition en sous-systèmes")
    rows = [["Sous-système", "Fonction et périmètre", "Exigences structurantes", "Lot"],
            ["Alimentation", "Convoyeur d'entrée 700 mm, flacons couchés par groupes de 18 (rangées de 3), accumulation sans pression", "900 flacons/h ; pas 196 mm, rotation ±2°, ±2 mm", "Lot 2"],
            ["Repérage / recalage", "Correction de position et d'orientation du flacon couché avant prise", "Prise indexée et répétable ; aucune rayure", "Lots 2 et 3"],
            ["Cellule robotisée", "Robot, cinématique, trajectoires, temps de cycle", "Takt 4,00 s ; évitement de collision total", "Lot 1"],
            ["Préhenseur", "Outil en bout de bras, vide, compliance", "Zéro rayure ; encliquetage 5 N ; dépose à 0,1 mm", "Lot 3"],
            ["Poste de pesée", "Rack à 6 empreintes + boîtier 6 entrées analogiques / 6 sorties TOR", "±2 g ; attente de 2 s ; voyants", "Lots 1 et 4"],
            ["Dépose / évacuation", "2 convoyeurs aller-retour 900 mm, intercalaires de 9 cales", "Indexation ; un seul flux d'entrée, deux sorties", "Lots 1 et 2"],
            ["Châssis et sécurité", "Structure fixée au sol, protections, accès", "2 500 × 1 500 × 2 200 mm ; convoyeurs à 900 ± 20 mm", "Lot 2"],
            ["Communication / IT", "Robot, automate, pesée, vision, sécurité, traçabilité", "Traçabilité unitaire complète", "Lot 4"],
            ["Jumeau numérique", "Cellule ROBOGUIDE : cinématique, collisions, cycle", "Livrable 2 au format .rgx", "Livrables"]]
    S += [table(rows, [17, 38, 35, 10])]
    S += figure(A.get("mindmap_wide") or A.get("mindmap"), 165, "Carte mentale du dossier (aperçu du fichier .mvdx, découpé en trois colonnes) : métiers, cinq unités de production et lots à concevoir.", max_h_mm=100)

    S += H2("2.3 Données consolidées et incohérences du dossier")
    rows = [["N°", "Constat", "Impact", "Traitement retenu"],
            ["1", "Masse du flacon : 380 g au CDC §1.1 et §6.1 ; 180 g dans les cartouches des quatre plans (la cale, le rack et l'intercalaire portent aussi « 180 g » : valeur par défaut du gabarit)", "Dimensionnement du vide et de la charge utile", "380 g retenu (cas défavorable) ; à confirmer par écrit auprès du support"],
            ["2", "CDC §7 : quatre CSB annoncés ; l'archive ne contient que flacon.CSB", "Jumeau numérique incomplet", "Modéliser rack, cale et intercalaire d'après les plans, ou demander les fichiers (Olympiade_France@fanuc.eu)"],
            ["3", "Plastron frontal décrit « surface lisse, plane, étanche » mais grain de 0,2 à 0,5 mm", "Étanchéité du vide incertaine", "Soufflet souple en silicone + éjecteur à fort débit ; essai sur échantillon obligatoire"],
            ["4", "Cale 210 × 180 mm dans une alvéole de 211 × 181 mm, tolérance ±0,5 mm", "Jeu nominal 0,5 mm par côté, nul au pire cas", "Aucune reprise de position sur la cale ; compliance latérale de l'outil"],
            ["5", "Cadence convoyeur = 900/h = débit requis (takt 4,00 s)", "Aucune marge de débit amont", "Cycle cible ≤ 3,6 s (marge ≥ 10 %), accumulation en amont"],
            ["6", "Entraxe des convoyeurs de sortie « à définir »", "Dépend de l'implantation", f"Entraxe de {fr(2 * L.fill_dx, 0)} mm (fill A/B de part et d'autre du robot)"],
            ["7", "Convoyeurs de sortie « largeur 900 mm » ; Interroll 3500 : TW = BF + 80 mm (BF 840 → 920 mm)", "Possible dépassement de 20 mm si 900 est la largeur hors tout", "Largeur utile 840 mm acceptée pour l'intercalaire de 710 mm ; à préciser"],
            ["8", "Cotes de la figure 3 : 196 ± 2 mm et 30 ± 2 mm, sans définition explicite", "Pas des flacons dans la rangée", f"Interprétées : 196 mm entre axes de flacons, 30 mm entre rangées (pas {fr(cad.row_pitch_mm, 0)} mm) ; largeur de rangée {fr(cad.row_width_mm, 0)} mm < 700 mm"],
            ["9", "Numérotation des lots : CDC 2027 (1 robot, 2 châssis, 3 préhenseur, 4 communication) ≠ carte mentale (2 préhension, 3 châssis, 4 automatisme)", "Risque de confusion de livrables", "Numérotation du CDC 2027 suivie dans tout le rapport"],
            ["10", "Carte mentale : « bocaux », « agro-alimentaire » (reprise 2018)", "Aucun", "Ignoré pour le fond, conservé pour la répartition des métiers"]]
    S += [table(rows, [4, 40, 24, 32], zebra=True)]
    S += figure_row([A.get("cdc_flacon_face"), A.get("cdc_cale"), A.get("cdc_coffret")], 165,
                    "Visuels du cahier des charges : flacon (gros plan sur la tête et le plastron), cale thermoformée et coffret fini.", h_mm=40)
    S += figure(A.get("plan_flacon"), 128, "Plan FF-2027-BTL-001 du flacon : 135 mm de haut, 77,9 mm avec les bras, 54 mm de torse, 45 mm au sommet de la tête.")
    S += figure_row([A.get("plan_interc"), A.get("plan_thermo"), A.get("plan_rack")], 168,
                    "Plans FF-2027-PKG-001 (intercalaire, 9 alvéoles), PKG-002 (thermoformé 210 × 180) et PKG-003 (rack de mesure, 6 empreintes au pas de 221 mm) – vignettes, cotes principales reprises au §2.1.", h_mm=42)

    # ---------------------------- 3. CALCULS ----------------------------
    S += H1("3. Calculs techniques détaillés et justifications")
    S += H2("3.1 Cadence, temps disponible et takt")
    S += [P("Hypothèse : un poste « 8 h » dure 480 min dont 45 min de pause (CDC §2) ; un coffret contient un seul flacon ; les 20 jours ouvrés sont travaillés en 2×8. "
            "Le takt est le temps productif disponible divisé par le volume à produire.")]
    S += [P("Takt = (jours × postes × durée nette d'un poste × TRS) ÷ volume", "formula")]
    rows = [["Étape", "Formule", "Résultat"],
            ["Durée nette d'un poste", "480 min − 45 min", f"{fr(cad.shift_net_min, 0)} min = {fr(cad.shift_net_min / 60, 2)} h"],
            ["Temps net par jour", f"2 postes × {fr(cad.shift_net_min, 0)} min", f"{fr(cad.day_min, 0)} min = {fr(cad.day_h, 1)} h = {fr(cad.day_s, 0)} s"],
            ["Temps net de campagne", f"{INP.days} jours × {fr(cad.day_min, 0)} min", f"{fr(cad.camp_h, 0)} h = {fr(cad.camp_s, 0)} s"],
            ["Temps productif (TRS 85 %)", f"{fr(cad.camp_s, 0)} s × 0,85", f"{fr(cad.prod_h, 1)} h = {fr(cad.prod_s, 0)} s"],
            ["<b>Takt</b>", f"{fr(cad.prod_s, 0)} s ÷ {fr(INP.volume, 0)} coffrets", f"<b>{fr(cad.takt, 3)} s</b>"],
            ["Débit horaire requis", "3 600 s ÷ takt", f"{fr(cad.rate_h, 0)} pièces/h (= convoyeur d'amenée)"],
            ["Takt brut (TRS = 100 %)", f"{fr(cad.camp_s, 0)} s ÷ {fr(INP.volume, 0)}", f"{fr(cad.takt_gross, 3)} s ({fr(cad.rate_h_gross, 0)} pièces/h)"],
            ["Production par jour / par poste", f"{fr(INP.volume, 0)} ÷ {INP.days} ; ÷ 2", f"{fr(cad.per_day, 1)} / {fr(cad.per_shift, 1)} coffrets"],
            ["Intercalaires à produire", f"{fr(INP.volume, 0)} ÷ 9", f"{fr(cad.n_interc, 0)} (soit {fr(cad.n_interc_conv, 0)} par convoyeur)"],
            ["Rythme d'arrivée des flacons", "rangée de 3 ; groupe de 18", f"une rangée toutes les {fr(cad.row_period_s, 0)} s ; un groupe toutes les {fr(cad.group_period_s, 0)} s"]]
    S += [table(rows, [34, 33, 33], right=(2,), hl_rows=(5,))]
    S += figure(F_["takt"], 150, "Bilan temporel de la campagne : le takt de 4,00 s est la conséquence directe du volume, du calendrier et du TRS de 85 %.")
    S += callout(f"Le débit requis ({fr(cad.rate_h, 0)}/h) est <b>identique</b> à la cadence paramétrée du convoyeur : l'amont ne peut pas rattraper un retard. Le TRS de 85 % n'est tenable que si le "
                 f"temps de cycle réel du robot est nettement inférieur à {fr(cad.takt)} s (objectif de conception : ≤ {fr(0.9 * cad.takt)} s, soit 10 % de marge). Un budget de TRS illustratif "
                 f"(disponibilité 90 % × performance 96 % × qualité 98,5 %) donne 85,1 % ; il montre que les micro-arrêts et rebuts pondéraux doivent rester sous 15 % du temps.", "warn")

    S += H2("3.2 Flux d'intercalaires et synchronisation des convoyeurs de sortie")
    S += [P(f"Un intercalaire reçoit 9 flacons : à la cadence cible, le robot l'occupe <b>9 × {fr(cad.takt)} = {fr(sh.fill, 0)} s</b>. Pendant ce temps, l'autre convoyeur doit "
            f"renvoyer l'intercalaire plein, laisser s'effectuer l'échange (hors cellule), réintroduire un intercalaire vide et l'indexer. Budget disponible = {fr(sh.fill, 0)} s.")]
    rows = [["Poste du budget", "Valeur", "Hypothèse / calcul"],
            ["Course utile par convoyeur", f"{fr(sh.L_travel, 1)} m", "HYP – fourchette du fill vers la sortie"],
            ["Vitesse de convoyage", f"{fr(sh.v, 2)} m/s", "HYP – Interroll EC310 : 0,1 à 1,0 m/s"],
            ["Trajet simple", f"{fr(sh.t_leg, 1)} s", "1,8 m ÷ 0,30 m/s ; deux trajets (retour, entrée)"],
            ["Indexation (butée + 2 pions)", f"{fr(sh.t_index, 1)} s", "HYP"],
            ["Durée maximale de l'échange externe", f"{fr(sh.t_exch_max, 0)} s", f"{fr(sh.fill, 0)} − 2 × {fr(sh.t_leg, 0)} − {fr(sh.t_index, 0)}"],
            ["Échange visé (opérateur ou automatisme amont)", f"{fr(sh.t_exch_target, 0)} s", "HYP"],
            ["<b>Réserve par période</b>", f"<b>{fr(sh.margin, 0)} s</b>", f"soit {pct(sh.margin / sh.fill)} de la période de {fr(sh.fill, 0)} s"]]
    S += [table(rows, [38, 14, 48], right=(1,), hl_rows=(7,))]
    S += figure(F_["shuttle"], 160, "Chronogramme des deux convoyeurs aller-retour : l'échange d'un convoyeur est entièrement masqué par le remplissage de l'autre.")

    S += H2("3.3 Implantation, emprise et portée requise")
    S += [P("L'implantation est libre mais doit tenir dans 2 500 × 1 500 mm. Les convoyeurs de sortie (900 mm) ne pouvant être côte à côte dans 1 500 mm, ils sont placés <b>face à face</b> "
            "(ouest et est) ; l'entrée (700 mm) arrive du sud entre leurs extrémités, le rack de pesée est au nord à 30 mm de leur flanc. Le robot occupe le centre. "
            f"Tous les postes de travail se trouvent entre {fr(L.r_min, 0)} et {fr(L.r_max, 0)} mm de l'axe J1.")]
    S += figure(F_["layout"], 163, "Implantation proposée (vue de dessus, à l'échelle). Les alvéoles de chaque intercalaire sont au pas 181 × 211 mm.")
    ang = lambda p: __import__("math").degrees(__import__("math").atan2(p[1] - L.robot[1], p[0] - L.robot[0]))
    rows = [["Poste", "Position (x ; y) mm", "Rayon à l'axe J1", f"% de la portée ({chosen['reach']} mm)"],
            ["P – rangée de prise (3 flacons)", f"{fr(L.pick_pts[0][0], 0)} à {fr(L.pick_pts[2][0], 0)} ; {fr(L.row_y, 0)}", f"{fr(min(L.rad_pick), 0)} – {fr(max(L.rad_pick), 0)} mm", pct(max(L.rad_pick) / chosen['reach'])],
            ["R – empreintes 3 et 4 du rack", f"{fr(L.imprints[2][0], 0)} et {fr(L.imprints[3][0], 0)} ; {fr(L.rack_y, 0)}", f"{fr(L.rad_rack_used[0], 0)} mm", pct(L.rad_rack_used[0] / chosen['reach'])],
            ["R – empreintes extrêmes (secours)", f"{fr(L.imprints[0][0], 0)} et {fr(L.imprints[5][0], 0)} ; {fr(L.rack_y, 0)}", f"{fr(max(L.rad_rack_all), 0)} mm", pct(max(L.rad_rack_all) / chosen['reach'])],
            ["C1 – 9 alvéoles, convoyeur A", f"centre {fr(L.fill['W'][0], 0)} ; {fr(L.fill['W'][1], 0)}", f"{fr(min(L.rad_alv['W']), 0)} – {fr(max(L.rad_alv['W']), 0)} mm", pct(max(L.rad_alv['W']) / chosen['reach'])],
            ["C2 – 9 alvéoles, convoyeur B", f"centre {fr(L.fill['E'][0], 0)} ; {fr(L.fill['E'][1], 0)}", f"{fr(min(L.rad_alv['E']), 0)} – {fr(max(L.rad_alv['E']), 0)} mm", pct(max(L.rad_alv['E']) / chosen['reach'])]]
    S += [table(rows, [34, 27, 21, 18], right=(2, 3))]
    S += [Spacer(1, 5), P("<b>Contrôles géométriques automatiques</b> (calculés par le script, jeu minimal de 30 mm entre éléments) :")]
    rows = [["Contrôle", "Résultat"]] + [[c, "Conforme" if ok else "<font color='#D97706'><b>Non conforme</b></font>"] for c, ok in L.checks]
    S += [table(rows, [80, 20], center=(1,))]
    S += [Spacer(1, 4), P(f"Réserve disponible : espace libre entre les extrémités des deux convoyeurs de sortie = {fr(L.free_gap_W_E, 0)} mm (passage de l'entrée de 700 mm) ; "
                           f"jeu entre le rack et le bord de l'enveloppe = {fr(L.occupied_margin_y, 0)} mm. Les convoyeurs de transport restent à 900 ± 20 mm ; "
                           "le point d'outil le plus haut en production est à environ 1,4 m, bien sous la limite de 2,2 m.")]

    S += H2("3.4 Choix argumenté du robot")
    S += [P("Les critères sont : la portée (point de travail le plus éloigné parmi les flacons de la rangée de prise, les empreintes du rack et les 18 alvéoles, avec une exigence d'utilisation ≤ 80 % préconisée par FANUC, « performances optimales dans l'enveloppe intermédiaire »), "
            "le temps de rotation de J1 sur un cycle (somme des débattements de 360° : P → R → C → P), la charge utile, la répétabilité (exigence de dépose : 0,1 mm), l'intégration (masse, socle, armoire) "
            "et la sécurité. Les robots à 4 axes (SCARA) ne permettent pas la bascule de 90° du flacon ; le delta M-3iA et le SCARA SR-6iA sont, de plus, hors de portée (zone de travail de 650 à 675 mm de rayon).")]
    rows = [["Robot", "Charge", "Portée", "Rép.", "Utilisation portée", "Rotation J1", "Note /100", "Statut"]]
    for r in sorted(sel, key=lambda d: (-d["score"] if not d["eliminated"] else -d["score"] + 1000)):
        t1 = "n.a." if r["t_j1"] is None else fr(r["t_j1"], 2) + NB + "s"
        status = "Éliminé : " + r["elim"][0].split(" (")[0] if r["eliminated"] else ("<b>Retenu</b>" if r["name"] == "LR-10iA/10" else "Admissible")
        rows.append([r["name"], f"{r['payload']} kg", f"{r['reach']} mm", f"±{fr(r['rep'], 2)}", pct(r["util_reach"]), t1, fr(r["score"], 0), status])
    hl = [i for i, r in enumerate(rows) if r[0] == "LR-10iA/10"]
    S += [table(rows, [17, 8, 9, 7, 12, 11, 9, 27], right=(1, 2, 3, 4, 5, 6), hl_rows=hl)]
    S += [Spacer(1, 3), P(f"<font size=7.5 color='#64748B'>Notation 0–5 par critère (formules dans le script), pondérée : portée {wts['reach']} %, cycle {wts['cycle']} %, charge utile {wts['payload']} %, "
                          f"répétabilité {wts['rep']} %, intégration {wts['integ']} %, sécurité {wts['safety']} %. Les trois premiers robots sont séparés de {fr(max(r['score'] for r in sel if not r['eliminated']) - sorted([r['score'] for r in sel if not r['eliminated']])[-3], 0)} points seulement : le choix repose sur la marge de portée "
                          f"({pct(1 - chosen['util_reach'])} contre {pct(1 - sel[0]['util_reach'])} pour le LR Mate 200iD/7L) et la vitesse conservée sur les axes.</font>", "small")]
    S += figure(F_["robots"], 160, "Comparaison des candidats : utilisation de la portée (gauche) et temps de rotation de J1 par cycle (droite). Gris clair = éliminé.")
    S += H3("Vérification de la charge embarquée (préconisation FANUC : déclarer masse, centre de gravité et inerties)")
    rows = [["Grandeur", "Valeur", "Limite LR-10iA/10", "Taux"],
            ["Masse de l'outil double (HYP)", f"{fr(tool.m_tool, 2)} kg", "", ""],
            ["Pièces (cas défavorable : 2 flacons)", f"{fr(tool.m_parts, 2)} kg", "", ""],
            ["Charge totale au poignet", f"{fr(tool.m_total, 2)} kg", "10 kg", pct(tool.m_total / 10)],
            ["Inertie autour de J4 / J5 (CDG à 120 mm)", f"{fr(tool.I_J4J5, 3)} kg·m² = {fr(tool.I_J4J5 * 10.197, 2)} kgf·cm·s²", "0,77 kg·m²", pct(tool.I_J4J5 / 0.77)],
            ["Inertie autour de J6", f"{fr(tool.I_J6, 3)} kg·m²", "0,28 kg·m²", pct(tool.I_J6 / 0.28)],
            ["Moment statique à J5 (m·g·d)", f"{fr(tool.M_J5, 2)} N·m", "21 N·m", pct(tool.M_J5 / 21)]]
    S += [table(rows, [38, 30, 18, 14], right=(1, 2, 3))]
    S += [Spacer(1, 3), P("Le catalogue précise que la capacité de 10" + NB + "kg est standard, un mode optionnel portant la charge à 13" + NB + "kg avec un espace de travail réduit à 890" + NB + "mm : "
                          "il n'est pas utilisé ici. Le contrôleur est le R-30iB Plus <b>Mate</b> (470 × 400 × 322 mm), implantable sous la table de cellule.")]
    S += [P("<b>Position du besoin sur le diagramme charge – rayon d'action</b> (question de la fiche ressources) : le besoin est de "
            f"{fr(tool.m_total, 2)}" + NB + f"kg à {fr(L.r_max, 0)}" + NB + "mm, très en dessous des capacités de toute la gamme ; le critère discriminant n'est donc pas la charge mais la portée, la vitesse et la précision.")]
    S += figure(F_["payload"], 150, "Diagramme charge – portée des robots du catalogue OF27 (points relevés dans le catalogue) et position du besoin.")

    S += H2("3.5 Temps de cycle")
    S += [P("<b>Méthode.</b> Un cycle enchaîne trois transferts (P → R, R → C, C → P) et trois opérations locales (prise, dépose / prise sur le rack, insertion). Un transfert de longueur d à vitesse "
            f"maximale v et accélération a dure t = 2·√(d/a) si d ≤ v²/a, sinon t = d/v + v/a ; il est borné par le temps de rotation de J1 (Δθ/ω + {fr(F.CYC.j1_ov, 2)} s). "
            f"Les opérations locales sont réduites de {pct(F.CYC.k_blend)} (enchaînement des trajectoires en CNT, préconisé par FANUC en lieu et place de FINE). Un coefficient de sécurité de {fr(F.CYC.k_safe, 2)} "
            "couvre l'écart entre modèle et simulation. Le résultat est une moyenne sur les 108 combinaisons possibles (2 sorties × 9 alvéoles × 3 flacons de la rangée × 2 empreintes).")]
    S += [P("Tcycle = 1,10 × [ Σ t(transferts) + 0,75 × Σ t(opérations locales) ]", "formula")]
    rows = [["Paramètre", "Valeur", "Origine"],
            ["Vitesse TCP maximale v", f"{fr(F.CYC.v, 1)} m/s", "HYP, charge faible (flacon + outil ≤ 3 kg)"],
            ["Accélération TCP a", f"{fr(F.CYC.a, 1)} m/s²", f"HYP, ACC ≤ 100 ; compatible avec la prise (cas 2 : {fr(vac.rows[0]['f'], 1)} N < {fr(cup['f'], 1)} N)"],
            ["Vitesse de J1", f"{fr(F.CYC.j1, 0)} °/s", "Catalogue LR-10iA/10"],
            ["Prise sur convoyeur", f"{fr(F.CYC.t_pick, 2)} s", "approche 50 mm, vide amorcé avant contact, retrait 50 mm"],
            ["Dépose + prise simultanées sur le rack", f"{fr(F.CYC.t_rack_double, 2)} s", "descente 60 mm, commutation vide / soufflage, remontée"],
            ["Insertion dans la cale", f"{fr(F.CYC.t_cale, 2)} s", "descente 60 mm, 8 mm à 40 mm/s (5 N), libération, retrait"]]
    S += [table(rows, [34, 14, 52], right=(1,))]
    d = m_d["detail"]
    S += [Spacer(1, 5), P("<b>Exemple détaillé</b> (cycle central : alvéole du milieu de C1, flacon central, empreinte 3) :")]
    rows = [["Segment", "Distance", "Rotation J1", "Durée"],
            ["P → R (prise vers rack, bascule 90° en vol)", f"{fr(d['d1'], 0)} mm", f"{fr(d['s1'], 0)}°", f"{fr(d['t1'], 2)} s"],
            ["R → C (rack vers cale)", f"{fr(d['d2'], 0)} mm", f"{fr(d['s2'], 0)}°", f"{fr(d['t2'], 2)} s"],
            ["C → P (retour à vide)", f"{fr(d['d3'], 0)} mm", f"{fr(d['s3'], 0)}°", f"{fr(d['t3'], 2)} s"],
            ["Opérations locales (prise + rack + insertion)", "", "", f"{fr(d['loc'], 2)} s"],
            ["Cycle central (avec ×0,75 sur le local et ×1,10)", "", "", f"<b>{fr(d['tot'], 2)} s</b>"]]
    S += [table(rows, [48, 16, 16, 16], right=(1, 2, 3))]
    S += figure(F_["gantt"], 160, "Décomposition du cycle central (coefficient de sécurité inclus) pour l'outil double et pour l'outil simple. L'outil simple doit visiter deux fois le rack.")
    rows = [["Variante", "Cycle min.", "Cycle moyen", "Cycle max.", "Marge sur takt (moyen)", "Débit max."],
            ["<b>Outil double (retenu)</b>", f"{fr(m_d['min'])} s", f"<b>{fr(m_d['mean'])} s</b>", f"{fr(m_d['max'])} s", pct(margin_d), f"{fr(3600 / m_d['mean'], 0)} /h"],
            ["Outil simple", f"{fr(m_s['min'])} s", f"{fr(m_s['mean'])} s", f"{fr(m_s['max'])} s", pct(margin_s), f"{fr(3600 / m_s['mean'], 0)} /h"]]
    S += [table(rows, [24, 13, 14, 13, 20, 16], right=(1, 2, 3, 4, 5), hl_rows=(1,))]
    S += [Spacer(1, 5), P("<b>Sensibilité</b> du cycle moyen de l'outil double aux paramètres du modèle :")]
    rows = [["Scénario", "Cycle moyen", "Marge sur takt"]] + [[n, f"{fr(m)} s", pct(mg, 1)] for n, m, mg in ctx["sens"]]
    S += [table(rows, [50, 25, 25], right=(1, 2))]
    S += callout(f"Avec l'outil double, la marge moyenne est de {pct(margin_d)} ; elle reste positive dans tous les scénarios dégradés testés (minimum {pct(min(m for _, _, m in ctx['sens']), 1)} "
                 f"avec un coefficient de sécurité de 1,25). La capacité atteint {fr(rate_cap, 0)} pièces/h pour {fr(cad.rate_h, 0)} requises : le robot est occupé à {pct(m_d['mean'] / cad.takt)} du temps. "
                 "Avec un outil simple, la marge n'est que de " + pct(margin_s) + " : un seul aléa suffirait à faire perdre la campagne. <b>Validation à obtenir dans ROBOGUIDE</b> (cycle mesuré avec « Collect Profiler Data », vitesse de simulation synchronisée).", "ok")

    S += H2("3.6 Poste de pesée")
    S += [P(f"Le rack porte 6 empreintes au pas de {INP.rack_pitch} mm (6 × 221 = 1 326 mm, longueur du rack), chacune reliée à une voie du boîtier (6 entrées analogiques, 6 sorties TOR : 0 = mesure en cours ou défaut, 1 = poids validé). "
            "Le flacon est déposé debout dans l'empreinte, l'outil se retire, le poids doit rester stable 2 s avant la reprise.")]
    rows = [["Grandeur", "Calcul", "Résultat"],
            ["Temps de séjour sur l'empreinte", "outil double : un cycle complet entre dépose et reprise", f"{fr(wgh.dwell)} s"],
            ["Marge sur l'attente de stabilisation", f"{fr(wgh.dwell)} − {fr(INP.weigh_wait_s, 1)} s", f"{fr(wgh.margin)} s"],
            ["Empreintes nécessaires", "2 (dépose sur l'une, reprise sur l'autre, J6 alterne les rôles)", "2 sur 6 (3 et 4)"],
            ["Tolérance relative", f"{fr(INP.weigh_tol_g, 0)} g ÷ 380 g", pct(wgh.tol_pct / 100, 2)],
            ["Résolution de mesure exigée", f"≤ tolérance ÷ 10", f"{fr(wgh.res_req, 1)} g"],
            ["Points de mesure (étendue 0–600 g)", f"{fr(wgh.range_g, 0)} ÷ {fr(wgh.res_req, 1)}", f"{fr(wgh.counts_req, 0)} points ≥ {wgh.bits_req} bits"],
            ["Résolution d'une voie 16 bits", f"{fr(wgh.range_g, 0)} g ÷ 2^16", f"{fr(wgh.res_16, 3)} g"]]
    S += [table(rows, [34, 44, 22], right=(2,))]
    S += [Spacer(1, 4), P("Cas d'un flacon hors tolérance : le robot le dépose dans un bac de rebut situé hors de la zone de dépose (à ajouter à l'implantation si le client l'exige), puis la cale concernée "
                          "reçoit le flacon suivant ; la capacité excédentaire absorbe un taux de rebut de l'ordre de quelques pour cent sans perdre la cadence. Les voyants d'empreinte (vert / rouge) informent l'opérateur.")]

    S += H2("3.7 Préhenseur : choix de la surface de prise et dimensionnement du vide")
    S += H3("Choix de la zone de prise")
    rows = [["Zone", "Géométrie utile", "Prise par vide", "Décision"],
            ["Face supérieure de la tête (ABS laqué, Ra ≤ 0,8 µm)", f"≈ {fr(vac.head_top[0], 0)} × {fr(vac.head_top[1], 0)} mm (45 mm coté ; profondeur relevée graphiquement sur la vue de dessus, à confirmer)",
             f"Ø max {fr(vac.head_cup_max - 3, 0)} mm → FSGA 22 : {fr(vac.head_cup_f, 1)} N ; besoin statique {fr(vac.f_static_head, 1)} N (m·g·S) et moment de bascule {fr(vac.M_head, 2)} N·m (CDG à 70 mm)", "<b>Rejetée</b> : capacité insuffisante, même à l'arrêt"],
            ["Plastron frontal (cuir texturé)", f"largeur {fr(vac.plastron_w, 0)} mm, hauteur de torse ≈ 50 mm", f"FSGA {cup['type']} : {fr(cup['f'], 1)} N ; l'insertion se fait dans l'axe de la ventouse", "<b>Retenue</b>, sous réserve d'essai d'étanchéité (grain 0,2 à 0,5 mm)"],
            ["Bras dorés, jambes, côtés de la tête", "surfaces décorées ou arrondies", "—", "Exclues (aucun contact toléré)"]]
    S += [table(rows, [20, 24, 37, 19])]
    S += H3("Force de prise théorique (formules de la fiche ressources)")
    S += [P("Pour une ventouse, F_TH = force de prise théorique, m = masse, g = 9,81 m/s², a = accélération de l'installation, µ = coefficient de frottement, S = facteur de sécurité, "
            "n = nombre de ventouses par produit (F_S = F_TH ÷ n) :")]
    S += [P("Cas 1 (ventouse horizontale, force verticale) : F_TH = m·(g + a)·S", "formula"),
          P("Cas 2 (ventouse horizontale, force horizontale) : F_TH = m·(g + a/µ)·S", "formula"),
          P("Cas 3 (ventouse verticale, force verticale) : F_TH = (m/µ)·(g + a)·S", "formula")]
    S += figure_row([A.get("cas1"), A.get("cas2"), A.get("cas3")], 90, "Les trois cas de charge de la fiche ressources (pièce soulevée, déplacée latéralement, maintenue par une ventouse verticale).", h_mm=22)
    S += [P(f"Hypothèses : m = {fr(vac.m, 2)} kg, µ = {fr(vac.mu, 1)} (surface sèche et lisse, hypothèse prudente pour du silicone sur laque ou cuir), S = {fr(vac.S, 1)} (pièce de luxe, sécurité renforcée), n = 1 ventouse par flacon.")]
    rows = [["Phase du cycle", "Cas", "a (m/s²)", "F_TH (N)", f"Marge réelle (FSGA {cup['type']} = {fr(cup['f'], 1)} N)"]]
    for r, se in zip(vac.rows, vac.S_eff):
        rows.append([r["label"], str(r["case"]), fr(r["a"], 1), fr(r["f"], 1), f"S effectif = {fr(se, 2)}"])
    S += [table(rows, [46, 7, 10, 13, 24], center=(1,), right=(2, 3, 4))]
    S += [Spacer(1, 3), P(f"La force requise maximale est de <b>{fr(vac.f_req, 1)} N</b> : la plus petite ventouse à soufflets FSGA du tableau constructeur qui convient est la <b>FSGA {cup['type']}</b> "
                          f"({fr(cup['f'], 1)} N d'aspiration, {fr(cup['f_break'], 1)} N de rupture, volume {fr(cup['vol'], 2)} cm³, tuyau Ø6 mm), de diamètre {cup['type']} mm pour un plastron de {fr(vac.plastron_w, 0)} mm. "
                          "Elle tolère le décalage de ±2 mm et la rotation de ±2° du flacon à l'arrivée sans recalage mécanique, grâce à l'éjecteur à fort débit qui compense les fuites sur le grain du cuir. "
                          "Les valeurs du tableau constructeur correspondent au vide de référence (supposé −0,6 bar) ; le fonctionnement à −0,7 bar apporte une réserve supplémentaire d'environ 15 %.")]
    S += figure(F_["vacuum"], 150, "Force de prise requise en fonction de l'accélération (trois cas) ; points = phases réelles du cycle ; traits horizontaux = capacité des ventouses FSGA 33, 43 et 53.")
    S += figure(F_["gripper"], 160, "Principe de l'outil double (schéma de principe, hors échelle des organes) : à gauche, prise sur le convoyeur ou insertion, axe vertical ; à droite, échange sur le rack, axe horizontal.")
    S += H3("Génération du vide, compliance et masses")
    rows = [["Élément", "Choix / calcul", "Résultat"],
            ["Éjecteur", f"Schmalz {vac.ej['name']} (vide max −850 mbar, aspiration {fr(vac.ej['Q_lpm'], 0)} l/min, {fr(vac.ej['cons_lpm'], 0)} l/min d'air)", "un par ventouse, pilotage PNP, vacuostat intégré"],
            ["Volume à évacuer", f"{fr(cup['vol'], 2)} cm³ (ventouse) + tuyau Ø6 × 0,40 m", f"{fr(vac.V_cm3, 1)} cm³"],
            ["Constante de temps", f"τ = V ÷ Q = {fr(vac.V_cm3, 1)} cm³ ÷ {fr(vac.ej['Q_lpm'] * 1000 / 60, 0)} cm³/s", f"{fr(vac.tau * 1000, 0)} ms"],
            [f"Temps pour atteindre −{fr(vac.p_target, 0)} mbar", "t = τ·ln[1 ÷ (1 − 700/850)]", f"{fr(vac.t_evac * 1000, 0)} ms (idéal)"],
            ["Avec fuites sur le grain (×2,5, HYP)", "", f"<b>{fr(vac.t_evac_real * 1000, 0)} ms</b> → vide amorcé avant contact"],
            ["Compliance axiale", f"F = k·x : k = 5 N ÷ {fr(vac.stroke_mm, 0)} mm", f"{fr(vac.k_spring, 1)} N/mm ; ±0,5 mm de position → ±{fr(vac.dF_pos, 1)} N (±10 %)"],
            ["Consommation d'air", f"≈ {fr(vac.ej['cons_lpm'], 0)} l/min pendant ≈ 1 s de vide par cycle", f"≈ {fr(vac.air_per_cycle_l, 1)} l par cycle, 2 éjecteurs en alternance"]]
    S += [table(rows, [24, 50, 26])]
    S += callout("Le choix de saisir le flacon par le <b>plastron</b> évite le moment de bascule d'une prise en tête (m·g·0,07 m = 0,26 N·m à l'arrêt ; 5 N × 0,11 m = 0,55 N·m sous l'effort d'encliquetage) et fait passer "
                 "les 5 N d'insertion dans l'axe de la ventouse. <b>Un essai d'étanchéité et d'arrachement sur flacon réel est indispensable</b> avant de figer le choix : si le grain fuit "
                 "trop, les solutions de repli sont une ventouse à lèvre souple ou à mousse de même encombrement (la FSGA 53 ne tient pas sur un plastron de 54 mm) ou une prise mécanique sur une zone validée par le client.", "warn")

    S += H2("3.8 Recalage des flacons et chaîne de tolérances")
    rows = [["Solution", "Principe", "Avantages", "Limites"],
            ["A. Guides mécaniques et butée", "Peigne à doigts souples ou goulottes latérales sur le convoyeur", "Aucun capteur, coût minimal", "Contact avec les bras dorés et la laque : risque de rayure (exigence zéro défaut)"],
            ["B. Capture par la ventouse seule", "Ø43 sur un plastron de 54 mm : recouvrement théorique de ±5 mm ; le rack recentre le flacon avant la 2e prise", "Sans contact, sans coût", "Ne détecte pas un flacon retourné ou absent"],
            ["<b>C. B + iRVision 2D</b> (retenue)", "Caméra 5 Mpx sur la zone de prise : mesure x, y, θ de chaque flacon, contrôle de présence et de sens", "Sans contact, corrige ±2 mm / ±2°, tri des défauts, plug &amp; play dans le robot", "Éclairage dédié (cuir noir, laque brillante) ; coût du système de vision"]]
    S += [table(rows, [20, 32, 24, 24], hl_rows=(3,))]
    S += [Spacer(1, 5), P("Le <b>rack de pesée joue un double rôle</b> : la mise debout dans l'empreinte recentre mécaniquement le flacon (empreinte d'environ 80 × 47 mm pour un flacon de 77,9 × 45 mm), "
                          "si bien que la seconde prise, qui précède l'insertion, est référencée sur la pièce et non plus sur la dispersion d'arrivée.")]
    rows = [["Contributeur", "Valeur", "Maîtrise"],
            ["Dispersion d'arrivée (position / rotation)", "±2 mm / ±2°", "Capture par la ventouse + correction vision"],
            ["Dépose dans l'empreinte (centrage par le rack)", "≈ ±0,5 mm (jeu estimé de 1 mm)", "Chanfreins d'entrée de l'empreinte"],
            ["Répétabilité du robot LR-10iA/10", "±0,01 mm (ISO 9283)", "Largement sous l'exigence de 0,1 mm"],
            ["Indexation de l'intercalaire sur le convoyeur", "±0,1 mm (visée)", "Butée + 2 pions coniques + serrage"],
            ["Position de la cale dans l'alvéole (211/181 vs 210/180)", "jusqu'à ±0,5 mm", "Compliance latérale de l'outil ; non corrigeable par le robot"],
            ["Force d'encliquetage", "5 N ±0,5 N", "Compliance 1 N/mm, détecteur de fin de course"]]
    S += [table(rows, [42, 25, 33])]

    S += H2("3.9 Châssis de cellule, sécurité et préconisations d'installation")
    rows = [["Point", "Proposition", "Justification"],
            ["Structure", "Profilés aluminium 45 × 45 (rainure 10) assemblés par équerres, 4 montants de 2 200 mm, ceinture haute et basse", "La carte mentale demande de justifier profilé aluminium ou mécano-soudé : rapidité de montage et de modification pendant la mise au point ; efforts du robot LR-10iA/10 (46 kg) faibles ; un mécano-soudé n'apporterait de rigidité que pour une charge bien supérieure"],
            ["Socle robot", "Rehausse mécano-soudée (acier) goupillée, platine rectifiée, indépendante du châssis ; hauteur ≈ 450 mm (HYP, à fixer dans ROBOGUIDE)", "Préconisation FANUC : robot goupillé sur plaque, planéité < 1 mm/m ; le châssis alu ne doit pas transmettre de vibration"],
            ["Sol", "Béton peint existant, ≥ 25 MPa et ≥ 250 mm ; ancrages hors joint de dalle", "Valeurs du manuel de préconisation ; sol du CDC §6.2 à vérifier"],
            ["Protection", "Panneaux grillagés h = 2 200 mm ; tunnels de sécurisation sur les deux convoyeurs de sortie ; rideau immatériel côté entrée si l'accès est nécessaire", "La carte mentale cite tunnels, barrières immatérielles et scrutateurs ; dimensionnement des distances selon ISO 13857 / 13855"],
            ["Sécurité robot", "Signaux EMGIN et FENCE câblés (2 canaux) ; DCS : zones de position et vitesse (Position / Speed Check)", "Préconisation « Utilisez les signaux de sécurité » ; l'arrêt d'urgence n'est pas un mode de marche (HOLD pour l'arrêt contrôlé)"],
            ["Environnement", "Air sec et filtré, < 75 % d'humidité, 0–45 °C ; alimentation 24 V externe pour les E/S", "Manuel de préconisation (pneumatique, électrique)"],
            ["Câblage", "Aucun câble ni flexible dans le passage interne du robot ; fixation de l'accastillage uniquement sur les points prévus ; masse de l'accastillage ajoutée à l'ARMLOAD", "Manuel de préconisation (accastillage)"],
            ["Contrôleur", "R-30iB Plus Mate sous la table, iPendant Touch en support amovible", "Dimensions 470 × 400 × 322 mm"],
            ["Convoyeur d'entrée", "Accumulation sans pression ; si des rouleaux Interroll 3500 (pas mini 60 mm) sont retenus, vérifier la stabilité du flacon couché (135 mm, appui sur ≈ 2 rouleaux, bras saillants) – sinon bande à faible frottement", "Fiche ressources : BF 420 / 620 / 840, pas 60 à 150 mm, EC310 24 V"]]
    S += [table(rows, [14, 46, 40], zebra=True)]

    S += H2("3.10 Architecture de communication inter-système (lot 4)")
    S += [P("L'architecture sépare trois familles de signaux : le <b>temps réel de l'outil</b> (vide, contrôle de vide, compliance : E/S TOR directement câblées sur le robot, déterministes), "
            "la <b>coordination de cellule</b> (automate ↔ robot sur PROFINET IO ou EtherNet/IP, avec les signaux UOP de la méthode OTHER : sélection de programme PNS1–8 + PNSTROBE, PROD_START, CMDENBL, SYSRDY, BUSY, FAULT) "
            "et la <b>sécurité</b>, câblée en dehors du réseau standard (EMGIN, FENCE).")]
    S += figure(F_["archi"], 160, "Architecture de communication proposée. Les convoyeurs, la pesée et le MES passent par l'automate ; l'outil et la sécurité sont reliés directement au robot.")
    rows = [["Famille", "Signal", "Type", "Source / destination"]] + [list(r) for r in F.IO_TABLE]
    S += [table(rows, [10, 34, 17, 39], zebra=True)]
    S += [Spacer(1, 5), P("<b>Séquence d'échanges d'un cycle</b> (poignée de main automate ↔ robot) :")]
    rows = [["N°", "Événement", "Signal", "Sens"],
            ["1", "L'automate a une rangée de prise présente et un intercalaire indexé", "PNS1 = cycle nominal vers A ou B + PNSTROBE", "Automate → robot"],
            ["2", "Le robot accepte et démarre", "SNO / SNACK, BUSY = 1", "Robot → automate"],
            ["3", "Vision : déclenchement avant la prise, résultat (x, y, θ) lu dans un registre de position", "DO caméra ; VR/PR", "Robot ↔ caméra"],
            ["4", "Dépose sur le rack, attente 2 s, lecture du poids validé de l'empreinte reprise", "DI « poids validé » (empreinte 3 / 4)", "Boîtier → robot"],
            ["5", "Poids hors tolérance : le robot ne place pas la cale, appelle le programme de rebut", "UO personnalisée REJECT + enregistrement", "Robot → automate"],
            ["6", "9e flacon posé : demande de changement d'intercalaire, bascule vers l'autre sortie", "UO « Intercalaire plein » ; PNS2", "Robot → automate"],
            ["7", "Défaut ou arrêt : HOLD, mise en sécurité, reprise par FAULT_RESET puis START", "UI 2, UI 5, UI 6 ; UO FAULT", "Automate ↔ robot"]]
    S += [table(rows, [4, 46, 32, 18])]
    rows = [["Dimensionnement réseau et données", "Calcul", "Résultat"],
            ["Échange cyclique automate ↔ robot", f"{com.cyc_bytes_in} octets + {com.cyc_bytes_out} octets, période {fr(com.cycle_ms, 0)} ms, trame minimale {com.frame_overhead} octets sur le fil", f"{fr(com.bw_kbps, 0)} kbit/s ≈ {fr(com.bw_pct, 2)} % de 100 Mbit/s"],
            ["Enregistrement de traçabilité par flacon", f"{com.rec_bytes} octets (horodatage, identifiant, poids, statut, empreinte)", f"{fr(com.rec_day_kB, 0)} ko/jour ; {fr(com.rec_total_MB, 1)} Mo pour la campagne"],
            ["Flux image iRVision (si archivé)", f"{fr(com.img_mpx, 0)} Mpx × 8 bits = {fr(com.img_MB, 0)} Mo par image, 1 image par {fr(cad.takt, 0)} s", f"{fr(com.img_Mbps, 0)} Mbit/s ≈ {fr(com.img_pct, 0)} % de 1 Gbit/s"],
            ["Archivage des seules images défectueuses (1 %)", f"{fr(INP.volume, 0)} × 1 % × {fr(com.img_MB, 0)} Mo", f"{fr(com.ng_GB, 0)} Go (contre {fr(com.all_TB, 1)} To pour toutes les images)"]]
    S += [Spacer(1, 6), table(rows, [28, 46, 26])]

    # ---------------------------- 4. RÉPONSES ----------------------------
    S += H1("4. Réponses aux questions du sujet")
    rows = [["Question du sujet", "Réponse apportée", "Réf."],
            ["Lot 1 – Sélection du robot : choix argumenté au sein de la gamme FANUC", f"FANUC <b>LR-10iA/10</b> (6 axes, 10 kg, 1 101 mm, ±0,01 mm, IP67, R-30iB Plus Mate) : portée utilisée {pct(chosen['util_reach'])}, charge {pct(chosen['util_payload'])}, rotation J1 de {fr(chosen['t_j1'], 2)} s par cycle. CRX éliminé (J1 à 120 °/s), delta et SCARA éliminés (portée, 4 axes). Repli : M-10iD/12.", "§3.4"],
            ["Lot 1 – Optimisation des trajectoires : tracé précis, évitement total de collision, mouvement fluide", f"Trois transferts P → R → C → P ; approche verticale de 60 mm sur chaque poste, bascule de 90° exécutée en vol entre P et R, trajectoires en CNT (pas de FINE), repères TOOL / USER pour les 4 postes, ACC ≤ 100. Vérification de collision à réaliser dans ROBOGUIDE (outil double, rack, bords d'intercalaire).", "§3.3, §3.5, §5.1"],
            ["Lot 1 – Valider le temps de cycle pour tenir le volume de campagne", f"Cycle moyen estimé {fr(m_d['mean'])} s (min {fr(m_d['min'])} s, max {fr(m_d['max'])} s) pour un takt de {fr(cad.takt)} s : marge {pct(margin_d)} ; capacité {fr(rate_cap, 0)} pièces/h pour {fr(cad.rate_h, 0)} requises. Validation formelle à produire dans ROBOGUIDE.", "§3.1, §3.5"],
            ["Lot 2 – Châssis : solution justifiée respectant l'encombrement", "Châssis en profilés aluminium 45 × 45, 2 500 × 1 500 × 2 200 mm, socle robot mécano-soudé indépendant ; tous les contrôles d'emprise et de jeu sont conformes.", "§3.3, §3.9"],
            ["Lot 2 – Système de recalage des flacons sur le convoyeur", "Capture sans contact par ventouse Ø43 sur plastron de 54 mm + iRVision 2D (x, y, θ) ; recentrage mécanique par le rack avant l'insertion. Les guides mécaniques sont écartés (risque de rayure).", "§3.8"],
            ["Lot 3 – Conception du préhenseur répondant à l'exigence de qualité cosmétique", f"Outil double à deux ventouses FSGA {cup['type']} en silicone non marquant, entraxe 221 mm, éjecteurs SCPS 10, vérins de dégagement, compliance 1 N/mm (5 N), contrôle de vide. Aucune pince sur les zones décorées.", "§3.7"],
            ["Lot 4 – Architecture de communication robot / périphériques existants ou ajoutés", "Automate + robot sur PROFINET / EtherNet-IP (UOP, PNS), E/S TOR câblées pour l'outil et la pesée, caméra GigE, sécurité câblée, remontée de traçabilité vers le MES.", "§3.10"],
            ["Implantation libre ; un seul convoyeur d'entrée, deux d'évacuation", "Implantation en « T » : entrée au sud, sorties A et B face à face avec un entraxe de 1 200 mm entre centres de remplissage.", "§3.3"],
            ["Fiche ressources – Position du besoin sur le diagramme charge / rayon d'action", f"{fr(tool.m_total, 2)} kg à {fr(L.r_max, 0)} mm : zone très basse du diagramme, au centre de la gamme poly-articulée compacte.", "§3.4"],
            ["Fiche ressources – Référence du robot et justification", "LR-10iA/10, détaillé ci-dessus ; la fiche cite à titre d'exemple d'autres familles (SCARA, delta, cartésien, cobot) écartées pour les raisons du §3.4.", "§3.4"],
            ["Fiche ressources – Force de prise théorique d'une ventouse", f"Cas 2 à a = {fr(F.CYC.a, 0)} m/s² : {fr(vac.rows[0]['f'], 1)} N ; cas 3 à 3 m/s² : {fr(vac.rows[1]['f'], 1)} N ; cas 1 à 2 m/s² : {fr(vac.rows[2]['f'], 1)} N → FSGA {cup['type']} (n = 1 par flacon, S = 2).", "§3.7"],
            ["Livrable 1 – Présentation technique (.ppt / .pdf)", "Le présent rapport en constitue la trame ; ses figures et tableaux sont réutilisables en diapositives.", "—"],
            ["Livrable 2 – Cellule ROBOGUIDE (procédure jointe)", "File > Package Cell > Compressed Cell → fichier .rgx à joindre au dossier ; vidéo AVI 1680 × 1050.", "§5.1"],
            ["Jalons : 5 janv. 2027 (livrables), 11–19 janv. (revue), 1er avril (lancement)", "Rétroplanning proposé au §5.4 ; remise via le Portail École avant le 5 janvier 2027 (pénalité en cas de retard).", "§5.4"]]
    S += [table(rows, [28, 62, 10], zebra=True)]

    # ---------------------------- 5. RECOMMANDATIONS ----------------------------
    S += H1("5. Recommandations")
    S += H2("5.1 Construction du jumeau numérique ROBOGUIDE")
    S += B([f"<b>Cellule</b> : importer flacon.CSB ; modéliser rack, thermoformé et intercalaire d'après les plans (ou obtenir les CSB) ; poser le robot LR-10iA/10 sur sa rehausse à la cote (x = {fr(L.robot[0], 0)} ; y = {fr(L.robot[1], 0)}) et reprendre les coordonnées du §3.3.",
            f"<b>Charge embarquée</b> : déclarer deux PAYLOAD complets – outil à vide ({fr(tool.m_tool, 1)} kg, CDG à 120 mm) et outil chargé ({fr(tool.m_tool + INP.m_flacon, 2)} kg) – avec masse, centre de gravité (cm) et inerties ({fr(tool.I_J4J5 * 10.197, 2)} kgf·cm·s² selon J4/J5) ; les activer par programme avant chaque prise et dépose.",
            "<b>Repères</b> : un TOOL par ventouse (G1, G2) et un USER par poste (convoyeur d'entrée, rack, intercalaires A et B) ; trajectoires apprises dans ces repères, ce qui permet de recaler un poste sans réapprendre les points.",
            "<b>Programmes</b> : un programme principal appelé par PNS, des sous-programmes PRISE, RACK, CALE_A, CALE_B et REBUT, positions des 9 alvéoles calculées par registres de position (pas 181 × 211 mm) plutôt que 18 points appris.",
            "<b>Mouvements</b> : CNT élevé (jamais FINE en fin de trajet), ACC ≤ 100, pas d'arrêt d'urgence en mode de marche (HOLD), contrôle de la sollicitation des axes (écran Overheat) et iRDiagnostics.",
            "<b>Validation du temps de cycle</b> : ouvrir le Run Panel, cocher « Collect Profiler Data », vitesse de simulation synchronisée ; <b>ne pas lire le temps affiché sur l'AVI</b> (l'option « Simulation Time on AVI » n'est pas représentative du cycle). Mesurer sur au moins 18 cycles couvrant les 2 sorties × 9 alvéoles.",
            "<b>Livrables</b> : AVI en 1680 × 1050 (répertoire AVIs de la cellule) ; cellule sauvegardée par File > Package Cell > Compressed Cell (fichier .rgx) ; le tout à déposer sur le Portail École avant le 5 janvier 2027."])
    S += H2("5.2 Optimisations de la cellule réelle")
    S += B([f"<b>Réduire la distance P → R</b> (transfert le plus long du cycle : {fr(m_d['detail']['d1'] / 1000, 1)} m, {fr(m_d['detail']['t1'])} s) : le rack pourrait être rapproché de l'entrée si le client accepte une entrée latérale ; gain potentiel de l'ordre de 0,2 à 0,3 s, à confirmer par simulation.",
            "<b>Synchroniser l'alternance A / B</b> sur le 9e flacon : le robot enchaîne directement sur l'autre intercalaire, déjà indexé, sans aucune attente.",
            "<b>Plafonner l'accélération avec charge</b> à la valeur qui garantit S ≥ 2 sur la ventouse et surveiller le vacuostat en continu : une perte de vide en transfert doit déclencher HOLD, pas une chute du flacon.",
            "<b>Fiabiliser le vide</b> : filtre sur chaque ligne, remplacement préventif des soufflets en silicone après un nombre de cycles défini à l'essai (suivi par le MES).",
            "<b>Traçabilité</b> : horodater chaque pesée et l'associer à l'identifiant d'intercalaire / position de cale ; conserver les images vision des seuls défauts (≈ 11 Go sur la campagne).",
            "<b>Exploiter les 4 empreintes de rack inutilisées</b> comme secours ou pour alterner l'usure ; elles sont déjà dans l'enveloppe de portée.",
            "<b>Maintenance</b> : activer ZDT (Zero Down Time) et iRDiagnostics (présents dans le catalogue) pour anticiper les dérives."])
    S += H2("5.3 Risques et actions")
    rows = [["Risque", "Gravité", "Probabilité", "Action de réduction"],
            ["Étanchéité insuffisante sur le grain du plastron (0,2–0,5 mm)", "Élevée", "Moyenne", "Essai sur flacon réel avant gel de la conception ; repli : soufflet à lèvre souple ou prise mécanique validée par le client"],
            ["Masse réelle du flacon différente de 380 g", "Moyenne", "Faible", "Confirmer par écrit ; le dimensionnement a 10 % de réserve sur le cas le plus défavorable"],
            ["Cycle réel supérieur à l'estimation", "Élevée", "Moyenne", "Simulation ROBOGUIDE ; leviers : rapprocher le rack, accélérations, réduction du local"],
            ["Collision de l'outil double avec les bords d'intercalaire ou le flacon voisin", "Moyenne", "Moyenne", "Vérins de dégagement de 20 mm, contrôle de collision ROBOGUIDE, calage des orientations de J6"],
            ["Jeu insuffisant entre cale et alvéole (0,5 mm)", "Moyenne", "Moyenne", "Compliance latérale ; mesurer le jeu réel sur échantillon"],
            ["Débit amont exactement égal au takt", "Élevée", "Certaine", "Zone d'accumulation en amont, cycle ≤ 3,6 s, alerte automate si l'accumulation tombe sous 2 groupes"],
            ["Pièces CAO manquantes (3 CSB)", "Faible", "Certaine", "Demande au support dès maintenant ; modélisation de secours d'après les plans"]]
    S += [table(rows, [34, 10, 11, 45], zebra=True)]
    S += H2("5.4 Rétroplanning vers les jalons")
    rows = [["Période", "Jalon / activité", "Sortie"],
            ["Oct. 2026", "Questions au support (CSB, masse, zones de prise) ; essai de vide sur échantillon", "Hypothèses levées"],
            ["Nov. 2026", "Cellule ROBOGUIDE : modèles, repères, programmes", "Premier cycle complet"],
            ["Déc. 2026", "Optimisation du cycle, collisions, conception détaillée du préhenseur et du châssis, nomenclature", "Cycle ≤ 3,6 s validé"],
            ["Avant le 5 janv. 2027", "Jalon 1 – restitution des livrables (Portail École)", "Présentation + .rgx + AVI"],
            ["11–19 janv. 2027", "Jalon 2 – revue d'étude", "Soutenance"],
            ["1er avr. 2027", "Jalon 3 – lancement du projet", "—"]]
    S += [table(rows, [20, 56, 24])]
    S += H2("5.5 Ordre de grandeur budgétaire")
    S += [P("Le dossier ne fournit des prix que pour quelques familles de robots (poly-articulé ≈ 20 000 € HT, collaboratif ≈ 26 000 € HT). Les autres lignes ci-dessous sont des "
            "<b>estimations d'ordre de grandeur de l'auteur (± 30 %)</b>, à remplacer par des devis ; les convoyeurs et la pose ne sont pas chiffrés.")]
    rows = [["Poste", "Estimation HT", "Source"],
            ["Robot LR-10iA/10 + R-30iB Plus Mate + iPendant", "≈ 20 000 €", "Dossier (famille poly-articulé)"],
            ["Outil double (ventouses, éjecteurs, vérins, compliance)", "4 000 – 6 000 €", "HYP"],
            ["iRVision 2D (caméra, éclairage, licence)", "4 000 – 6 000 €", "HYP"],
            ["Châssis alu, protections, socle mécano-soudé", "8 000 – 12 000 €", "HYP"],
            ["Automate, E/S, IHM, sécurité", "7 000 – 10 000 €", "HYP"],
            ["<b>Total indicatif hors convoyeurs, ingénierie et pose</b>", "<b>≈ 43 000 – 54 000 €</b>", ""]]
    S += [table(rows, [56, 24, 20], right=(1,), bold_last=False)]

    # ---------------------------- ANNEXES ----------------------------
    S += H1("Annexe A – Hypothèses et paramètres du script")
    rows = [["Hypothèse (HYP)", "Valeur", "Effet si elle change"],
            ["Un poste « 8 h » = 480 min, pause de 45 min incluse", "435 min nettes", "Takt proportionnel"],
            ["Un coffret = un flacon", "221 850 flacons", "Takt proportionnel"],
            ["Pas de 196 mm = entre axes ; 30 mm = entre rangées", "voir §2.3 n°8", "Rangée de prise, distance P"],
            ["Coefficient de frottement ventouse / flacon", "µ = 0,5", "Marge de la ventouse"],
            ["Facteur de sécurité des ventouses", "S = 2", "Choix de la taille"],
            ["Masse de l'outil double", "2,0 kg", "Charge utile, inertie"],
            ["Accélération et vitesse TCP", "9 m/s², 1,8 m/s", "Temps de cycle (sensibilité au §3.5)"],
            ["Recouvrement des opérations locales par le CNT", "25 %", "Temps de cycle"],
            ["Coefficient de sécurité simulation → réel", "1,10", "Temps de cycle"],
            ["Rayon d'encombrement du socle", "230 mm", "Implantation"],
            ["Course utile des convoyeurs de sortie / vitesse", "1,8 m / 0,3 m/s", "Budget d'échange"],
            ["Fuites sur le grain du plastron", "×2,5 sur le temps de vide", "Temps de prise"]]
    S += [table(rows, [50, 20, 30])]
    S += H1("Annexe B – Sources")
    S += B(["Cahier des charges fonctionnel Flacon_ENCA2701_sept2026.pdf et plans FF-2027-BTL-001, PKG-001, PKG-002, PKG-003.",
            "Catalogue Robots Fanuc OF27 (pages 8, 9, 11, 21, 23–27, 35, 38–42) : caractéristiques des robots, contrôleurs, iRVision, DCS, ROBOGUIDE.",
            "Manuel de préconisation intégration FANUC V2.6 ; Manuel d'aide à la programmation TPE (Vs 2025), chapitres E/S et UOP.",
            "07 ACT Ressources complémentaires CRSA : formules de force de prise, ventouses Schmalz FSGA, éjecteurs SCPS, convoyeur Interroll série 3500.",
            "Procédures FANUC France : création de vidéo AVI et sauvegarde .rgx de la cellule ROBOGUIDE."])
    return S


# --------------------------------------------------------------------------------------
# Programme principal
# --------------------------------------------------------------------------------------
def main(argv=None):
    ap = argparse.ArgumentParser(description="Génère le rapport PDF d'avant-projet (jumeau numérique FANUC 2027).")
    ap.add_argument("--zip", required=True, help="Archive ZIP du sujet")
    ap.add_argument("--out", default="Rapport_AVP_Jumeau_Numerique_FANUC_2027.pdf", help="PDF de sortie")
    ap.add_argument("--workdir", default=None, help="Dossier de travail (par défaut : dossier temporaire)")
    a = ap.parse_args(argv)
    work = Path(a.workdir) if a.workdir else Path(tempfile.mkdtemp(prefix="avp_fanuc_"))
    work.mkdir(parents=True, exist_ok=True)

    print("1/4  Extraction de l'archive et des visuels…")
    assets, inv, _ = R.extract_assets(a.zip, work)
    print(f"     {len(inv)} fichiers, {len(assets)} visuels")

    print("2/4  Calculs techniques…")
    cad = F.calc_cadence(); L = F.calc_layout(); tool = F.calc_tool()
    sel, wts = F.calc_robot_selection(L, tool, cad.takt)
    cyc = F.calc_cycle(L); vac = F.calc_vacuum(); wgh = F.calc_weighing(cyc.rows["double"]["mean"])
    sh = F.calc_shuttle(cad); com = F.calc_comm(cad)
    sens = F.cycle_sensitivity(L, cad.takt)
    bad = [c for c, ok in L.checks if not ok]
    if bad:
        print("     ATTENTION – contrôles d'implantation non conformes :", bad, file=sys.stderr)

    print("3/4  Graphiques…")
    figs = R.build_figures(cad, L, tool, sel, cyc, vac, sh, work / "figs")

    print("4/4  Assemblage du PDF…")
    ctx = dict(cad=cad, L=L, tool=tool, sel=sel, wts=wts, cyc=cyc, vac=vac, wgh=wgh, sh=sh, com=com, assets=assets, figs=figs, inv=inv, sens=sens)
    _fig_counter["n"] = 0
    story = build_story(ctx)
    doc = Doc(a.out)
    doc.multiBuild(story, canvasmaker=NumberedCanvas)
    print("OK ->", a.out)


if __name__ == "__main__":
    main()

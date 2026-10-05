# -*- coding: utf-8 -*-
"""
Calculs techniques de l'avant-projet « Jumeau numérique – Olympiades FANUC AVP BAC+2 2027 ».

Module volontairement séparé du rendu PDF : toutes les valeurs citées dans le rapport
sont calculées ici (aucun résultat n'est saisi « en dur » dans le texte du rapport).

Convention : mm, s, kg, N, sauf mention contraire.
"""
from __future__ import annotations
import math
from types import SimpleNamespace

G = 9.81  # m/s²

# --------------------------------------------------------------------------------------
# 0. DONNÉES D'ENTRÉE (issues du dossier) ET HYPOTHÈSES (marquées HYP)
# --------------------------------------------------------------------------------------
INPUT = SimpleNamespace(
    volume=221_850,            # coffrets / campagne (CDC §2)
    days=20,                   # jours ouvrés (CDC §2)
    shifts=2,                  # 2x8 (CDC §2)
    shift_h=8.0,               # HYP : un poste = 8 h (« 2x8 »)
    pause_min=45,              # pause par équipe (CDC §2)
    trs=0.85,                  # TRS attendu (CDC §2)
    conv_rate_h=900,           # cadence convoyeur d'amenée (CDC §3, étape 1)
    group=18, row=3,           # 18 flacons par groupe, rangées de 3 (CDC §3)
    cales_per_interc=9,        # 9 alvéoles / intercalaire (PKG-001)
    m_flacon=0.380,            # kg (CDC §1.1) ; les plans indiquent 180 g -> incohérence
    m_flacon_plan=0.180,       # kg (cartouches des plans)
    weigh_tol_g=2.0, weigh_wait_s=2.0, weigh_n=6,   # CDC étape 3
    snap_force_N=5.0,          # CDC étape 4
    footprint=(2500, 1500), height_max=2200, conv_h=900, conv_h_tol=20,
    conv_w_in=700, conv_w_out=900,
    interc=(710, 620, 30), alv_pitch=(211, 181), cale=(210, 180),
    rack=(1326, 150), rack_pitch=221,
    arrival_pitch=196, arrival_gap=30, arrival_rot=2.0,
    flacon=dict(H=135.0, W_arms=77.9, W_torso=54.0, W_head_top=45.0, D=45.0, D_head=35.7, leg_h=39.0),
)

# Robots candidats : données issues du catalogue FANUC OF27 (pages 8, 9, 11, 21, 23-27)
ROBOTS = [
    # nom, charge kg, portée mm, axes, répétabilité mm, masse kg, vitesse J1 °/s (ou None), v_lin mm/s, type
    dict(name="LR Mate 200iD/7L", payload=7, reach=911, axes=6, rep=0.01, mass=27, j1=370, vlin=None, fam="poly-articulé", cab="R-30iB Plus Mate", prot="IP67", collab=False),
    dict(name="LR-10iA/10",       payload=10, reach=1101, axes=6, rep=0.01, mass=46, j1=300, vlin=None, fam="poly-articulé", cab="R-30iB Plus Mate", prot="IP67", collab=False),
    dict(name="M-10iD/12",        payload=12, reach=1441, axes=6, rep=0.02, mass=145, j1=260, vlin=None, fam="poly-articulé", cab="R-30iB Plus (A/Mate)", prot="IP54/65", collab=False),
    dict(name="CRX-10iA/L",       payload=10, reach=1418, axes=6, rep=0.04, mass=40, j1=120, vlin=1000, fam="collaboratif", cab="CRX", prot="IP67", collab=True),
    dict(name="M-3iA/6A (delta)", payload=6, reach=675, axes=6, rep=0.1, mass=175, j1=None, vlin=None, fam="delta", cab="R-30iB Plus", prot="IP67", collab=False),
    dict(name="SR-6iA (SCARA)",   payload=6, reach=650, axes=4, rep=0.01, mass=30, j1=None, vlin=None, fam="SCARA", cab="R-30iB Plus Mini", prot="IP20", collab=False),
]
# Nuage de points pour le diagramme charge-portée (catalogue)
CATALOG_POINTS = [
    ("LR Mate 200iD/4S", 550, 4), ("LR Mate 200iD/7L", 911, 7), ("LR Mate 200iD/14L", 911, 14),
    ("LR-10iA/10", 1101, 10), ("M-10iD/8L", 2032, 8), ("M-10iD/10L", 1636, 10), ("M-10iD/12", 1441, 12),
    ("M-10iD/16S", 1103, 16), ("CRX-5iA", 994, 5), ("CRX-10iA", 1249, 10), ("CRX-10iA/L", 1418, 10),
    ("CRX-20iA/L", 1418, 20), ("CRX-25iA", 1889, 25), ("CR-7iA/L", 911, 7), ("CR-15iA", 1441, 15),
    ("SR-3iA", 400, 3), ("SR-6iA", 650, 6), ("SR-12iA", 900, 12), ("M-3iA/6A", 675, 6), ("DR-3iB/8L", 800, 8),
]

# --------------------------------------------------------------------------------------
# 1. CADENCE ET TAKT
# --------------------------------------------------------------------------------------
def calc_cadence(p=INPUT):
    r = SimpleNamespace()
    r.shift_gross_min = p.shift_h * 60
    r.shift_net_min = r.shift_gross_min - p.pause_min
    r.day_min = r.shift_net_min * p.shifts
    r.day_h = r.day_min / 60
    r.day_s = r.day_min * 60
    r.camp_min = r.day_min * p.days
    r.camp_h = r.camp_min / 60
    r.camp_s = r.camp_min * 60
    r.prod_h = r.camp_h * p.trs
    r.prod_s = r.camp_s * p.trs
    r.takt = r.prod_s / p.volume                       # s / coffret (= 1 flacon)
    r.takt_gross = r.camp_s / p.volume
    r.rate_h = 3600 / r.takt                           # pièces / h requises
    r.rate_h_gross = 3600 / r.takt_gross
    r.per_day = p.volume / p.days
    r.per_shift = r.per_day / p.shifts
    r.n_interc = p.volume / p.cales_per_interc
    r.n_interc_conv = r.n_interc / 2
    r.fill_s = p.cales_per_interc * r.takt             # temps de remplissage d'un intercalaire à la cadence cible
    r.group_period_s = p.group * r.takt                 # un groupe de 18 toutes les ...
    r.row_period_s = p.row * r.takt
    r.row_pitch_mm = p.flacon["H"] + p.arrival_gap      # pas entre rangées (hypothèse : flacon "tête en avant")
    r.row_width_mm = 2 * p.arrival_pitch + p.flacon["W_arms"]
    r.conv_consistent = abs(r.rate_h - p.conv_rate_h) < 1e-6
    return r

# --------------------------------------------------------------------------------------
# 2. IMPLANTATION (coordonnées cellule, origine coin avant-gauche, X = 2500, Y = 1500)
# --------------------------------------------------------------------------------------
def rect(cx, cy, w, h):
    return (cx - w / 2, cy - h / 2, cx + w / 2, cy + h / 2)

def _ov(a, b, m=0.0):
    return not (a[2] + m <= b[0] or b[2] + m <= a[0] or a[3] + m <= b[1] or b[3] + m <= a[1])

def calc_layout(p=INPUT):
    L = SimpleNamespace()
    W, H = p.footprint
    L.W, L.H = W, H
    L.robot = (1250.0, 770.0)           # axe J1
    L.ped_r = 230.0                     # rayon d'encombrement socle + rehausse (HYP)
    # Sorties : convoyeurs W et E (aller-retour), intercalaire 620 selon X / 710 selon Y
    L.fill_dx = 600.0                   # distance axe robot -> centre intercalaire en X
    L.fill_dy = 60.0                    # décalage en Y du centre intercalaire / robot
    cw, ch = p.interc[1], p.interc[0]   # 620 (X) x 710 (Y)
    L.interc_w, L.interc_h = cw, ch
    L.fill = {
        "W": (L.robot[0] - L.fill_dx, L.robot[1] + L.fill_dy),
        "E": (L.robot[0] + L.fill_dx, L.robot[1] + L.fill_dy),
    }
    L.alv_px, L.alv_py = p.alv_pitch[1], p.alv_pitch[0]   # 181 selon X, 211 selon Y
    L.strip = {
        "W": (0, L.fill["W"][1] - p.conv_w_out / 2, L.fill["W"][0] + cw / 2, L.fill["W"][1] + p.conv_w_out / 2),
        "E": (L.fill["E"][0] - cw / 2, L.fill["E"][1] - p.conv_w_out / 2, W, L.fill["E"][1] + p.conv_w_out / 2),
    }
    # Entrée : convoyeur sud, axe x = robot, extrémité 30 mm sous les convoyeurs de sortie
    gap = 30.0
    L.in_end_y = L.strip["W"][1] - gap
    L.in_strip = (L.robot[0] - p.conv_w_in / 2, 0, L.robot[0] + p.conv_w_in / 2, L.in_end_y)
    # Rangée de prise (rangée de tête de 3 flacons) : centrée à 34 mm de l'extrémité (demi-longueur flacon + 1 mm)
    L.row_y = L.in_end_y - 0.5 * p.flacon["H"] - 10.0
    L.pick_pts = [(L.robot[0] + k, L.row_y) for k in (-p.arrival_pitch, 0, p.arrival_pitch)]
    # Rack de mesure : au nord, 30 mm au-dessus des convoyeurs de sortie
    L.rack_y = L.strip["W"][3] + gap + p.rack[1] / 2
    L.rack = rect(L.robot[0], L.rack_y, p.rack[0], p.rack[1])
    L.imprints = [(L.robot[0] + (k - 2.5) * p.rack_pitch, L.rack_y) for k in range(6)]
    L.used_imprints = (2, 3)            # empreintes centrales (indices 0..5)
    # Alvéoles (9 par intercalaire)
    L.alveoles = {}
    for side in "WE":
        cx, cy = L.fill[side]
        L.alveoles[side] = [(cx + i * L.alv_px, cy + j * L.alv_py) for j in (-1, 0, 1) for i in (-1, 0, 1)]
    # Rayons (distance axe J1 -> TCP)
    def rad(pt): return math.hypot(pt[0] - L.robot[0], pt[1] - L.robot[1])
    L.rad_pick = [rad(q) for q in L.pick_pts]
    L.rad_rack_used = [rad(L.imprints[i]) for i in L.used_imprints]
    L.rad_rack_all = [rad(q) for q in L.imprints]
    L.rad_alv = {s: [rad(q) for q in L.alveoles[s]] for s in "WE"}
    allr = L.rad_pick + L.rad_rack_used + L.rad_alv["W"] + L.rad_alv["E"]
    L.r_max, L.r_min = max(allr), min(allr)
    # Contrôles géométriques
    chk = []
    env = (0, 0, W, H)
    def inside(r): return r[0] >= 0 and r[1] >= 0 and r[2] <= W and r[3] <= H
    ped = rect(L.robot[0], L.robot[1], 2 * L.ped_r, 2 * L.ped_r)
    fillW = rect(*L.fill["W"], cw, ch); fillE = rect(*L.fill["E"], cw, ch)
    chk.append(("Convoyeur de sortie W dans l'enveloppe 2500 x 1500", inside(L.strip["W"])))
    chk.append(("Convoyeur de sortie E dans l'enveloppe 2500 x 1500", inside(L.strip["E"])))
    chk.append(("Convoyeur d'entrée dans l'enveloppe", inside(L.in_strip)))
    chk.append(("Rack de mesure dans l'enveloppe", inside(L.rack)))
    chk.append(("Pas de recouvrement entrée / sorties (jeu ≥ 30 mm)", not _ov(L.in_strip, L.strip["W"], gap - 1) and not _ov(L.in_strip, L.strip["E"], gap - 1)))
    chk.append(("Pas de recouvrement rack / sorties (jeu ≥ 30 mm)", not _ov(L.rack, L.strip["W"], gap - 1) and not _ov(L.rack, L.strip["E"], gap - 1)))
    chk.append(("Pas de recouvrement W / E", not _ov(L.strip["W"], L.strip["E"])))
    chk.append(("Socle robot hors convoyeurs", not any(_ov(ped, s) for s in (L.strip["W"], L.strip["E"], L.in_strip, L.rack))))
    chk.append(("Intercalaires W/E dans la largeur de convoyeur (710 ≤ 900)", ch <= p.conv_w_out))
    L.checks = chk
    L.free_gap_W_E = L.strip["E"][0] - L.strip["W"][2]
    L.occupied_margin_y = H - L.rack[3]
    return L

# --------------------------------------------------------------------------------------
# 3. ROBOT : indicateurs et matrice de décision
# --------------------------------------------------------------------------------------
def calc_tool(p=INPUT):
    t = SimpleNamespace()
    t.m_tool = 2.0            # HYP : outil double (barre, 2 ventouses, 2 compliances, 2 vérins, flasque)
    t.m_parts = 2 * p.m_flacon  # pire cas : deux flacons simultanément (en pratique 1)
    t.m_total = t.m_tool + t.m_parts
    t.d_cg = 0.12             # m, HYP : CDG / flasque
    t.arm = 0.110             # m, demi-entraxe des ventouses
    t.I_J4J5 = t.m_total * t.d_cg ** 2 + 0.02          # kg·m²  (+ inertie propre HYP)
    t.I_J6 = 2 * (t.m_tool / 2 + p.m_flacon) * t.arm ** 2 + 0.01
    t.M_J5 = t.m_total * G * t.d_cg                    # N·m
    return t

def calc_robot_selection(L, tool, takt, p=INPUT):
    out = []
    sweep_deg = 360.0   # somme des débattements J1 sur un cycle (P→R→C→P, cf. implantation)
    for rb in ROBOTS:
        d = dict(rb)
        d["util_reach"] = L.r_max / rb["reach"]
        d["util_payload"] = tool.m_total / rb["payload"]
        if rb["j1"]:
            d["t_j1"] = sweep_deg / rb["j1"] + 3 * 0.12
        elif rb["vlin"]:
            d["t_j1"] = sweep_deg / 120 + 0.36
        else:
            d["t_j1"] = None
        d["elim"] = []
        if d["util_reach"] > 1.0:
            d["elim"].append("portée insuffisante (r_max = %.0f mm > %d mm)" % (L.r_max, rb["reach"]))
        if rb["axes"] < 6:
            d["elim"].append("4 axes : bascule 90° du flacon impossible sans axe additionnel")
        if d["t_j1"] and d["t_j1"] > 0.75 * takt:
            d["elim"].append("axe J1 trop lent (%.1f s de rotation par cycle > 75 %% du takt)" % d["t_j1"])
        if rb["rep"] > 0.1:
            d["elim"].append("répétabilité > 0,1 mm")
        # Notes 0..5
        u = d["util_reach"]
        d["s_reach"] = 0 if u > 1 else (5 if u <= 0.65 else 4 if u <= 0.80 else 2 if u <= 0.90 else 1)
        t = d["t_j1"]
        d["s_cycle"] = 0 if t is None else (5 if t <= 1.5 else 4 if t <= 1.8 else 3 if t <= 2.2 else 2 if t <= 2.8 else 1)
        up = d["util_payload"]
        d["s_payload"] = 5 if up <= 0.22 else 4 if up <= 0.30 else 3 if up <= 0.40 else 2 if up <= 0.60 else 1
        d["s_rep"] = 5 if rb["rep"] <= 0.01 else 4 if rb["rep"] <= 0.02 else 3 if rb["rep"] <= 0.04 else 1
        # intégration : masse / socle / armoire (jugement documenté)
        d["s_integ"] = {"LR Mate 200iD/7L": 5, "LR-10iA/10": 4, "M-10iD/12": 2, "CRX-10iA/L": 4,
                        "M-3iA/6A (delta)": 1, "SR-6iA (SCARA)": 3}[rb["name"]]
        d["s_safety"] = 4 if rb["collab"] else 2
        W = dict(reach=25, cycle=30, payload=10, rep=10, integ=15, safety=10)
        d["score"] = (W["reach"] * d["s_reach"] + W["cycle"] * d["s_cycle"] + W["payload"] * d["s_payload"]
                      + W["rep"] * d["s_rep"] + W["integ"] * d["s_integ"] + W["safety"] * d["s_safety"]) / 5.0
        d["eliminated"] = bool(d["elim"])
        out.append(d)
    return out, dict(reach=25, cycle=30, payload=10, rep=10, integ=15, safety=10)

# --------------------------------------------------------------------------------------
# 4. TEMPS DE CYCLE (modèle analytique trapézoïdal + rotation J1)
# --------------------------------------------------------------------------------------
CYC = SimpleNamespace(
    v=1.8, a=9.0,                 # m/s, m/s²  (TCP, charge faible, ACC ≤ 100 selon préconisations FANUC)
    j1=300.0, j1_ov=0.12,         # °/s (catalogue LR-10iA/10), s d'accélération/décélération J1 (HYP)
    k_blend=0.25,                 # part du temps « local » recouverte par les trajectoires en CNT (HYP)
    k_safe=1.10,                  # coefficient de sécurité simulation -> réel (HYP)
    t_pick=0.34,                  # approche 50 mm + vide amorcé avant contact + retrait 50 mm
    t_rack_double=0.40,           # descente 60 mm + dépose/prise simultanées + remontée
    t_rack_place=0.33, t_rack_pick=0.70,   # outil simple : dépose, puis décalage de 221 mm + prise
    t_cale=0.55,                  # descente 60 mm + insertion 8 mm à 40 mm/s + libération + retrait
    z_pick=940.0, z_rack=960.0, z_cale=950.0, z_clear=60.0,
)

def _tt(d_mm, v=None, a=None):
    v = CYC.v if v is None else v
    a = CYC.a if a is None else a
    d = d_mm / 1000.0
    return 2 * math.sqrt(d / a) if d <= v * v / a else d / v + v / a

def _angle(p, c): return math.degrees(math.atan2(p[1] - c[1], p[0] - c[0]))

def _sweep(a, b):
    d = abs(a - b) % 360
    return min(d, 360 - d)

def _transfer(p, q, robot):
    d = math.dist(p, q)
    sw = _sweep(_angle(p, robot), _angle(q, robot))
    t_cart = _tt(d)
    t_j1 = sw / CYC.j1 + CYC.j1_ov
    return max(t_cart, t_j1), d, sw, t_cart, t_j1

def calc_cycle(L):
    R = L.robot
    P = [(x, y, CYC.z_pick + CYC.z_clear) for (x, y) in L.pick_pts]
    ri = [L.imprints[i] for i in L.used_imprints]
    RK = [(x, y, CYC.z_rack + CYC.z_clear) for (x, y) in ri]
    res = SimpleNamespace()
    res.rows = {}
    for mode in ("double", "simple"):
        vals = []
        detail = None
        for side in "WE":
            for ci, C in enumerate(L.alveoles[side]):
                Cp = (C[0], C[1], CYC.z_cale + CYC.z_clear)
                for Pp in P:
                    for Rp in RK:
                        t1, d1, s1, *_ = _transfer(Pp, Rp, R)
                        t2, d2, s2, *_ = _transfer(Rp, Cp, R)
                        t3, d3, s3, *_ = _transfer(Cp, Pp, R)
                        tr = t1 + t2 + t3
                        if mode == "double":
                            loc = CYC.t_pick + CYC.t_rack_double + CYC.t_cale
                        else:
                            loc = CYC.t_pick + CYC.t_rack_place + CYC.t_rack_pick + CYC.t_cale
                        tot = (tr + loc - CYC.k_blend * loc) * CYC.k_safe
                        vals.append(tot)
                        if side == "W" and ci == 4 and Pp is P[1] and Rp is RK[0]:
                            detail = dict(t1=t1, d1=d1, s1=s1, t2=t2, d2=d2, s2=s2, t3=t3, d3=d3, s3=s3, tr=tr, loc=loc, tot=tot)
        res.rows[mode] = dict(mean=sum(vals) / len(vals), min=min(vals), max=max(vals), detail=detail, n=len(vals))
    return res

def cycle_timeline(L, mode="double"):
    """Décomposition d'un cycle moyen en opérations (pour le diagramme de Gantt)."""
    det = calc_cycle(L).rows[mode]["detail"]
    ops = []
    t = 0.0
    def add(name, dur, kind):
        nonlocal t
        ops.append((name, t, dur, kind)); t += dur
    if mode == "double":
        add("Prise convoyeur (G1)", CYC.t_pick * (1 - CYC.k_blend), "proc")
        add("Transfert P → R (+ bascule 90°)", det["t1"], "move")
        add("Dépose G1 / prise G2 sur rack", CYC.t_rack_double * (1 - CYC.k_blend), "proc")
        add("Transfert R → C", det["t2"], "move")
        add("Insertion cale (5 N)", CYC.t_cale * (1 - CYC.k_blend), "proc")
        add("Transfert C → P", det["t3"], "move")
    else:
        add("Prise convoyeur", CYC.t_pick * (1 - CYC.k_blend), "proc")
        add("Transfert P → R", det["t1"], "move")
        add("Dépose rack", CYC.t_rack_place * (1 - CYC.k_blend), "proc")
        add("Décalage + prise rack", CYC.t_rack_pick * (1 - CYC.k_blend), "proc")
        add("Transfert R → C", det["t2"], "move")
        add("Insertion cale (5 N)", CYC.t_cale * (1 - CYC.k_blend), "proc")
        add("Transfert C → P", det["t3"], "move")
    return ops, t

def cycle_sensitivity(L, takt):
    """Sensibilité du cycle moyen (mode double) à v, a et au coefficient de sécurité."""
    global CYC
    base = (CYC.v, CYC.a, CYC.k_safe)
    out = []
    for name, dv, da, ks in [("Nominal", 1.0, 1.0, 1.10), ("Accélérations −20 %", 1.0, 0.8, 1.10),
                              ("Vitesses −20 %", 0.8, 1.0, 1.10), ("v et a −20 %", 0.8, 0.8, 1.10),
                              ("Coefficient 1,25", 1.0, 1.0, 1.25), ("Optimisé (v +15 %, a +15 %)", 1.15, 1.15, 1.10)]:
        CYC.v, CYC.a, CYC.k_safe = base[0] * dv, base[1] * da, ks
        m = calc_cycle(L).rows["double"]["mean"]
        out.append((name, m, 1 - m / takt))
    CYC.v, CYC.a, CYC.k_safe = base
    return out

# --------------------------------------------------------------------------------------
# 5. PRÉHENSION PAR VENTOUSE (formules du dossier, docx « Ressources complémentaires »)
# --------------------------------------------------------------------------------------
FSGA = [  # type, force d'aspiration N, force de rupture N, volume cm3, diamètre tuyau mm (extrait fabricant)
    (11, 0.95, 3.8, 0.225), (14, 1.20, 5.0, 0.420), (16, 2.30, 6.7, 0.750), (20, 4.70, 10.7, 1.150),
    (22, 5.70, 15.2, 1.400), (25, 5.30, 17.3, 2.944), (33, 13.60, 39.6, 4.750), (43, 22.80, 64.5, 9.250),
    (53, 51.30, 95.0, 26.488), (63, 85.00, 135.0, 43.829),
]

def f_th(case, m, a, mu, S):
    if case == 1: return m * (G + a) * S
    if case == 2: return m * (G + a / mu) * S
    if case == 3: return (m / mu) * (G + a) * S
    raise ValueError

def calc_vacuum(p=INPUT, L=None):
    v = SimpleNamespace()
    v.m, v.mu, v.S = p.m_flacon, 0.5, 2.0
    # phases : (libellé, cas, accélération m/s²)
    v.phases = [
        ("Transfert, flacon à plat sous la ventouse (accélération maxi cellule)", 2, CYC.a),
        ("Bascule / maintien à la verticale (devant le rack)", 3, 3.0),
        ("Insertion, ventouse verticale, flacon à plat (5 N)", 1, 2.0),
    ]
    v.rows = []
    for lab, case, a in v.phases:
        f = f_th(case, v.m, a, v.mu, v.S)
        v.rows.append(dict(label=lab, case=case, a=a, f=f))
    v.f_req = max(r["f"] for r in v.rows)
    v.cup = None
    for t, fa, fr, vol in FSGA:
        if fa >= v.f_req:
            v.cup = dict(type=t, f=fa, f_break=fr, vol=vol); break
    # contrainte géométrique : plastron 54 mm / face de tête 45 x ~30 mm
    v.plastron_w = p.flacon["W_torso"]
    v.head_top = (p.flacon["W_head_top"], 30.0)    # mesuré sur FF-2027-BTL-001 (vue de dessus)
    v.cup_fit_plastron = v.cup["type"] <= v.plastron_w - 6
    v.head_cup_max = min(v.head_top)               # diamètre max. sur la face de tête
    v.head_cup_f = max([fa for t, fa, *_ in FSGA if t <= v.head_cup_max - 3], default=0)
    v.f_static_head = f_th(1, v.m, 0.0, v.mu, v.S)
    # marge réelle
    v.S_eff = [v.cup["f"] / (r["f"] / v.S) for r in v.rows]
    # éjecteur SCPS 10 : vide max -850 mbar, débit 36 l/min, conso 46 l/min
    v.ej = dict(name="SCPS 10 G02 NO M12-5 PNP", Q_lpm=36.0, cons_lpm=46.0, vmax_mbar=850.0)
    v.V_cm3 = v.cup["vol"] + math.pi * (0.003 ** 2) * 0.40 * 1e6   # tuyau Ø6 x 0,40 m  (cm3)
    v.tau = v.V_cm3 / (v.ej["Q_lpm"] * 1000 / 60.0)                 # s
    v.p_target = 700.0
    v.t_evac = v.tau * math.log(1 / (1 - v.p_target / v.ej["vmax_mbar"]))
    v.k_leak = 2.5
    v.t_evac_real = v.t_evac * v.k_leak
    v.air_per_cycle_l = v.ej["cons_lpm"] / 60.0 * (0.9 + 0.1) * 1.0   # ~1 s de vide par cycle (2 cups en alternance)
    # compliance : raideur pour 5 N
    v.stroke_mm = 5.0
    v.k_spring = p.snap_force_N / v.stroke_mm
    v.dF_pos = v.k_spring * 0.5          # N pour ±0,5 mm de défaut de position de la cale
    # moment de bascule d'une ventouse unique en tête (option rejetée)
    v.L_cg = 0.07
    v.M_head = p.m_flacon * G * v.L_cg
    return v

# --------------------------------------------------------------------------------------
# 6. PESÉE, INTERCALAIRES, COMMUNICATION
# --------------------------------------------------------------------------------------
def calc_weighing(cycle_mean, p=INPUT):
    w = SimpleNamespace()
    w.dwell = cycle_mean                                 # un flacon reste un cycle sur l'empreinte (outil double)
    w.margin = w.dwell - p.weigh_wait_s
    w.res_req = p.weigh_tol_g / 10.0                      # résolution ≤ tolérance/10 : 0,2 g
    w.range_g = 600.0
    w.counts_req = w.range_g / w.res_req
    w.bits_req = math.ceil(math.log2(w.counts_req))
    w.res_16 = w.range_g / 2 ** 16
    w.tol_pct = p.weigh_tol_g / (p.m_flacon * 1000) * 100
    return w

def calc_shuttle(cad, p=INPUT):
    s = SimpleNamespace()
    s.fill = cad.fill_s
    s.L_travel = 1.8       # m, HYP : course utile par convoyeur
    s.v = 0.30             # m/s, HYP (EC310 : 0,1 à 1,0 m/s)
    s.t_leg = s.L_travel / s.v
    s.t_index = 2.0        # s, HYP : positionnement/indexation par butée + 2 pions
    s.t_budget = s.fill
    s.t_exch_max = s.fill - 2 * s.t_leg - s.t_index
    s.t_exch_target = 15.0
    s.margin = s.t_exch_max - s.t_exch_target
    return s

def calc_comm(cad, p=INPUT):
    c = SimpleNamespace()
    c.cyc_bytes_in, c.cyc_bytes_out = 16, 16
    c.frame_overhead = 84       # octets sur le fil (Ethernet + préambule + IFG, trame mini)
    c.cycle_ms = 8.0
    c.bw_kbps = 2 * c.frame_overhead * 8 / (c.cycle_ms / 1000) / 1000   # aller + retour
    c.bw_pct = c.bw_kbps / 100_000 * 100
    c.rec_bytes = 40
    c.rec_total_MB = p.volume * c.rec_bytes / 1e6
    c.rec_day_kB = cad.per_day * c.rec_bytes / 1e3
    c.img_mpx = 5.0
    c.img_MB = c.img_mpx * 1.0       # 8 bits mono
    c.img_rate = 1 / cad.takt
    c.img_Mbps = c.img_MB * c.img_rate * 8
    c.img_pct = c.img_Mbps / 1000 * 100
    c.ng_rate = 0.01
    c.ng_GB = p.volume * c.ng_rate * c.img_MB / 1000
    c.all_TB = p.volume * c.img_MB / 1e6
    return c

IO_TABLE = [
    # (sens, signal, type, source/destination)
    ("DO robot", "Vide ventouse G1 (ON)", "TOR 24 V", "Électrovanne / éjecteur SCPS G1"),
    ("DO robot", "Soufflage G1", "TOR 24 V", "Éjecteur G1"),
    ("DO robot", "Vide ventouse G2 (ON)", "TOR 24 V", "Éjecteur G2"),
    ("DO robot", "Soufflage G2", "TOR 24 V", "Éjecteur G2"),
    ("DO robot", "Dégagement G1 / G2", "TOR 24 V", "Vérins de dégagement (2 sorties)"),
    ("DO robot", "Déclencheur caméra", "TOR 24 V", "iRVision 2D (trigger)"),
    ("DI robot", "Contrôle vide G1 / G2", "TOR PNP", "Vacuostats intégrés SCPS (2 entrées)"),
    ("DI robot", "Fin de course compliance G1 / G2", "TOR PNP", "Détecteurs inductifs (2 entrées)"),
    ("DI robot", "Rangée de prise présente", "TOR PNP", "Cellule photoélectrique sur convoyeur d'entrée"),
    ("DI robot", "Poids validé empreinte 3 / 4", "TOR 24 V", "Boîtier de pesée (sorties 3 et 4 sur 6)"),
    ("DI robot", "Intercalaire W / E indexé", "TOR PNP", "Détecteurs butée + pions (2 entrées)"),
    ("UOP (UI)", "PNS1–8, PNSTROBE, PROD_START", "Profinet / EtherNet/IP", "Automate : sélection du programme (UI 9–18)"),
    ("UOP (UO)", "CMDENBL, SYSRDY, PROGRUN, FAULT, BUSY", "Profinet / EtherNet/IP", "Automate : état robot (UO 1–10)"),
    ("Sécurité", "EMGIN, FENCE1, SFSPD, HOLD", "Câblage 2 canaux", "Arrêt d'urgence, portes, rideaux (hors réseau standard)"),
]

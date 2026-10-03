#!/usr/bin/env python3
"""
Builds the static, animated design SVGs used by the profile README:
banner, profile card, tech stack, featured projects, career timeline and logo,
each in a dark and a light variant. Live GitHub numbers (stats, languages,
achievements) are rendered separately by generate_profile_assets.py.

Everything is plain SVG + SMIL animation, so it renders inside GitHub's
<img> sandbox with no external fonts, scripts or image services.

Featured projects are partly automatic: any public repo of GITHUB_USER that
has the GitHub topic "featured" gets its own card (title from the repo name,
text from its description, tags from its other topics) plus a link badge in
README.md. The "Refresh Profile" workflow re-runs this script every day, so
tagging a repo on GitHub is all it takes. Hand-written entries in PROJECTS
cover private or company work.

Edit the content blocks below, then re-run from the repo root:
    python .github/scripts/build_design_assets.py
"""
import base64
import json
import math
import os
import random
import re
import sys
import urllib.error
import urllib.parse
import urllib.request
from textwrap import wrap
from xml.sax.saxutils import escape

FONT = "'Segoe UI', ui-sans-serif, system-ui, -apple-system, 'Helvetica Neue', Arial, sans-serif"
MONO = "'SFMono-Regular', 'Cascadia Code', Consolas, 'Courier New', monospace"

THEME = {
    "dark": dict(
        bg0="#090C17", bg1="#0D1122", bg2="#131735", panel="#121733", panel_op="0.74",
        panel_stroke="#2B3358", chip_fill="#141A31", chip_stroke="#283153",
        hairline="#1E2541", text_primary="#FFFFFF", text_secondary="#A5AECB",
        text_muted="#6F7898", a1="#8B5CF6", a2="#22D3EE", track="#222A47",
        ok="#22C55E", warn="#F59E0B", dot="#262E4F", name_from="#FFFFFF",
        name_to="#22D3EE", glow="0.18", sheen="0.08",
    ),
    "light": dict(
        bg0="#FFFFFF", bg1="#FAF9FF", bg2="#F1EEFF", panel="#FFFFFF", panel_op="0.86",
        panel_stroke="#DCD7F5", chip_fill="#F7F6FF", chip_stroke="#E0DCF6",
        hairline="#E8E5F8", text_primary="#14121F", text_secondary="#57546F",
        text_muted="#8B88A3", a1="#7C3AED", a2="#0891B2", track="#ECE9FB",
        ok="#16A34A", warn="#D97706", dot="#DCD8F2", name_from="#14121F",
        name_to="#7C3AED", glow="0.10", sheen="0.5",
    ),
}

ROOT = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".."))
OUT_DIR = os.path.join(ROOT, "assets")
README = os.path.join(ROOT, "README.md")
FEATURED_CACHE = os.path.join(ROOT, ".github", "featured-projects.json")

GITHUB_USER = "AtrePramod"
FEATURE_TOPIC = "featured"
MAX_AUTO_PROJECTS = 6


# ─────────────────────────────── content ────────────────────────────────

NAME = "Pramod Atre"
INITIALS = "PA"
ROLES = [
    "Full-Stack Developer",
    "React.js Engineer",
    "NestJS API Developer",
    "AI-Powered App Builder",
    "Go Backend Developer",
]
TAGLINE = "Secure, scalable web apps — from schema to screen."

TECH_ROWS = [
    ("FRONTEND", "UI & state", [
        ("React", "react"), ("Next.js", "next"), ("Redux", "redux"),
        ("Tailwind CSS", "tailwind"), ("Material UI", "mui"),
    ]),
    ("BACKEND", "APIs & auth", [
        ("Node.js", "node"), ("NestJS", "nest"), ("Express", "express"),
        ("Go · Gin", "go"), ("TypeScript", "ts"),
    ]),
    ("DATA & OPS", "storage & deploy", [
        ("PostgreSQL", "pg"), ("MySQL", "mysql"), ("MongoDB", "mongo"),
        ("Nginx · PM2", "server"), ("Git & GitHub", "git"),
    ]),
    ("AI / ML", "models & serving", [
        ("Python", "python"), ("TensorFlow", "tensorflow"), ("scikit-learn", "sklearn"),
        ("Pandas", "pandas"), ("Flask", "flask"),
    ]),
]

PROJECTS = [
    dict(title="XL-BI", status="Live", tone="ok", icon="bi",
         desc="Revenue-generating product I built and run end to end — frontend, "
              "architecture and database — self-hosted on a VPS with Nginx, SSL/TLS and PM2.",
         tags=["React", "Node.js", "PostgreSQL", "Nginx"], link="xl-bi.com", url="https://xl-bi.com"),
    dict(title="Loan Lead Management System", status="Production", tone="ok", icon="funnel",
         desc="Lead-tracking platform for a financial services client. I owned the "
              "backend, the REST APIs and the production deployment.",
         tags=["MongoDB", "Express", "React", "Node.js"], link="loanzil.com", url="https://loanzil.com"),
    dict(title="AI Investment Allocation Engine", status="Hackathon", tone="warn", icon="chip",
         desc="TensorFlow/Keras neural network that maps an investor's age, salary and "
              "risk appetite to clustered stock portfolios, served by a Flask API to a React wizard.",
         tags=["TensorFlow", "scikit-learn", "Flask", "React"], link="AtrePramod/allocationengine",
         repo="allocationengine", url="https://github.com/AtrePramod/allocationengine"),
    dict(title="Learning & Course Platform", status="Production", tone="ok", icon="book",
         desc="Course platform at ISKCON NVCC with auth, course assignment and dashboards — "
              "part of a suite serving ~5,000 users a day, peaking at 15,000.",
         tags=["React", "NestJS", "PostgreSQL", "MUI"], link="ISKCON NVCC · internal"),
    dict(title="Smart Dairy Management", status="Delivered", tone="a1", icon="drop",
         desc="Backend for milk collection, purchase & delivery workflows and financial "
              "ledgers, with RBAC and tuned SQL for daily operational reporting.",
         tags=["Node.js", "Express", "MySQL"], link="Vikern Smart Invent"),
    dict(title="Restaurant Management API", status="Open Source", tone="a2", icon="api",
         desc="30+ endpoint REST backend in Go with JWT middleware, bcrypt hashing, "
              "validation and pagination — covered by 91 passing Postman tests.",
         tags=["Go", "Gin", "MongoDB", "JWT"], link="AtrePramod/Restaurant-Management",
         repo="Restaurant-Management", url="https://github.com/AtrePramod/Restaurant-Management"),
]

TIMELINE = [
    ("2019 – 2022", "Diploma · IT", "MSBTE — programming foundations", "book"),
    ("2022 – 2025", "B.E. · Information Technology", "SPPU — Dr. Vithalrao Vikhe Patil COE", "cap"),
    ("Oct 2024", "Full-Stack Intern", "EonWeave — Next.js SSR company site", "code"),
    ("Jan 2025", "Software Engineer", "Vikern — Smart Dairy backend, MySQL", "db"),
    ("Aug 2025 – Now", "Software Engineer", "ISKCON NVCC — React + NestJS, 15K peak users", "layers"),
    ("Ongoing", "Building XL-BI", "Live product — design to deployment", "rocket"),
]

METRICS = [
    ("1+ yr", "production experience"),
    ("15K", "peak daily users served"),
    ("4+", "production apps shipped"),
]


# ─────────────────────────────── helpers ────────────────────────────────

def esc(s):
    return escape(s)


def svg_open(w, h, label):
    return (f'<svg width="{w}" height="{h}" viewBox="0 0 {w} {h}" '
            f'xmlns="http://www.w3.org/2000/svg" role="img" aria-label="{esc(label)}">')


def write(name, svg):
    path = os.path.join(OUT_DIR, name)
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        f.write(svg)
    print("wrote", os.path.relpath(path))


def lin_grad(gid, c1, c2, x2=1, y2=0):
    return (f'<linearGradient id="{gid}" x1="0" y1="0" x2="{x2}" y2="{y2}">'
            f'<stop offset="0%" stop-color="{c1}"/><stop offset="100%" stop-color="{c2}"/></linearGradient>')


def pulse_outline(w, h, rx, color, dur, begin, peak="0.5", width="1.2"):
    return (f'<rect width="{w}" height="{h}" rx="{rx}" fill="none" stroke="{color}" stroke-width="{width}" opacity="0">'
            f'<animate attributeName="opacity" values="0;{peak};0" dur="{dur}s" begin="{begin:.2f}s" repeatCount="indefinite"/></rect>')


def float_y(dur, begin, amp=3):
    return (f'<animateTransform attributeName="transform" type="translate" values="0,0; 0,-{amp}; 0,0" '
            f'dur="{dur}s" begin="{begin:.2f}s" repeatCount="indefinite"/>')


# ─────────────────────────────── icons ──────────────────────────────────
# Every icon is drawn around (0,0) inside a ~36px box, using only theme colours.

def icon(kind, t):
    a1, a2, bg = t["a1"], t["a2"], t["chip_fill"]
    s = lambda c, w=2: f'fill="none" stroke="{c}" stroke-width="{w}" stroke-linecap="round" stroke-linejoin="round"'
    if kind == "react":
        orbits = "".join(f'<ellipse rx="17" ry="6.5" {s(a2, 1.8)} transform="rotate({a})"/>' for a in (0, 60, 120))
        return (f'<g>{orbits}<circle r="2.8" fill="{a2}"/>'
                f'<animateTransform attributeName="transform" type="rotate" from="0" to="360" dur="24s" repeatCount="indefinite"/></g>')
    if kind == "next":
        return (f'<circle r="15" {s(a2)}/><path d="M-6,7 V-7 L8,11" {s(a2, 2.2)}/>'
                f'<line x1="6" y1="-7" x2="6" y2="2" {s(a1, 2.2)}/>')
    if kind == "redux":
        return (f'<path d="M-3,-14 C9,-15 16,-4 11,7" {s(a2, 2.4)}/>'
                f'<path d="M11,7 C4,17 -11,15 -15,5" {s(a1, 2.4)}/>'
                f'<path d="M-15,5 C-18,-5 -11,-13 -3,-14" {s(a2, 2.4)}/>'
                f'<circle cx="-3" cy="-14" r="3.2" fill="{a1}"/><circle cx="11" cy="7" r="3.2" fill="{a2}"/>'
                f'<circle cx="-15" cy="5" r="3.2" fill="{a1}"/>')
    if kind == "tailwind":
        return (f'<path d="M-12,-4 C-8,-12 0,-12 4,-6 C7,-2 12,-2 16,-8" {s(a2, 3)}/>'
                f'<path d="M-16,6 C-12,-2 -4,-2 0,4 C3,8 8,8 12,2" {s(a1, 3)}/>')
    if kind == "mui":
        return (f'<path d="M-15,10 V-7 L-5,-1 L5,-7 V10" {s(a2, 2.6)}/>'
                f'<rect x="10" y="-9" width="6" height="6" rx="1.2" fill="{a1}"/>'
                f'<line x1="13" y1="1" x2="13" y2="10" {s(a1, 2.6)}/>')
    if kind == "node":
        pts = " ".join(f"{16*math.cos(math.radians(-90+60*k)):.1f},{16*math.sin(math.radians(-90+60*k)):.1f}" for k in range(6))
        return (f'<polygon points="{pts}" {s(a2)}/>'
                f'<text y="4.5" text-anchor="middle" font-family="{FONT}" font-size="11.5" font-weight="800" fill="{a1}">JS</text>')
    if kind == "nest":
        return (f'<path d="M-13,9 C-17,-3 -8,-15 5,-13 C11,-12 15,-7 14,-1 C9,-7 1,-6 -3,0 C-6,5 -6,9 -13,9 Z" fill="{a1}"/>'
                f'<circle cx="7" cy="-7" r="1.9" fill="{bg}"/>'
                f'<path d="M-3,7 C2,12 9,11 13,5" {s(a2)}/>')
    if kind == "express":
        return (f'<text y="6" text-anchor="middle" font-family="{FONT}" font-size="22" font-weight="700" fill="{a2}">ex</text>'
                f'<line x1="-12" y1="12" x2="12" y2="12" {s(a1, 2)}/>')
    if kind == "go":
        lines = "".join(f'<line x1="{x1}" y1="{y}" x2="{x2}" y2="{y}" {s(a1)}/>' for x1, x2, y in ((-22, -15, -5), (-24, -16, 0), (-22, -15, 5)))
        return (f'{lines}<text x="4" y="7.5" text-anchor="middle" font-family="{FONT}" font-size="21" '
                f'font-weight="800" font-style="italic" fill="{a2}">GO</text>')
    if kind == "ts":
        return (f'<rect x="-15" y="-15" width="30" height="30" rx="5" fill="{a1}"/>'
                f'<text x="11" y="11" text-anchor="end" font-family="{FONT}" font-size="13" font-weight="800" fill="#FFFFFF">TS</text>')
    if kind in ("pg", "mysql", "db"):
        label = {"pg": "PG", "mysql": "My", "db": ""}[kind]
        return (f'<ellipse cy="-10" rx="14" ry="5" {s(a2)}/>'
                f'<path d="M-14,-10 v16 a14,5 0 0 0 28,0 v-16" {s(a2)}/>'
                + (f'<text y="6" text-anchor="middle" font-family="{FONT}" font-size="10" font-weight="800" fill="{a1}">{label}</text>'
                   if label else f'<path d="M-14,-2 a14,5 0 0 0 28,0" {s(a1)}/>'))
    if kind == "mongo":
        return (f'<path d="M0,-17 C9,-8 9,6 0,14 C-9,6 -9,-8 0,-17 Z" {s(a2)}/>'
                f'<line x1="0" y1="-11" x2="0" y2="19" {s(a1, 2)}/>')
    if kind == "server":
        return (f'<rect x="-15" y="-13" width="30" height="11" rx="3" {s(a2, 1.8)}/>'
                f'<rect x="-15" y="2" width="30" height="11" rx="3" {s(a2, 1.8)}/>'
                f'<line x1="-10" y1="-7.5" x2="0" y2="-7.5" {s(a2, 1.6)}/><line x1="-10" y1="7.5" x2="0" y2="7.5" {s(a2, 1.6)}/>'
                f'<circle cx="9" cy="-7.5" r="2" fill="{t["ok"]}"><animate attributeName="opacity" values="0.3;1;0.3" dur="1.4s" repeatCount="indefinite"/></circle>'
                f'<circle cx="9" cy="7.5" r="2" fill="{a1}"/>')
    if kind == "git":
        return (f'<line x1="-11" y1="11" x2="11" y2="-11" {s(a2)}/>'
                f'<circle cx="-11" cy="11" r="3.6" fill="{a1}" stroke="{a2}" stroke-width="1.6"/>'
                f'<circle cx="11" cy="-11" r="3.6" fill="{a1}" stroke="{a2}" stroke-width="1.6"/>'
                f'<circle cx="1" cy="-1" r="3.6" fill="{a1}" stroke="{a2}" stroke-width="1.6"/>'
                f'<path d="M-3,-3 C-8,-3 -8,4 -11,7" {s(a2, 1.6)}/>')
    if kind == "bi":
        bars = ""
        for i, (x, h0, h1) in enumerate(((-12, 8, 13), (-3, 13, 18), (6, 17, 22))):
            bars += (f'<rect x="{x}" y="{12-h0}" width="6" height="{h0}" rx="1.2" fill="{a1 if i < 2 else a2}">'
                     f'<animate attributeName="height" values="{h0};{h1};{h0}" dur="2.4s" begin="{i*0.3}s" repeatCount="indefinite"/>'
                     f'<animate attributeName="y" values="{12-h0};{12-h1};{12-h0}" dur="2.4s" begin="{i*0.3}s" repeatCount="indefinite"/></rect>')
        return bars + f'<path d="M-14,-6 L-5,-11 L3,-8 L13,-15" {s(a2, 1.8)}/>'
    if kind == "funnel":
        return (f'<path d="M-13,-10 H13 L4,1 V11 L-4,14 V1 Z" {s(a2)}/>'
                f'<circle r="2.2" fill="{a1}"><animate attributeName="cy" values="-17;4" dur="1.8s" repeatCount="indefinite"/>'
                f'<animate attributeName="opacity" values="0;1;1;0" keyTimes="0;0.2;0.75;1" dur="1.8s" repeatCount="indefinite"/></circle>')
    if kind == "book":
        return (f'<path d="M-12,-8 C-12,-11 -5,-11 0,-9 C5,-11 12,-11 12,-8 L12,9 C12,6 5,6 0,8 C-5,6 -12,6 -12,9 Z" {s(a2, 1.8)}/>'
                f'<line x1="0" y1="-9" x2="0" y2="8" {s(a1, 1.8)}/>')
    if kind == "drop":
        return (f'<path d="M0,-15 C6,-7 10,-2 10,4 A10,10 0 0 1 -10,4 C-10,-2 -6,-7 0,-15 Z" {s(a2)}/>'
                f'<path d="M-6,5 C-3,2 0,8 3,5 C4.5,3.5 5.5,4 6.5,5" {s(a1, 1.8)}/>')
    if kind == "api":
        return (f'<path d="M-6,-12 C-10,-12 -10,-8 -10,-4 C-10,-1 -12,0 -14,0 C-12,0 -10,1 -10,4 C-10,8 -10,12 -6,12" {s(a2)}/>'
                f'<path d="M6,-12 C10,-12 10,-8 10,-4 C10,-1 12,0 14,0 C12,0 10,1 10,4 C10,8 10,12 6,12" {s(a2)}/>'
                f'<circle r="3" fill="{a1}"><animate attributeName="opacity" values="0.35;1;0.35" dur="1.6s" repeatCount="indefinite"/></circle>')
    if kind == "chip":
        legs = "".join(f'<line x1="{x1}" y1="{y1}" x2="{x2}" y2="{y2}" {s(a2, 1.6)}/>' for x1, y1, x2, y2 in
                       ((-9, 0, -14, 0), (9, 0, 14, 0), (0, -9, 0, -14), (0, 9, 0, 14),
                        (-9, -5, -13, -5), (9, 5, 13, 5), (-5, 9, -5, 13), (5, -9, 5, -13)))
        return (f'<rect x="-9" y="-9" width="18" height="18" rx="4" {s(a2, 1.8)}/>{legs}'
                f'<circle r="3.2" fill="{a1}"><animate attributeName="opacity" values="0.4;1;0.4" dur="2s" repeatCount="indefinite"/></circle>')
    if kind == "cap":
        return (f'<path d="M-15,-4 L0,-11 L15,-4 L0,3 Z" {s(a2, 1.8)}/>'
                f'<path d="M-8,0 V6 C-4,10 4,10 8,6 V0" {s(a2, 1.8)}/>'
                f'<line x1="15" y1="-4" x2="15" y2="6" {s(a1, 1.8)}/>')
    if kind == "code":
        return (f'<path d="M-5,-9 L-13,0 L-5,9" {s(a2)}/><path d="M5,-9 L13,0 L5,9" {s(a2)}/>'
                f'<line x1="1.5" y1="-11" x2="-1.5" y2="11" {s(a1)}/>')
    if kind == "layers":
        return (f'<path d="M0,-11 L12,-5 L0,1 L-12,-5 Z" {s(a2, 1.8)}/>'
                f'<path d="M-12,0 L0,6 L12,0" {s(a1, 1.8)}/><path d="M-12,5 L0,11 L12,5" {s(a2, 1.8)}/>')
    if kind == "rocket":
        return (f'<path d="M0,-13 C6,-8 7,0 4,7 H-4 C-7,0 -6,-8 0,-13 Z" {s(a2, 1.8)}/>'
                f'<circle cy="-3" r="2.4" fill="{a1}"/>'
                f'<path d="M-4,2 L-9,9 L-4,7" {s(a2, 1.6)}/><path d="M4,2 L9,9 L4,7" {s(a2, 1.6)}/>'
                f'<path d="M-2.5,9 L0,15 L2.5,9 Z" fill="{t["warn"]}">'
                f'<animate attributeName="opacity" values="0.3;1;0.3" dur="0.9s" repeatCount="indefinite"/></path>')
    if kind == "browser":
        return (f'<rect x="-15" y="-12" width="30" height="24" rx="4" {s(a2, 1.8)}/>'
                f'<line x1="-15" y1="-5" x2="15" y2="-5" {s(a2, 1.6)}/>'
                f'<circle cx="-10.5" cy="-8.5" r="1.3" fill="{a1}"/><circle cx="-6.5" cy="-8.5" r="1.3" fill="{a1}"/>'
                f'<rect x="-10" y="0" width="9" height="7" rx="1.5" fill="{a1}" opacity="0.8"/>'
                f'<line x1="3" y1="1.5" x2="10" y2="1.5" {s(a2, 1.6)}/><line x1="3" y1="5.5" x2="8" y2="5.5" {s(a2, 1.6)}/>')
    if kind == "shield":
        return (f'<path d="M0,-14 L12,-9 V1 C12,8 6,13 0,15 C-6,13 -12,8 -12,1 V-9 Z" {s(a2)}/>'
                f'<path d="M-5,0 L-1,5 L6,-5" {s(a1, 2.4)}/>')
    if kind == "python":
        return (f'<path d="M-1,-16 C6,-16 6,-11 6,-8 V-3 H-8 V-1 H9 C9,-1 12,-1 12,6 C12,13 9,14 3,14 C-3,14 -3,10 -3,10 H2 '
                f'C2,11.5 3,12 5,12 C7,12 7,10.5 7,9 V4 H-6 C-6,4 -9,4 -9,-3 C-9,-10 -6,-11 -1,-11 Z" fill="{a2}"/>'
                f'<circle cx="2" cy="-9" r="1.5" fill="{bg}"/><circle cx="-2" cy="9" r="1.5" fill="{bg}"/>')
    if kind == "tensorflow":
        return (f'<path d="M-1,-16 L-14,-9 V-2 L-7,-6 V11 L-1,15 Z" fill="{a1}"/>'
                f'<path d="M1,-16 L14,-9 V-2 L1,-9 Z" fill="{a2}"/>'
                f'<path d="M1,-5 L8,-1 V6 L1,2 Z" fill="{a2}" opacity="0.85"/>')
    if kind == "sklearn":
        return (f'<circle cx="-5" cy="3" r="10" fill="{a1}" opacity="0.85"/>'
                f'<circle cx="7" cy="-4" r="8" fill="{a2}" opacity="0.85"/>'
                f'<text x="-5" y="7" text-anchor="middle" font-family="{FONT}" font-size="10" font-weight="800" fill="#FFFFFF">ML</text>')
    if kind == "pandas":
        return (f'<rect x="-12" y="-15" width="5" height="13" rx="1" fill="{a2}"/><rect x="-12" y="2" width="5" height="13" rx="1" fill="{a2}"/>'
                f'<rect x="-2.5" y="-9" width="5" height="18" rx="1" fill="{a1}"/>'
                f'<rect x="7" y="-15" width="5" height="13" rx="1" fill="{a2}"/><rect x="7" y="2" width="5" height="13" rx="1" fill="{a2}"/>')
    if kind == "flask":
        bubbles = "".join(
            f'<circle cx="{cx}" r="1.6" fill="{a2}"><animate attributeName="cy" values="10;-2" dur="{d}s" begin="{b}s" repeatCount="indefinite"/>'
            f'<animate attributeName="opacity" values="0;1;0" dur="{d}s" begin="{b}s" repeatCount="indefinite"/></circle>'
            for cx, d, b in ((-3, 1.8, 0), (3, 2.2, 0.7)))
        return (f'<path d="M-8,4 H8 L11,10 C12,13 11,14 9,14 H-9 C-11,14 -12,13 -11,10 Z" fill="{a1}" opacity="0.85"/>'
                f'<path d="M-6,-15 H6 M-3,-15 V-5 L-12,10 C-13,13 -11,15 -9,15 H9 C11,15 13,13 12,10 L3,-5 V-15" {s(a2, 2)}/>{bubbles}')
    raise ValueError(kind)


# ─────────────────────────────── photos ─────────────────────────────────
# SVGs shown through GitHub's <img> can't load external files, so photos are
# embedded as base64. Replace assets/photo-portrait.jpg (430:552, ~860x1104)
# or assets/photo-avatar.jpg (square, ~320px) to change them.

def photo_uri(name):
    with open(os.path.join(OUT_DIR, name), "rb") as f:
        return "data:image/jpeg;base64," + base64.b64encode(f.read()).decode()


def chip(x, y, label, dot, t, dur, begin):
    w = len(label) * 7.6 + 40
    return f'''<g transform="translate({x},{y})">
    <g>{float_y(dur, begin, 6)}
      <rect width="{w:.0f}" height="34" rx="17" fill="{t["panel"]}" fill-opacity="0.92" stroke="{t["panel_stroke"]}" stroke-width="1.2"/>
      <circle cx="18" cy="17" r="4" fill="{dot}"><animate attributeName="opacity" values="0.4;1;0.4" dur="1.8s" begin="{begin}s" repeatCount="indefinite"/></circle>
      <text x="30" y="21.5" font-family="{MONO}" font-size="12.5" fill="{t["text_primary"]}">{esc(label)}</text>
    </g>
  </g>'''


def banner_photo(t):
    cx, cy, pw, ph = 976, 320, 400, 512
    hx, hy = pw / 2, ph / 2
    rnd = random.Random(5)
    sparks = "".join(
        f'<circle cx="{rnd.uniform(-hx + 20, hx - 20):.1f}" cy="{rnd.uniform(-hy + 20, hy - 20):.1f}" r="{rnd.choice((1.4, 2, 2.6))}" fill="{t["a2"]}" opacity="0">'
        f'<animate attributeName="opacity" values="0;0.8;0" dur="{3.5 + i * 0.4:.1f}s" begin="{i * 0.6:.1f}s" repeatCount="indefinite"/>'
        f'<animateTransform attributeName="transform" type="translate" values="0,0;0,-14" dur="{3.5 + i * 0.4:.1f}s" begin="{i * 0.6:.1f}s" repeatCount="indefinite"/></circle>'
        for i in range(7))
    return f'''<defs>
    <linearGradient id="scanGrad" x1="0" y1="0" x2="0" y2="1">
      <stop offset="0%" stop-color="{t["a2"]}" stop-opacity="0"/><stop offset="50%" stop-color="{t["a2"]}" stop-opacity="0.55"/>
      <stop offset="100%" stop-color="{t["a2"]}" stop-opacity="0"/></linearGradient>
    {lin_grad("frameGrad", t["a1"], t["a2"], 1, 1)}
    <clipPath id="photoClip"><rect x="{-hx}" y="{-hy}" width="{pw}" height="{ph}" rx="26"/></clipPath>
  </defs>
  <g transform="translate({cx},{cy})">
    <animateTransform attributeName="transform" type="translate" values="{cx},{cy}; {cx},{cy - 9}; {cx},{cy}"
      dur="6.5s" repeatCount="indefinite" calcMode="spline" keySplines="0.45 0 0.55 1;0.45 0 0.55 1"/>
    <rect x="{-hx - 16}" y="{-hy - 16}" width="{pw + 32}" height="{ph + 32}" rx="40" fill="none" stroke="url(#frameGrad)" stroke-width="2" opacity="0.35">
      <animate attributeName="opacity" values="0.2;0.7;0.2" dur="3.6s" repeatCount="indefinite"/>
    </rect>
    <rect x="{-hx - 8}" y="{-hy - 8}" width="{pw + 16}" height="{ph + 16}" rx="33" fill="none" stroke="{t["a2"]}" stroke-width="1.2" opacity="0.45"/>
    <g clip-path="url(#photoClip)">
      <image href="{photo_uri("photo-portrait.jpg")}" x="{-hx}" y="{-hy}" width="{pw}" height="{ph}" preserveAspectRatio="xMidYMid slice"/>
      <rect x="{-hx}" y="{-hy}" width="{pw}" height="{ph}" fill="{t["a1"]}" opacity="0.06"/>
      {sparks}
      <rect x="{-hx}" y="{-hy - 40}" width="{pw}" height="40" fill="url(#scanGrad)" opacity="0.5">
        <animate attributeName="y" values="{-hy - 40};{hy}" dur="4.2s" repeatCount="indefinite"/>
      </rect>
      <polygon points="{-hx - 40},{-hy} {-hx + 10},{-hy} {-hx - 90},{hy} {-hx - 140},{hy}" fill="#FFFFFF" opacity="0.07">
        <animateTransform attributeName="transform" type="translate" values="0,0;{pw + 200},0" dur="7s" begin="1s" repeatCount="indefinite"/>
      </polygon>
    </g>
    <rect x="{-hx}" y="{-hy}" width="{pw}" height="{ph}" rx="26" fill="none" stroke="{t["panel_stroke"]}" stroke-width="2"/>
  </g>
  {chip(718, 112, "React · Next.js", t["a2"], t, 5.2, 0.0)}
  {chip(1098, 262, "NestJS · JWT/RBAC", t["a1"], t, 6.0, 0.8)}
  {chip(712, 470, "PostgreSQL", t["a2"], t, 5.6, 1.6)}
  {chip(1112, 150, "AI · TensorFlow", t["warn"], t, 5.9, 1.2)}
  {chip(1052, 556, "live · xl-bi.com", t["ok"], t, 6.4, 0.4)}'''


# ─────────────────────────────── banner ─────────────────────────────────

def banner(t, theme):
    W, H = 1280, 640
    rnd = random.Random(11)

    defs = (
        f'<defs>'
        f'<linearGradient id="bgGrad" x1="0" y1="0" x2="1" y2="1"><stop offset="0%" stop-color="{t["bg0"]}"/>'
        f'<stop offset="55%" stop-color="{t["bg1"]}"/><stop offset="100%" stop-color="{t["bg2"]}"/></linearGradient>'
        + lin_grad("roleGrad", t["a1"], t["a2"])
        + lin_grad("nameGrad", t["name_from"], t["name_to"])
        + lin_grad("laneDown", t["a1"], t["a2"], 0, 1)
        + f'<radialGradient id="glowR" cx="78%" cy="48%" r="60%"><stop offset="0%" stop-color="{t["a1"]}" stop-opacity="{t["glow"]}"/>'
          f'<stop offset="100%" stop-color="{t["a1"]}" stop-opacity="0"/></radialGradient>'
        + f'<radialGradient id="glowL" cx="8%" cy="95%" r="55%"><stop offset="0%" stop-color="{t["a2"]}" stop-opacity="{t["glow"]}"/>'
          f'<stop offset="100%" stop-color="{t["a2"]}" stop-opacity="0"/></radialGradient>'
        + f'<linearGradient id="sheen" x1="0" y1="0" x2="0" y2="1"><stop offset="0%" stop-color="#FFFFFF" stop-opacity="{t["sheen"]}"/>'
          f'<stop offset="100%" stop-color="#FFFFFF" stop-opacity="0"/></linearGradient>'
        + f'<filter id="softGlow" x="-30%" y="-30%" width="160%" height="160%"><feGaussianBlur stdDeviation="14"/></filter>'
        + f'<pattern id="gridDots" width="32" height="32" patternUnits="userSpaceOnUse"><circle cx="2" cy="2" r="1" fill="{t["dot"]}"/></pattern>'
        f'</defs>'
    )

    out = [svg_open(W, H, f"{NAME} — Full-Stack Developer banner"), defs,
           f'<rect width="{W}" height="{H}" fill="url(#bgGrad)"/>',
           f'<rect width="{W}" height="{H}" fill="url(#gridDots)" opacity="0.8"/>',
           f'<rect width="{W}" height="{H}" fill="url(#glowR)"/>',
           f'<rect width="{W}" height="{H}" fill="url(#glowL)"/>']

    # ambient constellation
    pts = [(rnd.uniform(20, W - 20), rnd.uniform(20, H - 20)) for _ in range(26)]
    lines = []
    for i, (x1, y1) in enumerate(pts):
        for j in range(i + 1, len(pts)):
            x2, y2 = pts[j]
            if math.hypot(x2 - x1, y2 - y1) < 150:
                lines.append(f'<line x1="{x1:.1f}" y1="{y1:.1f}" x2="{x2:.1f}" y2="{y2:.1f}" opacity="0.1">'
                             f'<animate attributeName="opacity" values="0.04;0.2;0.04" dur="{5 + len(lines) % 4}s" '
                             f'begin="{len(lines) * 0.3:.1f}s" repeatCount="indefinite"/></line>')
    out.append(f'<g stroke="{t["a2"]}" stroke-width="1">{"".join(lines)}</g>')
    for i, (x, y) in enumerate(pts):
        r = 1.4 + (i % 3) * 0.5
        out.append(f'<circle cx="{x:.1f}" cy="{y:.1f}" r="{r}" fill="{t["a2"] if i % 2 else t["a1"]}" opacity="0.3">'
                   f'<animate attributeName="opacity" values="0.1;0.55;0.1" dur="{3 + (i % 5) * 0.6:.1f}s" begin="{i * 0.22:.2f}s" repeatCount="indefinite"/></circle>')

    # ── left glass panel ──
    px, py, pw, ph = 56, 72, 628, 512
    out.append(f'<rect x="{px}" y="{py}" width="{pw}" height="{ph}" rx="28" fill="{t["a1"]}" opacity="0.10" filter="url(#softGlow)"/>')
    out.append(f'<rect x="{px}" y="{py}" width="{pw}" height="{ph}" rx="28" fill="{t["panel"]}" fill-opacity="{t["panel_op"]}" '
               f'stroke="{t["panel_stroke"]}" stroke-width="1.4"/>')
    out.append(f'<path d="M {px+28} {py} h {pw-56} a28,28 0 0 1 28,28 v60 h -{pw} v-60 a28,28 0 0 1 28,-28 Z" fill="url(#sheen)"/>')

    lx = px + 56
    # greeting + status pill
    out.append(f'''<g transform="translate({lx},140)">
    <text font-family="{FONT}" font-size="24" fill="{t["text_secondary"]}">Hello</text>
    <text x="62" y="1" font-family="{FONT}" font-size="24"><tspan>&#128075;</tspan>
      <animateTransform attributeName="transform" type="rotate" values="0 74 -8;18 74 -8;-8 74 -8;14 74 -8;0 74 -8" dur="2.4s" begin="0.6s" repeatCount="indefinite"/>
    </text>
    <g transform="translate(300,-19)">
      <rect width="216" height="28" rx="14" fill="{t["ok"]}" fill-opacity="0.10" stroke="{t["ok"]}" stroke-opacity="0.45"/>
      <circle cx="17" cy="14" r="4" fill="{t["ok"]}"><animate attributeName="opacity" values="0.35;1;0.35" dur="1.8s" repeatCount="indefinite"/></circle>
      <circle cx="17" cy="14" r="4" fill="none" stroke="{t["ok"]}"><animate attributeName="r" values="4;10" dur="1.8s" repeatCount="indefinite"/><animate attributeName="opacity" values="0.7;0" dur="1.8s" repeatCount="indefinite"/></circle>
      <text x="30" y="18.5" font-family="{FONT}" font-size="12" font-weight="600" fill="{t["ok"]}">Open to Full-Stack roles</text>
    </g>
  </g>''')

    # name + animated underline
    out.append(f'''<g transform="translate({lx},200)">
    <text font-family="{FONT}" font-size="44" font-weight="700" fill="url(#nameGrad)">I&#8217;m {esc(NAME)}</text>
    <rect x="0" y="14" height="4" rx="2" fill="url(#roleGrad)">
      <animate attributeName="width" values="0;336;336;0" keyTimes="0;0.35;0.85;1" dur="3.6s" repeatCount="indefinite"/>
    </rect>
  </g>''')

    # typing roles
    cycle = 2.0 * len(ROLES)
    role_parts = []
    for i, role in enumerate(ROLES):
        w = len(role) * 15.6 + 4
        b = i * 2.0
        kt = "0;0.0900;0.1650;0.1950;1"
        role_parts.append(f'''
      <clipPath id="roleClip{i}"><rect x="0" y="-30" width="0" height="60">
        <animate attributeName="width" values="0;{w:.1f};{w:.1f};0;0" keyTimes="{kt}" dur="{cycle}s" begin="{b}s" repeatCount="indefinite"/>
      </rect></clipPath>
      <g clip-path="url(#roleClip{i})"><text x="0" y="0" fill="url(#roleGrad)">{esc(role)}</text></g>
      <rect x="0" y="-22" width="3" height="30" fill="{t["a2"]}" opacity="0">
        <animate attributeName="x" values="0;{w:.1f};{w:.1f};0;0" keyTimes="{kt}" dur="{cycle}s" begin="{b}s" repeatCount="indefinite"/>
        <animate attributeName="opacity" values="1;1;0;1;0;1;0;0" keyTimes="0;0.0900;0.1087;0.1275;0.1462;0.1650;0.1950;1" dur="{cycle}s" begin="{b}s" repeatCount="indefinite"/>
      </rect>''')
    out.append(f'<g transform="translate({lx + 2},264)" font-family="{MONO}" font-size="26" font-weight="600">{"".join(role_parts)}</g>')

    out.append(f'<text x="{lx}" y="306" font-family="{FONT}" font-size="17" fill="{t["text_secondary"]}">'
               f'Building secure, scalable web apps — from schema to screen</text>')

    # terminal window
    tx, ty, tw, th = lx, 334, pw - 112, 162
    term = [f'<rect x="{tx}" y="{ty}" width="{tw}" height="{th}" rx="14" fill="{t["bg0"]}" fill-opacity="0.75" stroke="{t["hairline"]}" stroke-width="1.2"/>',
            f'<line x1="{tx}" y1="{ty+30}" x2="{tx+tw}" y2="{ty+30}" stroke="{t["hairline"]}"/>']
    for k, c in enumerate(("#FF5F57", "#FEBC2E", "#28C840")):
        term.append(f'<circle cx="{tx+20+k*16}" cy="{ty+15}" r="5" fill="{c}" opacity="0.85"/>')
    term.append(f'<text x="{tx+tw/2}" y="{ty+19.5}" text-anchor="middle" font-family="{MONO}" font-size="11" fill="{t["text_muted"]}">~/projects/xl-bi — deploy</text>')
    tlines = [
        ("$", "npm run build &amp;&amp; pm2 reload api", t["a2"]),
        ("[ok]", "client bundled · React + TypeScript", t["ok"]),
        ("[ok]", "api online · NestJS · JWT/RBAC", t["ok"]),
        ("[ok]", "postgres migrations applied · 0 errors", t["ok"]),
    ]
    starts = [0.04, 0.22, 0.36, 0.50]
    for k, ((tag, body, col), st) in enumerate(zip(tlines, starts)):
        yy = ty + 56 + k * 24
        term.append(
            f'<text x="{tx+18}" y="{yy}" font-family="{MONO}" font-size="13.5" opacity="0">'
            f'<tspan fill="{col}" font-weight="700">{tag}</tspan><tspan fill="{t["text_secondary"]}"> {body}</tspan>'
            f'<animate attributeName="opacity" values="0;0;1;1;0" keyTimes="0;{st:.2f};{st+0.03:.2f};0.93;1" dur="8s" repeatCount="indefinite"/></text>')
    cy_ = ty + 56 + 4 * 24
    term.append(f'<text x="{tx+18}" y="{cy_}" font-family="{MONO}" font-size="13.5" font-weight="700" fill="{t["a2"]}">$</text>')
    term.append(f'<rect x="{tx+34}" y="{cy_-12}" width="8" height="15" fill="{t["a2"]}">'
                f'<animate attributeName="opacity" values="1;1;0;0" keyTimes="0;0.5;0.5;1" dur="1s" repeatCount="indefinite"/></rect>')
    out.append("".join(term))

    out.append(f'<rect x="{lx}" y="522" width="{pw-112}" height="1" fill="{t["hairline"]}"/>')
    out.append(f'<text x="{lx}" y="552" font-family="{FONT}" font-size="12.5" fill="{t["text_muted"]}" letter-spacing="1.6">'
               f'PUNE, INDIA · REACT · NESTJS · POSTGRESQL · AI/ML</text>')

    # ── right: portrait ──
    out.append(banner_photo(t))

    out.append("</svg>")
    write(f"banner-{theme}.svg", "\n".join(out))


# ──────────────────────────── architecture ──────────────────────────────

def architecture(t, theme):
    W, H = 1200, 296
    cw, ch, gap = 320, 150, 95
    x0 = (W - 3 * cw - 2 * gap) / 2
    top = 58
    cards = [
        ("browser", "Client", "React · Next.js · Redux · MUI", "Responsive UI · SSR · state management", "FRONTEND"),
        ("shield", "API Layer", "Node.js · NestJS · Express · Gin", "REST · JWT auth · RBAC · validation", "BACKEND"),
        ("db", "Data", "PostgreSQL · MySQL · MongoDB", "Schema design · TypeORM · query tuning", "DATABASE"),
    ]
    out = [svg_open(W, H, "How I build: React client, Node.js and NestJS API, PostgreSQL, MySQL and MongoDB data layer, deployed on a VPS"),
           f'<rect width="{W}" height="{H}" rx="24" fill="{t["bg1"]}" stroke="{t["chip_stroke"]}" stroke-width="1.2"/>',
           f'<text x="{x0}" y="38" font-family="{MONO}" font-size="12.5" fill="{t["text_muted"]}">// how I ship a feature, end to end</text>']
    xs = [x0 + i * (cw + gap) for i in range(3)]
    for i, ((ic, title, stack, sub, tag), x) in enumerate(zip(cards, xs)):
        out.append(f'''<g transform="translate({x:.0f},{top})">
    <rect width="{cw}" height="{ch}" rx="20" fill="{t["chip_fill"]}" stroke="{t["chip_stroke"]}" stroke-width="1.3"/>
    {pulse_outline(cw, ch, 20, t["a2"], 4.5, i * 1.1, "0.75", "1.6")}
    <g transform="translate(48,52)">
      <circle r="26" fill="{t["bg0"]}" stroke="{t["a2"]}" stroke-opacity="0.6" stroke-width="1.3"/>
      <circle r="26" fill="none" stroke="{t["a1"]}" stroke-width="1"><animate attributeName="r" values="26;32;26" dur="4.5s" begin="{i*1.1:.1f}s" repeatCount="indefinite"/><animate attributeName="opacity" values="0;0.5;0" dur="4.5s" begin="{i*1.1:.1f}s" repeatCount="indefinite"/></circle>
      {icon(ic, dict(t, chip_fill=t["bg0"]))}
    </g>
    <text x="90" y="58" font-family="{FONT}" font-size="20" font-weight="700" fill="{t["text_primary"]}">{title}</text>
    <text x="{cw-22}" y="36" text-anchor="end" font-family="{FONT}" font-size="10.5" font-weight="700" letter-spacing="1.6" fill="{t["a1"]}">{tag}</text>
    <text x="24" y="108" font-family="{MONO}" font-size="12.5" fill="{t["a2"]}">{esc(stack)}</text>
    <text x="24" y="130" font-family="{FONT}" font-size="12.5" fill="{t["text_muted"]}">{esc(sub)}</text>
  </g>''')

    # lanes: requests travel right on the upper lane, responses come back left on the lower one
    for k in range(2):
        x1, x2 = xs[k] + cw, xs[k + 1]
        for ly, direction, col, label in ((top + 58, 1, t["a1"], "request →"), (top + 96, -1, t["a2"], "← response")):
            xs_, xe = (x1, x2) if direction == 1 else (x2, x1)
            out.append(f'<line x1="{x1:.0f}" y1="{ly}" x2="{x2:.0f}" y2="{ly}" stroke="{col}" stroke-width="1.6" stroke-dasharray="4 5" opacity="0.55">'
                       f'<animate attributeName="stroke-dashoffset" values="0;{-18 * direction}" dur="1s" repeatCount="indefinite"/></line>')
            begin = 0.4 + k * 1.1 if direction == 1 else 2.6 + (1 - k) * 0.9
            out.append(f'<circle cx="{xs_:.0f}" cy="{ly}" r="4" fill="{col}" opacity="0">'
                       f'<animate attributeName="cx" values="{xs_:.0f};{xe:.0f};{xe:.0f}" keyTimes="0;0.2;1" dur="4.5s" begin="{begin:.1f}s" repeatCount="indefinite"/>'
                       f'<animate attributeName="opacity" values="0;1;1;0;0" keyTimes="0;0.03;0.18;0.22;1" dur="4.5s" begin="{begin:.1f}s" repeatCount="indefinite"/></circle>')
            out.append(f'<text x="{(x1+x2)/2:.0f}" y="{ly - 9}" text-anchor="middle" font-family="{MONO}" font-size="10.5" fill="{t["text_muted"]}">{label}</text>')

    dw = 340
    out.append(f'''<g transform="translate({(W - dw) / 2:.0f},{top + ch + 30})">
    <rect width="{dw}" height="34" rx="17" fill="{t["chip_fill"]}" stroke="{t["chip_stroke"]}"/>
    <circle cx="20" cy="17" r="4" fill="{t["ok"]}"><animate attributeName="opacity" values="0.35;1;0.35" dur="1.8s" repeatCount="indefinite"/></circle>
    <text x="{dw/2+8}" y="21.5" text-anchor="middle" font-family="{MONO}" font-size="12" fill="{t["text_secondary"]}">deployed on VPS · Nginx · PM2 · SSL</text>
  </g>''')
    out.append("</svg>")
    write(f"architecture-{theme}.svg", "\n".join(out))


# ───────────────────────────── profile card ─────────────────────────────

def profile_card(t, theme):
    W, H = 960, 220
    cx, cy = 112, 110
    out = [svg_open(W, H, f"{NAME} profile card"),
           f'<defs><linearGradient id="cardBg" x1="0" y1="0" x2="1" y2="1"><stop offset="0%" stop-color="{t["bg0"]}"/>'
           f'<stop offset="100%" stop-color="{t["bg2"]}"/></linearGradient>'
           f'<linearGradient id="borderGrad" x1="0%" y1="0%" x2="100%" y2="0%">'
           f'<stop offset="0%" stop-color="{t["a1"]}" stop-opacity="0"/><stop offset="50%" stop-color="{t["a2"]}" stop-opacity="0.9"/>'
           f'<stop offset="100%" stop-color="{t["a1"]}" stop-opacity="0"/>'
           f'<animateTransform attributeName="gradientTransform" type="translate" values="-1 0; 1 0; -1 0" dur="6s" repeatCount="indefinite"/>'
           f'</linearGradient>' + lin_grad("markGrad", t["a1"], t["a2"], 1, 1) + lin_grad("valGrad", t["a1"], t["a2"]) + '</defs>',
           f'<rect x="1" y="1" width="{W-2}" height="{H-2}" rx="24" fill="url(#cardBg)" stroke="{t["panel_stroke"]}" stroke-width="1.4"/>',
           f'<rect x="1" y="1" width="{W-2}" height="{H-2}" rx="24" fill="none" stroke="url(#borderGrad)" stroke-width="1.6"/>']

    # photo avatar
    out.append(f'''<clipPath id="avatarClip"><circle cx="{cx}" cy="{cy}" r="62"/></clipPath>
  <circle cx="{cx}" cy="{cy}" r="80" fill="none" stroke="url(#markGrad)" stroke-width="2" stroke-dasharray="5 9" opacity="0.7">
    <animateTransform attributeName="transform" type="rotate" from="0 {cx} {cy}" to="360 {cx} {cy}" dur="20s" repeatCount="indefinite"/>
  </circle>
  <circle cx="{cx}" cy="{cy}" r="71" fill="none" stroke="{t["a2"]}" stroke-width="1.2" opacity="0.35">
    <animate attributeName="r" values="69;74;69" dur="3.4s" repeatCount="indefinite"/>
  </circle>
  <image href="{photo_uri("photo-avatar.jpg")}" x="{cx-62}" y="{cy-62}" width="124" height="124" clip-path="url(#avatarClip)" preserveAspectRatio="xMidYMid slice"/>
  <circle cx="{cx}" cy="{cy}" r="62" fill="none" stroke="url(#markGrad)" stroke-width="2.4"/>
  <circle cx="{cx+44}" cy="{cy+44}" r="9" fill="{t["bg0"]}" stroke="{t["a2"]}" stroke-width="2"/>
  <circle cx="{cx+44}" cy="{cy+44}" r="4" fill="{t["ok"]}"><animate attributeName="opacity" values="0.5;1;0.5" dur="1.8s" repeatCount="indefinite"/></circle>''')

    out.append(f'''<g transform="translate(214,70)">
    <text font-family="{FONT}" font-size="30" font-weight="700" fill="{t["text_primary"]}">{esc(NAME)}</text>
    <text y="30" font-family="{FONT}" font-size="15" font-weight="600" fill="{t["a2"]}">Full-Stack Developer &#183; React &#183; Node.js &#183; NestJS &#183; AI/ML</text>
    <text y="64" font-family="{MONO}" font-size="13.5" fill="{t["text_secondary"]}">&#8220;{esc(TAGLINE)}&#8221;</text>
    <rect y="84" width="430" height="1" fill="{t["hairline"]}"/>
    <g transform="translate(0,112)" font-family="{FONT}" font-size="12" fill="{t["text_muted"]}" letter-spacing="1.2">
      <text>ISKCON NVCC</text><text x="128">PUNE, INDIA</text><text x="250">OPEN TO RELOCATE</text>
    </g>
  </g>''')

    out.append(f'<line x1="684" y1="34" x2="684" y2="{H-34}" stroke="{t["hairline"]}"/>')
    for i, (val, label) in enumerate(METRICS):
        y = 70 + i * 50
        out.append(f'''<g transform="translate(708,{y})" opacity="0">
    <animate attributeName="opacity" from="0" to="1" dur="0.8s" begin="{0.3 + i * 0.35:.2f}s" fill="freeze"/>
    <text font-family="{MONO}" font-size="22" font-weight="700" fill="url(#valGrad)">{esc(val)}</text>
    <text x="84" y="-2" font-family="{FONT}" font-size="12.5" fill="{t["text_secondary"]}">{esc(label)}</text>
  </g>''')

    out.append("</svg>")
    write(f"profile-card-{theme}.svg", "\n".join(out))


# ───────────────────────────── tech stack ───────────────────────────────

def techstack(t, theme):
    tile_w, tile_h, gap, label_w = 164, 120, 14, 150
    cols = max(len(items) for _, _, items in TECH_ROWS)
    rows = len(TECH_ROWS)
    W = label_w + cols * tile_w + (cols - 1) * gap + 10
    H = 10 + rows * tile_h + (rows - 1) * gap + 10
    out = [svg_open(W, H, "Tech stack: " + ", ".join(n for _, _, row in TECH_ROWS for n, _ in row)),
           f'<defs>{lin_grad("barGrad", t["a1"], t["a2"], 0, 1)}</defs>']
    for r, (label, sub, items) in enumerate(TECH_ROWS):
        y = 10 + r * (tile_h + gap)
        out.append(f'''<g transform="translate(4,{y})">
    <rect x="0" y="{tile_h/2-24}" width="3" height="48" rx="1.5" fill="url(#barGrad)"/>
    <text x="16" y="{tile_h/2-2}" font-family="{FONT}" font-size="12.5" font-weight="700" letter-spacing="1.8" fill="{t["text_primary"]}">{esc(label)}</text>
    <text x="16" y="{tile_h/2+17}" font-family="{FONT}" font-size="12" fill="{t["text_muted"]}">{esc(sub)}</text>
  </g>''')
        for c, (name, ic) in enumerate(items):
            x = label_w + c * (tile_w + gap)
            dur = 3.2 + c * 0.35
            begin = c * 0.18 + r * 0.12
            out.append(f'''<g transform="translate({x},{y})">
    <rect width="{tile_w}" height="{tile_h}" rx="18" fill="{t["chip_fill"]}" stroke="{t["chip_stroke"]}" stroke-width="1.2"/>
    {pulse_outline(tile_w, tile_h, 18, t["a2"], f"{dur:.2f}", begin)}
    <g transform="translate({tile_w/2},48)">
      <circle r="27" fill="none" stroke="{t["a2"]}" stroke-width="1" opacity="0.25">
        <animate attributeName="r" values="25;29;25" dur="{dur:.2f}s" begin="{begin:.2f}s" repeatCount="indefinite"/>
        <animate attributeName="opacity" values="0.12;0.4;0.12" dur="{dur:.2f}s" begin="{begin:.2f}s" repeatCount="indefinite"/>
      </circle>
      <g>{float_y(f"{dur:.2f}", begin)}{icon(ic, t)}</g>
    </g>
    <text x="{tile_w/2}" y="102" text-anchor="middle" font-family="{FONT}" font-size="14.5" font-weight="600" fill="{t["text_primary"]}">{esc(name)}</text>
  </g>''')
    out.append("</svg>")
    write(f"techstack-{theme}.svg", "\n".join(out))


# ────────────────────────────── projects ────────────────────────────────

AI_TOPICS = {"ai", "ml", "genai", "generative-ai", "llm", "llms", "rag", "openai", "langchain", "gpt",
             "chatbot", "machine-learning", "deep-learning", "tensorflow", "pytorch", "nlp", "gemini", "ollama"}
PRETTY = {
    "ai": "AI", "ml": "ML", "genai": "GenAI", "generative-ai": "GenAI", "llm": "LLM", "llms": "LLM", "rag": "RAG",
    "openai": "OpenAI", "langchain": "LangChain", "gpt": "GPT", "nlp": "NLP", "api": "API", "rest": "REST",
    "rest-api": "REST API", "nextjs": "Next.js", "reactjs": "React", "react": "React", "nodejs": "Node.js",
    "nestjs": "NestJS", "expressjs": "Express", "express": "Express", "typescript": "TypeScript",
    "javascript": "JavaScript", "postgresql": "PostgreSQL", "postgres": "PostgreSQL", "mongodb": "MongoDB",
    "mysql": "MySQL", "python": "Python", "fastapi": "FastAPI", "flask": "Flask", "golang": "Go", "go": "Go",
    "tensorflow": "TensorFlow", "pytorch": "PyTorch", "docker": "Docker", "tailwindcss": "Tailwind",
    "redis": "Redis", "gemini": "Gemini", "ollama": "Ollama", "pinecone": "Pinecone", "chatbot": "Chatbot",
    "machine-learning": "ML", "deep-learning": "Deep Learning", "huggingface": "Hugging Face",
}
ACRONYMS = {"ai", "api", "llm", "rag", "ml", "gpt", "ui", "crm", "lms", "erp", "pdf", "sql", "jwt", "nlp", "bi"}


def pretty_title(name):
    words = re.split(r"[-_\s]+", name)
    return " ".join(w.upper() if w.lower() in ACRONYMS else w[:1].upper() + w[1:] for w in words if w)


def repo_to_project(r):
    topics = [tp for tp in r.get("topics", []) if tp != FEATURE_TOPIC]
    tags = []
    for tp in topics:
        label = PRETTY.get(tp, tp.replace("-", " ").title())
        if label not in tags:
            tags.append(label)
    if not tags and r.get("language"):
        tags = [r["language"]]
    is_ai = bool(AI_TOPICS & set(topics))
    homepage = (r.get("homepage") or "").strip()
    desc = (r.get("description") or "").strip() or "Project on GitHub."
    lines = wrap(desc, 62)
    if len(lines) > 4:
        desc = " ".join(lines[:4])[:-1].rstrip() + "…"
    return dict(
        title=pretty_title(r["name"]),
        status="Live" if homepage else ("AI Project" if is_ai else "Open Source"),
        tone="ok" if homepage else ("warn" if is_ai else "a2"),
        icon="chip" if is_ai else ("api" if r.get("language") == "Go" else "code"),
        desc=desc,
        tags=tags[:4],
        link=(urllib.parse.urlparse(homepage).netloc or homepage) if homepage else f"{GITHUB_USER}/{r['name']}",
        url=homepage or r["html_url"],
        repo=r["name"],
    )


def fetch_featured():
    """Public repos tagged FEATURE_TOPIC, most recently pushed first. Cached so offline runs keep them."""
    token = os.environ.get("GH_STATS_TOKEN") or os.environ.get("GITHUB_TOKEN")
    headers = {"Accept": "application/vnd.github+json", "User-Agent": "profile-asset-generator"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    try:
        repos, page = [], 1
        while True:
            req = urllib.request.Request(
                f"https://api.github.com/users/{GITHUB_USER}/repos?per_page=100&page={page}&type=owner&sort=pushed",
                headers=headers)
            with urllib.request.urlopen(req, timeout=20) as resp:
                batch = json.loads(resp.read().decode())
            repos.extend(batch)
            if len(batch) < 100:
                break
            page += 1
        featured = [repo_to_project(r) for r in repos if FEATURE_TOPIC in r.get("topics", []) and not r.get("fork")]
        with open(FEATURED_CACHE, "w", encoding="utf-8", newline="\n") as f:
            json.dump(featured, f, indent=2, ensure_ascii=False)
            f.write("\n")
        print(f"featured repos from GitHub: {len(featured)}")
        return featured
    except (urllib.error.URLError, OSError, ValueError) as e:
        print(f"[build_design_assets] GitHub unavailable ({e}); using cached featured repos", file=sys.stderr)
        try:
            with open(FEATURED_CACHE, encoding="utf-8") as f:
                return json.load(f)
        except (OSError, ValueError):
            return []


def all_projects():
    manual_repos = {p["repo"].lower() for p in PROJECTS if p.get("repo")}
    auto = [p for p in fetch_featured() if p["repo"].lower() not in manual_repos][:MAX_AUTO_PROJECTS]
    # newly featured repos go straight after the flagship (first) project
    return PROJECTS[:1] + auto + PROJECTS[1:]


def shield(text):
    return urllib.parse.quote(text.replace("-", "--").replace("_", "__").replace(" ", "_"), safe="")


def update_readme_links(projects_):
    badges = []
    for p in projects_:
        if not p.get("url"):
            continue
        on_github = "github.com/" in p["url"]
        msg = "GitHub" if on_github else p["link"]
        color, logo_ = ("0891B2", "github") if on_github else ("7C3AED", "googlechrome")
        badges.append(f'[![{p["title"]}](https://img.shields.io/badge/{shield(p["title"])}-{shield(msg)}-{color}'
                      f'?style=flat-square&logo={logo_}&logoColor=white)]({p["url"]})')
    block = "<!-- PROJECT-LINKS:START -->\n" + "\n".join(badges) + "\n<!-- PROJECT-LINKS:END -->"
    with open(README, encoding="utf-8") as f:
        text = f.read()
    new = re.sub(r"<!-- PROJECT-LINKS:START -->.*?<!-- PROJECT-LINKS:END -->", lambda _: block, text, flags=re.S)
    if new != text:
        with open(README, "w", encoding="utf-8", newline="\n") as f:
            f.write(new)
        print("updated README project links")


def projects(t, theme, projects_):
    cw, ch, gx, gy = 560, 210, 22, 22
    rows = -(-len(projects_) // 2)
    W, H = 8 * 2 + cw * 2 + gx, 8 * 2 + ch * rows + gy * (rows - 1)
    out = [svg_open(W, H, "Featured projects: " + ", ".join(p["title"] for p in projects_))]
    for i, p in enumerate(projects_):
        col, row = i % 2, i // 2
        x, y = 8 + col * (cw + gx), 8 + row * (ch + gy)
        tone = t[p["tone"]]
        pill_w = len(p["status"]) * 6.9 + 36
        px = cw - 24 - pill_w
        desc = "".join(f'<tspan x="0" dy="{0 if k == 0 else 19}">{esc(line)}</tspan>'
                       for k, line in enumerate(wrap(p["desc"], 62)[:4]))
        tags, tx = [], 0
        for tag in p["tags"]:
            w = len(tag) * 7.0 + 22
            tags.append(f'<g transform="translate({tx:.0f},0)"><rect width="{w:.0f}" height="24" rx="12" fill="{t["bg0"]}" fill-opacity="0.5" '
                        f'stroke="{t["chip_stroke"]}"/><text x="{w/2:.1f}" y="16" text-anchor="middle" font-family="{MONO}" '
                        f'font-size="11.5" fill="{t["text_secondary"]}">{esc(tag)}</text></g>')
            tx += w + 8
        out.append(f'''<g transform="translate({x},{y})">
    <rect width="{cw}" height="{ch}" rx="20" fill="{t["chip_fill"]}" stroke="{t["chip_stroke"]}" stroke-width="1.3"/>
    {pulse_outline(cw, ch, 20, t["a2"], 5, i * 0.5, "0.4")}
    <rect x="0" y="22" width="3" height="40" rx="1.5" fill="{t["a1"]}"/>
    <g transform="translate(46,44)">
      <circle r="22" fill="{t["bg0"]}" stroke="{t["a2"]}" stroke-opacity="0.6" stroke-width="1.2"/>
      {icon(p["icon"], dict(t, chip_fill=t["bg0"]))}
    </g>
    <text x="82" y="38" font-family="{FONT}" font-size="19" font-weight="700" fill="{t["text_primary"]}">{esc(p["title"])}</text>
    <text x="82" y="58" font-family="{MONO}" font-size="11.5" fill="{t["text_muted"]}"><tspan fill="{t["a2"]}">&#8599;</tspan> {esc(p["link"])}</text>
    <g transform="translate({px:.1f},22)">
      <rect width="{pill_w:.1f}" height="24" rx="12" fill="{tone}" fill-opacity="0.13"/>
      <circle cx="15" cy="12" r="3.4" fill="{tone}"><animate attributeName="opacity" values="0.4;1;0.4" dur="1.8s" begin="{i*0.3:.1f}s" repeatCount="indefinite"/></circle>
      <text x="25" y="16" font-family="{FONT}" font-size="11.5" font-weight="600" fill="{tone}">{esc(p["status"])}</text>
    </g>
    <text y="98" font-family="{FONT}" font-size="13.5" fill="{t["text_secondary"]}" transform="translate(26,0)">{desc}</text>
    <g transform="translate(26,{ch-40})">{"".join(tags)}</g>
  </g>''')
    out.append("</svg>")
    write(f"projects-{theme}.svg", "\n".join(out))


# ────────────────────────────── timeline ────────────────────────────────

def timeline(t, theme):
    W, H = 1300, 330
    axis = 168
    x0, x1 = 140, 1160
    step = (x1 - x0) / (len(TIMELINE) - 1)
    out = [svg_open(W, H, "Career timeline: " + ", ".join(f"{d} {ti}" for d, ti, _, _ in TIMELINE)),
           f'<defs>{lin_grad("tlGrad", t["a1"], t["a2"])}</defs>',
           f'<rect width="{W}" height="{H}" rx="24" fill="{t["bg1"]}" stroke="{t["chip_stroke"]}" stroke-width="1.2"/>',
           f'<line x1="{x0}" y1="{axis}" x2="{x1}" y2="{axis}" stroke="{t["hairline"]}" stroke-width="2"/>',
           f'<line x1="{x0}" y1="{axis}" x2="{x1}" y2="{axis}" stroke="url(#tlGrad)" stroke-width="2" stroke-dasharray="10 8">'
           f'<animate attributeName="stroke-dashoffset" values="0;-36" dur="2.4s" repeatCount="indefinite"/></line>',
           f'<circle cy="{axis}" r="5" fill="{t["a2"]}"><animateMotion dur="7s" repeatCount="indefinite" path="M{x0},0 L{x1},0"/>'
           f'<animate attributeName="opacity" values="0;1;1;0" keyTimes="0;0.05;0.92;1" dur="7s" repeatCount="indefinite"/></circle>']
    for i, (date, title, sub, ic) in enumerate(TIMELINE):
        x = x0 + i * step
        up = i % 2 == 0
        last = i == len(TIMELINE) - 1
        sgn = -1 if up else 1
        ring = t["a2"] if last else t["panel_stroke"]
        ys = (-96, -74, -55) if up else (64, 86, 105)
        out.append(f'''<g transform="translate({x:.1f},{axis})">
    <line x1="0" y1="0" x2="0" y2="{sgn * 44}" stroke="{t["hairline"]}" stroke-width="1.4"/>
    <circle r="23" fill="none" stroke="{t["a2"]}" stroke-width="1.2" opacity="0.3">
      <animate attributeName="r" values="21;27;21" dur="3s" begin="{i*0.35:.2f}s" repeatCount="indefinite"/>
      <animate attributeName="opacity" values="0.12;0.5;0.12" dur="3s" begin="{i*0.35:.2f}s" repeatCount="indefinite"/>
    </circle>
    <circle r="18" fill="{t["bg0"]}" stroke="{ring}" stroke-width="1.8"/>
    <g transform="scale(0.85)">{icon(ic, dict(t, chip_fill=t["bg0"]))}</g>
    <text y="{ys[0]}" text-anchor="middle" font-family="{MONO}" font-size="11.5" font-weight="600" fill="{t["a1"] if not last else t["ok"]}">{esc(date)}</text>
    <text y="{ys[1]}" text-anchor="middle" font-family="{FONT}" font-size="16" font-weight="700" fill="{t["text_primary"]}">{esc(title)}</text>
    <text y="{ys[2]}" text-anchor="middle" font-family="{FONT}" font-size="11.5" fill="{t["text_secondary"]}">{esc(sub)}</text>
  </g>''')
    out.append("</svg>")
    write(f"timeline-{theme}.svg", "\n".join(out))


# ──────────────────────────────── logo ──────────────────────────────────

def logo():
    t = THEME["dark"]
    svg = f'''{svg_open(160, 160, f"{NAME} logo")}
  <defs>{lin_grad("markGrad", t["a1"], t["a2"], 1, 1)}
    <filter id="glow" x="-50%" y="-50%" width="200%" height="200%"><feGaussianBlur stdDeviation="4" result="b"/>
      <feMerge><feMergeNode in="b"/><feMergeNode in="SourceGraphic"/></feMerge></filter></defs>
  <circle cx="80" cy="80" r="74" fill="none" stroke="url(#markGrad)" stroke-width="2" opacity="0.55" stroke-dasharray="6 10">
    <animateTransform attributeName="transform" type="rotate" from="0 80 80" to="360 80 80" dur="18s" repeatCount="indefinite"/>
  </circle>
  <circle cx="80" cy="80" r="62" fill="none" stroke="url(#markGrad)" stroke-width="1" opacity="0.3">
    <animate attributeName="r" values="60;64;60" dur="4s" repeatCount="indefinite"/>
  </circle>
  <g filter="url(#glow)">
    <circle cx="80" cy="80" r="50" fill="{t["bg0"]}"/>
    <circle cx="80" cy="80" r="50" fill="url(#markGrad)" opacity="0.1"/>
    <text x="80" y="97" text-anchor="middle" font-family="{FONT}" font-size="44" font-weight="700" fill="url(#markGrad)">{INITIALS}</text>
  </g>
  <circle cx="80" cy="80" r="50" fill="none" stroke="url(#markGrad)" stroke-width="1.6" opacity="0.8"/>
  <circle cx="130" cy="42" r="3.4" fill="{t["a2"]}"><animate attributeName="opacity" values="0.3;1;0.3" dur="2.6s" repeatCount="indefinite"/></circle>
</svg>'''
    write("logo.svg", svg)


def main():
    os.makedirs(OUT_DIR, exist_ok=True)
    projects_ = all_projects()
    update_readme_links(projects_)
    for theme, t in THEME.items():
        banner(t, theme)
        architecture(t, theme)
        profile_card(t, theme)
        techstack(t, theme)
        projects(t, theme, projects_)
        timeline(t, theme)
    logo()


if __name__ == "__main__":
    main()

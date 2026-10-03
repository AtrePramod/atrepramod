#!/usr/bin/env python3
"""
Generates the local, dependency-free GitHub stats SVG cards used by the
profile README: assets/stats-*.svg, assets/languages-*.svg, assets/trophies-*.svg.

Data comes straight from the GitHub REST + GraphQL APIs for the account named
by --user (real numbers only, never fabricated). When the API is unreachable
or no token is available for the GraphQL-only metrics, those metrics render
in an honest "pending sync" state instead of a made-up number, and the next
scheduled Action run replaces them with real data.

Usage:
    GITHUB_TOKEN=xxxx python3 generate_profile_assets.py --user AtrePramod
"""
import argparse
import json
import math
import os
import sys
import urllib.error
import urllib.request
from datetime import datetime, timezone

FONT = "'Segoe UI', ui-sans-serif, system-ui, -apple-system, 'Helvetica Neue', Arial, sans-serif"
MONO = "'SFMono-Regular', 'Cascadia Code', Consolas, 'Courier New', monospace"

# Kept in sync with build_design_assets.py
THEME = {
    "dark": dict(
        bg1="#0D1122", chip_fill="#141A31", chip_stroke="#283153", hairline="#1E2541",
        text_primary="#FFFFFF", text_secondary="#A5AECB", text_muted="#6F7898",
        accent1="#8B5CF6", accent2="#22D3EE", track="#222A47", live="#22C55E",
        shades=["#8B5CF6", "#22D3EE", "#A78BFA", "#67E8F9", "#C4B5FD", "#A5F3FC"],
    ),
    "light": dict(
        bg1="#FFFFFF", chip_fill="#F7F6FF", chip_stroke="#E0DCF6", hairline="#E8E5F8",
        text_primary="#14121F", text_secondary="#57546F", text_muted="#8B88A3",
        accent1="#7C3AED", accent2="#0891B2", track="#ECE9FB", live="#16A34A",
        shades=["#7C3AED", "#0891B2", "#8B5CF6", "#06B6D4", "#A78BFA", "#22D3EE"],
    ),
}

API = "https://api.github.com"
UA = "profile-asset-generator"


def gh_get(url, token):
    req = urllib.request.Request(url, headers={
        "Accept": "application/vnd.github+json",
        "User-Agent": UA,
        **({"Authorization": f"Bearer {token}"} if token else {}),
    })
    with urllib.request.urlopen(req, timeout=20) as resp:
        return json.loads(resp.read().decode())


def gh_graphql(query, variables, token):
    if not token:
        return None
    req = urllib.request.Request(
        f"{API}/graphql",
        data=json.dumps({"query": query, "variables": variables}).encode(),
        headers={
            "Authorization": f"Bearer {token}",
            "User-Agent": UA,
            "Content-Type": "application/json",
        },
    )
    with urllib.request.urlopen(req, timeout=20) as resp:
        return json.loads(resp.read().decode())


def fetch_data(user, token):
    """Best-effort real fetch. Returns a dict; any missing metric stays None."""
    data = dict(
        public_repos=None, followers=None, total_stars=None, total_forks=None,
        contributions_year=None, total_prs=None, total_issues=None,
        years_on_github=None, languages=[], synced=False,
    )
    try:
        u = gh_get(f"{API}/users/{user}", token)
        data["public_repos"] = u.get("public_repos")
        data["followers"] = u.get("followers")
        created = u.get("created_at")
        if created:
            start = datetime.strptime(created, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
            data["years_on_github"] = round((datetime.now(timezone.utc) - start).days / 365.25, 1)

        repos, page = [], 1
        while True:
            batch = gh_get(f"{API}/users/{user}/repos?per_page=100&page={page}&type=owner", token)
            if not batch:
                break
            repos.extend(batch)
            if len(batch) < 100:
                break
            page += 1

        data["total_stars"] = sum(r.get("stargazers_count", 0) for r in repos)
        data["total_forks"] = sum(r.get("forks_count", 0) for r in repos)

        lang_bytes = {}
        for r in repos:
            if r.get("fork"):
                continue
            try:
                langs = gh_get(r["languages_url"], token)
            except Exception:
                continue
            for lang, n in langs.items():
                lang_bytes[lang] = lang_bytes.get(lang, 0) + n
        total = sum(lang_bytes.values()) or 1
        data["languages"] = sorted(
            [(lang, round(n / total * 100, 1)) for lang, n in lang_bytes.items()],
            key=lambda x: -x[1],
        )[:6]

        gql = gh_graphql(
            """
            query($login: String!) {
              user(login: $login) {
                contributionsCollection {
                  contributionCalendar { totalContributions }
                  totalPullRequestContributions
                  totalIssueContributions
                }
              }
            }""",
            {"login": user},
            token,
        )
        if gql and gql.get("data", {}).get("user"):
            cc = gql["data"]["user"]["contributionsCollection"]
            data["contributions_year"] = cc["contributionCalendar"]["totalContributions"]
            data["total_prs"] = cc["totalPullRequestContributions"]
            data["total_issues"] = cc["totalIssueContributions"]

        data["synced"] = True
    except (urllib.error.URLError, urllib.error.HTTPError, KeyError, TimeoutError, OSError) as e:
        print(f"[generate_profile_assets] live fetch unavailable ({e}); rendering pending state", file=sys.stderr)
    return data


def write(out_path, svg):
    with open(out_path, "w", encoding="utf-8", newline="\n") as f:
        f.write(svg)
    print("wrote", out_path)


def fmt(n):
    if n is None:
        return "—"
    if n >= 1000:
        return f"{n/1000:.1f}k"
    return str(n)


def ring(cx, cy, r, pct, color, track):
    circ = 2 * math.pi * r
    arc = circ * pct
    return (
        f'<circle cx="{cx}" cy="{cy}" r="{r}" fill="none" stroke="{track}" stroke-width="7"/>'
        f'<circle cx="{cx}" cy="{cy}" r="{r}" fill="none" stroke="{color}" stroke-width="7" '
        f'stroke-linecap="round" stroke-dasharray="0 {circ:.1f}" transform="rotate(-90 {cx} {cy})">'
        f'<animate attributeName="stroke-dasharray" from="0 {circ:.1f}" to="{arc:.1f} {circ:.1f}" '
        f'dur="1.4s" begin="0.2s" fill="freeze" calcMode="spline" keySplines="0.2 0 0.2 1"/>'
        f"</circle>"
    )


def synced_badge(t, synced):
    color = t["live"] if synced else t["text_muted"]
    label = "LIVE" if synced else "SYNCING"
    return (
        f'<circle cx="0" cy="-4" r="3.4" fill="{color}">'
        f'<animate attributeName="opacity" values="0.5;1;0.5" dur="1.8s" repeatCount="indefinite"/></circle>'
        f'<text x="10" y="0" font-family="{FONT}" font-size="11" font-weight="700" '
        f'letter-spacing="1.2" fill="{color}">{label}</text>'
    )


def card_frame(t, W, H, title, synced, label):
    return (
        f'<svg width="{W}" height="{H}" viewBox="0 0 {W} {H}" xmlns="http://www.w3.org/2000/svg" role="img" aria-label="{label}">'
        f'<defs><linearGradient id="hdr" x1="0" y1="0" x2="1" y2="0"><stop offset="0%" stop-color="{t["accent1"]}"/>'
        f'<stop offset="100%" stop-color="{t["accent2"]}"/></linearGradient></defs>'
        f'<rect x="1" y="1" width="{W-2}" height="{H-2}" rx="22" fill="{t["bg1"]}" stroke="{t["chip_stroke"]}" stroke-width="1.3"/>'
        f'<rect x="28" y="22" width="3" height="20" rx="1.5" fill="url(#hdr)"/>'
        f'<text x="40" y="38" font-family="{FONT}" font-size="18" font-weight="700" fill="{t["text_primary"]}">{title}</text>'
        f'<g transform="translate({W-118},32)">{synced_badge(t, synced)}</g>'
        f'<line x1="28" y1="54" x2="{W-28}" y2="54" stroke="{t["hairline"]}" stroke-width="1"/>'
    )


def render_stats(data, theme_name, out_path):
    t = THEME[theme_name]
    W, H = 560, 300
    metrics = [
        ("Public Repos", data["public_repos"], 40, t["accent1"]),
        ("Total Stars", data["total_stars"], 200, t["accent2"]),
        ("Contributions (yr)", data["contributions_year"], 2000, t["accent1"]),
        ("Followers", data["followers"], 150, t["accent2"]),
    ]
    tiles = []
    for i, (label, val, cap, color) in enumerate(metrics):
        col, row = i % 2, i // 2
        x = 30 + col * 260
        y = 74 + row * 108
        pct = 0.06 if val is None else max(0.06, min(1, val / cap))
        tiles.append(f'''
    <g transform="translate({x},{y})">
      <g transform="translate(38,38)">{ring(0, 0, 30, pct, color, t['track'])}</g>
      <text x="38" y="43" text-anchor="middle" font-family="{MONO}" font-size="15" font-weight="700" fill="{t['text_primary']}">{fmt(val)}</text>
      <text x="88" y="34" font-family="{FONT}" font-size="13" fill="{t['text_secondary']}">{label}</text>
      <text x="88" y="52" font-family="{MONO}" font-size="11" fill="{t['text_muted']}">{'real-time via GitHub API' if val is not None else 'awaiting first sync'}</text>
    </g>''')

    synced_at = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC") if data["synced"] else "pending first run"
    svg = (card_frame(t, W, H, "GitHub Stats", data["synced"], "GitHub stats") + "".join(tiles) +
           f'<line x1="28" y1="{H-34}" x2="{W-28}" y2="{H-34}" stroke="{t["hairline"]}" stroke-width="1"/>'
           f'<text x="28" y="{H-14}" font-family="{MONO}" font-size="10.5" fill="{t["text_muted"]}">last synced: {synced_at}</text>'
           "</svg>")
    write(out_path, svg)


def render_languages(data, theme_name, out_path):
    t = THEME[theme_name]
    W, H = 560, 300
    langs = data["languages"] or [("Awaiting sync", 100.0)]
    rows = []
    y = 80
    for i, (name, pct) in enumerate(langs[:6]):
        color = t["shades"][i % len(t["shades"])]
        bar_w = 380 * (pct / 100 if data["languages"] else 0.0)
        rows.append(f'''
    <g transform="translate(28,{y})">
      <circle cx="5" cy="-4.5" r="4.5" fill="{color}"/>
      <text x="16" font-family="{FONT}" font-size="13" fill="{t['text_primary']}">{name}</text>
      <text x="{W-56}" y="0" text-anchor="end" font-family="{MONO}" font-size="12" fill="{t['text_secondary']}">{pct if data['languages'] else 0}%</text>
      <rect x="0" y="9" width="{W-84}" height="8" rx="4" fill="{t['track']}"/>
      <rect x="0" y="9" width="0" height="8" rx="4" fill="{color}">
        <animate attributeName="width" from="0" to="{bar_w * (W-84) / 380:.1f}" dur="1.2s" begin="{0.15*i:.2f}s" fill="freeze" calcMode="spline" keySplines="0.2 0 0.2 1"/>
      </rect>
    </g>''')
        y += 36

    svg = card_frame(t, W, H, "Most Used Languages", data["synced"], "Most used languages") + "".join(rows) + "</svg>"
    write(out_path, svg)


TROPHY_DEFS = [
    ("Repo Builder", "public_repos", [(1, "bronze"), (10, "silver"), (25, "gold")], "repo"),
    ("Star Collector", "total_stars", [(1, "bronze"), (25, "silver"), (100, "gold")], "star"),
    ("Community", "followers", [(5, "bronze"), (25, "silver"), (100, "gold")], "people"),
    ("Contributor", "contributions_year", [(100, "bronze"), (500, "silver"), (1500, "gold")], "commit"),
    ("PR Champion", "total_prs", [(5, "bronze"), (25, "silver"), (75, "gold")], "pr"),
    ("Veteran", "years_on_github", [(1, "bronze"), (3, "silver"), (5, "gold")], "clock"),
]

TIER_COLOR = {"locked": None, "bronze": "#C08A4E", "silver": "#9AA5B1", "gold": "#F0B429"}


def _star_points():
    pts = []
    for i in range(10):
        a = -math.pi / 2 + i * math.pi / 5
        r = 9 if i % 2 == 0 else 4
        pts.append((r * math.cos(a), r * math.sin(a)))
    return pts


def tier_icon(kind, color):
    if kind == "repo":
        return f'<rect x="-7" y="-9" width="14" height="18" rx="2" fill="none" stroke="{color}" stroke-width="1.8"/><line x1="-4" y1="-4" x2="4" y2="-4" stroke="{color}" stroke-width="1.4"/><line x1="-4" y1="0" x2="4" y2="0" stroke="{color}" stroke-width="1.4"/>'
    if kind == "star":
        pts = " ".join(f"{x:.1f},{y:.1f}" for x, y in _star_points())
        return f'<polygon points="{pts}" fill="{color}"/>'
    if kind == "people":
        return f'<circle cx="-5" cy="-6" r="4" fill="{color}"/><circle cx="5" cy="-6" r="4" fill="{color}" opacity="0.7"/><path d="M-11,10 C-11,2 -1,2 -1,10" fill="{color}"/><path d="M11,10 C11,3 3,3 3,9" fill="{color}" opacity="0.7"/>'
    if kind == "commit":
        return f'<circle cx="0" cy="0" r="5" fill="none" stroke="{color}" stroke-width="2"/><line x1="-14" y1="0" x2="-5" y2="0" stroke="{color}" stroke-width="2"/><line x1="5" y1="0" x2="14" y2="0" stroke="{color}" stroke-width="2"/>'
    if kind == "pr":
        return f'<circle cx="-7" cy="9" r="3" fill="none" stroke="{color}" stroke-width="1.8"/><circle cx="-7" cy="-9" r="3" fill="none" stroke="{color}" stroke-width="1.8"/><circle cx="7" cy="9" r="3" fill="none" stroke="{color}" stroke-width="1.8"/><path d="M-7,-6 V3 C-7,7 -1,7 4,7" fill="none" stroke="{color}" stroke-width="1.8"/>'
    if kind == "clock":
        return f'<circle cx="0" cy="0" r="11" fill="none" stroke="{color}" stroke-width="1.8"/><line x1="0" y1="0" x2="0" y2="-6" stroke="{color}" stroke-width="1.8"/><line x1="0" y1="0" x2="5" y2="2" stroke="{color}" stroke-width="1.8"/>'
    return ""


def tier_for(value, thresholds):
    if value is None:
        return "locked"
    tier = "locked"
    for min_val, name in thresholds:
        if value >= min_val:
            tier = name
    return tier


def render_trophies(data, theme_name, out_path):
    t = THEME[theme_name]
    cols, tile, gap, pad = 6, 160, 14, 14
    rows = -(-len(TROPHY_DEFS) // cols)
    W = cols * tile + (cols - 1) * gap + pad * 2
    th = 150
    H = rows * th + (rows - 1) * gap + pad * 2 + 46

    badges = []
    for i, (name, key, thresholds, icon_kind) in enumerate(TROPHY_DEFS):
        col, row = i % cols, i // cols
        x = pad + col * (tile + gap)
        y = pad + 46 + row * (th + gap)
        tier = tier_for(data.get(key), thresholds)
        locked = tier == "locked"
        color = TIER_COLOR.get(tier) or t["text_muted"]
        ring_color = color if not locked else t["hairline"]
        pulse = (f'<animate attributeName="opacity" values="0.5;0.95;0.5" dur="2.6s" begin="{i*0.3:.1f}s" repeatCount="indefinite"/>'
                 if not locked else "")
        badges.append(f'''
    <g transform="translate({x},{y})">
      <rect width="{tile}" height="{th}" rx="18" fill="{t['chip_fill']}" stroke="{t['chip_stroke']}" stroke-width="1.2"/>
      <g transform="translate({tile/2},52)">
        <circle r="28" fill="none" stroke="{ring_color}" stroke-width="2" stroke-dasharray="{'4 5' if locked else 'none'}" opacity="{'0.5' if locked else '0.9'}">{pulse}</circle>
        <g opacity="{'0.35' if locked else '1'}">{tier_icon(icon_kind, color if not locked else t['text_muted'])}</g>
      </g>
      <text x="{tile/2}" y="{th-34}" text-anchor="middle" font-family="{FONT}" font-size="13" font-weight="700" fill="{t['text_primary'] if not locked else t['text_muted']}">{name}</text>
      <text x="{tile/2}" y="{th-16}" text-anchor="middle" font-family="{MONO}" font-size="10.5" fill="{color if not locked else t['text_muted']}">{tier.upper() if not locked else 'LOCKED'}</text>
    </g>''')

    svg = (f'<svg width="{W}" height="{H}" viewBox="0 0 {W} {H}" xmlns="http://www.w3.org/2000/svg" role="img" aria-label="Achievements">'
           f'<rect x="1" y="1" width="{W-2}" height="{H-2}" rx="22" fill="{t["bg1"]}" stroke="{t["chip_stroke"]}" stroke-width="1.3"/>'
           f'<text x="{pad+14}" y="38" font-family="{FONT}" font-size="18" font-weight="700" fill="{t["text_primary"]}">Achievements</text>'
           f'<g transform="translate({W-pad-104},34)">{synced_badge(t, data["synced"])}</g>'
           + "".join(badges) + "</svg>")
    write(out_path, svg)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--user", default="AtrePramod")
    ap.add_argument("--output-dir", default="assets")
    args = ap.parse_args()

    token = os.environ.get("GH_STATS_TOKEN") or os.environ.get("GITHUB_TOKEN")
    data = fetch_data(args.user, token)

    os.makedirs(args.output_dir, exist_ok=True)
    for theme in ("dark", "light"):
        render_stats(data, theme, os.path.join(args.output_dir, f"stats-{theme}.svg"))
        render_languages(data, theme, os.path.join(args.output_dir, f"languages-{theme}.svg"))
        render_trophies(data, theme, os.path.join(args.output_dir, f"trophies-{theme}.svg"))


if __name__ == "__main__":
    main()

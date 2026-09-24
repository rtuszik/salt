"""Console summary and HTML report."""

import html
from collections import Counter
from datetime import datetime, timedelta
from pathlib import Path
from string import Template

from . import PACKAGE_DIR
from .scoring import QUESTIONS
from .sources import HOME, SOURCES

OUTPUT_DIR = Path.home() / ".claude" / "usage-data"
OUTPUT_HTML = OUTPUT_DIR / "salt-report.html"
TEMPLATE = Template((PACKAGE_DIR / "report.html").read_text())
SOURCE_LABELS = {"claude": "Claude", "codex": "Codex", "opencode": "Opencode"}
SOURCE_COLORS = {"claude": "#d97706", "codex": "#10a37f", "opencode": "#6366f1"}
NO_TIMESTAMPS = '<p class="sub"><em>No timestamps available.</em></p>'
e = html.escape


def pretty_project(name: str) -> str:
    home_prefix = str(HOME).replace("/", "-")
    return name.replace(home_prefix, "").lstrip("-").replace("-", "/")


def truncate(s: str, n: int = 160) -> str:
    s = " ".join(s.split())
    return s if len(s) <= n else s[: n - 1] + "…"


def by_severity(fs):
    return sorted(fs, key=lambda f: (-f["severity"], -len(f["triggers"])))


def print_summary(report):
    uniq = report["unique"]
    findings = report["findings"]
    tc = Counter(f["target"] for f in findings)
    sc = Counter(f["source"] for f in findings)
    mc = report["model_counts"]
    silent = [f for f in uniq if not f["is_profane"]]

    print("# Salt Insights\n")
    src = ", ".join(f"{SOURCE_LABELS[k]}: {sc[k]}" for k in SOURCES if sc.get(k))
    print(
        f"{len(findings)} salty messages out of {report['total_messages']}"
        f" scanned.  ({src})\n"
    )
    print(
        f"_Checkpoints: english {mc.get('english', 0)}, "
        f"multilingual {mc.get('multilingual', 0)}_\n"
    )

    by_src = ", ".join(
        f"{SOURCE_LABELS[k]} {report['saltiness_by_source'][k]}"
        for k in SOURCES
        if k in report["saltiness_by_source"]
    )
    print(f"**Saltiness: {report['saltiness']}/100**  ({by_src})\n")

    print("## At a Glance\n")
    print(f"- **Aimed at agent**:        {tc.get('agent', 0)}")
    print(f"- **Ambient**:               {tc.get('ambient', 0)}")
    print(f"- **Profane**:               {sum(f['is_profane'] for f in findings)}")
    print(
        f"- **Frustrated, no swearing**: "
        f"{len(findings) - sum(f['is_profane'] for f in findings)}"
    )
    print(f"- **Pure pastes skipped**:     {report['pasted']}")
    print()

    tw = Counter(w for f in findings for w in f["triggers"])
    if tw:
        print("## Trigger Words\n")
        print("| Count | Word |")
        print("|-------|------|")
        for w, c in tw.most_common(10):
            print(f"| {c:>5} | {w} |")
        print()

    print("## Hall of Shame\n")
    rows = [f for f in by_severity(uniq) if f["target"] == "agent"][:15]
    for f in rows:
        print(f'- [{f["severity"]:.2f}] "{truncate(f["content"])}"')
    if not rows:
        print("- (none, your agents survive unscathed)")
    print()

    print("## Frustrated Without Swearing\n")
    for f in by_severity(silent)[:10]:
        print(f'- [{f["severity"]:.2f}] "{truncate(f["content"])}"')
    if not silent:
        print("- (none)")
    print()


def quote_li(f) -> str:
    badges = [
        f'<span class="badge sev">severity {f["severity"]:.2f}</span>',
        f'<span class="badge alt">{e(f["target"])}</span>',
    ]
    badges += [
        f'<span class="badge word">{e(w)}</span>' for w in sorted(set(f["triggers"]))
    ]
    if f["model"] != "english":
        badges.append(f'<span class="badge alt">{e(f["model"])}</span>')
    ts = f' · <span class="mono">{f["ts"]:%Y-%m-%d}</span>' if f["ts"] else ""
    return (
        f'<li><div class="quote">"{e(truncate(f["content"], 280))}"</div>'
        f'<div class="meta">{" ".join(badges)} '
        f'<span class="mono">{e(pretty_project(f["project"]))}</span>{ts}</div></li>'
    )


def quotes(fs, limit: int) -> str:
    return "\n".join(quote_li(f) for f in fs[:limit]) or "<li><em>none</em></li>"


def make_bar(value, max_value, color="#d53") -> str:
    pct = value / max_value * 100 if max_value else 0
    return (
        f'<div class="bar-bg"><div class="bar" '
        f'style="width:{pct:.1f}%;background:{color}"></div></div>'
    )


def count_rows(items, color="#d53", label=e) -> str:
    """Table rows of (key, count) with proportional bars."""
    top = max((c for _, c in items), default=1)
    return "\n".join(
        f'<tr><td class="count">{c}</td><td>{label(k)}</td>'
        f'<td class="bar-cell">{make_bar(c, top, color)}</td></tr>'
        for k, c in items
    )


def verdict_for(sc: Counter, total: int) -> str:
    active = {k: v for k, v in sc.items() if v}
    if len(active) >= 2:
        worst, worst_n = max(active.items(), key=lambda x: x[1])
        rest = sum(v for k, v in active.items() if k != worst)
        if rest and worst_n / rest >= 1.5:
            return (
                f"<b>{SOURCE_LABELS[worst]}</b>"
                f" took <b>{worst_n / rest:.1f}&times;</b>"
                f" more rage than the rest combined."
            )
        return "Roughly even-handed rage across all agents."
    if total > 50:
        return "You curse like a sailor on a sinking ship."
    if total > 10:
        return "Mild grumbler. Mostly composed."
    return "Surprisingly polite. Are you sure these are your transcripts?"


def hour_chart(findings) -> str:
    hc = Counter(f["ts"].hour for f in findings if f["ts"])
    if not hc:
        return NO_TIMESTAMPS
    max_hr = max(hc.values())
    return (
        '<div class="hours">'
        + "".join(
            f'<div class="hr-col" title="{h:02d}:00, {hc.get(h, 0)}">'
            f'<div class="hr-bar" '
            f'style="height:{int(hc.get(h, 0) / max_hr * 100)}%"></div>'
            f'<div class="hr-label">{h:02d}</div></div>'
            for h in range(24)
        )
        + "</div>"
    )


def trend_chart(findings, date_range) -> str:
    if not date_range:
        return NO_TIMESTAMPS
    weekly: Counter[str] = Counter()
    weekly_src: dict[str, Counter[str]] = {s: Counter() for s in SOURCES}
    for f in findings:
        if f["ts"]:
            d = f["ts"].date()
            wk = (d - timedelta(days=d.weekday())).isoformat()
            weekly[wk] += 1
            weekly_src[f["source"]][wk] += 1
    start, end = (d.date() for d in date_range)
    cur = start - timedelta(days=start.weekday())
    weeks = []
    while cur <= end:
        weeks.append(cur.isoformat())
        cur += timedelta(days=7)
    max_w = max(weekly.values(), default=1)
    step = max(1, len(weeks) // 8)
    cells = []
    for i, w in enumerate(weeks):
        tot = weekly.get(w, 0)
        h = tot / max_w * 100
        segs = "".join(
            f'<div class="day-seg" '
            f'style="height:{weekly_src[s][w] / tot * h:.1f}%;'
            f'background:{SOURCE_COLORS[s]}"></div>'
            for s in SOURCES
            if weekly_src[s].get(w)
        )
        label = f"{datetime.fromisoformat(w):%b %d}" if i % step == 0 else ""
        cells.append(
            f'<div class="day-col" title="Week of {w}, {tot}">'
            f'<div class="day-stack">{segs}</div>'
            f'<div class="day-label">{label}</div></div>'
        )
    legend = " ".join(
        f'<span class="legend-item"><span class="legend-swatch" '
        f'style="background:{c}"></span>'
        f"{SOURCE_LABELS[s]}</span>"
        for s, c in SOURCE_COLORS.items()
        if weekly_src[s]
    )
    return f'<div class="legend">{legend}</div><div class="days">{"".join(cells)}</div>'


def agent_compare(sc: Counter) -> str:
    active = [k for k in SOURCES if sc.get(k)]
    if len(active) < 2:
        return ""
    m = max(sc[k] for k in active)
    rows = "\n".join(
        f'<div class="vs-row"><div class="vs-label">{SOURCE_LABELS[k]}</div>'
        f"{make_bar(sc[k], m, SOURCE_COLORS[k])}"
        f'<div class="vs-num">{sc[k]}</div></div>'
        for k in active
    )
    return f'<h2>Agent Comparison</h2>\n<div class="versus">\n{rows}\n</div>'


def render_html(report):
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    findings = report["findings"]
    total = len(findings)
    total_messages = report["total_messages"]
    sc = Counter(f["source"] for f in findings)
    mc = report["model_counts"]
    ranked = by_severity(report["unique"])
    hall = [f for f in ranked if f["target"] == "agent"]
    labels = QUESTIONS["severity"]["criteria"]
    buckets = Counter(min(int(f["severity"] + 0.5), 3) for f in findings)
    words = Counter(w for f in findings for w in f["triggers"]).most_common(15)
    range_str = ""
    if report["date_range"]:
        a, b = report["date_range"]
        range_str = f", from {a:%Y-%m-%d} to {b:%Y-%m-%d}"

    avg_severity = sum(f["severity"] for f in findings) / total if total else 0
    out = TEMPLATE.substitute(
        verdict=verdict_for(sc, total),
        total=total,
        aimed_at_agent=sum(f["target"] == "agent" for f in findings),
        salt_rate=f"{total / total_messages * 1000 if total_messages else 0:.1f}",
        saltiness=report["saltiness"],
        avg_severity=f"{avg_severity:.2f}",
        unsworn=sum(not f["is_profane"] for f in findings),
        generated=f"{datetime.now().astimezone():%Y-%m-%d %H:%M}",
        total_messages=f"{total_messages:,}",
        range_str=range_str,
        sources=e(
            ", ".join(SOURCE_LABELS[s] for s in SOURCES if s in report["include"])
        ),
        english=mc.get("english", 0),
        multilingual=mc.get("multilingual", 0),
        min_severity=f"{report['min_severity']:.2f}",
        pasted=report["pasted"],
        hall_of_shame=quotes(hall, 10),
        punchy=quotes([f for f in hall if len(f["content"]) <= 80], 8),
        unsworn_quotes=quotes([f for f in ranked if not f["is_profane"]], 15),
        agent_compare=agent_compare(sc),
        severity_rows=count_rows(
            [(labels[i], buckets.get(i, 0)) for i in range(3, -1, -1)], "#a37"
        ),
        word_rows=count_rows(words) or '<tr><td colspan="3"><em>none</em></td></tr>',
        project_rows=count_rows(
            Counter(f["project"] for f in findings).most_common(15),
            "#3a7",
            lambda p: e(pretty_project(p)),
        ),
        hour_chart=hour_chart(findings),
        trend_chart=trend_chart(findings, report["date_range"]),
        ambient=quotes([f for f in ranked if f["target"] == "ambient"], 10),
        all_agent=quotes(hall, 50),
    )
    OUTPUT_HTML.write_text(out)

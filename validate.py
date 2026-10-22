#!/usr/bin/env python3
"""KPI Claim Checker.

Reads LLM-written commentary, finds sentences that quote a KPI figure, recomputes
that KPI from source inputs, and flags every figure that does not match.
Usage: python validate.py   (exit code 1 if any figure is contradicted)
"""
import html, json, re, sys
from pathlib import Path

ROOT = Path(__file__).parent

# key: (label, unit, tolerance, formula, formula text)
# ratio: absolute tolerance | pct: percentage points | eur: relative tolerance
SPEC = {
    "cash_ratio":     ("Cash ratio", "ratio", 0.005, lambda d: d["cash"] / d["current_liabilities"], "cash ÷ current liabilities"),
    "current_ratio":  ("Current ratio", "ratio", 0.005, lambda d: d["current_assets"] / d["current_liabilities"], "current assets ÷ current liabilities"),
    "working_capital":("Working capital", "eur", 0.01, lambda d: d["current_assets"] - d["current_liabilities"], "current assets − current liabilities"),
    "ebit_margin":    ("EBIT margin", "pct", 0.1, lambda d: d["ebit"] / d["revenue"] * 100, "EBIT ÷ revenue"),
    "net_margin":     ("Net profit margin", "pct", 0.1, lambda d: d["retained_profit"] / d["revenue"] * 100, "retained profit ÷ revenue"),
    "equity_ratio":   ("Equity ratio", "pct", 0.1, lambda d: d["equity"] / d["total_assets"] * 100, "equity ÷ total assets"),
    "revenue_growth": ("Revenue growth", "pct", 0.1, lambda d: (d["revenue"] - d["revenue_prior"]) / d["revenue_prior"] * 100, "(revenue − prior revenue) ÷ prior revenue"),
}
ALIASES = {
    "cash_ratio": r"cash ratio",
    "current_ratio": r"current ratio",
    "working_capital": r"working capital",
    "ebit_margin": r"ebit margin",
    "net_margin": r"net (?:profit )?margin",
    "equity_ratio": r"(?<!debt-to-)(?<!debt to )\bequity ratio",
    "revenue_growth": r"revenue (?:growth|grew|increased)",
}
NUM = re.compile(r"(?P<n>[-−–]?\d[\d,]*(?:\.\d+)?)(?P<s>\s?%|\s?(?:EUR|€))?")


def fmt(unit, v):
    return f"{v:.2f}" if unit == "ratio" else f"{v:.1f}%" if unit == "pct" else f"{v:,.0f} EUR"


def find_number(text, unit):
    for m in NUM.finditer(text):
        s = (m.group("s") or "").strip()
        u = "pct" if s == "%" else "eur" if s in ("EUR", "€") else "ratio"
        if u == unit:
            v = float(m.group("n").replace(",", "").replace("−", "-").replace("–", "-"))
            return v, m.start(), m.end()
    return None


def check(sentences, kpis):
    rows = []
    for s in sentences:
        hit = next(((k, m) for k, p in ALIASES.items() if (m := re.search(p, s, re.I))), None)
        if not hit:
            why = "No KPI is defined for this figure." if NUM.search(s) else "No figure to check."
            rows.append({"sentence": s, "status": "unverifiable", "note": why})
            continue
        key, m = hit
        label, unit, tol, _, formula = SPEC[key]
        found = find_number(s[m.end():], unit)
        if not found:
            rows.append({"sentence": s, "status": "unverifiable", "note": f"{label} is named but no matching figure is quoted."})
            continue
        claimed, a, b = found
        a, b = a + m.end(), b + m.end()
        actual = kpis[key]
        diff = abs(claimed - actual)
        ok = diff <= (abs(actual) * tol if unit == "eur" else tol)
        rows.append({"sentence": s, "status": "verified" if ok else "contradicted", "kpi": key, "label": label,
                     "unit": unit, "claimed": claimed, "actual": round(actual, 4), "diff": round(diff, 4),
                     "formula": formula, "span": [a, b]})
    return rows


CSS = """
:root{--cream:#F5EFDF;--paper:#FBF8EF;--blue:#0B2C5F;--blue2:#1F4A8C;--mute:#5A6A86;--line:#D8CFB8;--red:#A8261C}
*{box-sizing:border-box}
body{margin:0;background:var(--cream);color:var(--blue);font:400 19px/1.6 Newsreader,Georgia,serif}
.wrap{max-width:1040px;margin:0 auto;padding:clamp(28px,6vw,72px) clamp(18px,4vw,40px)}
h1{font-weight:500;font-size:clamp(2.1rem,5vw,3.5rem);line-height:1.08;letter-spacing:-.01em;margin:0 0 14px;max-width:21ch}
.lede{font:400 1rem/1.55 "Public Sans",system-ui,sans-serif;color:var(--mute);max-width:60ch;margin:0 0 44px}
h2{font-weight:500;font-size:1.5rem;margin:56px 0 14px}
ol{list-style:none;margin:0;padding:0;border-top:2px solid var(--blue)}
.claim{display:grid;grid-template-columns:1.5fr 1fr;gap:12px 40px;padding:20px 0;border-bottom:1px solid var(--line)}
.said{margin:0;font-size:1.2rem;line-height:1.5}
.note{margin:0;font:400 .88rem/1.5 "Public Sans",system-ui,sans-serif;color:var(--mute)}
.note b{display:block;color:var(--blue);font-weight:600}
mark{background:none;color:inherit;font-weight:600;box-shadow:inset 0 -2px 0 var(--blue2)}
del{color:var(--red);text-decoration:line-through;text-decoration-thickness:2px}
ins{text-decoration:none;background:var(--blue);color:var(--cream);padding:0 .3em;border-radius:2px;font-weight:600}
.contradicted .note,.contradicted .note b{color:var(--red)}
.unverifiable .said{color:var(--mute)}
table{width:100%;border-collapse:collapse;font:400 .92rem/1.4 "Public Sans",system-ui,sans-serif;background:var(--paper)}
th,td{text-align:left;padding:12px 14px;border-bottom:1px solid var(--line)}
th{border-bottom:2px solid var(--blue);font-weight:600}
td.n{text-align:right;font-variant-numeric:tabular-nums}
.foot{margin-top:48px;font:400 .85rem/1.6 "Public Sans",system-ui,sans-serif;color:var(--mute);max-width:70ch}
@media(max-width:760px){.claim{grid-template-columns:1fr}}
"""


def render(meta, kpis, rows):
    e = html.escape
    n = len(rows)
    c = {s: sum(r["status"] == s for r in rows) for s in ("verified", "contradicted", "unverifiable")}
    items = []
    for r in rows:
        s = r["sentence"]
        if r["status"] == "unverifiable":
            said, note = e(s), f"<b>Not checked</b>{e(r['note'])}"
        else:
            a, b = r["span"]
            num = e(s[a:b])
            mid = f"<mark>{num}</mark>" if r["status"] == "verified" else f"<del>{num}</del> <ins>{fmt(r['unit'], r['actual'])}</ins>"
            said = e(s[:a]) + mid + e(s[b:])
            if r["status"] == "verified":
                note = f"<b>Matches</b>{e(r['label'])} is {fmt(r['unit'], r['actual'])} ({e(r['formula'])})."
            else:
                gap = f"{r['diff']:.2f}" if r["unit"] == "ratio" else f"{r['diff']:.1f} points" if r["unit"] == "pct" else f"{r['diff']:,.0f} EUR"
                note = f"<b>Does not match</b>{e(r['label'])} is {fmt(r['unit'], r['actual'])} ({e(r['formula'])}). The text is off by {gap}."
        items.append(f'<li class="claim {r["status"]}"><p class="said">{said}</p><p class="note">{note}</p></li>')
    ledger = "".join(
        f"<tr><td>{e(SPEC[k][0])}</td><td class='n'>{fmt(SPEC[k][1], v)}</td><td>{e(SPEC[k][4])}</td></tr>" for k, v in kpis.items())
    plural = "figure contradicts" if c["contradicted"] == 1 else "figures contradict"
    return f"""<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><title>KPI Claim Checker report</title>
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Newsreader:ital,wght@0,400;0,500;0,600&family=Public+Sans:wght@400;600&display=swap">
<style>{CSS}</style></head><body><main class="wrap">
<h1>{c['verified']} of {n} sentences in this AI commentary check out.</h1>
<p class="lede">{c['contradicted']} quoted {plural} the data, and {c['unverifiable']} could not be checked. Every figure below was recomputed from the source inputs for {e(meta['period'])}.</p>
<ol>{''.join(items)}</ol>
<h2>Recomputed KPIs</h2>
<table><thead><tr><th>KPI</th><th class="n">Value</th><th>Formula</th></tr></thead><tbody>{ledger}</tbody></table>
<p class="foot">{e(meta['note'])} Claims are found with keyword rules and a numeric tolerance per unit, so a paraphrased figure can slip through as “not checked” rather than being mis-scored.</p>
</main></body></html>"""


def main():
    meta = json.loads((ROOT / "data/inputs.json").read_text())
    kpis = {k: spec[3](meta["inputs"]) for k, spec in SPEC.items()}
    text = (ROOT / "data/commentary.txt").read_text().strip()
    sentences = re.split(r"(?<=[.!?])\s+(?=[A-Z])", text)
    rows = check(sentences, kpis)
    (ROOT / "results.json").write_text(json.dumps(rows, indent=2, ensure_ascii=False))
    (ROOT / "report.html").write_text(render(meta, kpis, rows))
    for r in rows:
        tag = {"verified": "OK  ", "contradicted": "FAIL", "unverifiable": "SKIP"}[r["status"]]
        extra = f" (said {r['claimed']}, data {r['actual']})" if r["status"] == "contradicted" else ""
        print(f"[{tag}] {r['sentence'][:70]}{extra}")
    sys.exit(1 if any(r["status"] == "contradicted" for r in rows) else 0)


if __name__ == "__main__":
    main()

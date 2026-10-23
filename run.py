#!/usr/bin/env python3
"""Late-order root cause: runs queries.sql on the Northwind SQLite database and writes index.html."""
import html, json, re, sqlite3, urllib.request
from pathlib import Path

ROOT = Path(__file__).parent
DB = ROOT / "northwind.db"
URL = "https://raw.githubusercontent.com/jpwhite3/northwind-SQLite3/main/dist/northwind.db"
DAYS = ["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"]
MIN_N = 100  # ignore segments smaller than this: their rates are mostly noise


def load_queries():
    out, name = {}, None
    for line in (ROOT / "queries.sql").read_text().splitlines():
        m = re.match(r"--\s*name:\s*(\w+)", line)
        if m:
            name = m.group(1)
            out[name] = []
        elif name:
            out[name].append(line)
    return {k: "\n".join(v).strip() for k, v in out.items()}


def chart(bl, avg):
    W, H, L, T, B = 640, 230, 44, 10, 28
    pw, ph = W - L - 10, H - T - B
    pts = [r for r in bl if 0 <= r["lead_days"] <= 30]
    bw, s = pw / len(pts), ""
    for i in range(5):
        y = T + ph - i / 4 * ph
        s += f'<line class="gl" x1="{L}" x2="{W-10}" y1="{y}" y2="{y}"/><text x="{L-8}" y="{y+4}" text-anchor="end">{i*25}%</text>'
    for i, r in enumerate(pts):
        h, x = r["rate"] * ph, L + i * bw
        s += f'<rect x="{x+1:.1f}" y="{T+ph-h:.1f}" width="{bw-2:.1f}" height="{h:.1f}" fill="#1F4A8C"><title>Promised {r["lead_days"]} days: {r["rate"]*100:.0f}% late ({r["n"]} orders)</title></rect>'
        if r["lead_days"] % 5 == 0:
            s += f'<text x="{x+bw/2:.1f}" y="{H-8}" text-anchor="middle">{r["lead_days"]}</text>'
    ya = T + ph - avg * ph
    s += f'<line x1="{L}" x2="{W-10}" y1="{ya}" y2="{ya}" stroke="#A8261C" stroke-width="2" stroke-dasharray="6 4"/>'
    s += f'<text x="{W-14}" y="{ya-6}" text-anchor="end" style="fill:#A8261C">All orders: {avg*100:.0f}% late</text>'
    return s


CSS = """
:root{--cream:#F5EFDF;--paper:#FBF8EF;--blue:#0B2C5F;--blue2:#1F4A8C;--mute:#5A6A86;--line:#D8CFB8;--red:#A8261C}
*{box-sizing:border-box}body{margin:0;background:var(--cream);color:var(--blue);font:400 18px/1.6 Newsreader,Georgia,serif}
.wrap{max-width:1000px;margin:0 auto;padding:clamp(28px,6vw,72px) clamp(18px,4vw,40px)}
h1{font-weight:500;font-size:clamp(2.1rem,5vw,3.5rem);line-height:1.08;letter-spacing:-.015em;margin:0 0 14px;max-width:20ch}
h2{font-weight:500;font-size:1.4rem;margin:56px 0 6px}
.lede,.note,table,.foot{font-family:"Public Sans",system-ui,sans-serif}
.lede{color:var(--mute);font-size:1rem;max-width:62ch;margin:0 0 36px}.note{color:var(--mute);font-size:.9rem;max-width:70ch;margin:4px 0 14px}
svg{width:100%;height:auto;display:block}.gl{stroke:var(--line)}svg text{font:11px "Public Sans",sans-serif;fill:var(--mute)}
table{width:100%;border-collapse:collapse;font-size:.92rem;background:var(--paper)}
th,td{text-align:left;padding:11px 14px;border-bottom:1px solid var(--line)}th{border-bottom:2px solid var(--blue);font-weight:600}
td.n,th.n{text-align:right;font-variant-numeric:tabular-nums}.bar{display:inline-block;height:9px;background:var(--blue2);vertical-align:middle}
.top td{font-weight:600}.fail{color:var(--red);font-weight:600}.foot{margin-top:48px;color:var(--mute);font-size:.85rem;max-width:75ch}
"""


def main():
    if not DB.exists():
        print("Downloading northwind.db (about 25 MB)...")
        urllib.request.urlretrieve(URL, DB)
    con, Q = sqlite3.connect(DB), load_queries()
    con.executescript(Q["base"])

    def q(name):
        cur = con.execute(Q[name])
        cols = [c[0] for c in cur.description]
        return [dict(zip(cols, r)) for r in cur.fetchall()]

    quality, overall, by_lead = q("quality")[0], q("overall")[0], q("by_lead")
    dims, ship_by_lead, ship_days = q("dims"), q("ship_by_lead"), q("ship_days")
    n_tot, avg = overall["n"], overall["rate"]

    spread = []
    for d in sorted({r["dim"] for r in dims}):
        seg = [r for r in dims if r["dim"] == d and r["n"] >= MIN_N]
        lo, hi = min(seg, key=lambda r: r["rate"]), max(seg, key=lambda r: r["rate"])
        lab = (lambda r: DAYS[int(r["seg"])]) if d == "Weekday ordered" else (lambda r: r["seg"])
        spread.append({"dim": d, "segments": len(seg), "lo": f"{lab(lo)} ({lo['rate']*100:.1f}%)",
                       "hi": f"{lab(hi)} ({hi['rate']*100:.1f}%)", "pp": (hi["rate"] - lo["rate"]) * 100})
    spread.sort(key=lambda r: -r["pp"])
    first, second = spread[0], spread[1]

    short = [r for r in by_lead if r["lead_days"] <= 7]
    short_orders = sum(r["n"] for r in short) / n_tot
    short_late = sum(r["n"] * r["rate"] for r in short) / (n_tot * avg)
    tail = lambda k: sum(r["n"] for r in ship_days if r["ship_days"] > k) / n_tot  # share of orders taking longer than k days
    # Promise raised to at least k days (longer promises are left alone), assuming shipping time is independent of the promise.
    whatif = [(k, sum(r["n"] * tail(max(r["lead_days"], k)) for r in by_lead) / n_tot) for k in (3, 5, 7, 10, 14, 21)]
    model0 = sum(r["n"] * tail(r["lead_days"]) for r in by_lead) / n_tot
    sb = [r["avg_ship_days"] for r in ship_by_lead]

    if first["dim"] == "Promised lead time" and first["pp"] > 3 * second["pp"]:
        head = "Late deliveries are a promise problem, not a carrier problem."
    else:
        head = "No single factor explains the late deliveries."
    e = html.escape
    rows = "".join(f'<tr class="{"top" if i == 0 else ""}"><td>{e(r["dim"])}</td><td class="n">{r["segments"]}</td><td>{e(r["lo"])}</td><td>{e(r["hi"])}</td>'
                   f'<td class="n"><span class="bar" style="width:{min(r["pp"],100)*1.2:.0f}px"></span> {r["pp"]:.1f}</td></tr>' for i, r in enumerate(spread))
    wi = "".join(f'<tr><td>At least {k} days</td><td class="n">{v*100:.1f}%</td></tr>' for k, v in whatif)
    expect0 = ("orphan_customers", "orphan_lines", "shipped_before_ordered", "required_before_ordered")
    labels = {"orders": "Orders", "order_lines": "Order lines", "orphan_customers": "Orders with no matching customer", "orphan_lines": "Order lines with no matching order",
              "shipped_before_ordered": "Shipped before ordered", "required_before_ordered": "Required before ordered",
              "not_yet_shipped": "Not yet shipped (excluded from lateness)", "mixed_date_formats": "Rows mixing dates and timestamps (normalised with date())"}
    dq = "".join(f'<tr><td>{labels[k]}</td><td class="n">{v:,}</td><td class="{"fail" if k in expect0 and v else ""}">'
                 f'{("Pass" if v == 0 else "Fail") if k in expect0 else ("Note" if k in ("not_yet_shipped", "mixed_date_formats") and v else "")}</td></tr>' for k, v in quality.items())
    page = f"""<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Late-order root cause</title>
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Newsreader:ital,wght@0,400;0,500;0,600&family=Public+Sans:wght@400;500;600&display=swap">
<style>{CSS}</style></head><body><main class="wrap">
<h1>{head}</h1>
<p class="lede">{avg*100:.0f}% of {n_tot:,} shipped orders arrived after the required date. Promising delivery within a week covers {short_orders*100:.0f}% of orders and causes {short_late*100:.0f}% of the late ones. Spread between the best and worst carrier is {next((r['pp'] for r in spread if r['dim']=='Carrier'),0):.1f} points; for promised lead time it is {first['pp'] if first['dim']=='Promised lead time' else next(r['pp'] for r in spread if r['dim']=='Promised lead time'):.0f}.</p>
<h2>Late rate by promised lead time</h2>
<p class="note">Lead time is the gap between order date and required date. Hover a bar for the order count. The dashed line is the overall late rate.</p>
<svg viewBox="0 0 640 230" role="img" aria-label="Late rate by promised lead time in days">{chart(by_lead, avg)}</svg>
<h2>Does anything else matter?</h2>
<p class="note">Spread is the gap in late rate, in percentage points, between the best and worst segment of each factor (segments under {MIN_N} orders ignored). Order size is large, so differences of a few points are mostly noise.</p>
<table><thead><tr><th>Factor</th><th class="n">Segments</th><th>Lowest late rate</th><th>Highest late rate</th><th class="n">Spread (points)</th></tr></thead><tbody>{rows}</tbody></table>
<h2>What if we promised more time?</h2>
<p class="note">Estimated late rate if any promise shorter than this were raised to it (longer promises left unchanged), using the observed distribution of actual shipping times. Average shipping time is almost the same whatever was promised ({min(sb):.1f} to {max(sb):.1f} days across lead-time groups), which supports this estimate. Model check: the same method reproduces today’s late rate as {model0*100:.1f}% against {avg*100:.1f}% actual.</p>
<table><thead><tr><th>Minimum promise</th><th class="n">Estimated late rate</th></tr></thead><tbody>{wi}</tbody></table>
<h2>Data checks</h2>
<table><thead><tr><th>Check</th><th class="n">Rows</th><th>Result</th></tr></thead><tbody>{dq}</tbody></table>
<p class="foot">Data: the enlarged community version of Microsoft’s Northwind sample database, a fictional trading company. It is a teaching dataset, so read this as a worked method, not a finding about a real business. The what-if ignores commercial effects: customers may not accept longer promises. The link between lead time and lateness is partly mechanical, since an order is late when shipping takes longer than promised, so the useful question is how often promises are shorter than normal shipping time.</p>
</main></body></html>"""
    (ROOT / "index.html").write_text(page)
    (ROOT / "results.json").write_text(json.dumps({"overall": overall, "spread": spread, "whatif": whatif, "quality": quality}, indent=2))
    print(head)
    print(f"{avg*100:.1f}% late of {n_tot:,}; <=7-day promises: {short_orders*100:.0f}% of orders, {short_late*100:.0f}% of late orders")
    for r in spread:
        print(f"  {r['dim']:<20} spread {r['pp']:5.1f} pts")


if __name__ == "__main__":
    main()

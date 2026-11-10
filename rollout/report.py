"""Render a static HTML report (no server, no dependencies) from the registry and past runs."""
import html
import os
import time

E = html.escape

CSS = """:root{--bg:#fff;--fg:#1a1a1a;--mut:#666;--line:#ddd;--ok:#1a7f37;--bad:#c62828;--warn:#9a6700}
@media(prefers-color-scheme:dark){:root{--bg:#161616;--fg:#eee;--mut:#9a9a9a;--line:#333;--ok:#4ac26b;--bad:#ff6b6b;--warn:#e3b341}}
body{font:15px/1.5 system-ui,sans-serif;background:var(--bg);color:var(--fg);margin:0 auto;padding:16px;max-width:900px}
h1{font-size:20px}h2{font-size:16px;margin-top:28px}table{border-collapse:collapse;width:100%}
td,th{padding:5px 8px;border-bottom:1px solid var(--line);text-align:left;vertical-align:top}
.ok{color:var(--ok)}.bad{color:var(--bad)}.warn{color:var(--warn)}.mut{color:var(--mut);font-size:13px;overflow-wrap:anywhere}
@media(max-width:600px){td,th{padding:4px}}"""

STATUS = {"completed": "ok", "nothing_to_do": "ok", "blocked_by_preview": "warn"}


def render(reg, runs, actual=None):
    actual = actual or {}
    out = [f"<!doctype html><html lang=en><meta charset=utf-8><meta name=viewport content='width=device-width,initial-scale=1'>"
           f"<title>Blueprint Rollouts</title><style>{CSS}</style><body><h1>Blueprint rollouts</h1>"
           f"<p class=mut>Generated {time.strftime('%Y-%m-%d %H:%M', time.gmtime())} UTC. Local results from a demo catalog; "
           f"not evidence of use at any company.</p><h2>Environments</h2><table><tr><th>Environment<th>Kind<th>Pinned<th>Actual</tr>"]
    for e in reg["environments"]:
        a = actual.get(e["name"], "")
        cls = "" if not a or a == e["version"] else " class=bad"
        out.append(f"<tr><td>{E(e['name'])}<td>{E(e['environment'])}<td>{E(e['version'])}<td{cls}>{E(a or '-')}</tr>")
    out.append("</table><h2>Rollouts</h2>")
    if not runs:
        out.append("<p class=mut>No rollouts recorded yet.</p>")
    for r in sorted(runs, key=lambda r: r.get("at", 0), reverse=True):
        cls = STATUS.get(r["status"], "bad")
        out.append(f"<h3>{E(r['version'])}: <span class={cls}>{E(r['status'])}</span> "
                   f"<span class=mut>{r.get('total_seconds', '?')}s, {len(r.get('targets', []))} environment(s)</span></h3><table>")
        for rec in r.get("records", []):
            res = "ok" if rec["ok"] else "FAILED"
            extra = "" if rec["ok"] else f" rolled back: {rec.get('rolled_back')}. {E('; '.join(rec['problems']))}"
            out.append(f"<tr><td>{E(rec['stage'])}<td>{E(rec['name'])}<td class={'ok' if rec['ok'] else 'bad'}>{res}"
                       f"<td class=mut>{rec['seconds']}s{extra}</tr>")
        for n, items in r.get("destroys", {}).items():
            out.append(f"<tr><td>blocked<td>{E(n)}<td class=warn>would destroy<td class=mut>{E(', '.join(items))}</tr>")
        if r.get("not_attempted"):
            out.append(f"<tr><td>not attempted<td colspan=3 class=mut>{E(', '.join(r['not_attempted']))}</tr>")
        out.append("</table>")
    return "".join(out) + "</body></html>"


def build(reg, runs, out_path, actual=None):
    os.makedirs(os.path.dirname(out_path) or ".", exist_ok=True)
    with open(out_path, "w") as f:
        f.write(render(reg, runs, actual))
    return out_path

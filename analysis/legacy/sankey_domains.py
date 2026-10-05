"""
sankey_domains.py
Scrollable, portrait-oriented Sankey diagram of domain -> resolution flows.
Tuned for crowded datasets.
"""

import colorsys
from collections import Counter
from pathlib import Path

import pandas as pd
import plotly.graph_objects as go
from plotly.offline import get_plotlyjs

# ----------------------------------------------------------------------
# Configuration
# ----------------------------------------------------------------------
INPUT_FILE   = "multired.csv"
OUTPUT_HTML  = "sankey_domains.html"

COL_DOMAIN      = "domain"
COL_RESOLUTIONS = "resolutions"

PLOT_WIDTH       = 1000     # portrait: keep this modest
PX_PER_NODE      = 24       # vertical breathing room per node  ← bump up if labels overlap
MIN_HEIGHT       = 1200
MAX_HEIGHT       = 30_000
NODE_THICKNESS   = 12
NODE_PAD         = 6
FONT_SIZE        = 9
MAX_LABEL_LEN    = 32       # truncate labels longer than this (full name on hover)
USE_CDN          = False    # True → small file, needs internet for plotly.js

# ----------------------------------------------------------------------
# Load data
# ----------------------------------------------------------------------
df = pd.read_csv(INPUT_FILE)
df = df.dropna(subset=[COL_DOMAIN, COL_RESOLUTIONS])
df["res_list"] = df[COL_RESOLUTIONS].str.split()

domains       = df[COL_DOMAIN].unique().tolist()
all_res       = [r for sub in df["res_list"] for r in sub]
unique_res    = list(dict.fromkeys(all_res))   # preserve order of appearance

n_left  = len(domains)
n_right = len(unique_res)

domain_idx = {d: i for i, d in enumerate(domains)}
res_idx    = {r: i + n_left for i, r in enumerate(unique_res)}

sources, targets, values = [], [], []
for _, row in df.iterrows():
    src = domain_idx[row[COL_DOMAIN]]
    for r in row["res_list"]:
        sources.append(src)
        targets.append(res_idx[r])
        values.append(1)

n_links = len(sources)
if n_links == 0:
    raise SystemExit("No links to plot — check the input CSV.")

# ----------------------------------------------------------------------
# Colours
# ----------------------------------------------------------------------
def hsv_rgba(h, s, v, a=1.0):
    r, g, b = colorsys.hsv_to_rgb(h, s, v)
    return f"rgba({int(r*255)},{int(g*255)},{int(b*255)},{a})"

GOLDEN = 0.618033988749895
domain_hues        = [(i * GOLDEN) % 1.0 for i in range(n_left)]
domain_node_colors = [hsv_rgba(h, 0.55, 0.85, 1.00) for h in domain_hues]
domain_link_colors = [hsv_rgba(h, 0.55, 0.85, 0.30) for h in domain_hues]

# Colour resolutions by in-degree
res_in_deg = Counter(targets)
res_node_colors = []
for r in unique_res:
    deg = res_in_deg.get(res_idx[r], 0)
    if deg <= 1:
        res_node_colors.append("rgba(200,200,200,1)")    # unique  → light grey
    elif deg <= 3:
        res_node_colors.append("rgba(255,169,77,1)")     # shared  → orange
    else:
        res_node_colors.append("rgba(224,49,49,1)")      # popular → red

node_colors = domain_node_colors + res_node_colors
link_colors = [domain_link_colors[s] for s in sources]

# ----------------------------------------------------------------------
# Labels (truncated for display, full in hover via customdata)
# ----------------------------------------------------------------------
def trunc(s: str) -> str:
    return s if len(s) <= MAX_LABEL_LEN else s[: MAX_LABEL_LEN - 1] + "…"

display_labels = [trunc(d) for d in domains] + [trunc(r) for r in unique_res]
node_customdata = [[d, "domain"]     for d in domains] + \
                  [[r, "resolution"] for r in unique_res]

# ----------------------------------------------------------------------
# Dynamic size — portrait, tall
# ----------------------------------------------------------------------
n_max = max(n_left, n_right)
height = max(MIN_HEIGHT, min(MAX_HEIGHT, n_max * PX_PER_NODE + 160))

# ----------------------------------------------------------------------
# Build figure
# ----------------------------------------------------------------------
fig = go.Figure(data=[go.Sankey(
    arrangement="snap",
    node=dict(
        pad=NODE_PAD,
        thickness=NODE_THICKNESS,
        line=dict(color="rgba(0,0,0,0.35)", width=0.5),
        label=display_labels,
        color=node_colors,
        customdata=node_customdata,
        hovertemplate=(
            "<b>%{customdata[0]}</b>"
            "<br>type: %{customdata[1]}"
            "<br>flow: %{value}<extra></extra>"
        ),
    ),
    link=dict(
        source=sources,
        target=targets,
        value=values,
        color=link_colors,
        hovertemplate=(
            "%{source.label} → %{target.label}"
            "<br>value: %{value}<extra></extra>"
        ),
    ),
)])

fig.update_layout(
    font=dict(size=FONT_SIZE,
              family="-apple-system, Segoe UI, Roboto, sans-serif"),
    height=height,
    width=PLOT_WIDTH,
    margin=dict(l=10, r=10, t=10, b=10),
    paper_bgcolor="white",
    plot_bgcolor="white",
)

# ----------------------------------------------------------------------
# Wrap in a scrollable portrait HTML shell
# ----------------------------------------------------------------------
div_html = fig.to_html(
    full_html=False,
    include_plotlyjs=False,
    div_id="sankey",
    config={
        "displaylogo": False,
        "responsive": False,    # keeps the explicit px size — needed for scrolling
        "scrollZoom": False,    # wheel scrolls the page instead of zooming
        "doubleClick": "reset",
    },
)

plotly_tag = (
    '<script src="https://cdn.plot.ly/plotly-2.27.0.min.js" charset="utf-8"></script>'
    if USE_CDN else f'<script charset="utf-8">{get_plotlyjs()}</script>'
)

html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>Domains → Resolutions Sankey</title>
{plotly_tag}
<style>
  *, *::before, *::after {{ box-sizing: border-box; }}
  html, body {{ margin: 0; padding: 0; height: 100%; }}
  body {{
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
    background: #f4f4f5;
    display: flex; flex-direction: column; height: 100vh;
  }}
  header {{
    flex: 0 0 auto;
    background: #ffffff;
    border-bottom: 1px solid #e4e4e7;
    padding: 10px 16px;
    font-size: 13px;
    display: flex; align-items: center; gap: 16px;
    box-shadow: 0 1px 3px rgba(0,0,0,0.04);
    z-index: 100;
  }}
  header h1 {{ font-size: 14px; margin: 0; font-weight: 600; }}
  header .stats {{ color: #52525b; }}
  header .hint  {{ color: #a1a1aa; font-size: 12px; }}
  header .legend {{
    margin-left: auto; display: flex; gap: 14px;
    font-size: 12px; color: #52525b;
  }}
  header .legend span::before {{
    content: ""; display: inline-block;
    width: 10px; height: 10px; border-radius: 2px;
    margin-right: 5px; vertical-align: -1px;
  }}
  header .legend .s1::before {{ background: rgba(200,200,200,1); }}
  header .legend .s2::before {{ background: rgba(255,169,77,1); }}
  header .legend .s3::before {{ background: rgba(224,49,49,1); }}

  #scroll {{
    flex: 1 1 auto;
    overflow-y: auto;
    overflow-x: auto;
    padding: 14px 0;
  }}
  #inner {{
    width: {PLOT_WIDTH}px;
    height: {height}px;
    margin: 0 auto;
    background: white;
    box-shadow: 0 1px 4px rgba(0,0,0,0.06);
  }}
</style>
</head>
<body>
<header>
  <h1>Domains → Resolutions</h1>
  <span class="stats">{n_left} domains · {n_right} resolutions · {n_links} links</span>
  <span class="hint">scroll ↓ · drag to pan</span>
  <span class="legend">
    <span class="s1">unique</span>
    <span class="s2">shared (2–3)</span>
    <span class="s3">popular (4+)</span>
  </span>
</header>
<div id="scroll"><div id="inner">{div_html}</div></div>
</body>
</html>
"""

Path(OUTPUT_HTML).write_text(html, encoding="utf-8")
print(f"Wrote {OUTPUT_HTML}: {n_left} domains, {n_right} resolutions, "
      f"{n_links} links, canvas {PLOT_WIDTH}×{height}px")
#!/usr/bin/env python3
"""
Convert a CSV file with columns:
    domain, n_resolutions, resolutions
into a Gephi-compatible directed GEXF graph.

Edges go from each domain to each of its resolutions.
Domain nodes are positioned at the top, resolution nodes at the bottom,
using embedded viz:position coordinates.
"""

import csv
import argparse
from xml.sax.saxutils import quoteattr


def parse_csv(path):
    """Yield (domain, n_resolutions, [resolutions]) from the CSV."""
    with open(path, newline="", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        for row in reader:
            row = {(k or "").strip(): (v or "").strip() for k, v in row.items()}
            domain = row.get("domain", "")
            if not domain:
                continue
            n_res = row.get("n_resolutions", "")
            res_field = row.get("resolutions", "")
            resolutions = [r for r in res_field.split() if r]
            yield domain, n_res, resolutions


def write_gexf(rows, out_path):
    """Write rows as a directed GEXF graph with top/bottom node positions."""
    nodes = {}          # id -> {"type":..., "n_resolutions":...}
    edges = set()
    domains_order = []  # preserve CSV order for x positioning
    resolutions_order = []

    for domain, n_res, resolutions in rows:
        if domain not in nodes:
            nodes[domain] = {"type": "domain", "n_resolutions": n_res}
            domains_order.append(domain)
        else:
            nodes[domain]["type"] = "domain"
            if n_res:
                nodes[domain]["n_resolutions"] = n_res

        for r in resolutions:
            if r not in nodes:
                nodes[r] = {"type": "resolution", "n_resolutions": ""}
                resolutions_order.append(r)
            edges.add((domain, r))

    # --- Compute positions ------------------------------------------------
    # Gephi's viz coordinates: x grows right, y grows DOWN.
    # So "top"  -> small y ; "bottom" -> large y.
    # We'll use a 1000-wide band and separate the two layers vertically.
    TOP_Y = 0.0
    BOTTOM_Y = 1000.0
    X_MIN, X_MAX = 0.0, 1000.0

    def spread(index, total):
        if total <= 1:
            return (X_MIN + X_MAX) / 2.0
        return X_MIN + (X_MAX - X_MIN) * index / (total - 1)

    positions = {}
    for i, nid in enumerate(domains_order):
        positions[nid] = (spread(i, len(domains_order)), TOP_Y, 0.0)
    for i, nid in enumerate(resolutions_order):
        positions[nid] = (spread(i, len(resolutions_order)), BOTTOM_Y, 0.0)

    # --- Write GEXF -------------------------------------------------------
    with open(out_path, "w", encoding="utf-8") as f:
        f.write('<?xml version="1.0" encoding="UTF-8"?>\n')
        f.write(
            '<gexf xmlns="http://gexf.net/1.3" '
            'xmlns:viz="http://gexf.net/1.3/viz" '
            'version="1.3">\n'
        )
        f.write('  <graph mode="static" defaultedgetype="directed">\n')

        f.write('    <attributes class="node">\n')
        f.write('      <attribute id="0" title="type" type="string"/>\n')
        f.write('      <attribute id="1" title="n_resolutions" type="integer"/>\n')
        f.write('    </attributes>\n')

        f.write("    <nodes>\n")
        for nid, data in nodes.items():
            x, y, z = positions[nid]
            f.write(f'      <node id={quoteattr(nid)} label={quoteattr(nid)}>\n')
            f.write("        <attvalues>\n")
            f.write(f'          <attvalue for="0" value={quoteattr(data["type"])}/>\n')
            if data["n_resolutions"]:
                f.write(
                    f'          <attvalue for="1" value={quoteattr(data["n_resolutions"])}/>\n'
                )
            f.write("        </attvalues>\n")
            f.write(f'        <viz:position x="{x}" y="{y}" z="{z}"/>\n')
            f.write("      </node>\n")
        f.write("    </nodes>\n")

        f.write("    <edges>\n")
        for i, (src, tgt) in enumerate(sorted(edges)):
            f.write(
                f'      <edge id="{i}" source={quoteattr(src)} '
                f'target={quoteattr(tgt)} weight="1.0"/>\n'
            )
        f.write("    </edges>\n")

        f.write("  </graph>\n")
        f.write("</gexf>\n")


def main():
    parser = argparse.ArgumentParser(
        description="Convert CSV to a Gephi-compatible directed GEXF graph."
    )
    parser.add_argument("input", help="input CSV file")
    parser.add_argument(
        "-o", "--output", default="graph.gexf",
        help="output GEXF file (default: graph.gexf)",
    )
    args = parser.parse_args()

    rows = list(parse_csv(args.input))
    write_gexf(rows, args.output)
    print(f"Wrote {args.output} from {len(rows)} CSV rows.")


if __name__ == "__main__":
    main()
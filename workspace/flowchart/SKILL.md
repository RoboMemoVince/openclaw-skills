---
name: flowchart
description: "Draw computation flowcharts and data-flow diagrams using Graphviz dot. Use when user asks for flowcharts, computation graphs, data-flow diagrams, operator diagrams, or pipeline visualizations. NOT for: sequence diagrams, Gantt charts, or mind maps."
platform: [openclaw, claude-code]
---

# Flowchart with Graphviz

## Defaults

- **Engine**: `dot` (top-to-bottom DAG layout)
- **Splines**: `ortho` (horizontal/vertical only — no diagonals)
- **Output**: PNG at 150 dpi, white background
- **Source format**: `.dot` file alongside the `.png`

## Render Command

```bash
dot -Tpng -Gdpi=150 <name>.dot -o <name>.png
```

## Graph Skeleton

```dot
digraph G {
    rankdir=TB;
    bgcolor=white;
    splines=ortho;
    nodesep=0.8;
    ranksep=0.8;
    node [shape=box, style="filled,rounded", fontname="monospace", fontsize=12,
          margin="0.25,0.15", width=2.5];
    edge [color="#555555", arrowsize=0.8];

    // nodes & edges …
}
```

## Layout Rules

1. **Lines must be straight or right-angled** — `splines=ortho` enforces this. Never use `splines=true/curved`.
2. **Lines exit from node center** — if ortho routes from corners, add `{rank=same;}` constraints or invisible spacer nodes to shift layout.
3. **No line-over-node occlusion** — increase `nodesep`/`ranksep`, add spacer nodes, or reorder `{rank=same;}` groups to eliminate overlaps.
4. **Minimize long cross-layer edges** — place a node's direct consumers in the next rank whenever possible. For unavoidable long edges, widen `nodesep` so the routing channel has room.
5. **Use `{rank=same; A; B;}` liberally** — force related nodes onto the same row.
6. **Invisible spacer nodes** — `spacer [style=invis, label=""]` + invisible edges keep columns aligned without visual clutter.

## Color Convention

| Role | fillcolor | border (color) |
|------|-----------|----------------|
| Input tensors | `#e3f2fd` | `#1565c0` pw=2 |
| Host preprocessing | `#fff3e0` | default |
| Kernel main compute | `#fff9c4` | default |
| Branch A (e.g. grad_weight) | `#f3e5f5` | default |
| Branch B (e.g. grad_scale) | `#fce4ec` | default |
| Scalar params | `#f3e5f5` | `#7b1fa2` |
| Output stores | `#e8f5e9` | `#2e7d32` pw=2 |

Adapt colors to the diagram; the above is a sensible default for compute kernels.

## Node Label Format

Include in every node:
- **Operation** (bold or first line): what the node computes
- **Variable name** and **dtype + shape**: e.g. `w_div · fp32 [M]`

```dot
node_id [label="w_div = w / s_clamped\nfp32 [M]", fillcolor="#fff9c4"];
```

## Iterating on Layout

Expect 2-3 rounds of adjustment:

1. **Draft**: get topology right — all nodes and edges correct.
2. **Rank tuning**: add `{rank=same;}` groups, spacer nodes, adjust `nodesep`/`ranksep`.
3. **Visual polish**: verify no edge-over-node, adjust node widths if labels overflow.

Render and visually inspect after each round before delivering.

## Checklist Before Delivery

- [ ] All lines horizontal or vertical (no diagonals)
- [ ] Lines exit from node center area (not corners)
- [ ] No lines hidden behind nodes
- [ ] Every node has operation + variable name + dtype + shape
- [ ] Color-coded by role
- [ ] `.dot` source and `.png` both saved

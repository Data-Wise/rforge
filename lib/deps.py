"""
R ecosystem dependency analysis.

Builds a dependency graph across the packages discovered by `discovery.py`,
exposes topological layers (build order), detects circular dependencies, and
analyzes downstream impact of a change to one package.

Pure Python — no R subprocess. Ported from
`rforge-mcp/dist/tools/deps/{deps,impact}.js` (Path B Phase B.1).

Edge convention: `Edge(from_=importer, to=imported)`. Topological layers
contain leaves first (deepest deps), which is the correct order to build in.

Usage (CLI):
    python3 lib/deps.py --path /path/to/eco --format text
    python3 lib/deps.py impact --package medfit --change-type breaking \\
        --path /path/to/eco --format json

Usage (Python API):
    from discovery import detect_ecosystem
    from deps import build_graph, analyze_impact
    eco = detect_ecosystem(".")
    graph = build_graph(eco)
    impact = analyze_impact(graph, "medfit", change_type="breaking")
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict, dataclass, field
from typing import Literal, Optional

# Allow `python3 lib/deps.py` invocation from the repo root.
_HERE = __file__
import os as _os
sys.path.insert(0, _os.path.dirname(_os.path.abspath(_HERE)))

from discovery import Ecosystem, Package, detect_ecosystem  # noqa: E402


EdgeType = Literal["imports", "depends", "suggests", "linkingTo"]
ChangeType = Literal["breaking", "feature", "fix", "internal"]
RiskLevel = Literal["low", "medium", "high"]


@dataclass(frozen=True)
class Edge:
    from_: str
    to: str
    type: EdgeType

    def to_dict(self) -> dict:
        return {"from": self.from_, "to": self.to, "type": self.type}


@dataclass
class DepGraph:
    """Dependency graph for an ecosystem.

    Attributes:
        nodes: package names in the ecosystem.
        edges: directed edges (importer → imported).
        layers: topological layers, leaves first. Layer i+1 depends only on
            layers ≤ i. Within a layer, packages can be built in parallel.
        circular: any cycles detected (each cycle is a list of node names
            forming the loop, not closed — i.e. last → first is implied).
    """

    nodes: list[str]
    edges: list[Edge]
    layers: list[list[str]]
    circular: list[list[str]] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "nodes": self.nodes,
            "edges": [e.to_dict() for e in self.edges],
            "layers": self.layers,
            "circular": self.circular,
        }


@dataclass
class Impact:
    package: str
    change_type: ChangeType
    direct_dependents: list[str]
    indirect_dependents: list[str]
    affected_tests: int
    update_sequence: list[str]
    estimated_work: str
    risk_level: RiskLevel
    recommendations: list[str]

    def to_dict(self) -> dict:
        return asdict(self)


# ───────────────────────── Graph construction ─────────────────────────


_HARD_TYPES: frozenset[EdgeType] = frozenset({"imports", "depends"})


def build_graph(ecosystem: Ecosystem) -> DepGraph:
    """Build a dependency graph from an `Ecosystem`.

    Only edges where both endpoints are *internal* packages are recorded —
    external CRAN deps are filtered out (they're not part of our graph).
    """
    package_names = {p.name for p in ecosystem.packages}
    edges: list[Edge] = []

    for pkg in ecosystem.packages:
        desc = pkg.description
        if desc is None:
            continue
        for dep_field, etype in (
            (desc.imports, "imports"),
            (desc.depends, "depends"),
            (desc.suggests, "suggests"),
            (desc.linking_to, "linkingTo"),
        ):
            for dep in dep_field:
                if dep in package_names:
                    edges.append(Edge(from_=pkg.name, to=dep, type=etype))  # type: ignore[arg-type]

    nodes = [p.name for p in ecosystem.packages]
    layers = _topological_layers(nodes, edges)
    cycles = _detect_cycles(nodes, edges)
    return DepGraph(nodes=nodes, edges=edges, layers=layers, circular=cycles)


def _topological_layers(nodes: list[str], edges: list[Edge]) -> list[list[str]]:
    """Kahn-style layering using only hard edges (imports, depends).

    A node enters a layer when all its hard out-edges point at nodes already
    placed in earlier layers. Leaves come first.
    """
    hard = [e for e in edges if e.type in _HARD_TYPES]
    remaining: set[str] = set(nodes)
    layers: list[list[str]] = []

    while remaining:
        layer: list[str] = []
        for node in remaining:
            outgoing = [e.to for e in hard if e.from_ == node and e.to in remaining]
            if not outgoing:
                layer.append(node)
        if not layer:
            # Cycle — emit what's left and stop.
            layers.append(sorted(remaining))
            break
        layer.sort()
        layers.append(layer)
        for node in layer:
            remaining.discard(node)

    return layers


def _detect_cycles(nodes: list[str], edges: list[Edge]) -> list[list[str]]:
    """DFS-based cycle detection over hard edges only.

    Returns a list of cycles; each cycle is the slice of the DFS path from
    the back-edge target onward.
    """
    adj: dict[str, list[str]] = {n: [] for n in nodes}
    for e in edges:
        if e.type in _HARD_TYPES:
            adj[e.from_].append(e.to)

    cycles: list[list[str]] = []
    visited: set[str] = set()
    rec_stack: set[str] = set()
    path: list[str] = []

    def dfs(node: str) -> bool:
        visited.add(node)
        rec_stack.add(node)
        path.append(node)
        for neighbor in adj[node]:
            if neighbor not in visited:
                if dfs(neighbor):
                    return True
            elif neighbor in rec_stack:
                start = path.index(neighbor)
                cycles.append(path[start:])
                return True
        path.pop()
        rec_stack.discard(node)
        return False

    for n in nodes:
        if n not in visited:
            dfs(n)
    return cycles


# ───────────────────────── Dependent traversal ─────────────────────────


def get_all_dependents(
    package: str, graph: DepGraph, hard_only: bool = True
) -> tuple[list[str], list[str]]:
    """Find packages that depend on `package` — directly and transitively.

    Returns (direct, indirect). 'Direct' = immediate importers. 'Indirect' =
    packages reachable by following dependent edges further out.
    """
    edges = [e for e in graph.edges if e.type in _HARD_TYPES] if hard_only else list(graph.edges)
    direct: list[str] = []
    indirect: list[str] = []
    visited: set[str] = set()

    def collect(pkg: str, depth: int) -> None:
        dependents = [e.from_ for e in edges if e.to == pkg]
        for dep in dependents:
            if dep not in visited:
                visited.add(dep)
                (direct if depth == 0 else indirect).append(dep)
                collect(dep, depth + 1)

    collect(package, 0)
    return direct, indirect


def get_update_order(packages: list[str], graph: DepGraph) -> list[str]:
    """Order `packages` according to the graph's topological layers."""
    requested = set(packages)
    out: list[str] = []
    for layer in graph.layers:
        for pkg in layer:
            if pkg in requested:
                out.append(pkg)
    return out


# ───────────────────────── Impact analysis ─────────────────────────


def _format_time_estimate(minutes: int) -> str:
    if minutes < 60:
        return f"{minutes} min"
    if minutes < 480:
        return f"{minutes / 60:.1f}h"
    days = minutes / 480  # 8h workday
    return f"{days:.1f} day{'s' if days >= 1.5 else ''}"


def analyze_impact(
    graph: DepGraph,
    package: str,
    change_type: ChangeType = "feature",
    affected_exports: Optional[list[str]] = None,
) -> Impact:
    """Compute the downstream blast radius of a change to `package`.

    Mirrors `rforge-mcp/dist/tools/deps/impact.js` — same heuristic for
    affected tests, work estimate, and risk level. Useful for pre-flight
    questions like "what does breaking medfit cost us?"
    """
    if package not in graph.nodes:
        raise ValueError(f"Package {package!r} not found in graph (nodes: {graph.nodes})")

    direct, indirect = get_all_dependents(package, graph, hard_only=True)
    affected_packages = [package, *direct, *indirect]
    affected_tests = len(affected_packages) * 15  # MCP's rough heuristic

    update_sequence = get_update_order(affected_packages, graph)

    base = 60 if change_type == "breaking" else 30
    work_minutes = base + len(direct) * 30 + len(indirect) * 15

    if change_type == "breaking" or len(direct) > 2:
        risk: RiskLevel = "high"
    elif len(direct) > 0 or change_type == "feature":
        risk = "medium"
    else:
        risk = "low"

    recs: list[str] = []
    if change_type == "breaking":
        recs.append("Add deprecation warning before removing old behavior")
        recs.append("Maintain backward compatibility for 2 release cycles")
        recs.append("Update dependent packages before CRAN submission")
    if direct:
        recs.append(f"Update {len(direct)} direct dependent package(s)")
    if affected_exports:
        recs.append(f"Document changes to: {', '.join(affected_exports)}")

    return Impact(
        package=package,
        change_type=change_type,
        direct_dependents=direct,
        indirect_dependents=indirect,
        affected_tests=affected_tests,
        update_sequence=update_sequence,
        estimated_work=_format_time_estimate(work_minutes),
        risk_level=risk,
        recommendations=recs,
    )


def identify_blockers(graph: DepGraph) -> list[dict]:
    """Find packages that block others from releasing.

    A blocker sits in an earlier topo layer and has dependents in later
    layers. Sorted by blast radius, most-blocking first.
    """
    blockers: list[dict] = []
    for i in range(len(graph.layers) - 1):
        for pkg in graph.layers[i]:
            direct, indirect = get_all_dependents(pkg, graph, hard_only=True)
            blocked = direct + indirect
            if blocked:
                blockers.append({"blocker": pkg, "blocks": blocked})
    blockers.sort(key=lambda b: len(b["blocks"]), reverse=True)
    return blockers


# ───────────────────────── Formatters ─────────────────────────


def format_graph_text(graph: DepGraph, ecosystem: Ecosystem) -> str:
    lines = ["🔗 DEPENDENCY ANALYSIS", ""]
    lines.append(f"Packages: {len(graph.nodes)}")
    hard_count = sum(1 for e in graph.edges if e.type in _HARD_TYPES)
    lines.append(f"Internal dependencies: {hard_count}")
    lines.append("")

    lines.append("📊 BUILD ORDER (Topological Layers)")
    for i, layer in enumerate(graph.layers, start=1):
        lines.append(f"  Layer {i}: {', '.join(layer)}")
    lines.append("")

    by_name = {p.name: p for p in ecosystem.packages}
    dep_rows: list[str] = []
    for node in graph.nodes:
        deps = [e.to for e in graph.edges if e.from_ == node and e.type in _HARD_TYPES]
        if deps:
            dep_rows.append(f"  {node} → {', '.join(deps)}")
    lines.append("→ DEPENDENCIES")
    lines.extend(dep_rows or ["  (no internal dependencies)"])
    lines.append("")

    if graph.circular:
        lines.append("🔴 CIRCULAR DEPENDENCIES")
        for cycle in graph.circular:
            lines.append(f"  • {' → '.join(cycle)} → {cycle[0]}")
        lines.append("")

    blockers = identify_blockers(graph)
    if blockers:
        lines.append("🚧 BLOCKING PACKAGES")
        for b in blockers[:5]:
            lines.append(f"  • {b['blocker']} blocks: {', '.join(b['blocks'])}")
        lines.append("")

    # External deps (collected from descriptions, since the graph filters them)
    external: set[str] = set()
    internal_names = set(graph.nodes)
    for pkg in ecosystem.packages:
        if pkg.description is None:
            continue
        for field_ in (pkg.description.imports, pkg.description.depends, pkg.description.linking_to):
            for dep in field_:
                if dep not in internal_names:
                    external.add(dep)
    if external:
        lines.append("📦 EXTERNAL DEPENDENCIES")
        lines.append("  " + ", ".join(sorted(external)))

    _ = by_name  # reserved for future per-package rendering
    return "\n".join(lines)


def format_impact_text(impact: Impact) -> str:
    lines = [
        f"📊 IMPACT: {impact.package} ({impact.change_type})",
        "",
        f"  Direct dependents:   {len(impact.direct_dependents)}",
        f"  Indirect dependents: {len(impact.indirect_dependents)}",
        f"  Affected tests:      ~{impact.affected_tests}",
        f"  Risk level:          {impact.risk_level}",
        f"  Estimated work:      {impact.estimated_work}",
    ]
    if impact.direct_dependents:
        lines += ["", "→ DIRECT DEPENDENTS"]
        lines += [f"  • {d}" for d in impact.direct_dependents]
    if impact.indirect_dependents:
        lines += ["", "→→ INDIRECT DEPENDENTS"]
        lines += [f"  • {d}" for d in impact.indirect_dependents]
    if len(impact.update_sequence) > 1:
        lines += ["", "🔄 UPDATE SEQUENCE"]
        for i, pkg in enumerate(impact.update_sequence, start=1):
            lines.append(f"  {i}. {pkg}")
    if impact.recommendations:
        lines += ["", "💡 RECOMMENDATIONS"]
        lines += [f"  • {r}" for r in impact.recommendations]
    return "\n".join(lines)


# ───────────────────────── CLI ─────────────────────────


def _cmd_deps(args: argparse.Namespace) -> int:
    try:
        eco = detect_ecosystem(args.path)
    except (FileNotFoundError, NotADirectoryError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    graph = build_graph(eco)
    if args.format == "json":
        print(json.dumps(graph.to_dict(), indent=2, sort_keys=True))
    else:
        print(format_graph_text(graph, eco))
    return 0


def _cmd_impact(args: argparse.Namespace) -> int:
    try:
        eco = detect_ecosystem(args.path)
    except (FileNotFoundError, NotADirectoryError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    graph = build_graph(eco)
    try:
        impact = analyze_impact(
            graph,
            package=args.package,
            change_type=args.change_type,
            affected_exports=args.affected_exports or None,
        )
    except ValueError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    if args.format == "json":
        print(json.dumps(impact.to_dict(), indent=2, sort_keys=True))
    else:
        print(format_impact_text(impact))
    return 0


def _main(argv: Optional[list[str]] = None) -> int:
    parser = argparse.ArgumentParser(
        prog="deps",
        description="R ecosystem dependency graph + impact analysis.",
    )
    parser.add_argument("--path", default=".", help="Ecosystem root (default: cwd)")
    parser.add_argument(
        "--format", choices=("text", "json"), default="text", help="Output format"
    )
    sub = parser.add_subparsers(dest="cmd")

    sub_deps = sub.add_parser("graph", help="Print dependency graph (default)")
    sub_deps.set_defaults(func=_cmd_deps)

    sub_impact = sub.add_parser("impact", help="Analyze change impact")
    sub_impact.add_argument("--package", required=True, help="Package being changed")
    sub_impact.add_argument(
        "--change-type",
        choices=("breaking", "feature", "fix", "internal"),
        default="feature",
    )
    sub_impact.add_argument(
        "--affected-exports",
        nargs="*",
        default=[],
        help="Exported symbols affected by the change (for recommendations)",
    )
    sub_impact.set_defaults(func=_cmd_impact)

    args = parser.parse_args(argv)
    if not hasattr(args, "func"):
        args.func = _cmd_deps  # default: graph
    return args.func(args)


if __name__ == "__main__":
    sys.exit(_main())

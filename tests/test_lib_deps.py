"""Tests for lib/deps.py."""

from __future__ import annotations

import pytest

from discovery import detect_ecosystem
from deps import (
    analyze_impact,
    build_graph,
    get_all_dependents,
    get_update_order,
    identify_blockers,
)


# ───────────────────────── Helpers ─────────────────────────


def _build_eco(tmp_path, make_pkg, spec):
    """Create packages in `tmp_path` per `spec` (dict: name → imports list)."""
    for name, deps in spec.items():
        make_pkg(name, imports=deps)
    return detect_ecosystem(tmp_path)


# ───────────────────────── Graph construction ─────────────────────────


def test_build_graph_records_internal_edges_only(tmp_path, make_pkg):
    # core ← impl ← top; ggplot2 is external and must not appear in graph
    make_pkg("core")
    make_pkg("impl", imports=["core", "dplyr"])
    make_pkg("top", imports=["impl", "ggplot2"])

    eco = detect_ecosystem(tmp_path)
    graph = build_graph(eco)

    edge_pairs = {(e.from_, e.to) for e in graph.edges}
    assert edge_pairs == {("impl", "core"), ("top", "impl")}
    assert set(graph.nodes) == {"core", "impl", "top"}


def test_topological_layers_leaves_first(tmp_path, make_pkg):
    # core ← impl ← top; expected layers: [[core], [impl], [top]]
    make_pkg("core")
    make_pkg("impl", imports=["core"])
    make_pkg("top", imports=["impl"])

    graph = build_graph(detect_ecosystem(tmp_path))
    assert graph.layers == [["core"], ["impl"], ["top"]]


def test_topological_layers_parallel_within_layer(tmp_path, make_pkg):
    # Two siblings depending on the same core.
    make_pkg("core")
    make_pkg("a", imports=["core"])
    make_pkg("b", imports=["core"])

    graph = build_graph(detect_ecosystem(tmp_path))
    # core alone first; a & b can be built in parallel in layer 2
    assert graph.layers[0] == ["core"]
    assert sorted(graph.layers[1]) == ["a", "b"]


def test_circular_dependency_detected(tmp_path, make_pkg):
    make_pkg("a", imports=["b"])
    make_pkg("b", imports=["a"])

    graph = build_graph(detect_ecosystem(tmp_path))
    assert graph.circular  # non-empty
    # The cycle should mention both packages
    flat = {pkg for cycle in graph.circular for pkg in cycle}
    assert flat == {"a", "b"}


def test_suggests_does_not_affect_topo_layers(tmp_path, make_pkg):
    # 'suggests' is a soft edge — it appears in graph.edges but shouldn't
    # block topological ordering.
    make_pkg("a")
    make_pkg("b", suggests=["a"])

    graph = build_graph(detect_ecosystem(tmp_path))
    # Both should land in layer 1 since suggests is not a hard edge.
    assert sorted(graph.layers[0]) == ["a", "b"]
    # Suggests edge IS recorded:
    assert any(e.type == "suggests" for e in graph.edges)


# ───────────────────────── Dependent traversal ─────────────────────────


def test_get_all_dependents_direct_and_indirect(tmp_path, make_pkg):
    # core ← impl ← top
    make_pkg("core")
    make_pkg("impl", imports=["core"])
    make_pkg("top", imports=["impl"])

    graph = build_graph(detect_ecosystem(tmp_path))
    direct, indirect = get_all_dependents("core", graph)
    assert direct == ["impl"]
    assert indirect == ["top"]


def test_get_all_dependents_handles_diamond(tmp_path, make_pkg):
    # core ← a, b → meta (both a and b imported by meta)
    make_pkg("core")
    make_pkg("a", imports=["core"])
    make_pkg("b", imports=["core"])
    make_pkg("meta", imports=["a", "b"])

    graph = build_graph(detect_ecosystem(tmp_path))
    direct, indirect = get_all_dependents("core", graph)
    assert sorted(direct) == ["a", "b"]
    assert indirect == ["meta"]  # only once despite two paths


def test_get_update_order_respects_topo_layers(tmp_path, make_pkg):
    make_pkg("core")
    make_pkg("impl", imports=["core"])
    make_pkg("top", imports=["impl"])

    graph = build_graph(detect_ecosystem(tmp_path))
    order = get_update_order(["top", "core", "impl"], graph)
    assert order == ["core", "impl", "top"]


# ───────────────────────── Impact analysis ─────────────────────────


def test_analyze_impact_breaking_change_high_risk(tmp_path, make_pkg):
    make_pkg("core")
    make_pkg("a", imports=["core"])
    make_pkg("b", imports=["core"])
    make_pkg("c", imports=["core"])

    graph = build_graph(detect_ecosystem(tmp_path))
    impact = analyze_impact(graph, "core", change_type="breaking")

    assert impact.risk_level == "high"  # breaking → high regardless
    assert sorted(impact.direct_dependents) == ["a", "b", "c"]
    assert "Add deprecation warning before removing old behavior" in impact.recommendations


def test_analyze_impact_internal_no_dependents_is_low(tmp_path, make_pkg):
    make_pkg("solo")
    graph = build_graph(detect_ecosystem(tmp_path))
    impact = analyze_impact(graph, "solo", change_type="internal")
    assert impact.risk_level == "low"
    assert impact.direct_dependents == []
    assert impact.indirect_dependents == []


def test_analyze_impact_feature_with_dependents_is_medium(tmp_path, make_pkg):
    make_pkg("core")
    make_pkg("a", imports=["core"])
    graph = build_graph(detect_ecosystem(tmp_path))
    impact = analyze_impact(graph, "core", change_type="feature")
    assert impact.risk_level == "medium"


def test_analyze_impact_high_when_many_direct_dependents(tmp_path, make_pkg):
    make_pkg("core")
    make_pkg("a", imports=["core"])
    make_pkg("b", imports=["core"])
    make_pkg("c", imports=["core"])  # 3 direct > 2 → high even on non-breaking
    graph = build_graph(detect_ecosystem(tmp_path))
    impact = analyze_impact(graph, "core", change_type="feature")
    assert impact.risk_level == "high"


def test_analyze_impact_update_sequence_is_topo(tmp_path, make_pkg):
    make_pkg("core")
    make_pkg("impl", imports=["core"])
    make_pkg("top", imports=["impl"])
    graph = build_graph(detect_ecosystem(tmp_path))
    impact = analyze_impact(graph, "core", change_type="breaking")
    assert impact.update_sequence == ["core", "impl", "top"]


def test_analyze_impact_affected_exports_appear_in_recommendations(tmp_path, make_pkg):
    make_pkg("core")
    make_pkg("a", imports=["core"])
    graph = build_graph(detect_ecosystem(tmp_path))
    impact = analyze_impact(
        graph, "core", change_type="feature", affected_exports=["fit", "predict"]
    )
    assert any("fit, predict" in r for r in impact.recommendations)


def test_analyze_impact_unknown_package_raises(tmp_path, make_pkg):
    make_pkg("solo")
    graph = build_graph(detect_ecosystem(tmp_path))
    with pytest.raises(ValueError, match="not found in graph"):
        analyze_impact(graph, "ghost", change_type="feature")


# ───────────────────────── Blockers ─────────────────────────


def test_deps_cli_exits_1_on_missing_path(tmp_path):
    """deps CLI: missing path → exit 1, error on stderr (both subcommands)."""
    import subprocess
    from pathlib import Path as _P

    script = _P(__file__).resolve().parent.parent / "lib" / "deps.py"
    missing = str(tmp_path / "ghost")

    # graph subcommand
    result = subprocess.run(
        ["python3", str(script), "--path", missing, "--format", "json"],
        capture_output=True, text=True,
    )
    assert result.returncode == 1
    assert "does not exist" in result.stderr

    # impact subcommand
    result = subprocess.run(
        ["python3", str(script), "--path", missing, "impact",
         "--package", "anything", "--change-type", "feature"],
        capture_output=True, text=True,
    )
    assert result.returncode == 1
    assert "does not exist" in result.stderr


def test_identify_blockers_sorted_by_blast_radius(tmp_path, make_pkg):
    # core ← a, b, c; impl ← top
    make_pkg("core")
    make_pkg("a", imports=["core"])
    make_pkg("b", imports=["core"])
    make_pkg("c", imports=["core"])
    make_pkg("impl")
    make_pkg("top", imports=["impl"])

    graph = build_graph(detect_ecosystem(tmp_path))
    blockers = identify_blockers(graph)

    # core blocks 3, impl blocks 1 — core should come first
    assert blockers[0]["blocker"] == "core"
    assert sorted(blockers[0]["blocks"]) == ["a", "b", "c"]
    assert any(b["blocker"] == "impl" for b in blockers)

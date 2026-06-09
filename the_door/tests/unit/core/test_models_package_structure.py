"""DSM regression test for the the_door.models package.

Pins the post-split structure as an enforced invariant:
  (a) every public name re-exported by the façade is importable;
  (b) the module dependency graph is acyclic (ADP);
  (c) the cross-module edge set equals the designed set (no new coupling);
  (d) every dependency points toward greater stability (SDP, Martin's I).

The dependency graph is rebuilt at runtime by resolving each dataclass's
field type hints (and exception bases) and mapping referenced model classes
to their defining submodule — so it tracks real code, not a transcript.
"""
from __future__ import annotations

import dataclasses
import importlib
import typing

import the_door.models as M

# ── (a) the façade must export exactly these 79 names ────────────────────
EXPECTED_NAMES = set(M.__all__)
# T5-A removed 8 analyze/pipeline-execution types (AnalyzeConfig/AnalyzeResult/
# StepTimeouts/PipelineConfig/PipelineResult/PipelineError/AnalyzeError/
# CostConfirmationRequired): 79 → 71, then TheDoorConfig + CostEstimate
# (provider config): 71 → 69, then the dead ParseResult (config.py removed
# entirely once response_parser was deleted): 69 → 68.
EXPECTED_COUNT = 68

# ── (c) the designed cross-module edge set (module -> module) ────────────
# T5-A: pipeline now holds only the report-data cluster (no cross-module
# references), so all ("pipeline", *) edges are gone.
EXPECTED_MODULE_EDGES = {
    ("snapshot", "vulnerability"),
    ("diff", "snapshot"),
}

SUBMODULES = [
    "extraction", "analysis", "vulnerability", "snapshot",
    "diff", "scope", "doubt", "timeline", "pipeline",
]

PKG = "the_door.models"


def _short(module_name: str) -> str | None:
    """'the_door.models.snapshot' -> 'snapshot'; None if outside the package."""
    if module_name == PKG or not module_name.startswith(PKG + "."):
        return None
    return module_name[len(PKG) + 1:]


def _referenced_model_classes(hint) -> set:
    """Walk a (possibly generic) type hint, collecting model classes."""
    found = set()
    for arg in typing.get_args(hint):
        found |= _referenced_model_classes(arg)
    if isinstance(hint, type) and getattr(hint, "__module__", "").startswith(PKG):
        found.add(hint)
    return found


def _build_module_graph():
    edges = set()
    nodes = set()
    for sub in SUBMODULES:
        mod = importlib.import_module(f"{PKG}.{sub}")
        nodes.add(sub)
        for name in dir(mod):
            obj = getattr(mod, name)
            if not isinstance(obj, type):
                continue
            if getattr(obj, "__module__", None) != f"{PKG}.{sub}":
                continue  # only classes DEFINED here, not re-imports
            referenced = set()
            if dataclasses.is_dataclass(obj):
                hints = typing.get_type_hints(obj)
                for h in hints.values():
                    referenced |= _referenced_model_classes(h)
            for base in getattr(obj, "__bases__", ()):
                if getattr(base, "__module__", "").startswith(PKG):
                    referenced.add(base)
            for ref in referenced:
                target = _short(ref.__module__)
                if target and target != sub:
                    edges.add((sub, target))
    return nodes, edges


def _instability(nodes, edges):
    ce = {n: 0 for n in nodes}  # efferent: depends on
    ca = {n: 0 for n in nodes}  # afferent: depended on by
    for a, b in edges:
        ce[a] += 1
        ca[b] += 1
    return {n: (ce[n] / (ca[n] + ce[n]) if (ca[n] + ce[n]) else 0.0) for n in nodes}


def _has_cycle(nodes, edges):
    adj = {n: set() for n in nodes}
    for a, b in edges:
        adj[a].add(b)
    color = {n: 0 for n in nodes}

    def dfs(u):
        color[u] = 1
        for v in adj[u]:
            if color[v] == 1:
                return True
            if color[v] == 0 and dfs(v):
                return True
        color[u] = 2
        return False

    return any(color[n] == 0 and dfs(n) for n in nodes)


def test_facade_exports_exactly_79_names():
    assert len(M.__all__) == EXPECTED_COUNT
    assert len(set(M.__all__)) == EXPECTED_COUNT  # no duplicates


def test_every_public_name_is_importable():
    for name in EXPECTED_NAMES:
        assert hasattr(M, name), f"façade missing re-export: {name}"
        assert isinstance(getattr(M, name), type), f"{name} is not a class"


def test_module_graph_is_acyclic():
    nodes, edges = _build_module_graph()
    assert not _has_cycle(nodes, edges), f"models package has an import cycle: {edges}"


def test_cross_module_edges_match_design():
    _, edges = _build_module_graph()
    assert edges == EXPECTED_MODULE_EDGES, (
        f"unexpected edges (new coupling?): added={edges - EXPECTED_MODULE_EDGES}, "
        f"missing={EXPECTED_MODULE_EDGES - edges}"
    )


def test_dependencies_point_toward_stability():
    nodes, edges = _build_module_graph()
    I = _instability(nodes, edges)
    violations = [(a, I[a], b, I[b]) for a, b in edges if I[a] < I[b] - 1e-9]
    assert not violations, f"SDP violations (depend on less stable): {violations}"

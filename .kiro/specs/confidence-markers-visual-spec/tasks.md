# Implementation Plan: Confidence Markers Visual Specification (Phase 0b)

## Overview

Add confidence marker visual encoding to the existing Mermaid renderer and JSON output. This is primarily a rendering concern: one new field on `Feature`, new constants and functions in `mermaid_renderer.py`, and minor wiring in the two CLI/tool entry points. TDD approach — tests are written first, then implementation.

## Tasks

- [x] 1. Add `source_reviewed` field to Feature and write marker resolution tests
  - [x] 1.1 Add `source_reviewed: bool = False` field to `Feature` dataclass in `models.py`
    - Add after `review_reason` field, before end of class
    - Must be backward-compatible (default `False`)
    - Verify existing 250 tests still pass
    - _Requirements: 1.1, 1.2_

  - [x] 1.2 Add `MarkerDef` dataclass and `MARKER_DEFS` constant to `mermaid_renderer.py`
    - Define `MarkerDef` frozen dataclass with fields: `name`, `icon`, `fill`, `stroke`, `stroke_dasharray`, `stroke_width`, `display_label`
    - Define `MARKER_DEFS` dict with all 6 states (high, medium, low, reviewed, regenerated, incomplete)
    - _Requirements: 2.1, 2.2, 2.4_

  - [x] 1.3 Write unit tests for `MarkerDef` uniqueness constraints in `test_mermaid_renderer.py`
    - Test all 6 fill colors are unique (Req 2.4)
    - Test all 6 border styles are unique (Req 5.1)
    - Test all 6 icon prefixes are unique (Req 5.2)
    - _Requirements: 2.4, 5.1, 5.2_

  - [x] 1.4 Implement `resolve_marker_state()` function in `mermaid_renderer.py`
    - Pure function: `(Feature, *, regenerated_differs=False, incomplete_reading=False) -> str`
    - Priority: incomplete > regenerated > reviewed > base confidence
    - Returns a key from `MARKER_DEFS`
    - _Requirements: 1.1, 1.2_

  - [ ]* 1.5 Write property test `test_resolve_returns_one_valid_state` in `test_rendering_properties.py`
    - **Property 1: Marker priority resolution returns exactly one valid state**
    - Generate all combinations of confidence (high/medium/low), source_reviewed, regenerated_differs, incomplete_reading
    - Assert return value is always a key in `MARKER_DEFS`
    - Assert priority ordering is respected
    - **Validates: Requirements 1.1, 1.2, 3.2**

- [x] 2. Checkpoint — Verify model change and resolution logic
  - Ensure all tests pass, ask the user if questions arise.

- [x] 3. Implement `build_confidence_marker()` and JSON integration
  - [x] 3.1 Implement `build_confidence_marker()` in `mermaid_renderer.py`
    - Public function returning dict with keys: `confidence`, `source_reviewed`, `regenerated_differs`, `incomplete_reading`, `display_label`
    - All boolean fields always present regardless of active state
    - _Requirements: 3.1, 3.2_

  - [ ]* 3.2 Write property test `test_json_marker_preserves_all_booleans` in `test_rendering_properties.py`
    - **Property 2: JSON confidence_marker preserves all boolean states**
    - For any Feature + flag combination, assert all 5 keys present and booleans match inputs
    - **Validates: Requirements 1.3, 3.1**

  - [x] 3.3 Wire `build_confidence_marker()` into `analyze_cmd.py`
    - Import `build_confidence_marker` from `mermaid_renderer`
    - Add `confidence_marker` key to feature dicts in JSON output
    - Ensure `confidence_reason` remains present
    - _Requirements: 3.1, 3.2, 3.3_

  - [x] 3.4 Wire `build_confidence_marker()` into `analyze_tool.py`
    - Same integration as `analyze_cmd.py`
    - _Requirements: 3.1, 3.2, 3.3_

  - [ ]* 3.5 Write unit tests for JSON output in `test_mermaid_renderer.py`
    - Test `confidence_reason` still present in JSON output (Req 3.3)
    - Test `regenerated_differs` cleared after accept (Req 1.4)
    - _Requirements: 1.4, 3.3_

- [x] 4. Modify `render_l1()` for marker-aware rendering
  - [x] 4.1 Update `render_l1()` signature and classDef generation
    - Add `marker_context: dict[str, dict[str, bool]] | None = None` and `show_legend: bool = False` params
    - Replace 3 hardcoded classDef lines with all 6 from `MARKER_DEFS`
    - Prepend resolved icon to node labels
    - Use resolved marker key for class assignment
    - Default behavior (no marker_context) must match existing output for high-confidence features
    - _Requirements: 2.1, 2.2, 2.3_

  - [ ]* 4.2 Write property test `test_mermaid_labels_have_correct_icon` in `test_rendering_properties.py`
    - **Property 3: Mermaid node labels contain the correct icon prefix**
    - For any Feature, assert rendered label starts with `MARKER_DEFS[resolved_state].icon`
    - **Validates: Requirements 2.1, 2.3**

  - [x] 4.3 Write unit test for exact classDef output in `test_mermaid_renderer.py`
    - Verify classDef lines match the spec table for each state
    - _Requirements: 2.2_

  - [x] 4.4 Implement `_render_legend()` and integrate into `render_l1()`
    - Generate legend subgraph only when `show_legend=True` and at least one non-high state exists
    - Legend contains entries for exactly the set of resolved states present
    - _Requirements: 4.1, 4.2, 4.3_

  - [ ]* 4.5 Write property test `test_legend_matches_present_states` in `test_rendering_properties.py`
    - **Property 4: Conditional legend contains exactly the present states**
    - For any set of features with `show_legend=True`, assert legend appears iff non-high state exists
    - Assert legend entries match exactly the set of resolved states
    - **Validates: Requirements 4.1, 4.2, 4.3**

  - [ ]* 4.6 Write unit test for `show_legend=False` suppression in `test_mermaid_renderer.py`
    - Verify `show_legend=False` suppresses legend even when non-high states present
    - _Requirements: 4.4_

- [x] 5. Final checkpoint — Full regression
  - Ensure all existing 250 tests plus new tests pass, ask the user if questions arise.

## Notes

- Tasks marked with `*` are optional and can be skipped for faster MVP
- TDD order: tests in 1.3/1.5 are written before or alongside implementation in 1.2/1.4
- All changes touch existing files only (no new source files created)
- New test code goes in existing `test_rendering_properties.py` and `test_mermaid_renderer.py`
- Property tests use Hypothesis (already in project) with minimum 100 iterations per property
- Each task references specific requirements for traceability

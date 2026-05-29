# Edge Noise Projection — Implementation Plan Index

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement these tasks task-by-task.

**Spec:** `docs/superpowers/specs/2026-05-29-edge-noise-projection-design.md`

**Builds on:** v1.4.5（Scope-Aware Edge Resolution，4 種 resolution 標籤已上線）

**Target version:** v1.4.6（incremental — 無 schema breaking change）

---

## Task Files

| # | File | Goal | Layer |
|---|---|---|---|
| 01 | `01-resolution-enum.md` | `Edge.resolution` 新增 `name_match_ambiguous` 枚舉值 + source-level guard 釘住 `core/diff/` 不引用 resolution | schema |
| 02 | `02-edge-projection-pure-module.md` | `core/llm/edge_projection.py` 新檔（純函式 drop ambiguous + aggregate hint，無旗標）+ 10 unit + 4 property test | projection |
| 03 | `03-edge-builder-fanout-threshold.md` | `_resolve()` Step 4 加 `FANOUT_THRESHOLD`；自動涵蓋 calls 與 extends | extraction |
| 04 | `04-batch-reader-integration.md` | `_build_payload` detail mode 套用 projection，加 `aggregate_call_hints` payload key | reading |
| 05 | `05-prompt-update.md` | `prompts.py` resolution 區塊改寫 + aggregate_call_hints 說明 | prompt |
| 06 | `06-dogfood-and-docs.md` | dogfood histogram 腳本決定 `N`、CHANGELOG、出版前驗收 | verification + docs |

---

## Dependency Graph

```
01 (resolution enum)
 ├─ 02 (projection module)       ┐
 └─ 03 (fanout threshold)        ┘ 兩者可平行
        ↓
       04 (batch_reader 整合，需要 02)
        ↓
       05 (prompt 更新，需要 04 的 payload shape)
        ↓
       06 (dogfood + CHANGELOG)
```

**順序紀律：**
- 01 必須先完成（其他全部依賴枚舉值合法）
- 02 與 03 可平行（不共用檔案、不互相依賴）
- 04 必須在 02 完成後（消費 `project_edges_for_prompt`）
- 05 必須在 04 完成後（prompt 描述要對應實際 payload shape）
- 06 最後（dogfood 跑出來才能定 N、CHANGELOG 才能寫驗收數據）

---

## Self-Containment 紀律

每個 task 文件 **完整自含**：
- 含所有測試程式碼（不要求讀其他 task）
- 含所有實作程式碼（不要求讀 spec）
- 含完整 commit 指令
- 不指示「另外寫一份 X 文件」

100% 覆蓋率紀律：
- 新檔（`edge_projection.py`、`dogfood_edge_projection_report.py`）覆蓋率必達 100%
- 既有檔（`edge_builder.py`、`batch_reader.py`、`prompts.py`）新增分支必達 100%
- 不退步既有檔覆蓋率

---

## 驗收（出版前）

- [ ] 全測試 GREEN（含新增 unit / property / integration / contract）
- [ ] `edge_projection.py` cov = 100%
- [ ] `edge_builder.py` 累積 cov = 100%（v1.4.5 已達）
- [ ] dogfood §7.2 Step 2 比較結果記入 CHANGELOG
- [ ] CHANGELOG v1.4.6 entry + README 雙語 core capabilities 表更新（task 06）

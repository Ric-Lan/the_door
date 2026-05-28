# Scope-Aware Edge Resolution — Implementation Plan Index

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement these tasks task-by-task.

**Spec:** `docs/superpowers/specs/2026-05-28-scope-aware-edge-resolution-design.md`

**Builds on:** v1.4.0（L1 Prompt Context Modes + declarative `LanguageConfig`）

**Target version:** v1.5.0

---

## Task Files

| # | File | Goal | Languages touched |
|---|---|---|---|
| 01 | `01-schema-foundation.md` | `ScopeRules` / `ScopeContext` / `Edge.resolution` schema + serializer 向後相容 | — (schema only) |
| 02 | `02-edgebuilder-core-python.md` | EdgeBuilder 三段式 `_resolve()` 核心 + Python `qualified` import 解析 + 更新 `ast_extractor.py` 呼叫端 | Python |
| 03 | `03-typescript-java-scope-rules.md` | `_parse_es_module_imports` (TS) + `_parse_namespaced_imports` (Java) | TypeScript, Java |
| 04 | `04-go-rust-scope-rules.md` | `_parse_module_path_imports` (Go, Rust) | Go, Rust |
| 05 | `05-ruby-php-csharp-scope-rules.md` | Ruby 簡化（`dynamic_dispatch`）+ PHP/C# 擴充 `_walk_namespaced_imports` | Ruby, PHP, C# |
| 06 | `06-prompt-changelog-verification.md` | L1 prompt 教 LLM 看 resolution + CHANGELOG + dogfood 驗收 | — (LLM + docs) |

---

## Dependency Graph

```
01 (schema)
 └─ 02 (EdgeBuilder core + Python)
     ├─ 03 (TS + Java)        ┐
     ├─ 04 (Go + Rust)        ├─ 可平行（不互相依賴）
     └─ 05 (Ruby + PHP + C#)  ┘
            ↓
       06 (prompt + CHANGELOG + dogfood)
```

**順序紀律：**

- 01 必須先完成（其他全部依賴 schema）
- 02 必須在 01 之後完成（內含 EdgeBuilder 核心，03/04/05 都假設 `_parse_import_aliases` dispatch 機制存在）
- 03 / 04 / 05 **可平行**執行（三者修改 `language_configs.py` 不同 entry、修改 `edge_builder.py` 不同 stub method，git merge 衝突極小）
- 06 必須在 03/04/05 全部完成後執行（dogfood 驗收依賴所有語言到位）

**注意：** 03 與 05 都修改 `_walk_namespaced_imports`（03 加 Java、05 擴充 PHP+C#）。若兩者平行進行，05 必須在 03 commit 後 rebase。建議順序：03 先 commit，05 接著做。

---

## Acceptance（spec §7 全部驗收項目，集中於 06 確認）

**§7.1 結構性驗收（Task 06 Step 17）：**
- LanguageConfig.scope_rules 7 種語言皆有
- ScopeRules dataclass 5 欄位
- 所有新 Edge 必有 resolution
- _resolve() 三段式
- 舊 snapshot 向後相容
- L1 prompt 含四種 resolution 說明

**§7.2 數據驗收（Task 06 Step 13/14）：**
- scope_rule + import_alias ≥ 50%
- name_match ≤ 40%
- 總邊數下降 10-30%

**§7.3 LLM 主觀驗收：**
- 抽 10 個 L1 description 對比 §4.2 風格規則違反條目數 ≤ v1.4.0

**§7.4 紀律驗收：**
- 紀律 1：每條 Edge 有 resolution（grep 證明）
- 紀律 2：_resolve() fallback 路徑存在 + property test 釘住「scope 失敗時必出 name_match edge」
- 紀律 3：dynamic_markers 偵測測試覆蓋

---

## 測試覆蓋率紀律

**每個 task 對所改動的檔案要求 100% line coverage。** 各 task 文件末段都有對應的 `pytest --cov-fail-under=100` 指令。

**全套回歸：** 每個 task 結束前都跑 `pytest tests/ -q`，確保不破壞既有測試。

---

## Out-of-Scope（spec §3 / §11）

不在本 plan 範圍，不要在執行時順手做：

- W3 typed references（永遠不做）
- SCIP / LSIF 接入（永遠不做）
- 跨 repo 分析（另開 spec）
- 新語言擴張（Kotlin / Scala / Swift / Elixir — 另開 spec）
- DB schema diff as L1 signal（已有 spawn_task 紀錄）
- Edge UI 視覺差異化（後續 viewer spec）

若執行中發現必要的擴展需求，記入 handoff，**不要**在本 plan 中加 task。

# Viewer Fixes + Data Quality + Wizard — Plan Index

> 此文件為索引。各分類已拆為獨立文件。

## 執行順序

```
A（models）→ B-Task01（cli/status）+ C（extraction） [可並行]
         → D（integration tests）+ E（frontend js）  [可並行，A+C 完成後]
         → B-Task10（cli/wizard，需 C 完成）
         → F（css，任意時機）
```

## 分類索引

| 文件 | Tasks | 依賴 |
|---|---|---|
| [2026-05-24-A-models.md](2026-05-24-A-models.md) | Task 03 — FeatureSummary.confidence_reason + warnings | 無 |
| [2026-05-24-B-cli.md](2026-05-24-B-cli.md) | Task 01 — status_cmd cp950；Task 10 — wizard | Task 01 無依賴；Task 10 需 C |
| [2026-05-24-C-extraction.md](2026-05-24-C-extraction.md) | Task 02 — file_discovery .claude/ + extra_ignore | 無 |
| [2026-05-24-D-integration-tests.md](2026-05-24-D-integration-tests.md) | Task 04 — FlowGuard e2e；Task 05 — source_nodes | 需 A |
| [2026-05-24-E-frontend-js.md](2026-05-24-E-frontend-js.md) | Task 06 — filter；Task 07 — topbar；Task 08 — mindmap | 無 |
| [2026-05-24-F-frontend-css.md](2026-05-24-F-frontend-css.md) | Task 09 — CSS row-gap | 無 |

## Review 修正記錄（已修入各分類文件）

| 問題 | 嚴重度 | 修正 |
|---|---|---|
| Task 01 測試用 FailWriter 攔截 sys.stdout 無效（CliRunner 有獨立 stream） | critical | 改驗 `os.environ` + `result.output` |
| Task 01 `click.echo(err=True)` 將 status 輸出移到 stderr，破壞可腳本化介面 | critical | 移除 `err=True`，輸出留在 stdout |
| Task 06 Step 4 描述兩種互斥實作（parameter-passing vs state），無決策 | warning | 刪除 parameter-passing 路徑，只保留 `state._filteredFeatures` |
| Task 10 `AnalyzeConfig(provider_config=config)` — `provider_config` 不存在 | critical hallucination | 改為 `AnalyzeConfig()`（pipeline 內部呼叫 ConfigManager.load()） |
| Task 10 `result.error` — `AnalyzeResult` 無此欄位 | critical hallucination | 改為 try/except 包覆 `run_analyze_pipeline` |
| Task 10 `test_wizard_excludes_specified_directory` 斷言永遠 True | warning | 改驗 `"排除後剩餘 1 個檔案" in result.output` |

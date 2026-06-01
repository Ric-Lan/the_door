# AI-Agent API Index

Auto-generated from the live route table (`the_door.core.ui.api.router.build_routes`). Do not edit by hand — run `python -m the_door.core.ui.api._gen_docs` to regenerate.

Total routes: 21

| Method | Path | Summary | Handler |
| --- | --- | --- | --- |
| GET | `/api/project` | 讀取當前專案狀態與基本資訊 | `ProjectHandlers.get` |
| POST | `/api/set-project` | 切換當前分析的目標專案 | `ProjectHandlers.set_project` |
| GET | `/api/status` | 回報當前專案狀態與建議下一步 | `ProjectHandlers.status` |
| POST | `/api/analyze` | 啟動完整分析的非同步任務（需 API key） | `AnalysisHandlers.analyze` |
| POST | `/api/update` | 啟動增量更新分析的非同步任務 | `AnalysisHandlers.update` |
| GET | `/api/update/status/{job_id}` | 查詢指定分析任務的進度 | `AnalysisHandlers.update_status` |
| GET | `/api/snapshots` | 列出所有版本快照 | `CatalogHandlers.snapshots` |
| GET | `/api/timeline` | 回傳跨版本時間軸 | `CatalogHandlers.timeline` |
| GET | `/api/report/latest` | 讀取最近一次分析報告 | `CatalogHandlers.report_latest` |
| GET | `/api/l1` | 讀取指定版本的 L1 功能圖（節點+關聯） | `GraphHandlers.get_l1` |
| GET | `/api/l2/{feature_id}` | 讀取指定功能的 L2 模組分解（若已生成） | `GraphHandlers.get_l2` |
| POST | `/api/l2/{feature_id}/generate` | 為指定功能啟動 L2 生成任務（需 LLM） | `GraphHandlers.generate_l2` |
| GET | `/api/structure` | 讀取原始抽取結構 structure.json | `GraphHandlers.get_structure` |
| GET | `/api/layer-explanation/{feature_id}/{layer}` | 讀取指定功能在指定層的說明 | `GraphHandlers.get_layer_explanation` |
| POST | `/api/layer-explanation/{feature_id}/{layer}/generate` | 為指定功能層啟動說明生成（需 LLM） | `GraphHandlers.generate_layer_explanation` |
| GET | `/api/diff` | 比對 baseline 與 current 兩版本的功能層差異 | `DiffHandlers.versions` |
| GET | `/api/diff-explanations/{feature_id}` | 讀取指定功能的差異說明（若已生成） | `DiffHandlers.get_explanation` |
| POST | `/api/diff-explanations/{feature_id}/generate` | 為指定功能啟動差異說明生成（需 LLM） | `DiffHandlers.generate_explanation` |
| GET | `/api/doubts` | 列出作用域分析產生的疑慮項 | `AnnotationHandlers.doubts` |
| GET | `/api/notes` | 讀取使用者註記 | `AnnotationHandlers.get_notes` |
| POST | `/api/notes` | 新增使用者註記 | `AnnotationHandlers.post_notes` |

## Error codes

Every handler returns errors via the central registry. See [error-codes.md](./error-codes.md) for the full catalog of codes, HTTP statuses, owning source files, and descriptions.

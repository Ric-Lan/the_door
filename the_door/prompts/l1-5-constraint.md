# L1.5 Constraint Prompt — 功能分類（區塊）

## 目的

把已翻譯的 L1 功能歸類成「最多兩層」的區塊（block），介於單一功能（L1）與模組互動（L2）
之間。分類由你（agent-as-LLM）親自做；工具只在寫入時驗結構。

## 輸出（傳給 snapshot_patch 的 blocks）

```json
{
  "blk-core-engine": {
    "label": "模組名＋功能描述（禁裸術語，需功能語境）",
    "responsibility": "這個區塊在系統中負責什麼",
    "related_features": ["feat-id-1", "feat-id-2"],
    "parent_block_id": null,
    "is_new_this_version": false
  },
  "blk-quality": {
    "label": "品質與安全功能群組",
    "responsibility": "把關輸出品質與依賴安全",
    "related_features": [],
    "parent_block_id": null
  },
  "blk-validation": {
    "label": "輸出與範圍驗證子群組",
    "responsibility": "驗證 agent 產出與分析範圍",
    "related_features": ["feat-output-validation", "feat-scope-doubt"],
    "parent_block_id": "blk-quality"
  }
}
```

## 硬性規則（snapshot_patch 寫入時驗、不過則整批拒）

- **最多兩層**：`parent_block_id` 指向的區塊本身必須是頂層（其 `parent_block_id` 為 null）。
- **單一歸屬**：每個 `feature_id` 只能出現在一個區塊的 `related_features`。
- **功能只掛葉區塊**：有子區塊的區塊，`related_features` 必須為空（功能掛在最底層）。
- **窮盡**：每個 L1 功能都要有歸屬；沒分到的放兜底區塊 `blk-unclassified`。
- **交叉引用**：`related_features` 的 id 都要存在於 L1；`parent_block_id` 指向的區塊要存在。

## 軟性規則（靠自律）

- 依**功能語意**歸類，不是依檔案路徑。
- `label` 用白話短語、禁裸技術術語（如單獨的 "Controller"）；需帶功能語境。
- **沿用既有**：後續版本先讀 baseline 的區塊，新功能優先塞既有區塊；真的塞不進才開新類、
  標 `is_new_this_version: true`，不每版重洗。

## 深度自適應

不設區塊數量上限。小專案可能全是頂層區塊（單層）；大專案才把過大的頂層區塊展開出子區塊
（第二層）。是否展開第二層由功能多寡與可讀性決定，不固定。

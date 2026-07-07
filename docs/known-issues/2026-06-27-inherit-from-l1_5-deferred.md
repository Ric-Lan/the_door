# 擱置項現況快照：`inherit_from` 繼承 `l1_5_snapshot`（最佳化，延後）

> 用途：此項是 backlog 第 5 項「L1.5 分類層 `inherit_from` 繼承 l1_5 最佳化」的**現況存證**。
> 之後若重開此項，先讀本文件對照「當時 vs 屆時」程式差異，確認問題仍存在、未被其他改動順手解掉。
>
> 調查日期：2026-06-27　調查者：agent（未動程式，純驗證）
> 對應 spec：[`docs/superpowers/specs/2026-06-21-feature-classification-blocks-design.md`](../superpowers/specs/2026-06-21-feature-classification-blocks-design.md) §6「inherit_from 繼承 l1_5（最佳化，可延後）」、§12-6。

---

## 1. 一句話

`snapshot_write(inherit_from=...)` 產的純繼承版本，其 `l1_5_snapshot`（功能分類區塊）會是**空的**——
baseline 的區塊分類不會自動沿用。此為**最佳化、非必要**（spec 自身定性），現況已存證，**未修**。

## 2. 驗證到的程式現況（2026-06-27，作為 diff 基準）

inherit 分支只繼承三樣，**不碰 `l1_5_snapshot`**：

- `snapshot_write_tool.py:217-313`（inherit 分支）：只組 `l1_snapshot`(features)、`relations`、
  `project_summary`。全程無 `l1_5` 字樣。
- `snapshot_write_tool.py:356`：`store.create_snapshot(...)` 呼叫**未傳 `l1_5_snapshot` 參數**
  （direct 與 inherit 兩模式皆然）。
- `core/diff/snapshot_store.py:103,131`：`create_snapshot(l1_5_snapshot=None)` 預設 → 未傳時填 `{}`。

⟹ 淨效果：`snapshot_write(inherit_from=baseline)` 的新版本 `l1_5_snapshot == {}`，
不論 baseline 是否已分類。

### 對照其他三樣「有」繼承的（佐證這是漏的一塊、非設計如此）
- features：`snapshot_write_tool.py:282-294`（merge on top of `baseline_snap.l1_snapshot`）
- relations：`:309-310`（未給則 `list(baseline_snap.feature_relations_snapshot)`）
- project_summary：`:312-313`（未給則沿用 `baseline_snap.project_summary`，呼應「組成沒變不重寫」）

`l1_5_snapshot` 是這組「純繼承沿用」語義裡**唯一沒被涵蓋**的欄位。

## 3. 現有 workaround（為何「非必要」）

agent 在 `snapshot_write(inherit_from=...)` 後，再呼叫
`snapshot_patch(version_ref=新版, blocks={...整批...})` 重帶**所有**區塊（blocks 是整批取代，
spec §5）。結果**正確**，只是多一道機械重貼。省掉的是一次決定性 patch 呼叫（複製 baseline blocks），
**不是 LLM 重譯成本**——agent 不需重新翻譯。

未做此優化時：viewer `GET /api/blocks` 對該純繼承版本讀到空 `l1_5_snapshot` → fallback 平鋪。

## 4. 必要性判斷（當時結論）

**結論：現在不做。** 三點理由：
1. **正確性不缺**：spec 自定性非必要，workaround 產出正確。
2. **過「能做≠該做」閘門**：只服務「純繼承版本 ∩ 已做 L1.5 分類」交集工作流；L1.5 分類層是
   v1.7.9 才出的新層、僅在 v170 測試資料跑過，**真實使用幾近於零**，無真痛點驅動。
3. **省的成本小**：省的是一次機械 patch，非翻譯成本。

**唯一翻案情境**：開始大量用 `inherit_from` 做純繼承版本、又依賴 viewer 顯示分類區塊、
且嫌每版 re-patch 煩。屆時重估。

## 5. 若重開——執行大綱（spec 已寫，無需重 spike）

1. 薄 plan（spec §6/§12-6 已寫，直接 plan）。
2. 核心改動（純加法、約一處）：inherit 分支把 `baseline_snap.l1_5_snapshot` 傳進
   `create_snapshot(l1_5_snapshot=...)`。決策點：
   - snapshot_write 目前**無 `blocks` 參數**，故單純沿用 baseline 即可、無覆寫衝突。
   - affected set 非空時仍以 baseline blocks 作沿用起點（不傷正確性；spec 精神是建議 re-patch 調整，
     但沿用為起點即可）。
3. TDD roundtrip：`inherit_from` 後新版 `l1_5_snapshot == baseline 的`；無 baseline blocks 時回 `{}` 不變。
4. 契約：純加法，**不 bump** `SNAPSHOT_CONTRACT_VERSION`。
5. 本地 ff-merge、明示才 push。

## 6. 重開前的對照清單（diff 用）

重開時逐項複查，確認下列「當時為真」是否仍為真：
- [ ] `snapshot_write_tool.py` inherit 分支仍未傳 `l1_5_snapshot` 給 `create_snapshot`
      （若已有人順手加上，本項已自動解決，存證作廢）。
- [ ] `create_snapshot` 簽章 `l1_5_snapshot` 仍預設 `None→{}`。
- [ ] snapshot_write 仍無 `blocks` 入參（若已加，覆寫優先序需重議）。
- [ ] L1.5 分類層的真實使用是否已從「近乎零」上升（決定必要性是否翻案的關鍵）。

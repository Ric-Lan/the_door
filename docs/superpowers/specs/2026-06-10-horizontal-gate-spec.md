# 水平推廣 gate spec：把 C3 coverage gate 擴到 snapshot_patch（丙案 軌2 階段2）

> 承接：種子 `2026-08...seed.md` §10.7.2 階段2「（擴展 gate 到 extract/snapshot/diff 鏈，C1 確認表）＝水平推廣」、
> §10.6 守則（強制力 100% 在 deny gate；多重綁定不增加控制力）。
> 承接 C2/C3（snapshot_write 已 gate on checklist existence+currency+coverage）、C5（guidance 權威
> 已涵蓋 edge_residue、deny 已指回單一權威）。
>
> **核心洞察（spike 實證，§1）**：C3 只 gate `snapshot_write` 的 source_nodes coverage。但
> **`snapshot_patch` 透過 `source_nodes_by_feature` 寫 source_nodes 進既有 snapshot，完全未 gate
> ＝C3 coverage 的第二寫入口繞道**。這是唯一真正的水平 gap。`diff`/`analyze_changes` 唯讀且
> in-tool 已對「無 snapshot/baseline」回 error → 加 gate＝冗餘軟層（違反守則）；`snapshot_create`
> 只 clone 既有 latest（無 agent source_nodes）→ 無捏造風險。⟹ **水平推廣＝把既有 C3 gate 擴到
> `snapshot_patch`，非 blanket-gate 全鏈。**

---

## 1. spike（已對真實碼驗，事實寫入；不需事後再驗）

| 工具 | 是否寫 agent source_nodes | in-tool 既有驗證 | 是否該 gate | 來源 file:line |
|---|---|---|---|---|
| `snapshot_write` | 是（l1_features/updated_features[].source_nodes） | — | ✅ 已 gate（C2/C3） | `snapshot_write_tool.py:53-56,100-103` |
| **`snapshot_patch`** | **是（`source_nodes_by_feature`: {fid:[node_id]}）** | 僅 SnapshotNotFound | **🔴 未 gate＝真 gap** | `snapshot_patch_tool.py:26-36,67-72` |
| `snapshot_create` | 否（clone `latest.l1_snapshot`） | `get_latest() is None → error` | ❌ 無捏造風險、不 gate | `snapshot_create_tool.py:26-28,31-39` |
| `diff` | 否（唯讀比對 snapshot） | `get_latest() None→error`、baseline NotFound→error | ❌ 唯讀＋已自驗，gate＝冗餘軟層 | `diff_tool.py:35-42` |
| `analyze_changes` | 否（唯讀 incremental） | pipeline IncrementalAnalysisError→error envelope | ❌ 唯讀＋已自驗 | `analyze_changes_tool.py:126-137` |
| `extract_structure` | 否（鏈首步、唯讀觀察） | — | ❌ 無前置可 gate | seed §288 |

其他證據：
| 事實 | 來源 | 影響 |
|---|---|---|
| C3 hook `_source_nodes` 目前讀 `l1_features`/`updated_features`，**未讀 `source_nodes_by_feature`** | `c3_gate_snapshot_write.py:53-59` | 擴 snapshot_patch＝`_source_nodes` 也 flatten `source_nodes_by_feature` 的 dict values |
| C3 hook 對缺 checklist **existence-always** deny（不論 payload 有無 source_nodes）；C2-6 釘此 | `c3_gate_snapshot_write.py:78-91`、`test_execution_gates.py:51-54` | 不可改 snapshot_write 路徑的 existence-always（否則 C2-6 回歸）⟹ snapshot_patch 採**同樣 existence-always**（full symmetry，§3.2） |
| PreToolUse event JSON 含 `tool_name`（如 `mcp__the-door__snapshot_patch`） | hook 慣例（C3/C4 讀 `tool_input`，event 亦含 `tool_name`） | deny 訊息可用 tool_name 短名，避免謊稱 snapshot_write |
| repair-drift guidance 建議 CLI extract → snapshot_patch 補 source_nodes，**CLI extract 不蓋 checklist**（只 edge_residue MCP 蓋） | `suggester.py:65-71`、C2 | snapshot_patch 一旦 gate，repair-drift 流程需先 edge_residue ⟹ 本刀同步更新 repair-drift rationale（與其 gate 同落、自洽） |
| settings.json 既有 PreToolUse matcher `mcp__the-door__snapshot_write`→c3 hook | `.claude/settings.json:22-30` | 加 `mcp__the-door__snapshot_patch`→**同一** c3 hook（DRY，共用 existence/currency/coverage） |

---

## 2. 目標與非目標

**目標**：
1. **gate `snapshot_patch`**：把既有 C3 checklist gate（existence + currency + coverage）擴到 `snapshot_patch`，coverage 對其 `source_nodes_by_feature` 的所有 node_id 做 ⊆ covered 檢查。共用同一 c3 hook（加 settings matcher），不另寫 hook（DRY、守則 #2 不重複綁定）。
2. **deny 訊息 tool-aware**：deny 用 event 的 `tool_name` 短名（snapshot_write／snapshot_patch），不謊稱 snapshot_write。
3. **repair-drift guidance 同步**：`_rule_repair_drift` rationale 補 edge_residue（與新 gate 一致：補 source_nodes 前先 edge_residue）。

**非目標（釘樁，防 gold-plating／違守則）**：
- ❌ **不 gate `diff`/`analyze_changes`/`extract_structure`/`snapshot_create`**：唯讀或無 agent source_nodes；in-tool 已自驗。加 gate＝冗餘軟層（守則 #2「多重綁定不增加控制力」）。**明確記為證據裁定的排除。**
- ❌ **不另寫新 hook**：共用 c3 hook（避免兩份 checklist 讀取邏輯漂移）。
- ❌ **不改 snapshot_write 既有 gate 行為**（existence-always／coverage 不動；C2-6..13 不回歸）。
- ❌ **不做 staleness／completeness**（C2 已 deferred 的部分，正交）。

---

## 3. 設計

### 3.1 c3 hook 擴 source_nodes 來源 + tool-aware deny
- `_source_nodes(tool_input)`：除既有 `l1_features`/`updated_features[].source_nodes`，再**flatten `source_nodes_by_feature`**（dict，值為 node_id list）：
  ```python
  by_feat = tool_input.get("source_nodes_by_feature")
  if isinstance(by_feat, dict):
      for nodes in by_feat.values():
          out.extend(nodes or [])
  ```
- deny 訊息：讀 `data.get("tool_name")`，取短名（strip `mcp__the-door__` 前綴；缺則 fallback `"snapshot 寫入"`），用於三段 deny 的主詞，取代硬編 `snapshot_write`。
- existence/currency/coverage 三段邏輯、exit code、fail-open、C5 的 system_status 指回**皆不變**。

### 3.2 gate 的統一原則＝「gate node-writes」（snapshot_patch 採 source_nodes-conditional）
gate 的明文目的（C2/§1）＝**node-coverage**（擋未涵蓋/捏造的 source_nodes）。據此統一原則：**對「寫 node 歸屬」的呼叫 engage existence+currency+coverage**。
- `snapshot_write`＝**永遠是 node-write**（其用途即寫 L1 features；direct 必有 l1_features、inherit 有 updated_features）→ **existence-always**（與 C2-6 既定不變量一致，行為零變）。
- `snapshot_patch`＝**iff 帶 `source_nodes_by_feature`（非空）才是 node-write**。
  - 帶 source_nodes_by_feature → existence+currency+coverage（與 snapshot_write 同條路）。
  - **純 metadata-only**（只 `feature_metadata_by_feature`/`analyzed_files`、無 source_nodes_by_feature）→ **不 engage、allow**（無 node 寫入＝在 gate 目的之外；over-gate 它＝scope-creep）。
- **實作幾乎零成本**：hook 本就需讀 `tool_name`（為 §3.1 tool-aware deny）。先算 `src = _source_nodes(tool_input)`（已 flatten l1_features/updated_features/source_nodes_by_feature 的實際 node），engage 判斷＝
  `engage = (tool_short != "snapshot_patch") or bool(src)`。
  - snapshot_write → 恆 engage（C2-6..13 零回歸）。
  - snapshot_patch 有實際 source_nodes → engage；`{}`／`{"feat-x":[]}`／無 → `src` 空 → 不 engage、allow（非 node-write）。
- coverage 對 engage 的 snapshot_write 呼叫：`src` 空（inherit-only）仍 existence-always、coverage 真空通過（既有行為）。
- 🔴 **tool_name 缺失的安全退化（第一輪審 warning）**：若 event 無 `tool_name`，`tool_short` 未知 → `tool_short != "snapshot_patch"` 為真 → `engage` 恆真 ⟹ 回退成 existence-always（**過度 gate、絕不漏 gate**＝安全方向）。hook 只掛在 snapshot_write/snapshot_patch 兩 matcher（§3.3），故有 tool_name 時 `tool_short` 足以區分二者；無 tool_name 時退化安全。實作對 tool_name 缺失用 `data.get("tool_name") or ""`，不可 crash。

### 3.3 settings.json 註冊
- PreToolUse 加一條 matcher `mcp__the-door__snapshot_patch`，command 指向**同一** `c3_gate_snapshot_write.py`（守衛式 python，與既有 snapshot_write 條目同形）。

### 3.4 repair-drift guidance 同步（與 gate 自洽）
- `_rule_repair_drift` rationale：「偵測到 source_nodes_drift — 重跑 extract、**跑 edge_residue**，再用 snapshot_patch 補 source_nodes。」（prose 準確；cli 面，與 C5 first_time/incremental 同模式）。
- 不改其 cli_command（仍 extract 入口）；edge_residue 以 prose 明示（state 無法精確偵測「repair 進行中、edge_residue 未跑」，同 C5 incremental 的處理）。
- ⚠ **範圍澄清（第一輪審 suggestion）**：repair_drift surfaces=`("cli",)` ⟹ 此 rationale 更新＝**cli/人類權威準確性**。執行 snapshot_patch 的 **mcp agent 收不到此 rationale**，其避/解 deny 靠 **gate deny → C5 authority 指回**（與 C5 incremental 同：deny 兜底）。本刀對 mcp agent 的保障在 gate＋deny，非 repair_drift rationale。

### 3.5 hook 命名（誠實註記）
- 檔名保留 `c3_gate_snapshot_write.py`（避免 settings×2＋drift-pin 測 churn）；docstring 更新明述「gate snapshot_write **與 snapshot_patch** 兩條 source_nodes 寫入路」。`_write` 涵蓋「patch 亦為對 snapshot 的寫入」。

---

## 4. 向後相容 / 遷移
- snapshot_write 路徑邏輯完全不變（C2-6..13、C5-6 不回歸）。
- snapshot_patch 新受 gate：既有對 snapshot_patch 的**單元/整合測呼叫 execute() 直接**（不經 hook）→ 不受影響；唯 live agent 呼叫受 gate。
- repair-drift 流程：agent 照更新後 guidance 先 edge_residue（蓋 checklist + 覆蓋 node）再 snapshot_patch → 通過 gate。
- settings 新 matcher＝純加法。

## 5. 測試（spec 層；plan 細分 task）

**hook gate（黑箱 subprocess，比照 test_execution_gates C2-*）**：
- H-1 snapshot_patch 無 checklist → deny(rc2)，stderr 提 edge_residue（existence-always）。
- H-2 checklist 蓋章（edge_residue, covered=["a","b"]）＋ `source_nodes_by_feature={"feat-x":["a"]}` → allow(rc0)。
- H-3 同上但 `source_nodes_by_feature={"feat-x":["a","zzz"]}`（zzz 未涵蓋）→ deny(rc2)，stderr 提 coverage/涵蓋。
- H-4 contract_version 過期 → deny(rc2)。
- H-5 snapshot_patch metadata-only（只 feature_metadata_by_feature、**無 source_nodes_by_feature**）＋ **無 checklist** → allow(rc0)（非 node-write、在 gate 目的之外、不 engage）。**event 必須帶 `tool_name="mcp__the-door__snapshot_patch"`**，否則測到的是 tool_name 缺失的安全退化路徑（會 deny）而非豁免路徑。
- H-5b snapshot_patch 帶**空** `source_nodes_by_feature={}`（無實際 node）＋無 checklist → 視為非 node-write → allow(rc0)（同 H-5，須帶 tool_name）。
- H-5c **tool_name 缺失安全退化**：snapshot_patch metadata-only payload 但 event **不帶 tool_name** ＋無 checklist → deny(rc2)（退化成 existence-always＝安全、絕不漏 gate）。釘住安全退化方向。
- H-6 deny 訊息含 tool 短名 `snapshot_patch`（tool-aware，不謊稱 snapshot_write）：以 event 帶 `tool_name="mcp__the-door__snapshot_patch"` 餵 hook，斷言 stderr 含 `snapshot_patch`。
- H-7 snapshot_write 路徑回歸：既有 C2-6..13 全綠（`_source_nodes` 加 source_nodes_by_feature 不影響 l1_features/updated_features 讀取）。

**settings 註冊**：
- H-8 settings.json PreToolUse 有 matcher `mcp__the-door__snapshot_patch` 指向 c3 hook；既有 snapshot_write matcher 仍在（G-9 不回歸）。

**guidance**：
- H-9 `_rule_repair_drift` rationale 含 "edge_residue"（prose 準確回歸樁）。

**drift-pin 回歸**：
- H-10 既有 C2-14/15 drift-pin（hook 字面 vs checklist 常數）仍綠（本刀不動欄位常數）。

## 6. 終局護欄
- Python 全套 0 failed；新測 H-1..H-9 綠。
- snapshot_patch 對「無 checklist／coverage 不足／version 過期」皆 deny；對合法（蓋章+covered，或 metadata-only+蓋章）allow。
- snapshot_write 既有 gate 行為零變（C2-6..13、C5-6、drift-pin 全綠）。
- 唯讀工具（diff/analyze_changes/extract/snapshot_create）**未被加 gate**（守則 #2）。
- production gate 強制邏輯只**擴來源＋擴 matcher**，三段判定語義不變。

## 7. Forward-coherence
- **完整 staleness**（C2 deferred）：與本刀正交；snapshot_patch coverage 同樣只擋「引用未涵蓋 node」，不偵測刪除/原地改。誠實延續 C2 邊界。
- **再水平推廣**：若日後要 gate 其他寫入路徑，沿用「共用 c3 hook + payload source_nodes 來源擴充 + settings matcher」範式。唯讀工具仍不在範圍（守則 #2）。

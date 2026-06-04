# DoubtLifecycle 抽出 + 轉換規範單一真相（Finding B-2，甲案）— 設計

> **日期**：2026-06-04　**狀態**：設計中、待審（spike 已對真實碼完成）
> **刀序**：Finding B 第二刀（store 各藏一個子元件 → 顯性化）。承 B-1（BaselineResolver）同型；命題不同（B-1=差異/參照解析，B-2=範圍/狀態機）。
> **scope = 甲案（純內部、零輸出改動、行為保留）**。經使用者拍板。乙案（把意義經 tile schema/結構送達 agent）**明確延後**至重構 campaign 結束後的全專案輸出 pass，見 memory `todo_output_direction_assessment`，本刀不碰。
> **目標檔**：新 `core/scope/doubt_lifecycle.py`；改 `core/scope/doubt_store.py`、`mcp/tools/doubt_transition_tool.py`、`cli/doubt_cmd.py`；新測試 + characterization 測試。

---

## §1 命題（為什麼動）

`DoubtStore` 同時是「疑義的儲存者」與「疑義生命週期的裁決者」。後者——一條疑義可以怎麼動、每一動代表什麼——是一套獨立的**政策**，目前以「合法性表 ＋ 命令式動詞 ＋ 落盤」糊在 store 裡，而且**同一套規則被重複表達四遍**（見 §2.1）。

**主軸：政策與機制分離（Separation of Policy from Mechanism）。** 抽出純 `DoubtLifecycle` ＝ 讓「什麼轉換合法、每個轉換產出什麼」成為**單一宣告式真相**（純、零 I/O）；`DoubtStore` 退回純機制（load/persist），消費端（MCP tool、CLI）改讀同一份來源。

**為什麼是 Mealy（決定設計形狀、也決定剔除 GoF State）**：doubt 的副作用掛在**轉換（邊）**上、且帶**輸入負載**（assignee/reason/description），這是 Mealy 機。GoF State 模式天生契合 Moore 機（行為封進狀態類別），套到 Mealy 機是模型錯置。故設計把「效果」放在**以 target_state 為鍵**的宣告裡，**不**做 per-state 類別階層。

**零輸出改動界線**：本刀只收斂「規則的內部表達」與「落盤次數」。**不改**任何 agent/使用者看得到的輸出——MCP tool 的 `TOOL_SCHEMA`（含 `target_state` 的裸描述）、CLI 的 echo 文字、回傳 dict 欄位、`doubt-record.schema.json` 一律不動。意義送達消費端＝乙案，延後。

---

## §2 驗證事實（spike 已對真實碼核對，不需重驗）

### §2.1 轉換政策被表達四遍（真正的重複）
1. **合法性**：`doubt_store.py` 的 `VALID_TRANSITIONS`（61–69）＋ `TERMINAL_STATES`（71）。
2. **操作本體＋副作用**：5 個公開動詞 `assign`(205) / `explain`(218) / `fix`(236) / `escalate`(254) / `resolve_escalation`(265)，各自 `_transition`(377) 後手刻副作用。
3. **MCP 路由**：`doubt_transition_tool.py` 的 `execute` if-elif（56–92）：target_state → 哪個動詞、必填檢查、**escalated 分支**（`explained`/`fixed` 在 escalated 時走 `resolve_escalation` 否則走 `explain`/`fix`，66–79）。
4. **CLI 路由**：`doubt_cmd.py` 的 `doubt_resolve`（174–187）：current_state＋resolution_type → 哪個動詞、**同一個 escalated 分支**。

### §2.2 副作用是「target_state」的函數，不是動詞的（核心簡化、行為保留依據）
- →`investigating`：設 `assigned_to`（輸入 assignee）。
- →`escalated`：只把 reason 記進 `StateTransition`，**無 Resolution**（輸入 reason）。
- →`explained`/`fixed`/`accepted_risk`：產 `Resolution(type=target_state, description=...)`（輸入 description/reason）。
- **逐欄相同證明**：`explain(...)`（226–232）與 `resolve_escalation("explained",...)`（274–280）產出的 `Resolution` 四欄（type/description/resolved_by/resolved_at）完全相同，**只差 from_state**（由 `_transition` 記進 history）。→ §2.1 的「escalated 分支」是「同一效果拆成兩動詞」的產物；以 target_state 為鍵的單一來源使該分支**自然消失**，結果 doubt 逐欄一致。

### §2.3 雙重落盤
- `_transition`(377) 結尾 `self._persist(doubt)`(422)。
- `assign`(215)/`explain`(233)/`fix`(251)/`resolve_escalation`(281) 在 `_transition` 後補欄位再 `self._persist` **第二次**。
- `escalate` 無第二次 persist（單次）。
- → 收成「改完整體、落盤一次」即消除冗餘寫檔（同一檔內容、DRY/簡化，**非效能宣稱**）。

### §2.4 公開介面與觸發源（行為保留硬約束）
- 5 個公開動詞被 **CLI ＋ MCP 都呼叫**（CLI: `doubt_cmd.py` assign 131 / explain 176 / fix 178 / escalate 219 / resolve_escalation 180；MCP: `doubt_transition_tool.py` 60/68/70/77/79/84/89）→ **簽名與行為不得變**。
- 第 6 個觸發源：`check_timeouts`(288) 經 `_transition`(315/334) 自動升級（actor=`system_timeout`），且 `list_doubts`(132) lazy 呼叫它 → 單一來源/統一路徑**必須一併服務 timeout**。
- 錯誤型別：`DoubtTerminalError(doubt_id, from_state)`(399)、`InvalidTransitionError(from_state, to_state)`(404)、`DoubtNotFoundError(doubt_id)`。各消費端的錯誤**呈現**（tool 回 `{"error":True,"message":...}`、CLI `click.echo`+`sys.exit(1)`）與訊息文字須保留。

### §2.5 模型欄位（序列化來源）
- `StateTransition`：from_state / to_state / timestamp / actor / reason（425–445）。
- `Resolution`：type / description / resolved_by / resolved_at（446–455）。
- `DoubtRecord`：doubt_id / source_node / doubt_type / current_state / created_by / created_at / updated_at / assigned_to / state_history / resolution。
- `_persist`(495) 落盤前 `jsonschema.validate`（與 Finding A `_write_snapshot` 同形，已一致、不動）。

### §2.6 消費面盤點（共 8 源碼檔）
`cli/doubt_cmd.py`、`cli/scope_cmd.py`、`mcp/tools/doubt_transition_tool.py`、`mcp/tools/doubt_list_tool.py`、`mcp/tools/scope_verify_tool.py`、`core/ui/api/handlers/project.py`、`core/ui/api/handlers/annotation.py`、`core/scope/scope_verifier.py`。其中只有 `doubt_cmd.py` 與 `doubt_transition_tool.py` 含**轉換路由**（本刀改它倆）；其餘只呼 `list_doubts`/`get_summary`/`create_doubt`（不碰）。

---

## §3 理論收貨／剔除紀錄（理論當磨刀、不當背書）

| 理論 | 留下的利刃（換得到具體改動） | 剔除的過頭版本 |
|---|---|---|
| 政策/機制分離（**承重**） | lifecycle=政策（合法性＋效果）、store=機制（load/persist）；4 份重複收成 1 份 | 不抽 interface/ABC、不建 policy engine |
| Mealy/Moore（**剔除武器**） | 效果以 target_state 為鍵掛在「轉換」上＝Mealy 的具體落地 | **剔除 GoF State 模式**：doubt 是 Mealy 機，套 Moore 式 per-state 類別＝模型錯置、過度設計 |
| 語意/語用（補充稜鏡） | 「產 Resolution 值」是語意（lifecycle）、「寫磁碟」是語用（store）→ 印證接縫位置 | 同政策/機制，是同一條縫的別名，不當獨立論據堆疊 |
| DRY/單一真相（減法軸） | 消 4 份路由重複 ＋ 雙重落盤 | 不宣稱效能/吞吐收益（見 §10） |
| K8s 宣告式 API | —（已剔除） | **剔除 reconcile/Controller 隱喻**：doubt 轉換是同步離散命令、無收斂/drift 語意 |
| schema-loader 去重 | —（已剔除） | 假目標：各 schema 用途本就不同、已用獨立命名檔結構標示，重複讀檔非問題 |

乙案（意義經 tool schema 送 agent）整體延後，見 §8 / `todo_output_direction_assessment`。

---

## §4 設計

### §4.1 新檔 `core/scope/doubt_lifecycle.py`（純、零 I/O）

具體 class（**不抽 interface/ABC**）。持規則、回「轉換方案」值物件；不碰檔案、不碰 `DoubtRecord` 持久化。

```python
"""The law of how a doubt moves: legal transitions + what each transition produces.

Pure: no file I/O, no persistence. The store loads/saves DoubtRecords and applies
the plan this class returns. Single home of doubt transition policy (Mealy: the
effect is keyed on the *target state* and carries transition inputs).
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone

from the_door.models import (
    DoubtTerminalError,
    InvalidTransitionError,
    Resolution,
    StateTransition,
)


@dataclass(frozen=True)
class TransitionPlan:
    """What a single legal transition mutates. Pure value, applied by the store."""
    transition: StateTransition          # appended to state_history
    resolution: Resolution | None        # set when target is a resolving state
    assigned_to: str | None              # set when target is investigating
    set_assigned_to: bool                # True only for →investigating (distinguishes "set None")


class DoubtLifecycle:
    """Maps (from_state, target_state, inputs) → a TransitionPlan, or raises."""

    VALID_TRANSITIONS: dict[str, set[str]] = {
        "discovered": {"investigating", "escalated"},
        "investigating": {"explained", "fixed", "escalated"},
        "escalated": {"explained", "fixed", "accepted_risk"},
        "explained": set(),
        "fixed": set(),
        "accepted_risk": set(),
    }
    TERMINAL_STATES: set[str] = {"explained", "fixed", "accepted_risk"}
    _RESOLVING_STATES: set[str] = {"explained", "fixed", "accepted_risk"}

    def is_terminal(self, state: str) -> bool:
        return state in self.TERMINAL_STATES

    def check_transition(self, from_state: str, to_state: str, doubt_id: str) -> None:
        """Legality only. Raises DoubtTerminalError / InvalidTransitionError."""
        if from_state in self.TERMINAL_STATES:
            raise DoubtTerminalError(doubt_id, from_state)
        if to_state not in self.VALID_TRANSITIONS.get(from_state, set()):
            raise InvalidTransitionError(from_state, to_state)

    def plan(
        self,
        *,
        doubt_id: str,
        from_state: str,
        to_state: str,
        actor: str,
        reason: str | None = None,
        assignee: str | None = None,
        description: str | None = None,
    ) -> TransitionPlan:
        """Validate legality and build the effect for *to_state* (Mealy: by target).

        Effect by target (behaviour-preserving, see spec §2.2):
          - investigating          -> set assigned_to=assignee
          - escalated               -> record reason only (no resolution)
          - explained/fixed/accepted_risk -> Resolution(type=to_state, description)
        Inputs are assumed present (callers keep their own required-input guards &
        messages — see §4.3); this method does not re-validate presence.
        """
        self.check_transition(from_state, to_state, doubt_id)
        now = datetime.now(timezone.utc).isoformat()
        transition = StateTransition(
            from_state=from_state, to_state=to_state,
            timestamp=now, actor=actor, reason=reason,
        )
        resolution = None
        assigned_to = None
        set_assigned = False
        if to_state == "investigating":
            assigned_to = assignee
            set_assigned = True
        elif to_state in self._RESOLVING_STATES:
            resolution = Resolution(
                type=to_state, description=description or "",
                resolved_by=actor, resolved_at=now,
            )
        return TransitionPlan(transition, resolution, assigned_to, set_assigned)
```

> 註：`description or ""` 僅防呆；呼叫端在 resolving 路徑一律已帶 description（§2.4/§4.3 guard）。Resolution 的 `resolved_at` 與 transition `timestamp` 共用同一 `now`（與現況 `_transition` 各取一次 now 的差異＝兩值原本就極近、且非契約；以共用 now 收斂、characterization 測不斷言跨欄時間相等）。

### §4.2 `DoubtStore` 變薄殼（規則委派、落盤一次）

- `__init__`（73）新增 `self._lifecycle = DoubtLifecycle()`（單一實例，stateless collaborator，比照 B-1）。
- **刪除** store 的 `VALID_TRANSITIONS`/`TERMINAL_STATES` 類屬性（61–71）——唯一真相移入 lifecycle。對 `TERMINAL_STATES` 的活碼引用**共三處**（grep 驗證、`_transition` 內 398/402 隨刪而消）須全部改指 lifecycle：`list_doubts`(165)、`get_summary`(182)、**`has_active_doubt`(197)**——改 `self._lifecycle.TERMINAL_STATES`（或 `self._lifecycle.is_terminal(...)`）。⚠️ 漏改 197 會 AttributeError。
- **新增統一內部套用點**，取代舊 `_transition`：
  ```python
  def _apply_transition(self, doubt, to_state, actor, *, reason=None,
                        assignee=None, description=None):
      plan = self._lifecycle.plan(
          doubt_id=doubt.doubt_id, from_state=doubt.current_state,
          to_state=to_state, actor=actor, reason=reason,
          assignee=assignee, description=description,
      )
      doubt.current_state = to_state
      doubt.updated_at = plan.transition.timestamp
      doubt.state_history.append(plan.transition)
      if plan.resolution is not None:
          doubt.resolution = plan.resolution
      if plan.set_assigned_to:
          doubt.assigned_to = plan.assigned_to
      self._persist(doubt)          # 落盤一次（消雙重）
      return doubt
  ```
- **新增公開統一入口**（供 tool/CLI 共讀、且不破壞 5 動詞）：
  ```python
  def transition(self, doubt_id, target_state, *, actor,
                 reason=None, assignee=None, description=None):
      """Single public entry: resolve & apply any transition by target state."""
      doubt = self.get_doubt(doubt_id)
      return self._apply_transition(doubt, target_state, actor,
                                    reason=reason, assignee=assignee,
                                    description=description)
  ```
- **5 個動詞改為薄殼**（簽名/行為不變），各自帶固定 target 呼叫內部套用點：
  ```python
  def assign(self, doubt_id, assignee, actor):
      return self.transition(doubt_id, "investigating", actor=actor, assignee=assignee)
  def explain(self, doubt_id, description, resolved_by):
      return self.transition(doubt_id, "explained", actor=resolved_by, description=description)
  def fix(self, doubt_id, description, resolved_by):
      return self.transition(doubt_id, "fixed", actor=resolved_by, description=description)
  def escalate(self, doubt_id, reason, actor):
      return self.transition(doubt_id, "escalated", actor=actor, reason=reason)
  def resolve_escalation(self, doubt_id, resolution_type, description, resolved_by):
      return self.transition(doubt_id, resolution_type, actor=resolved_by, description=description)
  ```
  > `assign` 行為核對：舊碼 `_transition`(213) 後 `doubt.assigned_to = assignee`(214)。新碼 plan 對 →investigating 設 `assigned_to=assignee`、`set_assigned_to=True`。一致。
  > `escalate` 核對：舊碼 `_transition(→escalated, reason=reason)`、無 resolution、無 assigned。新碼 plan 對 →escalated 只記 reason。一致（且舊碼本就單次 persist，新碼亦單次）。
- **`check_timeouts`(288)** 內兩處 `self._transition(doubt, "escalated", "system_timeout", reason=...)`（315/334）改為 `self._apply_transition(doubt, "escalated", "system_timeout", reason=...)`。行為一致（escalated 路徑只記 reason）。
- **刪除** 舊 `_transition`(377–423)（被 `_apply_transition` 取代、無殘留呼叫）。

### §4.3 消費端路由收斂（讀同一份來源，呈現自保）

**(a) `doubt_transition_tool.py` `execute`（56–92）** → 移除 if-elif 與 escalated 分支；**保留**必填 guard 與其 error 訊息（呈現層），改單一呼叫：
```python
    # required-input guards 原文保留（assignee for investigating；reason for 其餘 4 個）
    if target_state == "investigating" and not assignee:
        return {"error": True, "message": "assignee is required for investigating transition"}
    if target_state in ("explained", "fixed", "escalated", "accepted_risk") and not reason:
        return {"error": True, "message": f"reason is required for {target_state} transition"}
    if target_state not in ("investigating", "explained", "fixed", "escalated", "accepted_risk"):
        return {"error": True, "message": f"Unknown target_state: {target_state}"}

    try:
        doubt = store.transition(
            doubt_id, target_state, actor=actor,
            reason=reason, assignee=assignee,
            description=reason,   # 見下「description 對位」
        )
    except (DoubtNotFoundError, DoubtTerminalError, InvalidTransitionError) as e:
        ... # 既有 except 分支與訊息原文保留
```
- **description 對位（行為保留關鍵）**：舊 tool 對 explained/fixed/accepted_risk 用 `reason` 當 `description` 傳給 `explain`/`fix`/`resolve_escalation`（63/73/87→傳 reason）。新碼把 `reason` 同時當 `description` 傳入 `transition`（resolving 路徑取 description、escalated 路徑取 reason）。逐路核對：
  - investigating：用 assignee（reason 忽略）✓
  - escalated：用 reason 記 history（description 忽略）✓
  - explained/fixed/accepted_risk：description=reason → `Resolution.description=reason` ✓（與舊一致）
- **per-message guard 文字需逐字核對**：舊 escalated 訊息為 `"reason is required for escalated transition"`、explained/fixed/accepted_risk 同模式 → 上方 f-string 產生相同文字。實作時須對 `doubt_transition_tool.py:59/64/74/83/88` 逐字比對（characterization 測釘）。

**(b) `doubt_cmd.py` `doubt_resolve`（174–197）** → 移除整段 if/elif/else dispatch（含 escalated 分支），改單一呼叫 ＋ **把兩種例外映射回原客製句**（完全忠實、零行為改變）：
```python
    try:
        updated = store.transition(
            resolved_id, resolution_type, actor="cli_user", description=reason,
        )
        click.echo(f"Doubt {updated.doubt_id[:8]} resolved as {resolution_type} (state: {updated.current_state})")
        from the_door.cli.post_run_hook import cli_post_run_hook
        cli_post_run_hook(codebase_path, json_mode_active=False)
    except (DoubtTerminalError, InvalidTransitionError):
        click.echo(
            f"Error: Cannot resolve as '{resolution_type}' from state '{doubt.current_state}'. "
            f"Expected: investigating + explained/fixed, or escalated + any resolution type.",
            err=True,
        )
        sys.exit(1)
```
- **為何完全忠實（核對舊行為，grep 驗）**：舊碼 if/elif **只對 3 種合法組合**呼 store 方法（必成功，不拋）、**所有非法組合一律走 else 印客製句＋exit(1)**（181–187）。故舊 `except DoubtTerminalError`(192)/`except InvalidTransitionError`(195)（印 `Error: {e}`）在 `doubt_resolve` 內**實際是死碼**（else 先攔掉所有非法）。新碼把全部非法（含 terminal）交給 `store.transition` 拋出 → 統一 catch 兩種例外、印**同一句客製訊息**＋exit(1)。對位：
  - 合法（investigating+explained/fixed、escalated+任一）→ 成功，訊息與舊一致 ✓
  - 非法（discovered+任一、investigating+accepted_risk、terminal+任一）→ 舊走 else 客製句；新由例外映射回**同一客製句**（`doubt.current_state` 取自 168 已載入的 doubt）✓ 逐字相同
- `doubt` 仍需在 try 前 `get_doubt`(168) 載入（供客製句的 `current_state`）；其與 `store.transition` 內再載入＝**既有的雙重載入**（舊碼同樣 168＋verb 內各載一次），非本刀引入、不處理。
- **消費端零路由達成**：CLI 不再判斷 current_state/escalated，不再選 explain/fix/resolve_escalation；合法性與效果全由 lifecycle 決定。

**(c) `doubt_assign` / `doubt_escalate`（CLI）**：本就單一呼叫 `store.assign`/`store.escalate`，**不改**（動詞薄殼後行為不變）。

### §4.4 不改清單（零輸出改動驗收）
- `doubt_transition_tool.py` 的 `TOOL_SCHEMA`（4–33）一字不動（含 `target_state` 裸描述）。
- 所有回傳 dict／CLI echo 文字／`doubt-record.schema.json`／模型欄位不動。
- `list_doubts`/`get_summary`/`create_doubt`/`get_doubt`/序列化/`_persist`/schema-loader 不動。

---

## §5 契約保留（驗收硬條件）
- 5 公開動詞簽名與行為逐欄不變（§4.2 薄殼核對）。
- `transition` 為**新增**公開方法（純加法、不破既有）。
- 錯誤型別與各消費端錯誤呈現/訊息不變（§4.3 逐字核對 + §7.4 CLI else 決議）。
- 落盤格式、schema、輸出 dict、tool schema 不變（§4.4）。
- `check_timeouts`/`list_doubts` 行為不變。

---

## §6 測試計畫

### §6.1 前置：characterization 測試（**先寫、釘現況、必過於改前**）
doubt 子系統零直接測試 → 重構前先補，覆蓋（對「改前」HEAD 全綠）：
1. 5 動詞 happy path：狀態轉移 + 副作用（assigned_to / Resolution 四欄 / reason 記 history）+ 落盤後可重載。
2. 合法性：每種非法轉換拋 `InvalidTransitionError`；終態再轉拋 `DoubtTerminalError`。
3. timeout：discovered 超 discovery_timeout → escalated（actor=system_timeout）；investigating 超 investigation_timeout → escalated；未超/不適用 → None。
4. MCP tool `execute`：每個 target_state 路徑（含 escalated 時 explained/fixed 走 resolve_escalation 的結果）、必填錯誤（assignee/reason）文字、unknown target_state、terminal/invalid 錯誤 → 回傳 dict 形狀與訊息逐字。
5. CLI：`doubt_resolve` 三條合法 dispatch + else 錯誤句、`doubt_assign`、`doubt_escalate`、`doubt_list`/`doubt_show` 輸出。

### §6.2 新 `tests/unit/core/scope/test_doubt_lifecycle.py`（純單元、無 I/O）
- 直接建 from_state/to_state 呼 `plan`/`check_transition`：6 狀態合法性、終態拋錯、效果 by target（investigating→assigned、escalated→僅 reason、3 resolving→Resolution(type=target)）、§2.2 序保留等價（explained 經 investigating vs escalated 產同 Resolution 欄）。

### §6.3 回歸
全套件零回歸（基準＝改前）；§6.1 characterization 測改後仍全綠（行為保留的硬證據）。

---

## §7 陷阱（給實作者）
1. **順序鐵則**：§6.1 characterization 測**先寫先綠**，再動結構；否則無安全網、靜默回歸無從察覺。
2. **description 對位**：tool/CLI 的 resolving 路徑把 `reason` 當 `description` 傳（§4.3a）；漏傳會讓 `Resolution.description` 變空 → characterization 測 4 會抓。
3. **escalated 分支消失要等價**：移除 explain-vs-resolve_escalation 分支後，結果 doubt 必須逐欄等同舊碼（§2.2 已證）；測試對「escalated→explained」與「investigating→explained」分別斷言 Resolution 欄位。
4. **CLI else 客製訊息**（§4.3b）：`doubt_resolve` 必須把 `DoubtTerminalError` **與** `InvalidTransitionError` 都 catch 並印**原客製句**（非 `Error: {e}`）——舊 192/195 的 `Error: {e}` 分支在此函式是死碼、由本映射取代。`DoubtTerminalError`/`InvalidTransitionError` 已在 157 import，不需新增。`doubt_assign`/`doubt_escalate` 的 except 維持原樣（它們本就會真的拋這些例外、印 `Error: {e}`）。
5. **單一 lifecycle 實例**：store `__init__` 建一次、重用 `self._lifecycle`；勿每次 `DoubtLifecycle()`。
6. **刪 store 類屬性後**：`list_doubts`/`get_summary` 對 `TERMINAL_STATES` 的引用要改指 lifecycle，勿留懸空。
7. **timeout 路徑**：`check_timeouts` 兩處改 `_apply_transition`，actor 仍 `system_timeout`、reason 文字不變。

---

## §8 Non-goals
- **不碰乙案**：不改 tool `TOOL_SCHEMA`、不加 enum/意義標示、不改任何 agent/使用者輸出。意義送達消費端延後至全專案輸出 pass（`todo_output_direction_assessment`）。
- 不抽 interface/ABC、不建 policy/strategy/workflow 引擎、不套 GoF State（§3）。
- 不碰 schema-loader、不碰讀取路徑、不碰 `doubt-record.schema.json`、不碰 B-1 產物。
- 不宣稱效能收益（§10）。

---

## §9 驗收
- 新 `DoubtLifecycle` 純、零 I/O，持唯一合法性表＋效果 by target；單元測涵蓋 §6.2。
- store 委派薄殼、5 動詞簽名/行為不變、雙重落盤消除、舊 `_transition` 與類屬性已刪無殘留。
- tool/CLI 路由改讀單一來源、escalated 分支消失、**輸出與錯誤呈現逐字不變**。
- characterization 測（§6.1）改前改後皆全綠；全套件零回歸。
- 改動面：新 `doubt_lifecycle.py` + `doubt_store.py` + `doubt_transition_tool.py` + `doubt_cmd.py` + 2 新測試檔。**不得有其他檔被改**（tool schema、輸出、模型、datamodel 皆未動）。

---

## §10 校準宣言（執行期資源中性）
本刀買到的是**可理解性與變更局部性**：4 份轉換規則收斂一處、消費端去重、副作用宣告化（Mealy 落地）。執行期中性——同樣的 load/persist；順帶消掉雙重落盤的冗餘寫檔，記為 **DRY/簡化**，**不**作 throughput/效能宣稱。剔除 Kahn 式讀寫效能語言、剔除 K8s reconcile 語意（§3）。意義送達消費端（乙案）為**輸出契約改動**、與本刀性質相反，明確延後。

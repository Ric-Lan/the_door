# Requirements Document — Graphical Language Specification (Phase 0a 圖形語言規範)

## Introduction

Phase 0a 定義 The Door 的圖形語言規範（結構層），涵蓋 L1–L2 三層圖形語言、Diff 視覺符號、範圍邊界協定、以及疑義路徑概念設計。本 Phase 的交付物是**設計規範文件與 paper prototype**，不是程式碼實作。

**核心驗收場景（來自 Spec v4.1 §8）：** 給 PM / 發布經理看 paper prototype，能在 10 分鐘內回答「這次改了哪裡」並識別出至少一個刻意埋入的疑義點，且能說出「發現疑義後的下一步」。

**Go 標準：** 5 人中 ≥ 4 人（80%）能在 10 分鐘內完成驗收場景。
**停損條件：** ≥ 3 輪迭代後仍有 > 50% 測試對象無法完成 → 圖形語言規範根本性重設計。

**範圍邊界：**
- **包含：** L1–L2 圖形語言定義、Diff 視覺符號、範圍邊界協定、疑義路徑概念設計
- **不包含：** 信心標示（已在 Phase 0b 完成）、程式碼實作、Mermaid 渲染引擎
- **Prototype 工具：** MD 純文字模擬圖 + Claude artifact 互動版本，零工程成本

## Glossary

- **Graphical_Language_Spec**: The Door 的圖形語言規範，定義節點形狀、邊的含義、層級切換規則、Diff 符號、範圍邊界標記、疑義路徑等視覺語言元素
- **L1_View**: 功能總覽層——純功能語言，零技術詞彙，回答「這個系統能做什麼」
- **L1_5_View**: 結構概覽層——過渡語言，模組名稱附帶功能說明，回答「各區塊負責哪一段、彼此如何關聯」
- **L2_View**: 功能連動圖層——技術語言，模組層次互動關係，含異常標示，回答「有沒有異常」
- **Paper_Prototype**: 以 MD 純文字模擬圖或 Claude artifact 互動版本呈現的低成本原型，用於非工程師測試
- **Diff_View**: 顯示兩個版本之間差異的視圖，標記新增、移除、屬性變更、依賴關係變更
- **Scope_Boundary**: 範圍邊界標記，標示功能是否在預定義的 sprint/release 範圍內
- **Doubt_Path**: 疑義路徑——使用者在圖形上發現疑義後的處理流程，從識別到追蹤到解決的完整路徑
- **Anomaly_Marker**: L2 層的異常標示，包含死碼（◎）、邏輯死路（⚠）、不確定邊界（⊙）、已知漏洞（⚑）
- **Node_Shape**: 圖形中節點的形狀，用於區分不同類型的功能或結構元素
- **Edge_Semantics**: 圖形中邊（連線）的含義，用於表達節點之間的關係類型
- **Layer_Switching**: 層級切換機制——L1 ↔ L1.5 為平行視角切換（tab），L2 為點擊展開
- **Test_Subject**: 測試對象——3–5 位外部非工程師（PM 和非技術管理者各至少一人）
- **Planted_Doubt**: 刻意埋入的疑義點——paper prototype 中故意設計的異常或超出範圍項目，用於測試使用者是否能識別

## Requirements

### Requirement 1: L1 功能總覽層圖形語言定義

**User Story:** As a PM or release manager, I want the L1 functional overview to use a clear visual language with distinct node shapes and edge meanings, so that I can understand what the system does without any technical knowledge.

#### Acceptance Criteria

1. THE Graphical_Language_Spec SHALL define node shapes for L1_View that encode both functional category AND trigger type, distinguishing at least: user-facing features (user action trigger), automated/scheduled features (scheduled trigger), and event-triggered features (auto-triggered by another feature completing)
2. THE Graphical_Language_Spec SHALL define edge semantics for L1_View that express causal relationships between features using human-readable labels (e.g., "completes then triggers", "depends on result of")
3. THE Graphical_Language_Spec SHALL prohibit any technical vocabulary in L1_View node labels and edge labels, consistent with Spec §3 language rules
4. THE Graphical_Language_Spec SHALL define a visual grouping mechanism for L1_View that clusters related features without implying hierarchical structure

### Requirement 2: L1.5 結構概覽層圖形語言定義

**User Story:** As a PM or release manager, I want the L1.5 structural overview to show which parts compose the system and how they connect, so that I can build a mental model of the system architecture without entering technical details.

#### Acceptance Criteria

1. THE Graphical_Language_Spec SHALL define node shapes for L1_5_View that distinguish structural blocks from the infrastructure block
2. THE Graphical_Language_Spec SHALL define edge semantics for L1_5_View that express inter-block relationships: direct invocation, event notification, and data flow
3. THE Graphical_Language_Spec SHALL require each L1_5_View node label to include both the module name and a functional description in transitional language
4. THE Graphical_Language_Spec SHALL define a visual representation for trigger mechanisms on L1_5_View nodes using human-readable labels (e.g., "triggered by user request", "runs on schedule", "notified by another feature")
5. THE Graphical_Language_Spec SHALL define the infrastructure block as a visually distinct collapsed element that can be expanded to show its components

### Requirement 3: L2 功能連動圖層圖形語言定義

**User Story:** As a verification-oriented user, I want the L2 module interaction view to show detailed connections and anomaly markers, so that I can identify potential issues and areas requiring further investigation.

#### Acceptance Criteria

1. THE Graphical_Language_Spec SHALL define node shapes for L2_View that distinguish modules, sub-modules, and external dependencies
2. THE Graphical_Language_Spec SHALL define edge semantics for L2_View that express: static call relationships, inferred relationships (with visual distinction), and data dependencies
3. THE Graphical_Language_Spec SHALL define Anomaly_Marker visual encoding for L2_View consistent with Spec §3.2:
   - Dead code: blue-gray fill, ◎ symbol
   - Logic dead-end: yellow fill, ⚠ symbol
   - Uncertain boundary: light gray fill, ⊙ symbol
   - Known vulnerability: red (high) or orange (medium) fill, ⚑ symbol
4. THE Graphical_Language_Spec SHALL define severity priority ordering for Anomaly_Markers: known vulnerability > logic dead-end > dead code > uncertain boundary
5. WHEN a node has multiple anomaly types, THE Graphical_Language_Spec SHALL display the highest-priority anomaly symbol on the node and list remaining anomalies in the side description panel

### Requirement 4: 層級切換視覺規範

**User Story:** As a non-technical user, I want clear visual cues for switching between L1, L1.5, and L2 views, so that I understand I am changing perspective rather than drilling into details.

#### Acceptance Criteria

1. THE Graphical_Language_Spec SHALL define L1 ↔ L1.5 switching as parallel tab-based navigation, visually communicating that these are equal-status perspectives (not parent-child hierarchy)
2. THE Graphical_Language_Spec SHALL define L2 expansion as a click-to-expand interaction on L1.5 block nodes, visually communicating a drill-down into detail
3. THE Graphical_Language_Spec SHALL define visual affordances (icons or indicators) on L1.5 nodes that signal "expandable to L2"
4. THE Graphical_Language_Spec SHALL define a current-level indicator concept so users always know which view (L1 / L1.5 / L2) they are on
5. THE Paper_Prototype SHALL demonstrate the layer switching interaction in at least one scenario showing a user navigating from L1 to L1.5 to L2

### Requirement 5: Diff 視覺符號定義

**User Story:** As a PM or release manager, I want to see what changed between two versions using clear visual symbols, so that I can answer "what changed this time" without reading code or asking engineers.

#### Acceptance Criteria

1. THE Graphical_Language_Spec SHALL define Diff_View node-level symbols consistent with Spec §4.2:
   - Node added: green fill with + indicator
   - Node removed: red fill with − indicator
   - Node attribute changed: light orange fill with ~ indicator
   - Dependency relation changed: dark orange fill with ≠ indicator (visually distinct from attribute change via both color shade and symbol)
2. THE Graphical_Language_Spec SHALL define that dependency relation changes take visual priority over attribute changes when both occur on the same node
3. THE Graphical_Language_Spec SHALL define Diff_View edge-level symbols: new edge (green dashed), removed edge (red dashed with strikethrough), and modified edge (orange)
4. THE Graphical_Language_Spec SHALL define a Diff summary panel that lists all changes in natural language (e.g., "2 features added, 1 removed, 3 modified")
5. THE Graphical_Language_Spec SHALL define visual encoding for the three "previous version" trigger methods: git tag/commit SHA, date picker, and manual version snapshot — each showing the comparison reference clearly in the Diff_View header
6. THE Paper_Prototype SHALL include at least one Diff scenario where a Test_Subject can identify all changes within the 10-minute time limit
7. THE Graphical_Language_Spec SHALL define that unchanged nodes in Diff_View are visually de-emphasized (e.g., reduced opacity or muted colors) so that changed nodes stand out

### Requirement 6: 範圍邊界協定

**User Story:** As a PM, I want to define a sprint scope and see which features are in scope, out of scope, or incomplete, so that I can verify development output against commitments.

#### Acceptance Criteria

1. THE Graphical_Language_Spec SHALL define Scope_Boundary visual markers consistent with Spec §4.3:
   - In scope and complete: ✓ green checkmark
   - Out of scope (unexpected): ⚠ orange warning
   - In scope but incomplete: ○ hollow circle
2. THE Graphical_Language_Spec SHALL define that Scope_Boundary markers overlay on existing nodes without replacing other visual indicators (confidence markers, anomaly markers)
3. THE Graphical_Language_Spec SHALL define a scope summary panel showing counts: N in scope complete, M out of scope, K in scope incomplete
4. WHEN a node is marked out of scope (⚠), THE Graphical_Language_Spec SHALL define a visual affordance indicating "click to investigate" that leads to the Doubt_Path

### Requirement 7: 疑義路徑概念設計

**User Story:** As a PM or release manager, I want a clear process for what to do after finding a doubt on the diagram, so that doubts lead to resolution rather than confusion.

#### Acceptance Criteria

1. THE Graphical_Language_Spec SHALL define the Doubt_Path concept as a three-stage process: Identify (識別) → Track (追蹤) → Resolve (解決)
2. THE Graphical_Language_Spec SHALL define the Identify stage: user sees an anomaly marker (⚠, ⊙, ◎, ⚑) or scope boundary warning (⚠, ○) on the diagram and clicks it
3. THE Graphical_Language_Spec SHALL define the Track stage: the system records the doubt with metadata (who found it, when, which node, what type) and assigns it a tracking status that progresses from discovery toward resolution or escalation
4. THE Graphical_Language_Spec SHALL define the Resolve stage: the doubt is either explained (false alarm), fixed (code change), or escalated (requires management decision)
5. THE Graphical_Language_Spec SHALL define a doubt state machine concept showing the general flow from discovery to resolution, without prescribing specific state names (full state machine defined in Phase 3)
6. THE Graphical_Language_Spec SHALL include a timeout escalation concept: doubts left unresolved beyond a configurable period are automatically elevated (detailed rules in Phase 3)
7. THE Paper_Prototype SHALL include a scenario showing "user finds ⚠ on diagram → clicks it → sees doubt details → takes next step" as required by Spec §8

### Requirement 8: Paper Prototype 驗收場景設計

**User Story:** As a product owner, I want the paper prototype to contain a realistic scenario with planted doubts, so that testing with non-engineers produces meaningful validation data.

#### Acceptance Criteria

1. THE Paper_Prototype SHALL contain at least one complete scenario that includes: L1 functional overview, L1.5 structural overview, L2 detail view, Diff view showing changes, and at least one Planted_Doubt
2. THE Paper_Prototype SHALL include at least one Planted_Doubt that is an out-of-scope change (⚠ scope boundary marker)
3. THE Paper_Prototype SHALL include at least one Planted_Doubt that is an anomaly marker (logic dead-end ⚠ or uncertain boundary ⊙)
4. THE Paper_Prototype SHALL include a "next step after finding doubt" interaction flow that the Test_Subject can follow
5. THE Paper_Prototype SHALL be implementable in MD plain text simulation format and optionally as a Claude artifact interactive version, with zero engineering cost
6. THE Paper_Prototype SHALL be testable with 3–5 external non-engineer Test_Subjects (at least one PM and one non-technical manager)

### Requirement 9: 視覺語言一致性與可區分性

**User Story:** As a non-technical user, I want all visual elements to be consistent and distinguishable without relying on color alone, so that the diagram is accessible and unambiguous.

#### Acceptance Criteria

1. THE Graphical_Language_Spec SHALL ensure that no two distinct semantic meanings share the same visual encoding (shape + color + symbol combination)
2. THE Graphical_Language_Spec SHALL ensure that all visual distinctions are perceivable through at least two independent channels (e.g., shape + symbol, color + border style) for accessibility
3. THE Graphical_Language_Spec SHALL define a complete visual vocabulary table mapping every semantic concept to its visual encoding across all layers (L1, L1.5, L2, Diff, Scope)
4. THE Graphical_Language_Spec SHALL ensure visual compatibility with the confidence marker encoding defined in Phase 0b (high/medium/low/reviewed/regenerated/incomplete states)
5. THE Graphical_Language_Spec SHALL define how confidence markers (Phase 0b) and anomaly markers (Phase 0a) coexist on the same node without visual conflict
6. THE Graphical_Language_Spec SHALL define visual layering rules for combined views: scope boundary markers appear as badge overlays, diff colors apply to node fill/border, confidence markers apply to border style
7. WHEN a node carries multiple indicator types simultaneously (e.g., diff "added" + scope "out of scope"), THE Graphical_Language_Spec SHALL define which indicator takes visual prominence
8. THE Graphical_Language_Spec SHALL define a combined summary panel format for Diff + Scope views showing: "N changes in scope, M changes out of scope, K expected changes missing"

### Requirement 10: MD 純文字模擬圖格式規範

**User Story:** As a prototype designer, I want a standardized MD plain text format for simulating diagrams, so that paper prototypes can be created quickly and consistently without any engineering tools.

#### Acceptance Criteria

1. THE Graphical_Language_Spec SHALL define an MD plain text simulation format that can represent: nodes with labels, edges with labels, node visual states (diff colors, scope markers, anomaly markers, confidence markers), and layer structure
2. THE Graphical_Language_Spec SHALL define MD text conventions for representing visual states using ASCII/Unicode characters (e.g., `[✓]` for in-scope, `[⚠]` for out-of-scope, `[+]` for added node, `[−]` for removed node)
3. THE MD plain text format SHALL be readable by a non-technical person without explanation of the format itself
4. THE MD plain text format SHALL be designed with Mermaid conversion in mind, ensuring all semantic concepts have corresponding Mermaid representations in Phase 1-full
5. THE Graphical_Language_Spec SHALL provide at least one complete example of an MD plain text simulation covering L1, L1.5, and Diff views


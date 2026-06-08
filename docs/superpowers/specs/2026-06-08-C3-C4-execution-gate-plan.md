# C3+C4 plan：執行序 gate（inline TDD 任務分解）

> **承接 spec**：`2026-06-08-C3-C4-execution-gate-spec.md`（已雙審通過、critical 修畢）。
> **執行模式**：inline TDD，3 task；全綠後一次 ff-merge（commit 已獲連跑授權、不 push）。
> **環境**：pytest cwd＝內層 `the_door/`、`PYTHONUTF8=1`。測試以 subprocess 黑箱跑 hook 腳本。
> **性質**：純加法（新 hook 腳本＋settings.json 2 條＋測試）；不動 the_door production code。

---

## 測試策略（雙審已定）
- hook 腳本＝黑箱：subprocess 餵 stdin JSON、斷言 exit code＋stderr 內容。
- 測試檔＝`the_door/tests/unit/hooks/test_execution_gates.py`（隨既有 pytest 跑、納零回歸護欄）。
- 腳本定位：`HOOKS_DIR = Path(__file__).resolve().parents[4] / ".claude" / "hooks"`（file→hooks/unit/tests/the_door/repo-root）。
- G-10 跑真實 settings command 字串（`bash -c`）；無 bash → `pytest.skip`。

---

## Task 1 — hook 腳本 ＋ 腳本黑箱測（G-1..G-8）

**Red（先寫測，腳本未存在→subprocess 報錯/非 0）**
新增 `the_door/tests/unit/hooks/__init__.py`（空；**確定要加**——`tests/unit` 21 個子目錄皆有 `__init__.py`，比照慣例）＋ `test_execution_gates.py`：
> 註：expect-exit-0 的測（G-2/3/4/7/8）在腳本缺時 rc==2 → 自然紅；expect-exit-2 的測（G-1/5/6）靠**stderr 內容斷言**（`edge_residue`/C4 訊息）才是誠實紅（腳本缺時 stderr＝「can't open file」不含教學字串）。
- helper `run_hook(script_name, payload_dict, *, text=None) -> (returncode, stderr)`：`subprocess.run([sys.executable, str(HOOKS_DIR/script_name)], input=json.dumps(payload) if text is None else text, capture_output=True, text=True)`。
- C3（`c3_gate_snapshot_write.py`）：
  - G-1 artifact 缺（tmp codebase 無 `.the-door/edge-residue.json`）→ rc==2、stderr 含 `edge_residue`。
  - G-2 artifact 在（建檔）→ rc==0。
  - G-3 無 `codebase_path` → rc==0。
  - G-4 stdin 非 JSON（`text="not json"`）→ rc==0。
- C4（`c4_block_native_exec.py`）：
  - G-5 `python -c "import the_door"` → rc==2、stderr 含 C4 訊息。
  - G-6 參數化 `python foo.py` / `python ./a/b.py` → rc==2。
  - G-7 參數化 allow：`PYTHONUTF8=1 python -m pytest -q` / `pytest tests/` / `pip install -e ./the_door` / `git commit -m x` / `npx vitest run` / `the-door ui .` → rc==0。
  - G-8 stdin 非 JSON、`{}`（無 command）→ rc==0。

**Green（impl）**：依 spec §3.1 建兩腳本（jq-free、python、fail-open）。
- `c3_gate_snapshot_write.py`：load stdin→`tool_input.codebase_path`；空/解析失敗→exit 0；`os.path.isfile(join(p,".the-door","edge-residue.json"))`→exit 0；否則 stderr 教學（指回 `edge_residue`、含路徑）→exit 2。
- `c4_block_native_exec.py`：load→`tool_input.command`；`re.search(r"\bpython[0-9.]*\s+(-c\b|[^-\s][^\s]*\.py\b)", cmd)`→stderr 教學→exit 2；否則 exit 0。

**Verify**：`PYTHONUTF8=1 python -m pytest tests/unit/hooks/test_execution_gates.py -q`。

---

## Task 2 — settings.json 註冊 ＋ 完整性/指令字串測（G-9, G-10）

**Red（先寫測）**
- G-9：讀 `repo-root/.claude/settings.json`，JSON load；PreToolUse matcher 集合含 `mcp__the-door__snapshot_write` 與 `Bash`（C4）；從 C3/C4 的 command 字串抽出 `.claude/hooks/*.py` 路徑、斷言檔存在。
  - 注意：`Bash` matcher 會有兩條（既有 serve-block＋新 C4）；斷言「存在一條 Bash hook 的 command 引用 `c4_block_native_exec.py`」。
- G-10（`bash -c` 跑真實 command 字串）：
  - 設 `env["CLAUDE_PROJECT_DIR"]=repo_root.as_posix()`（**正斜線**——避免 Windows 反斜線在 bash `[ -f ]`/Windows-python `open` 兩端解析不一致；雙審 warning），`bash -c "<C4 command 字串>"`，stdin 餵 `{"tool_input":{"command":"python -c \"x\""}}`→rc==2；餵 `git status`→rc==0。
  - **腳本缺**案：`env["CLAUDE_PROJECT_DIR"]="/no/such/dir"`→rc==0（fail-open，不 brick）。
  - 無 `bash`（`shutil.which("bash") is None`）→ `pytest.skip("bash unavailable")`。本機已確認 `/usr/bin/bash` 存在 ⟹ 不 skip。

**Green**：編輯 `.claude/settings.json`，在 PreToolUse 陣列加 spec §3.2 兩條（守衛式 command）。**保留**既有 3 條（prototype/serve/UserPromptSubmit 不動）。

**Verify**：`PYTHONUTF8=1 python -m pytest tests/unit/hooks/ -q`。

---

## Task 3 — 全套零回歸 ＋ ff-merge

- 全套：`PYTHONUTF8=1 python -m pytest -q`（預期 baseline+新測、0 failed）。
- 不跑 viewer（本刀不碰前端）。
- **自我保護**：本刀更新 settings.json 後，本 session 剩餘指令只有 `git`（C4 allow）＋ `python -m pytest`（C4 allow）；不使用 `python -c`/臨時腳本（會被自己的 C4 擋）。

**done-state（全綠才 ff-merge）**
- [ ] `.claude/hooks/c3_gate_snapshot_write.py`、`c4_block_native_exec.py` 存在、行為符 spec §3.1。
- [ ] `.claude/settings.json` 加 C3/C4 兩守衛式 PreToolUse、既有 3 條不動、JSON 合法。
- [ ] G-1..G-10 全綠（含 fail-open、指令字串、settings 完整性）。
- [ ] `pytest -q` 全套 0 failed。
- [ ] the_door production code git diff＝空（只新增 hooks/tests/settings/spec/plan）。

## 不做（釘樁，承 spec §4）
- 不改既有 jq hooks（F1 另刀）、不 gate `Write`/`snapshot_create`/`snapshot_patch`、不做 C2/C5/PostToolUse、不碰 provider/viewer。

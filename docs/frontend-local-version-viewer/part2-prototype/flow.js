// flow.js — 精靈→Viewer 進場流程原型(純 vanilla JS / ES module)
// 與本地 viewer 同技術棧:手寫狀態機 + renderPage() 直接操作 DOM,無框架、無 Babel。

// ─── 常數 ──────────────────────────────────────────────────────────────────
const PROJECT_PATH = "~/code/the-door";
const FILE_COUNT = 247;
const STAGES = ["選擇操作", "設定範圍", "快照標籤", "確認送出", "分析中", "進入 Viewer"];
const PHASES = ["探索檔案", "LLM 分析", "寫入快照"];
const WALK = [
  { id: "action", label: "1 · 入口", stage: 0 },
  { id: "setup", label: "2 · 設定範圍", stage: 1 },
  { id: "label", label: "3 · 標籤", stage: 2 },
  { id: "confirm", label: "4 · 確認", stage: 3 },
  { id: "progress", label: "5 · 進度", stage: 4 },
  { id: "agent", label: "6 · Agent", stage: 4 },
  { id: "transient", label: "7 · 過場", stage: 4 },
  { id: "error", label: "8 · 錯誤", stage: 4 },
  { id: "landing", label: "9 · 落地", stage: 5 },
];

// ─── 狀態 ──────────────────────────────────────────────────────────────────
const TWEAK_KEYS = ["accent", "doorAnim", "entryMode", "returning", "progressSpeed"];
const TWEAK_DEFAULTS = { accent: "#0f766e", doorAnim: true, entryMode: "api", returning: false, progressSpeed: 1 };

function loadTweaks() {
  try {
    const s = JSON.parse(localStorage.getItem("door-flow-tweaks") || "{}");
    return { ...TWEAK_DEFAULTS, ...s };
  } catch { return { ...TWEAK_DEFAULTS }; }
}

const state = {
  screen: "action",
  crossing: false,
  steps: initialSteps(),
  activeIdx: 0,
  excludes: "tests/, docs/",
  label: "v1.4.5",
  progCount: 0,
  progFeed: [],
  tweaks: loadTweaks(),
};
let timers = [];
let ticker = null;

// 進度畫面即時動態:正在分析的檔案(取自 the-door 真實路徑風格)
const FILES = [
  "src/the_door/core/extraction/node_builder.py",
  "src/the_door/core/extraction/language_configs.py",
  "src/the_door/core/extraction/ast_extractor.py",
  "src/the_door/core/edges/edge_builder.py",
  "src/the_door/core/edges/scope_rules.py",
  "src/the_door/core/ui/api_handlers.py",
  "src/the_door/core/ui/ui_server.py",
  "src/the_door/core/analysis/batch_reader.py",
  "src/the_door/core/analysis/scope_verifier.py",
  "src/the_door/core/store/doubt_store.py",
  "src/the_door/core/store/snapshot_store.py",
  "src/the_door/core/store/project_identity.py",
  "src/the_door/mcp/tools.py",
  "src/the_door/mcp/checkpoint.py",
  "src/the_door/cli/analyze_cmd.py",
  "src/the_door/cli/status_cmd.py",
  "viewer/js/ui-wizard.js",
  "viewer/js/ui-detail.js",
  "viewer/js/ui-list.js",
  "viewer/js/graph.js",
  "viewer/js/layers.js",
  "viewer/js/viewmodel.js",
];
const MODE_NOTE = {
  api: { cls: "api", txt: "偵測到 API key — 分析會在本機自動執行,完成後直接進入 Viewer。" },
  agent: { cls: "agent", txt: "未偵測到 API key — 將以 Agent 模式產生 MCP 指令,交由你的 coding agent 執行。" },
};

function initialSteps() {
  return [
    { step_name: "探索檔案", status: "pending", duration_ms: null },
    { step_name: "LLM 分析功能", status: "pending", duration_ms: null },
    { step_name: "寫入快照", status: "pending", duration_ms: null },
  ];
}
function clearTimers() { timers.forEach(clearTimeout); timers = []; if (ticker) { clearInterval(ticker); ticker = null; } }
const hasApiKey = () => state.tweaks.entryMode === "api";

// ─── SVG / icons ─────────────────────────────────────────────────────────────
const doorLeaf = (cls) => `
  <svg class="${cls}" viewBox="0 0 100 100" fill="none" aria-label="The Door">
    <rect x="22" y="10" width="56" height="76" fill="#d9f3ef"></rect>
    <path d="M22 10 L22 86 M78 10 L78 86 M22 10 L78 10" stroke="#0f766e" stroke-width="6" stroke-linejoin="miter"></path>
    <line x1="10" y1="90" x2="90" y2="90" stroke="#0f766e" stroke-width="6" stroke-linecap="square"></line>
    <circle cx="70" cy="50" r="2.5" fill="#0f766e"></circle>
  </svg>`;
const I = {
  scan: `<svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M3 7V5a2 2 0 0 1 2-2h2M17 3h2a2 2 0 0 1 2 2v2M21 17v2a2 2 0 0 1-2 2h-2M7 21H5a2 2 0 0 1-2-2v-2"></path><line x1="3" y1="12" x2="21" y2="12"></line></svg>`,
  refresh: `<svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M21 2v6h-6M3 12a9 9 0 0 1 15-6.7L21 8M3 22v-6h6M21 12a9 9 0 0 1-15 6.7L3 16"></path></svg>`,
  eye: `<svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M2 12s3.5-7 10-7 10 7 10 7-3.5 7-10 7-10-7-10-7Z"></path><circle cx="12" cy="12" r="3"></circle></svg>`,
  arrow: `<svg class="arrow" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M5 12h14M13 6l6 6-6 6"></path></svg>`,
  clock: `<svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="var(--muted)" stroke-width="2" stroke-linecap="round"><circle cx="12" cy="12" r="9"></circle><path d="M12 7v5l3 2"></path></svg>`,
  info: `<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><circle cx="12" cy="12" r="9"></circle><path d="M12 8h.01M11 12h1v4h1"></path></svg>`,
  warn: `<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><path d="M12 9v4M12 17h.01M10.3 3.9 1.8 18a2 2 0 0 0 1.7 3h17a2 2 0 0 0 1.7-3L13.7 3.9a2 2 0 0 0-3.4 0Z"></path></svg>`,
  lock: `<svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="#667085" stroke-width="2"><rect x="3" y="11" width="18" height="11" rx="2"></rect><path d="M7 11V7a5 5 0 0 1 10 0v4"></path></svg>`,
  lines: `<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><path d="M3 12h18M3 6h18M3 18h18"></path></svg>`,
};

// ─── 左欄:門外暗面 + 開門 + 步驟 ───────────────────────────────────────────
function railHTML(stage, lit, doorAnim) {
  const frac = Math.min(stage, 5) / 5;
  const angle = -(78 * frac);
  const fillH = `calc(${frac * 100}% - 0px)`;
  const steps = STAGES.map((s, i) => {
    const st = i < stage ? "done" : i === stage ? "active" : "";
    return `<div class="step ${st}"><span class="dot">${i < stage ? "✓" : i + 1}</span><span class="lbl">${s}</span></div>`;
  }).join("");
  return `
    <div class="rail">
      <div class="rail-brand">${doorLeaf("leaf")}<div><div class="wd">The Door</div><div class="sub">門 · 啟動精靈</div></div></div>
      <div class="door-wrap">
        <svg class="door-frame" viewBox="0 0 148 188" fill="none">
          <path d="M12 8 L12 182 M136 8 L136 182 M12 8 L136 8" stroke="rgba(217,243,239,.6)" stroke-width="3" stroke-linejoin="miter"></path>
          <line x1="4" y1="184" x2="144" y2="184" stroke="rgba(217,243,239,.6)" stroke-width="3.5" stroke-linecap="square"></line>
        </svg>
        <div class="door-light${lit ? " lit" : ""}"></div>
        <div class="door-leaf" style="transform:rotateY(${doorAnim ? angle : 0}deg)"><span class="grain"></span><span class="knob"></span></div>
        <div class="door-pct">${lit ? "已開啟" : "開啟 " + Math.round(frac * 100) + "%"}</div>
      </div>
      <div class="stepper">
        <div class="stepper-line"></div>
        <div class="stepper-fill" style="height:${fillH}"></div>
        ${steps}
      </div>
      <div class="rail-foot">CODE → FUNCTIONAL LANGUAGE</div>
    </div>`;
}

// ─── 各畫面 HTML ─────────────────────────────────────────────────────────────
function screenHTML(s) {
  const tw = state.tweaks;
  switch (s) {
    case "action": {
      const opts = tw.returning ? `
        <button class="opt" data-act="update"><span class="ico">${I.refresh}</span><span class="tx"><strong>更新分析</strong><span>重新掃描原始碼,產生新版本快照並比對差異。</span></span>${I.arrow}</button>
        <button class="opt" data-act="view"><span class="ico">${I.eye}</span><span class="tx"><strong>查看現有快照</strong><span>直接進入 Viewer,不重新分析。</span></span>${I.arrow}</button>`
      : `
        <button class="opt" data-act="analyze"><span class="ico">${I.scan}</span><span class="tx"><strong>首次分析此專案</strong><span>掃描原始碼,建立第一個功能快照。</span></span>${I.arrow}</button>
        <button class="opt" disabled><span class="ico">${I.eye}</span><span class="tx"><strong>查看快照</strong><span>尚無資料,請先執行分析。</span></span></button>`;
      return `<div class="screen screen-enter">
        <p class="eyebrow">步驟 1 / 開始</p>
        <h2>${tw.returning ? "歡迎回來,要做什麼?" : "歡迎使用 The Door"}</h2>
        <p class="lede">把程式碼翻譯成非技術者也能讀懂的功能語言。先選擇這次要進行的操作。</p>
        <div class="mode-note ${MODE_NOTE[hasApiKey() ? "api" : "agent"].cls}">
          <span class="mn-badge">${hasApiKey() ? "● API key 模式" : "◐ Agent 模式"}</span>
          <span>${MODE_NOTE[hasApiKey() ? "api" : "agent"].txt}</span>
        </div>
        <div class="opts">${opts}</div>
        <div class="switch-zone">
          <p class="sz-label">${I.lines} 目前分析目標:<code style="font-family:var(--font-mono);color:var(--text-body)">${PROJECT_PATH}</code> · 偵測到 ${FILE_COUNT} 個源碼檔</p>
          <div class="switch-row"><input type="text" placeholder="/absolute/path/to/another/project"><button class="btn btn-ghost">切換專案</button></div>
        </div>
      </div>`;
    }
    case "setup":
      return `<div class="screen screen-enter">
        <p class="eyebrow">步驟 2 / 設定</p><h2>要分析哪些範圍?</h2>
        <p class="lede">偵測到 <strong>${FILE_COUNT}</strong> 個源碼檔案。可排除測試、文件等不需納入功能分析的目錄。</p>
        <div class="fields"><div class="field"><label>排除目錄（逗號分隔,選填）</label>
          <input type="text" placeholder="tests/, docs/, vendor/" value="${state.excludes}">
          <p class="hint">留空則分析全部。排除的目錄不會送入 LLM,可降低 token 用量。</p></div></div>
        <div class="actions"><button class="btn btn-ghost" data-go="action">← 上一步</button><span class="spacer"></span><button class="btn btn-primary" data-go="label">下一步 ${I.arrow}</button></div>
      </div>`;
    case "label":
      return `<div class="screen screen-enter">
        <p class="eyebrow">步驟 3 / 設定</p><h2>替這個版本貼個標籤</h2>
        <p class="lede">標籤用來在 Viewer 的版本選擇器中辨識這份快照。選填,留空會自動帶入 v1.0.0。</p>
        <div class="fields"><div class="field"><label>版本標籤（選填）</label>
          <input type="text" placeholder="v1.0.0" value="${state.label}"><p class="hint">例:語意化版本、Git tag、或日期。</p></div></div>
        <div class="actions"><button class="btn btn-ghost" data-go="setup">← 上一步</button><span class="spacer"></span><button class="btn btn-primary" data-go="confirm">下一步 ${I.arrow}</button></div>
      </div>`;
    case "confirm": {
      const api = hasApiKey();
      return `<div class="screen screen-enter">
        <p class="eyebrow">步驟 4 / 確認</p><h2>確認後即開始</h2>
        <p class="lede">送出後會依下列設定執行。分析可能需要數分鐘,取決於專案大小。</p>
        <div class="summary">
          <div class="row"><span class="k">操作</span><span class="v mode">${tw.returning ? "更新分析" : "首次分析"}</span></div>
          <div class="row"><span class="k">排除目錄</span><span class="v">${state.excludes || "（無）"}</span></div>
          <div class="row"><span class="k">版本標籤</span><span class="v">${state.label || "v1.0.0"}</span></div>
          <div class="row"><span class="k">執行模式</span><span class="v"><span class="badge-mode ${api ? "api" : "agent"}">${api ? "● API key 模式" : "◐ Agent 模式"}</span></span></div>
        </div>
        <div class="actions"><button class="btn btn-ghost" data-go="${tw.returning ? "action" : "label"}">← 上一步</button><span class="spacer"></span><button class="btn btn-primary" data-submit>確認送出 ${I.arrow}</button></div>
      </div>`;
    }
    case "progress": {
      const phases = PHASES.map((p, i) => {
        const st = i < state.activeIdx ? "done" : i === state.activeIdx ? "active" : "";
        return `<div class="phase ${st}"><div class="track"><div class="fill"></div></div><div class="pl">${i < state.activeIdx ? "✓ " : ""}${p}</div></div>`;
      }).join("");
      const rows = state.steps.map((s) => {
        const ic = s.status === "done" ? "✓" : s.status === "running" ? '<span class="spin"></span>' : "○";
        const dur = s.duration_ms != null ? (s.duration_ms / 1000).toFixed(1) + "s" : s.status === "running" ? "進行中…" : "";
        return `<div class="sl-row ${s.status}"><span class="si">${ic}</span><span class="sn">${s.step_name}</span><span class="dur">${dur}</span></div>`;
      }).join("");
      return `<div class="screen screen-enter">
        <p class="eyebrow">步驟 5 / 分析中</p>
        <div class="prog-head"><h2>正在穿過門……</h2><p class="lede">The Door 正在解析原始碼結構並產生功能描述。完成後會自動進入 Viewer。</p></div>
        <div class="phasebar">${phases}</div>
        <div class="prog-live">
          <div class="pl-head"><span class="pl-dot"></span>正在分析 <span id="pl-count">${state.progCount || 0}</span> / ${FILE_COUNT} 個檔案</div>
          <div class="pl-feed" id="pl-feed">${state.progFeed.map((f) => `<div class="pl-line">${f}</div>`).join("")}</div>
        </div>
        <div class="steplist">${rows}</div>
        <p class="prog-note">${I.clock} LLM 分析是最耗時的階段。你可以離開這個畫面,任務會在背景繼續。</p>
      </div>`;
    }
    case "agent": {
      const cmd1 = `extract_structure(codebase_path=&quot;${PROJECT_PATH}&quot;)`;
      return `<div class="screen screen-enter">
        <p class="eyebrow">步驟 5 / Agent 模式</p><h2>交給你的 Agent 執行</h2>
        <div class="agent-why">${I.info}<div>未偵測到 API key。改由你的 coding agent(如 Claude)透過 MCP 工具執行分析 —— 把下面兩段指令貼給它即可。</div></div>
        <div class="agent-steps">
          <div class="astep"><span class="n">1</span><div class="ac">
            <p class="at">複製並貼給 Agent</p><p class="ad">先抽取結構,再寫入快照。</p>
            <div class="cmd"><div class="cmd-bar"><span class="lab">MCP · 抽取結構</span><button class="cmd-copy" data-copy="extract_structure(codebase_path=&quot;${PROJECT_PATH}&quot;)">⧉ 複製</button></div>
              <pre><span class="tok">extract_structure</span>(<span class="dim">codebase_path</span>=<span class="str">"${PROJECT_PATH}"</span>)</pre></div>
            <div class="cmd"><div class="cmd-bar"><span class="lab">MCP · 寫入快照</span><button class="cmd-copy" data-copy='snapshot_write(codebase_path="${PROJECT_PATH}", l1_features=[...], label="${state.label || "v1.0.0"}")'>⧉ 複製</button></div>
              <pre><span class="tok">snapshot_write</span>(<span class="dim">codebase_path</span>=<span class="str">"${PROJECT_PATH}"</span>,\n               <span class="dim">l1_features</span>=[...],\n               <span class="dim">label</span>=<span class="str">"${state.label || "v1.0.0"}"</span>)</pre></div>
          </div></div>
          <div class="astep"><span class="n">2</span><div class="ac"><p class="at">Agent 執行完畢後,回到這裡</p><p class="ad">快照寫入後即可進入 Viewer 查看結果。</p></div></div>
        </div>
        <div class="actions"><span class="spacer"></span><button class="btn btn-primary" data-cross>我已執行完畢,進入 Viewer ${I.arrow}</button></div>
      </div>`;
    }
    case "transient":
      return `<div class="screen"><div class="transient"><div class="bigspin"></div><div class="tl">送出中,正在啟動分析任務…</div></div></div>`;
    case "error":
      return `<div class="screen screen-enter">
        <p class="eyebrow">發生問題</p><h2>分析未能完成</h2>
        <div class="err-box"><span class="ei">${I.warn}</span><div><p class="et">分析失敗</p><p class="ed">LLM 供應商連線逾時(timeout)。任務可能仍在背景進行,可直接前往 Viewer 確認。</p></div></div>
        <div class="actions"><button class="btn btn-ghost" data-go="confirm">重試</button><span class="spacer"></span><button class="btn btn-primary" data-cross>前往 Viewer</button></div>
      </div>`;
    default:
      return "";
  }
}

function viewerHTML() {
  return `<div class="viewer">
    <div class="v-top">${doorLeaf("vmark")}<div class="vt"><div class="eb">The Door — Local Version Viewer</div><div class="h">本地版本 Viewer</div></div>
      <div class="vchips"><span class="v-chip">尚無快照</span><span class="v-chip">心智圖</span><span class="v-chip">重新分析</span></div></div>
    <div class="v-body"><div class="onboard">
      <div class="ob-h">${doorLeaf("leaf")}<h2>歡迎使用 The Door</h2></div>
      <p class="ob-sub">這個專案還沒有快照。完成第一次分析後,功能總覽、關聯圖與版本差異就會出現在這裡。先從下面三步開始:</p>
      <ol>
        <li><strong>建立第一個快照</strong><code class="ob-cmd">the-door analyze ./src --label v1.0.0</code></li>
        <li><strong>查看功能心智圖</strong><code class="ob-cmd">→ 開啟「心智圖」檢視結構</code></li>
        <li><strong>比對下一個版本</strong><code class="ob-cmd">the-door update ./src</code></li>
      </ol>
    </div></div>
  </div>`;
}

// ─── 渲染 ─────────────────────────────────────────────────────────────────────
function render() {
  const vp = document.getElementById("viewport");
  const meta = WALK.find((w) => w.id === state.screen) || WALK[0];
  const railStage = state.screen === "transient" ? 4 : meta.stage;
  const lit = state.screen === "landing";

  if (state.screen === "landing") {
    vp.innerHTML = viewerHTML();
  } else {
    vp.innerHTML = `<div class="wizard${state.crossing ? " leaving" : ""}">${railHTML(railStage, lit, state.tweaks.doorAnim)}<div class="content">${screenHTML(state.screen)}</div></div>`;
  }
  document.querySelector(".chrome .path").textContent = state.screen === "landing" ? "/" : "/wizard.html";
  document.getElementById("frame").style.setProperty("--accent", state.tweaks.accent);
  wireScreen(vp);
  updateWalk();
  fit();
}

function wireScreen(root) {
  root.querySelectorAll("[data-act]").forEach((b) => b.addEventListener("click", () => choose(b.dataset.act)));
  root.querySelectorAll("[data-go]").forEach((b) => b.addEventListener("click", () => go(b.dataset.go)));
  const sub = root.querySelector("[data-submit]"); if (sub) sub.addEventListener("click", submit);
  root.querySelectorAll("[data-cross]").forEach((b) => b.addEventListener("click", crossToViewer));
  root.querySelectorAll(".cmd-copy").forEach((b) => b.addEventListener("click", (e) => {
    navigator.clipboard && navigator.clipboard.writeText(b.dataset.copy || "");
    const o = b.innerHTML; b.innerHTML = "✓ 已複製"; setTimeout(() => (b.innerHTML = o), 1400);
  }));
}

// ─── 流程控制 ─────────────────────────────────────────────────────────────────
function go(id) { clearTimers(); state.crossing = false; state.screen = id; render(); if (id === "progress") runProgress(); }
function choose(act) {
  if (act === "view") return crossToViewer();
  if (act === "update") return go("confirm");
  go("setup");
}
function submit() {
  go("transient");
  timers.push(setTimeout(() => { state.screen = hasApiKey() ? "progress" : "agent"; render(); if (state.screen === "progress") runProgress(); }, 1100 / (state.tweaks.progressSpeed || 1)));
}
function crossToViewer() {
  clearTimers();
  if (state.tweaks.doorAnim) {
    state.crossing = true; render();
    timers.push(setTimeout(() => { state.crossing = false; state.screen = "landing"; render(); }, 600));
  } else { state.screen = "landing"; render(); }
}

function runProgress() {
  clearTimers();
  state.steps = initialSteps(); state.activeIdx = 0;
  const sp = state.tweaks.progressSpeed || 1;
  const set = (i, st, dur) => { state.steps = state.steps.map((s, j) => j === i ? { ...s, status: st, duration_ms: dur != null ? dur * 1000 : s.duration_ms } : s); };
  const seq = [
    [400, () => { set(0, "running"); }],
    [1200, () => { set(0, "done", 0.9); state.activeIdx = 1; set(1, "running"); }],
    [4200, () => { set(1, "done", 3.4); state.activeIdx = 2; set(2, "running"); }],
    [5200, () => { set(2, "done", 0.7); state.activeIdx = 3; stopTicker(247); }],
    [6000, () => { crossToViewer(); return; }],
  ];
  seq.forEach(([ms, fn]) => timers.push(setTimeout(() => { fn(); if (state.screen === "progress") render(); }, ms / sp)));
  startTicker(sp);
}

// 即時檔案 feed:在分析期間滾動目前正在解析的檔案 + 計數
function startTicker(sp) {
  if (ticker) clearInterval(ticker);
  state.progCount = 12; state.progFeed = [];
  let idx = 0;
  ticker = setInterval(() => {
    if (state.screen !== "progress") { clearInterval(ticker); ticker = null; return; }
    idx++;
    state.progCount = Math.min(FILE_COUNT, state.progCount + Math.floor(3 + Math.random() * 6));
    const file = FILES[idx % FILES.length];
    state.progFeed.push(file);
    while (state.progFeed.length > 4) state.progFeed.shift();
    const cnt = document.getElementById("pl-count");
    const feed = document.getElementById("pl-feed");
    if (cnt) cnt.textContent = state.progCount;
    if (feed) {
      const line = document.createElement("div");
      line.className = "pl-line";
      line.textContent = file;
      feed.appendChild(line);
      while (feed.children.length > 4) feed.removeChild(feed.firstChild);
    }
  }, 220 / sp);
}
function stopTicker(finalCount) {
  if (ticker) { clearInterval(ticker); ticker = null; }
  state.progCount = finalCount;
  const cnt = document.getElementById("pl-count");
  if (cnt) cnt.textContent = finalCount;
}

// ─── 走查列 ─────────────────────────────────────────────────────────────────
function buildWalk() {
  const w = document.getElementById("walk");
  w.innerHTML =
    `<button class="wnav" data-prev>‹</button>` +
    WALK.map((x) => `<button class="wbtn" data-walk="${x.id}">${x.label}</button>`).join("") +
    `<button class="wnav" data-next>›</button>`;
  w.querySelectorAll("[data-walk]").forEach((b) => b.addEventListener("click", () => go(b.dataset.walk)));
  w.querySelector("[data-prev]").addEventListener("click", () => { const i = WALK.findIndex((x) => x.id === state.screen); go(WALK[Math.max(0, i - 1)].id); });
  w.querySelector("[data-next]").addEventListener("click", () => { const i = WALK.findIndex((x) => x.id === state.screen); go(WALK[Math.min(WALK.length - 1, i + 1)].id); });
}
function updateWalk() {
  document.querySelectorAll("#walk [data-walk]").forEach((b) => b.classList.toggle("on", b.dataset.walk === state.screen));
}

// ─── Tweaks 面板(vanilla + host 協定) ─────────────────────────────────────────
function buildTweaks() {
  const p = document.createElement("div");
  p.id = "tweaks";
  p.style.cssText = "position:fixed;top:16px;right:16px;width:230px;z-index:60;background:rgba(20,24,30,.96);border:1px solid rgba(255,255,255,.12);border-radius:12px;padding:14px 14px 16px;box-shadow:0 12px 40px rgba(0,0,0,.5);font-family:var(--font-sans);color:#e7ecf2;display:none;backdrop-filter:blur(8px);";
  const accents = ["#0f766e", "#0a5d56", "#115e59", "#0369a1"];
  p.innerHTML = `
    <div style="display:flex;align-items:center;justify-content:space-between;margin-bottom:12px;">
      <span style="font-size:12px;font-weight:700;letter-spacing:.04em;">TWEAKS</span>
      <button id="tw-x" style="background:none;border:none;color:#8b96a4;font-size:16px;cursor:pointer;line-height:1;">✕</button>
    </div>
    <div class="tw-grp"><div class="tw-l">主色 Accent</div><div id="tw-acc" style="display:flex;gap:7px;">${accents.map((c) => `<button class="tw-sw" data-acc="${c}" style="width:26px;height:26px;border-radius:6px;background:${c};border:2px solid transparent;cursor:pointer;"></button>`).join("")}</div></div>
    <div class="tw-grp"><label class="tw-row"><span class="tw-l">開門進度動畫</span><input type="checkbox" id="tw-door"></label></div>
    <div class="tw-grp"><div class="tw-l">執行模式</div><div id="tw-mode" style="display:flex;gap:6px;">
      <button class="tw-seg" data-mode="api">API key</button><button class="tw-seg" data-mode="agent">Agent</button></div></div>
    <div class="tw-grp"><label class="tw-row"><span class="tw-l">回訪者（已有快照）</span><input type="checkbox" id="tw-ret"></label></div>
    <div class="tw-grp"><div class="tw-l">進度播放速度 <span id="tw-spd-v" style="color:#5eead4;"></span></div><input type="range" id="tw-spd" min="0.5" max="3" step="0.5" style="width:100%;accent-color:var(--accent);"></div>`;
  document.body.appendChild(p);

  const css = document.createElement("style");
  css.textContent = `#tweaks .tw-grp{margin-bottom:13px;} #tweaks .tw-l{font-size:11px;color:#9aa6b4;margin-bottom:7px;}
    #tweaks .tw-row{display:flex;align-items:center;justify-content:space-between;cursor:pointer;margin:0;}
    #tweaks .tw-row .tw-l{margin:0;} #tweaks input[type=checkbox]{width:34px;height:19px;-webkit-appearance:none;appearance:none;background:#3a4452;border-radius:99px;position:relative;cursor:pointer;transition:background .2s;}
    #tweaks input[type=checkbox]:checked{background:var(--accent);} #tweaks input[type=checkbox]::after{content:"";position:absolute;top:2px;left:2px;width:15px;height:15px;border-radius:50%;background:#fff;transition:left .2s;}
    #tweaks input[type=checkbox]:checked::after{left:17px;}
    #tweaks .tw-seg{flex:1;font-size:11.5px;padding:6px;border-radius:6px;background:#2a323d;border:1px solid transparent;color:#c7d0db;cursor:pointer;font-family:inherit;}
    #tweaks .tw-seg.on{background:var(--accent);color:#fff;font-weight:600;}
    #tweaks .tw-sw.on{border-color:#fff !important;}`;
  document.head.appendChild(css);
  syncTweaks();

  p.querySelector("#tw-x").addEventListener("click", () => postDismiss());
  p.querySelectorAll("[data-acc]").forEach((b) => b.addEventListener("click", () => setTweak("accent", b.dataset.acc)));
  p.querySelector("#tw-door").addEventListener("change", (e) => setTweak("doorAnim", e.target.checked));
  p.querySelector("#tw-ret").addEventListener("change", (e) => setTweak("returning", e.target.checked));
  p.querySelectorAll("[data-mode]").forEach((b) => b.addEventListener("click", () => setTweak("entryMode", b.dataset.mode)));
  p.querySelector("#tw-spd").addEventListener("input", (e) => setTweak("progressSpeed", parseFloat(e.target.value)));
}
function syncTweaks() {
  const t = state.tweaks;
  document.querySelectorAll("#tweaks [data-acc]").forEach((b) => b.classList.toggle("on", b.dataset.acc === t.accent));
  document.querySelector("#tw-door").checked = t.doorAnim;
  document.querySelector("#tw-ret").checked = t.returning;
  document.querySelectorAll("#tweaks [data-mode]").forEach((b) => b.classList.toggle("on", b.dataset.mode === t.entryMode));
  document.querySelector("#tw-spd").value = t.progressSpeed;
  document.querySelector("#tw-spd-v").textContent = t.progressSpeed + "×";
}
function setTweak(k, v) {
  state.tweaks[k] = v;
  localStorage.setItem("door-flow-tweaks", JSON.stringify(state.tweaks));
  syncTweaks(); render();
}

// host 協定:讓工具列的 Tweaks 開關能顯示/隱藏面板
function postReady() { try { parent.postMessage({ type: "__edit_mode_available", keys: TWEAK_KEYS }, "*"); } catch {} }
function postDismiss() { document.getElementById("tweaks").style.display = "none"; try { parent.postMessage({ type: "__edit_mode_dismissed" }, "*"); } catch {} }
window.addEventListener("message", (e) => {
  const t = e.data && e.data.type;
  if (t === "__activate_edit_mode") { document.getElementById("tweaks").style.display = "block"; try { parent.postMessage({ type: "__edit_mode_set_keys", keys: TWEAK_KEYS }, "*"); } catch {} }
  else if (t === "__deactivate_edit_mode") { document.getElementById("tweaks").style.display = "none"; }
});

// ─── 縮放 #frame 以 letterbox 填滿視窗 ──────────────────────────────────────────
function fit() {
  const f = document.getElementById("frame"); if (!f) return;
  const s = Math.min(window.innerWidth / 1180, (window.innerHeight - 64) / 760);
  f.style.transform = `scale(${Math.min(s, 1)})`;
}
window.addEventListener("resize", fit);

// ─── 啟動 ─────────────────────────────────────────────────────────────────────
buildWalk();
buildTweaks();
render();
postReady();

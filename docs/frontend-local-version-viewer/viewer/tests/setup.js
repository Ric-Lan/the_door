// jsdom HTML fixture — must match index.html element IDs used by els cache in dom.js
// This runs before every test file so dom.js sees a populated DOM on import.

document.body.innerHTML = `
  <div class="app-shell">
    <header class="topbar">
      <img id="logo-mark" src="./assets/mark-l1.svg" data-state="l1">
      <div id="version-selector-bar" hidden>
        <select id="select-version-a"></select>
        <select id="select-version-b"></select>
      </div>
      <nav class="mode-switch">
        <button id="btn-diff"     class="mode-button" type="button">差異</button>
        <button id="btn-baseline" class="mode-button" type="button">舊版</button>
        <button id="btn-current"  class="mode-button" type="button">新版</button>
      </nav>
      <div class="topbar-actions">
        <button id="btn-back-l1"   type="button" hidden>← L1</button>
        <button id="btn-mindmap"   type="button">心智圖</button>
        <button id="btn-reanalyze" type="button">重新分析</button>
      </div>
      <div class="status-strip">
        <span id="count-added"   >新增 0</span>
        <span id="count-removed" >移除 0</span>
        <span id="count-modified">修改 0</span>
        <span id="count-risk"    hidden>注意 0</span>
      </div>
    </header>

    <div id="summary-band"><p id="summary-text">載入中…</p></div>
    <div id="diff-mode-banner" hidden></div>
    <div id="pipeline-progress" hidden>
      <span id="current-step"></span>
      <ul id="steps-list"></ul>
    </div>
    <div id="breadcrumb"></div>

    <main class="workspace">
      <section class="cards-panel">
        <h2 id="list-title">功能總覽</h2>
        <p id="list-source"></p>
        <select id="filter-conf"><option value="">全部</option><option value="high">high</option></select>
        <select id="filter-type"><option value="">全部</option><option value="added">added</option></select>
        <div id="feature-list"></div>
      </section>
      <aside class="detail-panel">
        <p id="detail-source">尚未選取</p>
        <div id="detail-content"></div>
        <div id="notes-tab-pane" class="notes-tab-pane" hidden></div>
        <div id="layer-explanation"></div>
      </aside>
    </main>
  </div>

  <div id="graph-drawer" aria-hidden="true">
    <div id="legend-panel"></div>
    <button id="btn-drawer-close" type="button">✕</button>
    <div id="graph-container">
      <div id="graph-spinner"></div>
    </div>
  </div>

  <div id="graph-backdrop" hidden></div>
  <button id="btn-graph-toggle" type="button">関聯圖</button>

  <div id="update-modal" hidden>
    <input id="input-old-path" type="text">
    <input id="input-new-path" type="text">
    <select id="input-language"><option value="zh-Hant">繁體中文</option></select>
    <div id="modal-error" hidden></div>
    <p id="modal-project-hint" hidden></p>
    <button id="btn-modal-cancel" type="button">取消</button>
    <button id="btn-modal-submit" type="button">開始分析</button>
  </div>
`;

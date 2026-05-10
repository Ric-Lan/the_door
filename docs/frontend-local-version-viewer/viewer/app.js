/**
 * The Door — Phase UI-2 Local Version Viewer
 *
 * Design principles:
 * - All business logic lives in the Python ViewModel; JS only reads and renders.
 * - No sorting, no diff calculation, no risk inference in JS.
 * - All API requests go to 127.0.0.1 only (no external network).
 * - Fallback: static JSON only when /api/project network error (server not running).
 */

"use strict";

// ============================================================
// API base URL — uses current page's host so any port works
// ============================================================
const API_BASE = `http://${window.location.host}`;

// ============================================================
// State — single mutable object
// ============================================================

const state = {
  /** @type {object|null} UpdateReport ViewModel */
  updateModel: null,
  /** @type {object|null} L1 ViewModel (single-version modes) */
  l1Model: null,
  /** @type {"diff"|"baseline"|"current"} */
  mode: "diff",
  /** @type {string|null} */
  selectedId: null,
  /** @type {object|null} project status from /api/project */
  projectStatus: null,
  /** @type {string|null} current polling job_id */
  pollingJobId: null,
  /** @type {number|null} setInterval handle for polling */
  pollingHandle: null,

  // ── Phase UI-3: Interactive Graph ──────────────────────────
  /** @type {"L1"|"L2"|"L3"} 當前層級 */
  layerState: "L1",
  /** @type {string|null} 當前選定的 feature_id（L2/L3 時必填） */
  selectedFeatureId: null,
  /** @type {string|null} 當前選定的 module_id（L3 時必填） */
  selectedModuleId: null,
  /** @type {object|null} L1_Graph_ViewModel */
  l1GraphViewModel: null,
  /** @type {object|null} L2_Graph_ViewModel */
  l2GraphViewModel: null,
  /** @type {object|null} L3_Graph_ViewModel */
  l3GraphViewModel: null,
  /** @type {object|null} Diff_Graph_ViewModel */
  diffGraphViewModel: null,
  /** @type {object|null} Cytoscape.js 實例 */
  cytoscapeInstance: null,
  /** @type {boolean} Cytoscape.js 是否可用 */
  cytoscapeAvailable: false,
  /** @type {"risk"|"semantic"} 差異排序模式 */
  diffSortMode: "risk",
  /** @type {string|null} 層說明快取 */
  layerExplanation: null,

  /** @type {Array} 所有 snapshots（from /api/snapshots） */
  snapshots: [],
  /** @type {string|null} 版本 A 的 version_id（預設最新） */
  versionA: null,
  /** @type {string|null} 版本 B 的 version_id（預設第二新，若有） */
  versionB: null,
  /** @type {object|null} /api/diff 結果（version compare 模式用） */
  versionDiff: null,
};

// ============================================================
// DOM element cache
// ============================================================

const els = {
  btnDiff:          document.getElementById("btn-diff"),
  btnBaseline:      document.getElementById("btn-baseline"),
  btnCurrent:       document.getElementById("btn-current"),
  btnReanalyze:     document.getElementById("btn-reanalyze"),
  summaryText:      document.getElementById("summary-text"),
  countAdded:       document.getElementById("count-added"),
  countRemoved:     document.getElementById("count-removed"),
  countModified:    document.getElementById("count-modified"),
  countRisk:        document.getElementById("count-risk"),
  listTitle:        document.getElementById("list-title"),
  listSource:       document.getElementById("list-source"),
  featureList:      document.getElementById("feature-list"),
  detailSource:     document.getElementById("detail-source"),
  detailContent:    document.getElementById("detail-content"),
  pipelineProgress: document.getElementById("pipeline-progress"),
  currentStep:      document.getElementById("current-step"),
  stepsList:        document.getElementById("steps-list"),
  updateModal:      document.getElementById("update-modal"),
  inputOldPath:     document.getElementById("input-old-path"),
  inputNewPath:     document.getElementById("input-new-path"),
  modalError:       document.getElementById("modal-error"),
  btnModalCancel:   document.getElementById("btn-modal-cancel"),
  btnModalSubmit:   document.getElementById("btn-modal-submit"),
  graphDrawer:      document.getElementById("graph-drawer"),
  graphBackdrop:    document.getElementById("graph-backdrop"),
  btnGraphToggle:   document.getElementById("btn-graph-toggle"),
  btnDrawerClose:   document.getElementById("btn-drawer-close"),
  zoomControls:     document.getElementById("zoom-controls"),
  btnBackL1:   document.getElementById("btn-back-l1"),
  btnMindmap:  document.getElementById("btn-mindmap"),
};

// ============================================================
// Boot
// ============================================================

els.btnDiff.addEventListener("click",         () => setMode("diff"));
els.btnBaseline.addEventListener("click",     () => setMode("baseline"));
els.btnCurrent.addEventListener("click",      () => setMode("current"));
els.btnReanalyze.addEventListener("click",    () => showUpdateModal());
els.btnModalCancel.addEventListener("click",  () => hideUpdateModal());
els.btnModalSubmit.addEventListener("click",  () => {
  const oldPath = els.inputOldPath.value.trim();
  const newPath = els.inputNewPath.value.trim();
  if (!oldPath || !newPath) {
    showModalError("請輸入舊版與新版路徑。");
    return;
  }
  hideUpdateModal();
  submitUpdate(oldPath, newPath);
});

els.btnGraphToggle?.addEventListener("click", openGraphDrawer);
els.btnDrawerClose?.addEventListener("click", closeGraphDrawer);
els.graphBackdrop?.addEventListener("click", closeGraphDrawer);
els.btnMindmap?.addEventListener("click",  switchToMindmap);
els.btnBackL1?.addEventListener("click",   switchToL1);

// Start: try API first, fallback to static JSON on network error
loadProjectStatus();

// ============================================================
// API: project status
// ============================================================

async function loadProjectStatus() {
  try {
    const res = await fetch(`${API_BASE}/api/project`, { cache: "no-store" });
    if (!res.ok) {
      // Server running but error — show error, don't fallback
      const body = await res.json().catch(() => null);
      renderError(body?.error?.message || "無法取得專案狀態（" + res.status + "）");
      return;
    }
    state.projectStatus = await res.json();
    await loadFromApi();
  } catch (_) {
    // Network error: server not running — fallback to static JSON
    await loadStaticFallback();
  }
}

async function loadFromApi() {
  const ps = state.projectStatus;
  if (!ps) return;

  const ad = ps.available_data || {};

  if (ad.has_latest_report) {
    await loadReport();
  } else {
    // No report yet — show empty state
    state.updateModel = null;
    els.summaryText.textContent = "尚未有分析報告。請執行 the-door update 或點擊「重新分析」。";
  }

  if (ad.has_snapshots) {
    await loadSnapshots();
  }

  const hasVersionCompare = !!(state.versionA && state.versionB && state.versionA !== state.versionB);
  state.mode = (state.updateModel?.diff_available || hasVersionCompare) ? "diff" : "baseline";
  state.selectedId = firstSelectableId();
  render();

  // Phase UI-3: always load L1 graph from /api/l1 when snapshots exist
  if (ad.has_snapshots) {
    // In diff mode with version compare, load the "current" (versionB) graph
    await loadL1Graph(hasVersionCompare ? state.versionB : null);
    openGraphDrawer();
  }
}

// ============================================================
// API: report
// ============================================================

async function loadReport() {
  try {
    const res = await fetch(`${API_BASE}/api/report/latest`, { cache: "no-store" });
    if (!res.ok) {
      if (res.status === 404) {
        state.updateModel = null;
        return;
      }
      const body = await res.json().catch(() => null);
      handleApiError(res.status, body);
      return;
    }
    // /api/report/latest returns the raw UpdateReport dict
    // We need to convert it to a ViewModel — use the Python-generated ViewModel if available
    // For now, store the raw report and build a minimal ViewModel
    const report = await res.json();
    state.updateModel = buildViewModelFromReport(report);
  } catch (err) {
    renderError("載入報告失敗：" + (err.message || "network error"));
  }
}

// ============================================================
// API: snapshots
// ============================================================

async function loadSnapshots() {
  try {
    const res = await fetch(`${API_BASE}/api/snapshots`, { cache: "no-store" });
    if (!res.ok) return;
    const data = await res.json();
    state.snapshots = data.snapshots || [];
    // versionA = baseline (older), versionB = current (newer)
    // Snapshots are ordered newest-first, so index 0 = newest = current
    state.versionA = state.snapshots[1]?.version_id ?? null;
    state.versionB = state.snapshots[0]?.version_id ?? null;
    populateVersionSelectors();
  } catch (_) {
    // Non-fatal
  }
}

function snapshotLabel(snapshot) {
  if (!snapshot) return "（未知）";
  if (snapshot.git_tags?.length) return snapshot.git_tags[0];
  if (snapshot.label) return snapshot.label;
  return snapshot.timestamp?.slice(0, 16).replace("T", " ") ?? "（無時間）";
}

function populateVersionSelectors() {
  const selA = document.getElementById("select-version-a");
  const selB = document.getElementById("select-version-b");
  const selectorBar = document.getElementById("version-selector-bar");
  if (!selA || !selB || !selectorBar) return;

  // Single snapshot: hide selector
  if (state.snapshots.length <= 1) {
    selectorBar.hidden = true;
    return;
  }

  selectorBar.hidden = false;

  [selA, selB].forEach((sel, idx) => {
    sel.innerHTML = "";
    state.snapshots.forEach((s) => {
      const opt = document.createElement("option");
      opt.value = s.version_id;
      opt.textContent = snapshotLabel(s);
      sel.appendChild(opt);
    });
    // Default: A = baseline (older), B = current (newer)
    sel.value = idx === 0 ? state.versionA : state.versionB;
  });

  // 用賦值型 onchange（覆寫而非累積），確保多次呼叫 populateVersionSelectors() 不重複附加 handler
  selA.onchange = async () => {
    state.versionA = selA.value;
    state.mode = "diff";
    renderTopBar();
    // Show the "current" version (B) graph, overlay diff A→B
    await loadL1Graph(state.versionB ?? state.versionA);
  };
  selB.onchange = async () => {
    state.versionB = selB.value;
    state.mode = "diff";
    renderTopBar();
    await loadL1Graph(state.versionB);
  };
}

// ============================================================
// Static JSON fallback (server not running)
// ============================================================

async function loadStaticFallback() {
  const updatePath = "./data/update-view-model.json";
  try {
    const res = await fetch(updatePath, { cache: "no-store" });
    if (!res.ok) {
      renderError(updatePath + ": " + res.status);
      return;
    }
    state.updateModel = await res.json();
  } catch (err) {
    renderError(updatePath + ": " + (err.message || "network error"));
    return;
  }

  const l1Path = "./data/l1-view-model.json";
  try {
    const res = await fetch(l1Path, { cache: "no-store" });
    if (res.ok) {
      const graphData = await res.json().catch(() => null);
      if (graphData) {
        state.l1GraphViewModel = graphData;
        state.l1Model = {
          features: (graphData.nodes || []).map((n) => ({
            id: n.id,
            label: n.label,
            confidence: n.confidence,
            description: n.description,
            trigger_description: n.trigger_description,
            source: "L1Output.features",
          })),
          stats: { feature_count: (graphData.nodes || []).length },
        };
      }
    }
  } catch (_) {
    state.l1GraphViewModel = null;
    state.l1Model = null;
  }

  state.mode = state.updateModel?.diff_available ? "diff" : "baseline";
  state.selectedId = firstSelectableId();
  render();

  if (state.l1GraphViewModel) {
    state.layerState = "L1";
    initGraph("graph-container", state.l1GraphViewModel);
    renderLegend();
  }
}

// ============================================================
// ViewModel builder from raw UpdateReport
// ============================================================

/**
 * Build a minimal ViewModel from a raw UpdateReport dict.
 * Mirrors the Python build_update_report_view_model() logic.
 */
function buildViewModelFromReport(report) {
  const l1Changes = report.l1_changes || [];
  const l2Details = report.l2_details || [];
  const diffAvailable = l1Changes.length > 0;

  // Build details map
  const detailsMap = {};
  l2Details.forEach((d) => {
    detailsMap[d.feature_id] = {
      id: d.feature_id,
      change_type: d.change_type,
      before: {
        label: d.baseline_label || "未提供",
        description: d.baseline_description || "未提供",
      },
      after: {
        label: d.current_label || "未提供",
        description: d.current_description || "未提供",
      },
      scope_state: d.scope_state || null,
      related_vulnerabilities: d.related_vulnerabilities || [],
      affected_relations: d.affected_relations || [],
      source: "UpdateReport.l2_details",
    };
  });

  // For l1_changes without l2 entry, create fallback detail
  l1Changes.forEach((c) => {
    if (!detailsMap[c.feature_id]) {
      detailsMap[c.feature_id] = {
        id: c.feature_id,
        change_type: c.change_type,
        before: { label: "未提供", description: "未提供" },
        after: { label: c.current_label || "未提供", description: "未提供" },
        scope_state: null,
        related_vulnerabilities: [],
        affected_relations: [],
        source: "UpdateReport.l1_changes",
      };
    }
  });

  // Count changes
  const changeCounts = { added: 0, removed: 0, attribute_changed: 0, dependency_changed: 0 };
  const riskCounts = { out_of_scope: 0, vulnerability: 0, semantic_drift: 0 };
  l1Changes.forEach((c) => {
    if (c.change_type in changeCounts) changeCounts[c.change_type]++;
    (c.risk_flags || []).forEach((f) => { if (f in riskCounts) riskCounts[f]++; });
  });

  const changes = l1Changes.map((c) => ({
    id: c.feature_id,
    label: c.current_label || c.baseline_label || c.feature_id,
    change_type: c.change_type,
    risk_flags: c.risk_flags || [],
    current_label: c.current_label || null,
    baseline_label: c.baseline_label || null,
    source: "UpdateReport.l1_changes",
  }));

  return {
    mode: "update-report",
    diff_available: diffAvailable,
    summary: report.l0_summary || "（無摘要）",
    change_counts: changeCounts,
    risk_counts: riskCounts,
    changes,
    details: detailsMap,
    interrupted: report.interrupted || false,
    source: "UpdateReport",
  };
}

// ============================================================
// Update modal
// ============================================================

function showUpdateModal() {
  // Pre-fill old_path with current project path (the version being viewed)
  const projectPath = state.projectStatus?.project_path || "";
  els.inputOldPath.value = projectPath;
  els.inputNewPath.value = "";
  els.modalError.hidden = true;

  // Show project root as hint so user knows the constraint
  const hint = document.getElementById("modal-project-hint");
  if (hint) {
    if (projectPath) {
      hint.textContent = "專案根目錄：" + projectPath;
      hint.hidden = false;
    } else {
      hint.hidden = true;
    }
  }

  els.updateModal.hidden = false;
  els.inputNewPath.focus();
}

function hideUpdateModal() {
  els.updateModal.hidden = true;
}

function showModalError(msg) {
  els.modalError.textContent = msg;
  els.modalError.hidden = false;
}

// ============================================================
// POST /api/update + polling
// ============================================================

async function submitUpdate(oldPath, newPath) {
  try {
    const res = await fetch(`${API_BASE}/api/update`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ old_path: oldPath, new_path: newPath }),
    });
    const body = await res.json();
    if (!res.ok) {
      renderError("分析請求失敗：" + (body?.error?.message || res.status));
      return;
    }
    const jobId = body.job_id;
    startPolling(jobId);
  } catch (err) {
    renderError("無法連線到本地 server：" + (err.message || "network error"));
  }
}

function startPolling(jobId) {
  state.pollingJobId = jobId;
  els.pipelineProgress.hidden = false;
  els.stepsList.textContent = "";
  els.currentStep.textContent = "初始化…";

  state.pollingHandle = setInterval(() => pollJobStatus(jobId), 1500);
}

function stopPolling() {
  if (state.pollingHandle !== null) {
    clearInterval(state.pollingHandle);
    state.pollingHandle = null;
  }
  state.pollingJobId = null;
}

async function pollJobStatus(jobId) {
  try {
    const res = await fetch(`${API_BASE}/api/update/status/` + jobId, { cache: "no-store" });
    if (!res.ok) {
      stopPolling();
      const body = await res.json().catch(() => null);
      renderError("無法取得管線狀態：" + (body?.error?.message || res.status));
      return;
    }
    const job = await res.json();
    renderPipelineProgress(job);

    if (job.status === "completed") {
      stopPolling();
      els.pipelineProgress.hidden = true;
      await loadReport();
      state.mode = state.updateModel?.diff_available ? "diff" : "baseline";
      state.selectedId = firstSelectableId();
      render();
    } else if (job.status === "failed") {
      stopPolling();
      els.pipelineProgress.hidden = true;
      renderError("管線執行失敗：" + (job.error_message || "未知錯誤"));
    }
  } catch (err) {
    stopPolling();
    renderError("連線中斷，請確認 server 仍在執行：" + (err.message || "network error"));
  }
}

// ============================================================
// PipelineProgress component
// ============================================================

function renderPipelineProgress(job) {
  els.currentStep.textContent = job.current_step ? "執行中：" + job.current_step : "";

  const list = els.stepsList;
  list.textContent = "";
  (job.steps || []).forEach((step) => {
    const li = document.createElement("li");
    li.className = "step-item step-" + step.status;
    const sym = step.status === "completed" ? "✓" : step.status === "failed" ? "✗" : "⊘";
    const dur = step.duration_ms != null ? " (" + (step.duration_ms / 1000).toFixed(1) + "s)" : "";
    li.textContent = sym + " " + step.step_name + dur;
    if (step.error_message) {
      const err = document.createElement("span");
      err.className = "step-error";
      err.textContent = " — " + step.error_message;
      li.appendChild(err);
    }
    list.appendChild(li);
  });
}

// ============================================================
// API error handler
// ============================================================

function handleApiError(status, body) {
  const msg = body?.error?.message || "HTTP " + status;
  renderError("API 錯誤：" + msg);
}

// ============================================================
// Mode switching
// ============================================================

async function setMode(mode) {
  const hasDiff = state.updateModel?.diff_available === true;
  const hasVersionCompare = !!(state.versionA && state.versionB && state.versionA !== state.versionB);
  if (mode === "diff" && !hasDiff && !hasVersionCompare) return;
  state.mode = mode;
  state.selectedId = firstSelectableId();
  render();

  // Version-compare mode: reload graph for the appropriate version + overlay
  if (hasVersionCompare && !hasDiff) {
    if (mode === "baseline") {
      await loadL1Graph(state.versionA);
    } else if (mode === "current") {
      await loadL1Graph(state.versionB);
    } else if (mode === "diff") {
      await loadL1Graph(state.versionB);
      // Overlay is applied inside loadL1Graph automatically
    }
  }
}

function firstSelectableId() {
  if (state.mode === "diff") {
    return state.updateModel?.changes?.[0]?.id ?? null;
  }
  return state.l1Model?.features?.[0]?.id ?? null;
}

// ============================================================
// Top-level render
// ============================================================

function render() {
  renderTopBar();
  renderChangeList();
  renderDetailPanel();
}

// ============================================================
// renderTopBar
// ============================================================

function renderTopBar() {
  const um = state.updateModel;
  const hasDiff = um?.diff_available === true;
  const hasVersionCompare = !!(state.versionA && state.versionB && state.versionA !== state.versionB);

  // Show mode buttons when diff data OR two different versions are selected
  const modeSwitch = document.querySelector(".mode-switch");
  if (modeSwitch) {
    modeSwitch.hidden = !hasDiff && !hasVersionCompare;
  }

  // Summary text
  if (hasDiff) {
    els.summaryText.textContent = um?.summary || "（無摘要）";
  } else if (state.l1Model) {
    const fc = state.l1Model.stats?.feature_count ?? state.l1Model.features?.length ?? 0;
    els.summaryText.textContent = "功能總覽：共 " + fc + " 個功能。";
  } else {
    els.summaryText.textContent = "（載入中…）";
  }

  els.btnDiff.classList.toggle("active", state.mode === "diff");
  els.btnBaseline.classList.toggle("active", state.mode === "baseline");
  els.btnCurrent.classList.toggle("active", state.mode === "current");

  const snapA = state.snapshots.find(s => s.version_id === state.versionA);
  const snapB = state.snapshots.find(s => s.version_id === state.versionB);
  els.btnBaseline.textContent = snapA ? snapshotLabel(snapA) : "版本 A";
  els.btnCurrent.textContent  = snapB ? snapshotLabel(snapB) : "版本 B";

  els.btnDiff.disabled = !hasDiff && !hasVersionCompare;

  if (hasDiff && state.mode === "diff") {
    const cc = um.change_counts || {};
    const rc = um.risk_counts || {};

    els.countAdded.removeAttribute("hidden");
    els.countRemoved.removeAttribute("hidden");
    els.countModified.removeAttribute("hidden");
    els.countAdded.textContent    = "+" + (cc.added   ?? 0);
    els.countRemoved.textContent  = "-" + (cc.removed  ?? 0);
    const modified = (cc.attribute_changed ?? 0) + (cc.dependency_changed ?? 0);
    els.countModified.textContent = "~" + modified;

    const totalRisk = Object.values(rc).reduce((a, b) => a + b, 0);
    if (totalRisk > 0) {
      els.countRisk.textContent = "⚠ " + totalRisk;
      els.countRisk.removeAttribute("hidden");
    } else {
      els.countRisk.setAttribute("hidden", "");
    }
  } else {
    const fc = state.l1Model?.stats?.feature_count ?? state.l1Model?.features?.length ?? 0;
    els.countAdded.textContent = fc ? fc + " 功能" : "";
    els.countRemoved.setAttribute("hidden", "");
    els.countModified.setAttribute("hidden", "");
    els.countRisk.setAttribute("hidden", "");
  }
}

// ============================================================
// renderChangeList (sidebar)
// ============================================================

function renderChangeList() {
  const list = els.featureList;
  list.textContent = "";

  if (state.mode === "diff") {
    // Version-compare diff (no updateModel): build change list from versionDiff
    if (!state.updateModel?.diff_available && state.versionDiff) {
      els.listTitle.textContent  = "變更清單";
      els.listSource.textContent = "/api/diff";
      const nodeStates = state.versionDiff.node_states || {};
      const changedFeatures = (state.l1Model?.features ?? []).filter(
        f => nodeStates[f.id] && nodeStates[f.id] !== "unchanged"
      );
      if (!changedFeatures.length) {
        renderEmpty(list, "兩個版本之間無功能差異。");
        return;
      }
      changedFeatures.forEach(feature => {
        const change = {
          id: feature.id,
          label: feature.label,
          change_type: nodeStates[feature.id],
        };
        list.appendChild(changeListButton(change));
      });
      return;
    }

    const changes = state.updateModel?.changes ?? [];
    els.listTitle.textContent  = "變更清單";
    els.listSource.textContent = "UpdateReport.l1_changes";

    if (!changes.length) {
      renderEmpty(list, "無變更項目。");
      return;
    }

    changes.forEach((change) => {
      list.appendChild(changeListButton(change));
    });
    return;
  }

  const features = state.l1Model?.features ?? [];
  els.listTitle.textContent  = state.mode === "baseline" ? "舊版功能" : "新版功能";
  els.listSource.textContent = "L1Output.features";

  if (!features.length) {
    renderEmpty(list, state.l1Model ? "無功能資料。" : "L1 ViewModel 載入中…");
    return;
  }

  features.forEach((feature) => {
    list.appendChild(featureCard(feature));
  });
}

function changeListButton(change) {
  const card = document.createElement("button");
  card.type = "button";
  card.className = "feature-card" + (change.id === state.selectedId ? " active" : "");
  card.dataset.nodeId = change.id;

  const labelEl = document.createElement("span");
  labelEl.className = "feature-card-label";
  labelEl.textContent = change.label;

  const descEl = document.createElement("span");
  descEl.className = "feature-card-desc";
  const detail = state.updateModel?.details?.[change.id];
  descEl.textContent = detail?.after?.description || detail?.before?.description || "";

  const metaEl = document.createElement("div");
  metaEl.className = "feature-card-meta";
  const badge = document.createElement("span");
  badge.className = "change-badge change-" + change.change_type;
  badge.textContent = changeSymbol(change.change_type) + " " + change.change_type;
  metaEl.appendChild(badge);

  card.append(labelEl, descEl, metaEl);
  card.addEventListener("click", () => selectItem(change.id));
  return card;
}

function featureCard(feature) {
  const card = document.createElement("button");
  card.type = "button";
  card.className = "feature-card" + (feature.id === state.selectedId ? " active" : "");
  card.dataset.nodeId = feature.id;

  const labelEl = document.createElement("span");
  labelEl.className = "feature-card-label";
  labelEl.textContent = feature.label;

  const descEl = document.createElement("span");
  descEl.className = "feature-card-desc";
  descEl.textContent = feature.description || "";

  const metaEl = document.createElement("div");
  metaEl.className = "feature-card-meta";
  if (feature.confidence) {
    const badge = document.createElement("span");
    badge.className = "confidence-badge confidence-badge-" + (feature.confidence || "").toLowerCase();
    badge.textContent = feature.confidence;
    metaEl.appendChild(badge);
  }

  card.append(labelEl, descEl, metaEl);
  card.addEventListener("click", () => {
    state.selectedId = feature.id;
    state.selectedFeatureId = feature.id;
    if (state.cytoscapeInstance) {
      state.cytoscapeInstance.elements().unselect();
      const cyNode = state.cytoscapeInstance.getElementById(feature.id);
      if (cyNode) {
        cyNode.select();
        state.cytoscapeInstance.animate({ fit: { eles: cyNode, padding: 50 } });
      }
    }
    renderDetailPanelL1(feature);
    els.featureList.querySelectorAll(".feature-card").forEach((c) => c.classList.remove("active"));
    card.classList.add("active");
  });
  return card;
}


// ============================================================
// renderDetailPanel
// ============================================================

function renderDetailPanel() {
  if (state.mode === "diff") {
    renderDiffDetailPanel();
  } else {
    renderSingleVersionDetailPanel();
  }
}

function renderDiffDetailPanel() {
  const detail = state.updateModel?.details?.[state.selectedId];

  if (!detail) {
    renderNoSelection();
    return;
  }

  els.detailSource.textContent = detail.source;

  const content = els.detailContent;
  content.className = "detail-content";
  content.textContent = "";

  // A-class: Python already filled "未提供"
  content.appendChild(detailSection("變更前名稱",   detail.before.label));
  content.appendChild(detailSection("變更前描述",   detail.before.description));
  content.appendChild(detailSection("變更後名稱",   detail.after.label));
  content.appendChild(detailSection("變更後描述",   detail.after.description));

  // B-class: scope_state is null in Python; JS fills display text
  content.appendChild(detailSection("範圍狀態", detail.scope_state ?? "未提供"));

  content.appendChild(listDetailSection("相關漏洞",   detail.related_vulnerabilities ?? []));
  content.appendChild(listDetailSection("受影響關係", detail.affected_relations ?? []));

  // Attribution — always visible (anti-hallucination)
  content.appendChild(attributionSection(detail.source));
}

function renderSingleVersionDetailPanel() {
  const features = state.l1Model?.features ?? [];
  const feature = features.find((f) => f.id === state.selectedId);

  if (!feature) {
    renderNoSelection();
    return;
  }

  els.detailSource.textContent = feature.source;

  const content = els.detailContent;
  content.className = "detail-content";
  content.textContent = "";

  content.appendChild(detailSection("功能名稱",   feature.label));
  content.appendChild(detailSection("描述",       feature.description));
  content.appendChild(detailSection("觸發方式",   feature.trigger_description));
  content.appendChild(detailSection("信心等級",   feature.confidence));
  content.appendChild(detailSection("信心理由",   feature.confidence_reason));
  content.appendChild(listDetailSection("Source nodes", feature.source_nodes ?? []));

  content.appendChild(attributionSection(feature.source));
}

// ============================================================
// Detail panel helpers
// ============================================================

function detailSection(title, text) {
  const wrap = document.createElement("section");
  wrap.className = "detail-section";

  const h = document.createElement("h3");
  h.textContent = title;

  const p = document.createElement("p");
  const displayText = (text === null || text === undefined) ? "未提供" : String(text);
  if (displayText === "未提供") {
    p.className = "missing";
  }
  p.textContent = displayText;

  wrap.append(h, p);
  return wrap;
}

function listDetailSection(title, items) {
  const wrap = document.createElement("section");
  wrap.className = "detail-section";

  const h = document.createElement("h3");
  h.textContent = title;
  wrap.appendChild(h);

  if (!items.length) {
    const p = document.createElement("p");
    p.className = "missing";
    p.textContent = "未提供";
    wrap.appendChild(p);
    return wrap;
  }

  const ul = document.createElement("ul");
  ul.className = "source-list";
  items.forEach((item) => {
    const li = document.createElement("li");
    li.textContent = typeof item === "string" ? item : JSON.stringify(item);
    ul.appendChild(li);
  });
  wrap.appendChild(ul);
  return wrap;
}

function attributionSection(source) {
  const div = document.createElement("div");
  div.className = "attribution";
  div.textContent = "資料來源：";
  const code = document.createElement("code");
  code.textContent = source || "unknown";
  div.appendChild(code);
  return div;
}

function renderNoSelection() {
  els.detailSource.textContent = "尚未選取";
  els.detailContent.className = "detail-content empty-state";
  els.detailContent.textContent = "選取左側項目以查看詳情。";
}

// ============================================================
// Utilities
// ============================================================

function selectItem(id) {
  state.selectedId = id;
  render();
}

function changeSymbol(changeType) {
  const map = {
    added:              "+",
    removed:            "-",
    attribute_changed:  "~",
    dependency_changed: "!=",
  };
  return map[changeType] ?? "?";
}

function renderEmpty(parent, message) {
  const div = document.createElement("div");
  div.className = "empty-state";
  div.textContent = message;
  parent.appendChild(div);
}

function renderError(message) {
  els.summaryText.textContent = "資料載入失敗。";

  els.featureList.textContent = "";
  const box = document.createElement("div");
  box.className = "error-box";
  box.textContent = message;
  els.featureList.appendChild(box);

  els.btnDiff.disabled     = true;
  els.btnBaseline.disabled = true;
  els.btnCurrent.disabled  = true;
}

// ============================================================
// Phase UI-3: Cytoscape Graph Rendering
// ============================================================

/**
 * Task 7.2 — initGraph(containerId, viewModel)
 *
 * Initializes a Cytoscape.js instance in the specified container.
 * Falls back to Mermaid text output if:
 *   - cytoscape global is undefined (library not loaded)
 *   - cytoscape() constructor throws an exception
 *
 * If viewModel.nodes is empty, displays an empty-state message
 * without throwing an exception (Req 13 AC6, Task 7.7).
 *
 * On success, sets state.cytoscapeInstance and state.cytoscapeAvailable = true.
 *
 * @param {string} containerId - DOM element id for the graph container
 * @param {object} viewModel   - Graph ViewModel with .nodes and .edges arrays
 */
function initGraph(containerId, viewModel) {
  const container = document.getElementById(containerId);

  // Guard: empty ViewModel — show empty-state, do not throw (Req 13 AC6)
  if (!viewModel || !viewModel.nodes || viewModel.nodes.length === 0) {
    if (container) {
      container.textContent = "";
      const emptyDiv = document.createElement("div");
      emptyDiv.className = "empty-state";
      emptyDiv.textContent = "此層級目前沒有節點資料。";
      container.appendChild(emptyDiv);
    }
    return;
  }

  // Guard: Cytoscape.js not loaded — fallback to Mermaid
  if (typeof cytoscape === "undefined") {
    renderMermaidFallback(viewModel, state.layerState);
    return;
  }

  // Clear spinner / previous content
  container.textContent = "";

  try {
    const cy = cytoscape({
      container: container,
      elements: buildCytoscapeElements(viewModel),
      style: buildCytoscapeStyle(state.layerState),
      layout: {
        name: "breadthfirst",
        directed: true,
        padding: 30,
        spacingFactor: 1.8,
        avoidOverlap: true,
      },
      minZoom: 0.2,
      maxZoom: 4,
      wheelSensitivity: 0.15,
    });
    state.cytoscapeInstance = cy;
    state.cytoscapeAvailable = true;
    cy.one("layoutstop", () => {
      // Enforce minimum node size after label-based auto-sizing
      cy.nodes().forEach((node) => {
        if (node.width()  < 260) node.style("width",  260);
        if (node.height() <  90) node.style("height",  90);
      });
      cy.fit(undefined, 50);
      if (cy.zoom() > 0.65) { cy.zoom(0.65); cy.center(); }
    });
    bindCytoscapeEvents(cy, state.layerState);
    initZoomControls(cy);
  } catch (err) {
    // Cytoscape initialization failed — fallback to Mermaid
    renderMermaidFallback(viewModel, state.layerState);
    showFallbackIndicator(err.message);
  }
}

/**
 * Task 7.3 — buildCytoscapeElements(viewModel)
 *
 * Converts a Graph ViewModel into Cytoscape.js elements format.
 *
 * Nodes: { data: { id, label, ...otherFields } }
 * Edges: { data: { id: source+'-'+target, source, target, ...otherFields } }
 *
 * @param {object} viewModel - Graph ViewModel with .nodes and .edges arrays
 * @returns {Array} Cytoscape elements array
 */
function buildCytoscapeElements(viewModel) {
  const nodes = (viewModel.nodes || []).map((node) => {
    const { id, label, ...rest } = node;
    return {
      data: { id, label, ...rest },
    };
  });

  const edges = (viewModel.edges || []).map((edge) => {
    const { source, target, ...rest } = edge;
    return {
      data: {
        id: source + "-" + target,
        source,
        target,
        ...rest,
      },
    };
  });

  return [...nodes, ...edges];
}

/**
 * Task 7.4 — buildCytoscapeStyle(layerState)
 *
 * Returns a Cytoscape.js style array for the given layer.
 *
 * Node colors by change_type:
 *   added              → #4caf50 (green)
 *   removed            → #f44336 (red)
 *   attribute_changed  → #ff9800 (orange)
 *   dependency_changed → #ffc107 (yellow)
 *   unchanged / default → #9e9e9e (muted grey)
 *
 * Confidence markers (border style):
 *   high   → solid border
 *   medium → dashed border
 *   low    → dotted border
 *
 * Selected state: border-color #2196f3
 *
 * @param {string} layerState - "L1" | "L2" | "L3"
 * @returns {Array} Cytoscape style array
 */
function buildCytoscapeStyle(layerState) {
  return [
    // ── Base node style ──────────────────────────────────────
    {
      selector: "node",
      style: {
        "label": "data(label)",
        "text-valign": "center",
        "text-halign": "center",
        "font-size": "32px",
        "font-weight": "600",
        "color": "#ffffff",
        "text-outline-width": 2,
        "text-outline-color": "rgba(0,0,0,0.35)",
        "text-wrap": "wrap",
        "text-max-width": "280px",
        "background-color": "#607d8b",
        "border-width": 3,
        "border-color": "#455a64",
        "border-style": "solid",
        "width": "label",
        "height": "label",
        "padding": "22px",
        "shape": "roundrectangle",
      },
    },

    // ── change_type colors ───────────────────────────────────
    {
      selector: "node[change_type = 'added']",
      style: { "background-color": "#4caf50", "border-color": "#388e3c" },
    },
    {
      selector: "node[change_type = 'removed']",
      style: { "background-color": "#f44336", "border-color": "#c62828" },
    },
    {
      selector: "node[change_type = 'attribute_changed']",
      style: { "background-color": "#ff9800", "border-color": "#e65100" },
    },
    {
      selector: "node[change_type = 'dependency_changed']",
      style: { "background-color": "#ffc107", "border-color": "#f57f17", "color": "#333" },
    },

    // ── Confidence markers (border style) ────────────────────
    {
      selector: "node[confidence = 'high']",
      style: { "border-style": "solid", "border-width": 3 },
    },
    {
      selector: "node[confidence = 'medium']",
      style: { "border-style": "dashed", "border-width": 2 },
    },
    {
      selector: "node[confidence = 'low']",
      style: { "border-style": "dotted", "border-width": 2 },
    },

    // ── Selected state ───────────────────────────────────────
    {
      selector: "node:selected",
      style: {
        "border-color": "#2196f3",
        "border-width": 4,
        "border-style": "solid",
      },
    },

    // ── Base edge style ──────────────────────────────────────
    {
      selector: "edge",
      style: {
        "width": 2,
        "line-color": "#78909c",
        "target-arrow-color": "#78909c",
        "target-arrow-shape": "triangle",
        "arrow-scale": 1.2,
        "curve-style": "bezier",
        "font-size": "10px",
        "color": "#555",
      },
    },

    // ── Selected edge ────────────────────────────────────────
    {
      selector: "edge:selected",
      style: {
        "line-color": "#2196f3",
        "target-arrow-color": "#2196f3",
      },
    },
  ];
}

/**
 * Task 7.5 — renderMermaidFallback(viewModel, layerState)
 *
 * Generates Mermaid flowchart text from the ViewModel and displays it
 * in the #mermaid-fallback element. Hides #graph-container.
 *
 * Shows a .fallback-indicator message explaining that the interactive
 * graph is unavailable.
 *
 * @param {object} viewModel   - Graph ViewModel with .nodes and .edges arrays
 * @param {string} layerState  - "L1" | "L2" | "L3"
 */
function renderMermaidFallback(viewModel, layerState) {
  const graphContainer = document.getElementById("graph-container");
  const fallbackEl = document.getElementById("mermaid-fallback");

  if (graphContainer) graphContainer.style.display = "none";
  if (!fallbackEl) return;

  fallbackEl.style.display = "block";
  fallbackEl.textContent = "";

  // Fallback indicator
  const indicator = document.createElement("div");
  indicator.className = "fallback-indicator";
  indicator.textContent = "互動式圖形不可用（Cytoscape.js 未載入或初始化失敗），顯示文字圖形（" + layerState + " 層）";
  fallbackEl.appendChild(indicator);

  // Generate Mermaid flowchart text
  const mermaidText = buildMermaidText(viewModel);

  const pre = document.createElement("pre");
  pre.className = "mermaid-output";
  pre.textContent = mermaidText;
  fallbackEl.appendChild(pre);
}

/**
 * Builds a Mermaid flowchart LR text from a Graph ViewModel.
 *
 * @param {object} viewModel - Graph ViewModel with .nodes and .edges arrays
 * @returns {string} Mermaid diagram text
 */
function buildMermaidText(viewModel) {
  const nodes = viewModel.nodes || [];
  const edges = viewModel.edges || [];

  const lines = ["graph LR"];

  // Node definitions with sanitized IDs
  nodes.forEach((node) => {
    const safeId = sanitizeMermaidId(node.id);
    const label = (node.label || node.id).replace(/"/g, "'");
    lines.push("  " + safeId + '["' + label + '"]');
  });

  // Edge definitions
  edges.forEach((edge) => {
    const safeSource = sanitizeMermaidId(edge.source);
    const safeTarget = sanitizeMermaidId(edge.target);
    lines.push("  " + safeSource + " --> " + safeTarget);
  });

  if (nodes.length === 0) {
    lines.push("  empty[\"（無節點）\"]");
  }

  return lines.join("\n");
}

/**
 * Sanitizes a string for use as a Mermaid node ID.
 * Replaces non-alphanumeric characters with underscores.
 *
 * @param {string} id - Raw node ID
 * @returns {string} Sanitized ID safe for Mermaid
 */
function sanitizeMermaidId(id) {
  return String(id).replace(/[^a-zA-Z0-9_]/g, "_");
}

/**
 * Displays a fallback indicator message in the #mermaid-fallback element.
 * Called when Cytoscape initialization throws an exception.
 *
 * @param {string} [errorMessage] - Optional error message to display
 */
function showFallbackIndicator(errorMessage) {
  const fallbackEl = document.getElementById("mermaid-fallback");
  if (!fallbackEl) return;

  const existing = fallbackEl.querySelector(".fallback-indicator");
  if (existing && errorMessage) {
    existing.textContent += "（錯誤：" + errorMessage + "）";
  }
}

/**
 * Task 7.6 — bindCytoscapeEvents(cy, layerState)
 *
 * Binds Cytoscape.js node tap events.
 *
 * On node tap:
 *   - Updates state.selectedFeatureId (L1) or state.selectedModuleId (L2/L3)
 *   - Calls the appropriate renderDetailPanel* function based on layerState
 *   - Syncs the Feature_List selection state
 *
 * @param {object} cy         - Cytoscape.js instance
 * @param {string} layerState - "L1" | "L2" | "L3"
 */
function bindCytoscapeEvents(cy, layerState) {
  cy.on("tap", "node", function (evt) {
    const node = evt.target;
    const nodeData = node.data();

    if (layerState === "L1") {
      state.selectedFeatureId = nodeData.id;
      if (typeof renderDetailPanelL1 === "function") {
        renderDetailPanelL1(nodeData);
      }
    } else if (layerState === "L2") {
      state.selectedModuleId = nodeData.id;
      if (typeof renderDetailPanelL2 === "function") {
        renderDetailPanelL2(nodeData);
      }
    } else if (layerState === "L3") {
      if (typeof renderDetailPanelL3 === "function") {
        renderDetailPanelL3(nodeData);
      }
    }

    // Sync Feature_List selection state
    syncFeatureListSelection(nodeData.id);
  });
}

/**
 * Syncs the Feature_List sidebar selection to match the given node ID.
 * Adds/removes the "active" class on the corresponding list button.
 *
 * @param {string} nodeId - The selected node's ID
 */
function syncFeatureListSelection(nodeId) {
  const featureList = document.getElementById("feature-list");
  if (!featureList) return;

  featureList.querySelectorAll("[data-node-id]").forEach((el) => {
    el.classList.toggle("active", el.dataset.nodeId === nodeId);
  });
}

// ============================================================
// Phase UI-3: Task 8 — 層切換與 API 呼叫
// ============================================================

/**
 * Task 8.1 — loadL1Graph()
 * GET /api/l1，建立 L1_Graph_ViewModel，呼叫 initGraph
 */
async function loadL1Graph(versionId = null) {
  try {
    const url = versionId
      ? `${API_BASE}/api/l1?version_id=${encodeURIComponent(versionId)}`
      : `${API_BASE}/api/l1`;
    const res = await fetch(url, { cache: "no-store" });
    if (!res.ok) {
      const body = await res.json().catch(() => null);
      renderError("無法載入 L1 圖形：" + (body?.error?.message || res.status));
      return;
    }
    state.l1GraphViewModel = await res.json();
    state.layerState = "L1";

    // Bridge to legacy l1Model format so renderChangeList() works in baseline/current mode
    state.l1Model = {
      features: (state.l1GraphViewModel.nodes || []).map((n) => ({
        id: n.id,
        label: n.label,
        confidence: n.confidence,
        description: n.description,
        trigger_description: n.trigger_description,
        source: "L1Output.features",
      })),
      stats: { feature_count: (state.l1GraphViewModel.nodes || []).length },
    };

    initGraph("graph-container", state.l1GraphViewModel);
    renderLegend();
    renderBreadcrumb();

    // Re-render cards now that l1Model is populated
    if (!state.updateModel?.diff_available) {
      state.selectedId = state.l1Model?.features?.[0]?.id ?? null;
    }
    renderTopBar();
    renderChangeList();
    renderDetailPanel();

    // Apply diff overlay if two distinct versions are selected
    if (state.versionA && state.versionB && state.versionA !== state.versionB) {
      await loadDiffOverlay(state.versionA, state.versionB);
    }
  } catch (err) {
    renderError("載入 L1 圖形失敗：" + (err.message || "network error"));
  }
}

/**
 * loadDiffOverlay — fetch /api/diff and apply diff_state colors to Cytoscape nodes
 */
async function loadDiffOverlay(baselineId, currentId) {
  if (!baselineId || !currentId || baselineId === currentId) return;
  try {
    const url = `${API_BASE}/api/diff?baseline=${encodeURIComponent(baselineId)}&current=${encodeURIComponent(currentId)}`;
    const res = await fetch(url, { cache: "no-store" });
    if (!res.ok) return;
    const data = await res.json();

    // Save diff result to state so renderChangeList can use it
    state.versionDiff = data;

    // Apply color overlay to Cytoscape nodes if available
    const nodeStates = data.node_states || {};
    if (state.cytoscapeInstance) {
      state.cytoscapeInstance.nodes().forEach(node => {
        const diffState = nodeStates[node.id()];
        if (diffState && diffState !== "unchanged") {
          node.data("change_type", diffState);
        } else {
          node.removeData("change_type");
        }
      });
    }

    // Update summary text
    const s = data.summary || {};
    const total = s.total_changed ?? 0;
    if (total > 0) {
      els.summaryText.textContent =
        `版本比較：${s.added ?? 0} 新增 / ${s.removed ?? 0} 移除 / ` +
        `${(s.attribute_changed ?? 0) + (s.dependency_changed ?? 0)} 修改`;
    } else {
      els.summaryText.textContent = "版本比較：兩版本功能完全相同。";
    }

    // Re-render change list with diff data
    renderChangeList();
  } catch (e) {
    console.warn("Diff overlay failed:", e);
  }
}

/**
 * Task 8.2 — switchToL2(featureId)
 * 同時觸發兩個獨立 fetch（互不阻塞）：
 * 1. GET /api/l2/<featureId> 取得 L2 圖形資料
 * 2. loadLayerExplanation(featureId, "l2") 取得說明快取
 */
async function switchToL2(featureId) {
  state.selectedFeatureId = featureId;
  state.layerState = "L2";
  renderBreadcrumb();

  // Two independent fetches — neither blocks the other (Req 4 AC9)
  loadLayerExplanation(featureId, "l2"); // fire and forget

  try {
    const res = await fetch(`${API_BASE}/api/l2/` + encodeURIComponent(featureId), { cache: "no-store" });
    if (res.status === 404) {
      renderL2NotAnalyzed(featureId);
      return;
    }
    if (!res.ok) {
      const body = await res.json().catch(() => null);
      renderError("無法載入 L2 圖形：" + (body?.error?.message || res.status));
      return;
    }
    state.l2GraphViewModel = await res.json();
    initGraph("graph-container", state.l2GraphViewModel);
    renderFeatureList(state.l2GraphViewModel, state.layerState);
  } catch (err) {
    renderError("載入 L2 圖形失敗：" + (err.message || "network error"));
  }
}

/**
 * Task 8.3 — switchToL3(moduleId)
 * 從 state.l2GraphViewModel.nodes 找到 source_nodes，GET /api/structure，
 * 在前端過濾節點和邊
 */
async function switchToL3(moduleId) {
  state.selectedModuleId = moduleId;
  state.layerState = "L3";
  renderBreadcrumb();

  // Find source_nodes for this module
  const module = (state.l2GraphViewModel?.nodes || []).find((n) => n.id === moduleId);
  const sourceNodeIds = module?.source_nodes || [];

  if (sourceNodeIds.length === 0) {
    initGraph("graph-container", { nodes: [], edges: [] });
    renderFeatureList({ nodes: [], edges: [] }, "L3");
    return;
  }

  try {
    const res = await fetch(`${API_BASE}/api/structure`, { cache: "no-store" });
    if (res.status === 404) {
      const container = document.getElementById("graph-container");
      if (container) {
        container.textContent = "";
        const msg = document.createElement("div");
        msg.className = "empty-state";
        msg.textContent = "結構資料不存在，請重新執行 the-door extract。";
        container.appendChild(msg);
      }
      return;
    }
    if (!res.ok) {
      const body = await res.json().catch(() => null);
      renderError("無法載入結構資料：" + (body?.error?.message || res.status));
      return;
    }
    const structureJson = await res.json();
    const sourceSet = new Set(sourceNodeIds);

    // Build L3 ViewModel client-side
    const l3Nodes = (structureJson.nodes || [])
      .filter((n) => sourceSet.has(n.node_id))
      .map((n) => ({ id: n.node_id, label: n.name, type: n.type, file: n.file }));

    const l3Edges = (structureJson.edges || [])
      .filter((e) => sourceSet.has(e.from_node) && sourceSet.has(e.to_node))
      .map((e) => ({ source: e.from_node, target: e.to_node }));

    state.l3GraphViewModel = { nodes: l3Nodes, edges: l3Edges };
    initGraph("graph-container", state.l3GraphViewModel);
    renderFeatureList(state.l3GraphViewModel, state.layerState);
  } catch (err) {
    renderError("載入 L3 圖形失敗：" + (err.message || "network error"));
  }
}

/**
 * Task 8.4 — switchToL1()
 * 切換回 L1，恢復選取狀態
 */
function switchToL1() {
  state.layerState = "L1";
  state.selectedFeatureId = null;
  state.selectedModuleId = null;
  renderBreadcrumb();
  if (state.l1GraphViewModel) {
    initGraph("graph-container", state.l1GraphViewModel);
    renderFeatureList(state.l1GraphViewModel, "L1");
    // Restore selection if any
    if (state.cytoscapeInstance && state.selectedId) {
      const node = state.cytoscapeInstance.getElementById(state.selectedId);
      if (node) node.select();
    }
  } else {
    loadL1Graph();
  }
}

/**
 * Task 8.5 — switchToL2FromL3()
 * 切換回 L2，恢復選取狀態
 */
function switchToL2FromL3() {
  state.layerState = "L2";
  state.selectedModuleId = null;
  renderBreadcrumb();
  if (state.l2GraphViewModel) {
    initGraph("graph-container", state.l2GraphViewModel);
    renderFeatureList(state.l2GraphViewModel, "L2");
    // Restore module selection
    if (state.cytoscapeInstance && state.selectedModuleId) {
      const node = state.cytoscapeInstance.getElementById(state.selectedModuleId);
      if (node) node.select();
    }
  } else if (state.selectedFeatureId) {
    switchToL2(state.selectedFeatureId);
  }
}

/**
 * Task 8.6 — loadLayerExplanation(featureId, layer)
 * GET /api/layer-explanation/<featureId>/<layer>（獨立於 L2 圖形資料 fetch）
 */
async function loadLayerExplanation(featureId, layer) {
  try {
    const res = await fetch(
      `${API_BASE}/api/layer-explanation/` + encodeURIComponent(featureId) + "/" + layer,
      { cache: "no-store" }
    );
    const layerExplanationEl = document.getElementById("layer-explanation");
    if (!layerExplanationEl) return;

    if (res.status === 404) {
      state.layerExplanation = null;
      layerExplanationEl.textContent = "";
      return;
    }
    if (!res.ok) return;

    const data = await res.json();
    state.layerExplanation = data.explanation || null;
    if (state.layerExplanation) {
      layerExplanationEl.textContent = "";
      const p = document.createElement("p");
      p.className = "layer-explanation-text";
      p.textContent = state.layerExplanation;
      layerExplanationEl.appendChild(p);
    }
  } catch (_) {
    // Non-fatal — explanation is optional
  }
}

/**
 * Task 8.7 — generateL2(featureId)
 * POST /api/l2/<featureId>/generate，輪詢 GET /api/update/status/<job_id>
 */
async function generateL2(featureId) {
  try {
    const res = await fetch(
      `${API_BASE}/api/l2/` + encodeURIComponent(featureId) + "/generate",
      { method: "POST" }
    );
    if (!res.ok) {
      const body = await res.json().catch(() => null);
      renderError("L2 生成失敗：" + (body?.error?.message || res.status));
      return;
    }
    const { job_id } = await res.json();
    // Poll for completion
    await pollUntilComplete(job_id, async () => {
      await switchToL2(featureId);
    });
  } catch (err) {
    renderError("L2 生成請求失敗：" + (err.message || "network error"));
  }
}

/**
 * Task 8.8 — generateLayerExplanation(featureId, layer)
 * POST /api/layer-explanation/<featureId>/<layer>/generate，輪詢完成
 */
async function generateLayerExplanation(featureId, layer) {
  try {
    const res = await fetch(
      `${API_BASE}/api/layer-explanation/` + encodeURIComponent(featureId) + "/" + layer + "/generate",
      { method: "POST" }
    );
    if (!res.ok) {
      const body = await res.json().catch(() => null);
      renderError("說明生成失敗：" + (body?.error?.message || res.status));
      return;
    }
    const { job_id } = await res.json();
    await pollUntilComplete(job_id, async () => {
      await loadLayerExplanation(featureId, layer);
    });
  } catch (err) {
    renderError("說明生成請求失敗：" + (err.message || "network error"));
  }
}

/**
 * Task 8.9 — renderBreadcrumb()
 * 根據 state.layerState 渲染 Breadcrumb 路徑
 */
function renderBreadcrumb() {
  const breadcrumbEl = document.getElementById("breadcrumb");
  if (!breadcrumbEl) return;
  breadcrumbEl.textContent = "";
  breadcrumbEl.className = "breadcrumb";

  const parts = [];

  if (state.layerState === "L1") {
    parts.push({ label: "L1", action: null });
  } else if (state.layerState === "L2") {
    const featureLabel = _getFeatureLabel(state.selectedFeatureId);
    parts.push({ label: "L1", action: switchToL1 });
    parts.push({ label: featureLabel, action: null });
    parts.push({ label: "L2", action: null });
  } else if (state.layerState === "L3") {
    const featureLabel = _getFeatureLabel(state.selectedFeatureId);
    const moduleLabel = _getModuleLabel(state.selectedModuleId);
    parts.push({ label: "L1", action: switchToL1 });
    parts.push({ label: featureLabel, action: () => switchToL2(state.selectedFeatureId) });
    parts.push({ label: "L2", action: switchToL2FromL3 });
    parts.push({ label: moduleLabel, action: null });
    parts.push({ label: "L3", action: null });
  }

  parts.forEach((part, i) => {
    if (i > 0) {
      const sep = document.createElement("span");
      sep.className = "breadcrumb-sep";
      sep.textContent = " > ";
      breadcrumbEl.appendChild(sep);
    }
    if (part.action) {
      const btn = document.createElement("button");
      btn.type = "button";
      btn.className = "breadcrumb-link";
      btn.textContent = part.label;
      btn.addEventListener("click", part.action);
      breadcrumbEl.appendChild(btn);
    } else {
      const span = document.createElement("span");
      span.className = "breadcrumb-current";
      span.textContent = part.label;
      breadcrumbEl.appendChild(span);
    }
  });

  if (els.btnBackL1) els.btnBackL1.hidden = (state.layerState === "L1");
}

function _getFeatureLabel(featureId) {
  if (!featureId) return "（未知功能）";
  const node = (state.l1GraphViewModel?.nodes || []).find((n) => n.id === featureId);
  return node?.label || featureId;
}

function _getModuleLabel(moduleId) {
  if (!moduleId) return "（未知模組）";
  const node = (state.l2GraphViewModel?.nodes || []).find((n) => n.id === moduleId);
  return node?.label || moduleId;
}

/**
 * Task 8.10 — renderFeatureList(viewModel, layerState)
 * 渲染左側 Feature_List；L1 時顯示 feature 節點，L2 時顯示 module 節點，
 * Diff_Mode 時顯示已排序的變更節點
 *
 * Task 8.11 — 點選 Feature_List 項目時，Cytoscape 實例中對應節點被程式化選取（Req 3 AC4）
 */
function renderFeatureList(viewModel, layerState) {
  const list = document.getElementById("feature-list");
  if (!list) return;
  list.textContent = "";

  const nodes = viewModel?.nodes || [];

  if (!nodes.length) {
    const div = document.createElement("div");
    div.className = "empty-state";
    div.textContent = "此層級沒有節點。";
    list.appendChild(div);
    return;
  }

  nodes.forEach((node) => {
    const btn = document.createElement("button");
    btn.type = "button";
    btn.className = "feature-card" + (node.id === state.selectedId ? " active" : "");
    btn.dataset.nodeId = node.id;

    // Label — same style as L1 featureCard
    const labelEl = document.createElement("span");
    labelEl.className = "feature-card-label";
    labelEl.textContent = node.label || node.id;

    // Description — layer-specific secondary text
    const descEl = document.createElement("span");
    descEl.className = "feature-card-desc";
    if (layerState === "L1") {
      descEl.textContent = node.description || "";
    } else if (layerState === "L2") {
      descEl.textContent = node.confidence_reason || "";
    } else if (layerState === "L3") {
      descEl.textContent = node.file || "";
    } else if (layerState === "DIFF") {
      descEl.textContent = node.change_type || "";
    }

    // Meta badge row
    const metaEl = document.createElement("div");
    metaEl.className = "feature-card-meta";
    if (layerState === "L1" || layerState === "L2") {
      if (node.confidence) {
        const badge = document.createElement("span");
        badge.className = "confidence-badge confidence-badge-" + node.confidence.toLowerCase();
        badge.textContent = node.confidence;
        metaEl.appendChild(badge);
      }
    }
    // Diff type tag — only for L1, only when diff data is available
    if (layerState === "L1" && state.updateModel?.diff_available) {
      const DIFF_LABELS = {
        added:              "+ 新增",
        removed:            "- 移除",
        attribute_changed:  "~ 屬性變更",
        dependency_changed: "≠ 依賴變更",
      };
      const change = state.updateModel.changes?.find(c => c.id === node.id);
      if (change?.change_type) {
        const tag = document.createElement("span");
        tag.className = "diff-tag diff-tag-" + change.change_type;
        tag.textContent = DIFF_LABELS[change.change_type] ?? change.change_type;
        metaEl.appendChild(tag);
      }
    }
    if (layerState === "L3") {
      if (node.type) {
        const badge = document.createElement("span");
        badge.className = "confidence-badge";
        badge.textContent = node.type;
        metaEl.appendChild(badge);
      }
    } else if (layerState === "DIFF") {
      btn.classList.add("change-" + (node.change_type || ""));
      if (node.change_type) {
        const badge = document.createElement("span");
        badge.className = "change-badge change-" + node.change_type;
        badge.textContent = changeSymbol(node.change_type) + " " + node.change_type;
        metaEl.appendChild(badge);
      }
    }

    btn.append(labelEl, descEl, metaEl);
    btn.addEventListener("click", () => {
      // Programmatically select node in Cytoscape (Req 3 AC4)
      if (state.cytoscapeInstance) {
        state.cytoscapeInstance.elements().unselect();
        const cyNode = state.cytoscapeInstance.getElementById(node.id);
        if (cyNode) {
          cyNode.select();
          state.cytoscapeInstance.animate({ fit: { eles: cyNode, padding: 50 } });
        }
      }
      // Update detail panel
      if (layerState === "L1") {
        state.selectedFeatureId = node.id;
        renderDetailPanelL1(node);
      } else if (layerState === "L2") {
        state.selectedModuleId = node.id;
        renderDetailPanelL2(node);
      } else if (layerState === "L3") {
        renderDetailPanelL3(node);
      } else if (layerState === "DIFF") {
        renderDetailPanelDiff(node);
      }
      // Sync active state
      list.querySelectorAll(".feature-card").forEach((b) => b.classList.remove("active"));
      btn.classList.add("active");
    });

    list.appendChild(btn);
  });
}

/**
 * pollUntilComplete(jobId, onComplete)
 * 輪詢 GET /api/update/status/<jobId> 直到任務完成或失敗
 */
async function pollUntilComplete(jobId, onComplete) {
  const maxAttempts = 60;
  let attempts = 0;
  return new Promise((resolve) => {
    const handle = setInterval(async () => {
      attempts++;
      if (attempts > maxAttempts) {
        clearInterval(handle);
        renderError("任務逾時，請稍後重試。");
        resolve();
        return;
      }
      try {
        const res = await fetch(`${API_BASE}/api/update/status/` + jobId, { cache: "no-store" });
        if (!res.ok) { clearInterval(handle); resolve(); return; }
        const job = await res.json();
        if (job.status === "completed") {
          clearInterval(handle);
          await onComplete();
          resolve();
        } else if (job.status === "failed") {
          clearInterval(handle);
          renderError("任務失敗：" + (job.error_message || "未知錯誤"));
          resolve();
        }
      } catch (_) {
        clearInterval(handle);
        resolve();
      }
    }, 1500);
  });
}

// ============================================================
// Phase UI-3: Task 9 — Detail Panel 與差異模式
// ============================================================

/**
 * Task 9.1 — renderDetailPanelL1(node)
 * 顯示 label、description、confidence、trigger_description、Enter L2 按鈕、Data source 欄位
 */
function renderDetailPanelL1(node) {
  const content = document.getElementById("detail-content");
  const detailSrc = document.getElementById("detail-source");
  if (!content) return;

  if (detailSrc) detailSrc.textContent = "L1Output.features[feature_id=" + node.id + "]";
  content.className = "detail-content";
  content.textContent = "";

  content.appendChild(detailSection("功能名稱", node.label));
  content.appendChild(detailSection("描述", node.description));
  content.appendChild(detailSection("信心等級", node.confidence));
  content.appendChild(detailSection("觸發說明", node.trigger_description));

  // Enter L2 button (only in Single_Version_Mode, not Diff_Mode)
  const enterL2Btn = document.createElement("button");
  enterL2Btn.type = "button";
  enterL2Btn.className = "action-button";
  enterL2Btn.textContent = "進入 L2";
  enterL2Btn.addEventListener("click", () => switchToL2(node.id));
  content.appendChild(enterL2Btn);

  // Data source attribution
  content.appendChild(attributionSection("L1Output.features[feature_id=" + node.id + "]"));
}

/**
 * Task 9.2 — renderDetailPanelL2(node)
 * 顯示 label、confidence、source_nodes 列表、Enter L3 按鈕、Expand Explanation 按鈕；
 * anomalies 列表從 state.l2GraphViewModel.anomalies 讀取（Req 6 AC4）
 */
function renderDetailPanelL2(node) {
  const content = document.getElementById("detail-content");
  const detailSrc = document.getElementById("detail-source");
  if (!content) return;

  if (detailSrc) detailSrc.textContent = "L2Output.modules[module_id=" + node.id + "]";
  content.className = "detail-content";
  content.textContent = "";

  content.appendChild(detailSection("模組名稱", node.label));
  content.appendChild(detailSection("信心等級", node.confidence));
  content.appendChild(listDetailSection("Source Nodes", node.source_nodes || []));

  // Anomalies from state.l2GraphViewModel.anomalies (Req 6 AC4)
  const anomalies = state.l2GraphViewModel?.anomalies || [];
  if (anomalies.length > 0) {
    const anomalySection = document.createElement("section");
    anomalySection.className = "detail-section";
    const h = document.createElement("h3");
    h.textContent = "異常";
    anomalySection.appendChild(h);
    anomalies.forEach((a) => {
      const item = document.createElement("div");
      item.className = "anomaly-item";
      item.textContent = a.anomaly_type + "：" + a.explanation;
      anomalySection.appendChild(item);
    });
    content.appendChild(anomalySection);
  }

  // Enter L3 button
  const enterL3Btn = document.createElement("button");
  enterL3Btn.type = "button";
  enterL3Btn.className = "action-button";
  enterL3Btn.textContent = "進入 L3";
  enterL3Btn.addEventListener("click", () => switchToL3(node.id));
  content.appendChild(enterL3Btn);

  // Expand Explanation button
  const expandBtn = document.createElement("button");
  expandBtn.type = "button";
  expandBtn.className = "action-button";
  expandBtn.textContent = "展開說明";
  expandBtn.addEventListener("click", () => {
    const layerExplanationEl = document.getElementById("layer-explanation");
    if (state.layerExplanation) {
      if (layerExplanationEl) layerExplanationEl.style.display = "block";
    } else {
      // No cache — show generate prompt
      if (layerExplanationEl) {
        layerExplanationEl.textContent = "";
        const genBtn = document.createElement("button");
        genBtn.type = "button";
        genBtn.className = "action-button";
        genBtn.textContent = "生成 L2 說明";
        genBtn.addEventListener("click", () => generateLayerExplanation(state.selectedFeatureId, "l2"));
        layerExplanationEl.appendChild(genBtn);
      }
    }
  });
  content.appendChild(expandBtn);

  content.appendChild(attributionSection("L2Output.modules[module_id=" + node.id + "]"));
}

/**
 * Task 9.3 — renderDetailPanelL3(node)
 * 顯示 label、type、file、Data source 欄位
 */
function renderDetailPanelL3(node) {
  const content = document.getElementById("detail-content");
  const detailSrc = document.getElementById("detail-source");
  if (!content) return;

  if (detailSrc) detailSrc.textContent = "StructureJSON.nodes[node_id=" + node.id + "]";
  content.className = "detail-content";
  content.textContent = "";

  content.appendChild(detailSection("名稱", node.label));
  content.appendChild(detailSection("類型", node.type));
  content.appendChild(detailSection("檔案", node.file));
  content.appendChild(attributionSection("StructureJSON.nodes[node_id=" + node.id + "]"));
}

/**
 * Task 9.4 — renderDetailPanelDiff(node)
 * 顯示 change_type、current_label、baseline_label、risk_flags（無 Enter L2 按鈕）
 * Req 9 AC4: NO Enter L2 button in Diff_Mode
 */
function renderDetailPanelDiff(node) {
  const content = document.getElementById("detail-content");
  const detailSrc = document.getElementById("detail-source");
  if (!content) return;

  if (detailSrc) detailSrc.textContent = "UpdateReport.l1_changes[feature_id=" + node.id + "]";
  content.className = "detail-content";
  content.textContent = "";

  content.appendChild(detailSection("變更類型", node.change_type));
  content.appendChild(detailSection("現在名稱", node.current_label));
  content.appendChild(detailSection("原始名稱", node.baseline_label));
  content.appendChild(listDetailSection("風險標記", node.risk_flags || []));
  // NO Enter L2 button in Diff_Mode (Req 9 AC4)
  content.appendChild(attributionSection("UpdateReport.l1_changes[feature_id=" + node.id + "]"));
}

/**
 * Task 9.5 — toggleDiffSort(mode)
 * 切換 state.diffSortMode，重新渲染 Feature_List（client-side，不呼叫 API）
 */
function toggleDiffSort(mode) {
  state.diffSortMode = mode;
  // Re-render Feature_List client-side (no API call)
  if (state.diffGraphViewModel) {
    const sorted = applyDiffSort(state.diffGraphViewModel.nodes, mode);
    const sortedVm = Object.assign({}, state.diffGraphViewModel, { nodes: sorted });
    renderFeatureList(sortedVm, "DIFF");
  }
}

/**
 * Task 9.6 — applyDiffSort(nodes, mode)
 * 根據 mode 排序 nodes，回傳新陣列
 */
function applyDiffSort(nodes, mode) {
  if (mode === "semantic") {
    // Sort by edit distance magnitude (descending)
    return [...nodes].sort((a, b) => {
      const magA = _semanticMagnitude(a);
      const magB = _semanticMagnitude(b);
      return magB - magA;
    });
  }
  // Default: risk-first sort
  const RISK_PRIORITY = { out_of_scope: 0, vulnerability: 1, semantic_drift: 2 };
  const CHANGE_PRIORITY = { added: 3, attribute_changed: 4, dependency_changed: 5, removed: 6 };
  return [...nodes].sort((a, b) => {
    const riskA = Math.min(...(a.risk_flags || []).map((f) => RISK_PRIORITY[f] ?? 99), 3);
    const riskB = Math.min(...(b.risk_flags || []).map((f) => RISK_PRIORITY[f] ?? 99), 3);
    if (riskA !== riskB) return riskA - riskB;
    return (CHANGE_PRIORITY[a.change_type] ?? 7) - (CHANGE_PRIORITY[b.change_type] ?? 7);
  });
}

function _semanticMagnitude(node) {
  const a1 = node.current_label || "";
  const b1 = node.baseline_label || "";
  const a2 = node.current_description || "";
  const b2 = node.baseline_description || "";
  return _levenshteinApprox(a1, b1) + _levenshteinApprox(a2, b2);
}

function _levenshteinApprox(a, b) {
  // Simple approximation: max(len) * (1 - common/max)
  if (!a && !b) return 0;
  const maxLen = Math.max(a.length, b.length);
  if (maxLen === 0) return 0;
  let common = 0;
  const shorter = a.length <= b.length ? a : b;
  const longer = a.length <= b.length ? b : a;
  for (let i = 0; i < shorter.length; i++) {
    if (longer.includes(shorter[i])) common++;
  }
  return Math.round(maxLen * (1 - common / maxLen));
}

// ============================================================
// Graph drawer
// ============================================================

function openGraphDrawer() {
  els.graphDrawer?.classList.add("open");
  els.graphDrawer?.removeAttribute("aria-hidden");
  if (els.graphBackdrop) els.graphBackdrop.hidden = false;
  // Re-fit after drawer transition (drawer now has real dimensions)
  if (state.cytoscapeInstance) {
    setTimeout(() => state.cytoscapeInstance.fit(undefined, 40), 320);
  }
}

function closeGraphDrawer() {
  els.graphDrawer?.classList.remove("open");
  els.graphDrawer?.setAttribute("aria-hidden", "true");
  if (els.graphBackdrop) els.graphBackdrop.hidden = true;
}

// ============================================================
// Legend
// ============================================================

function renderLegend() {
  const panel = document.getElementById("legend-panel");
  if (!panel) return;
  panel.textContent = "";

  const items = [
    { color: "#4caf50", label: "新增" },
    { color: "#f44336", label: "移除" },
    { color: "#ff9800", label: "修改" },
    { color: "#9e9e9e", label: "未變更" },
  ];

  items.forEach(({ color, label }) => {
    const item = document.createElement("span");
    item.className = "legend-item";
    const swatch = document.createElement("span");
    swatch.className = "legend-swatch";
    swatch.style.background = color;
    const text = document.createTextNode(label);
    item.append(swatch, text);
    panel.appendChild(item);
  });
}

// ============================================================
// Zoom controls
// ============================================================

function initZoomControls(cy) {
  if (els.zoomControls) els.zoomControls.hidden = false;

  const fitBtn = document.getElementById("btn-zoom-fit");
  const inBtn  = document.getElementById("btn-zoom-in");
  const outBtn = document.getElementById("btn-zoom-out");

  if (fitBtn) fitBtn.onclick = () => { cy.fit(undefined, 60); if (cy.zoom() > 0.7) { cy.zoom(0.7); cy.center(); } };
  if (inBtn)  inBtn.onclick  = () => cy.zoom({
    level: cy.zoom() * 1.25,
    renderedPosition: { x: cy.width() / 2, y: cy.height() / 2 },
  });
  if (outBtn) outBtn.onclick = () => cy.zoom({
    level: cy.zoom() / 1.25,
    renderedPosition: { x: cy.width() / 2, y: cy.height() / 2 },
  });
}

function hideZoomControls() {
  if (els.zoomControls) els.zoomControls.hidden = true;
}

// ============================================================
// L2 not-analyzed empty state
// ============================================================

function renderL2NotAnalyzed(featureId) {
  const featureLabel = _getFeatureLabel(featureId);

  function makeNotAnalyzedBlock(withButton) {
    const wrap = document.createElement("div");
    wrap.className = "not-analyzed-state";

    const title = document.createElement("p");
    title.className = "not-analyzed-title";
    title.textContent = "「" + featureLabel + "」的 L2 層尚未分析";

    wrap.appendChild(title);

    if (withButton) {
      const btn = document.createElement("button");
      btn.type = "button";
      btn.className = "action-button";
      btn.textContent = "生成 L2 分析";
      btn.addEventListener("click", () => {
        btn.disabled = true;
        btn.textContent = "生成中…";
        generateL2(featureId);
      });
      wrap.appendChild(btn);

      const sep = document.createElement("p");
      sep.className = "not-analyzed-hint";
      sep.textContent = "或使用 CLI：";
      const cmd = document.createElement("code");
      cmd.className = "not-analyzed-cmd";
      cmd.textContent = "the-door analyze \"<專案路徑>\"";
      wrap.append(sep, cmd);
    }

    return wrap;
  }

  // Feature list area (main content)
  const list = document.getElementById("feature-list");
  if (list) {
    list.textContent = "";
    list.appendChild(makeNotAnalyzedBlock(true));
  }

  // Graph container (inside drawer)
  const container = document.getElementById("graph-container");
  if (container) {
    container.textContent = "";
    container.appendChild(makeNotAnalyzedBlock(false));
  }
}

/** 將當前 L1 資料寫入 sessionStorage 並開啟心智圖 popup。 */
function switchToMindmap() {
  const data = {
    project: state.projectStatus?.project_path ?? "專案",
    nodes: state.l1GraphViewModel?.nodes ?? [],
    diffNodes: state.updateModel?.changes ?? [],       // [{id, change_type, risk_flags}]
    diffAvailable: state.updateModel?.diff_available ?? false,
  };
  sessionStorage.setItem("mindmap-data", JSON.stringify(data));
  window.open("./mindmap-popup.html", "mindmap",
    "width=960,height=720,resizable=yes,scrollbars=yes");
}

import { state } from "./state.js";
import { els } from "./dom.js";
import { API_BASE } from "./api.js";
import { buildViewModelFromReport, snapshotLabel } from "./viewmodel.js";
import { renderTopBar, updateLogoMark } from "./ui-topbar.js";
import { renderChangeList } from "./ui-list.js";
import { renderDetailPanel, renderError } from "./ui-detail.js";
import {
  showUpdateModal,
  hideUpdateModal,
  showModalError,
  submitUpdate,
} from "./ui-modal.js";
import {
  loadL1Graph,
  switchToL1,
  switchToL2,
  switchToMindmap,
} from "./layers.js";
import {
  initGraph,
  renderLegend,
  openGraphDrawer,
  closeGraphDrawer,
} from "./graph.js";
import { renderOnboardingCard } from "./onboarding.js";

export function render() {
  renderTopBar();
  renderChangeList({
    onSelectFeature,
    onSelectChange,
  });
  renderDetailPanel({ onEnterL2: switchToL2 });
  updateLogoMark();
  document
    .querySelector(".app-shell")
    ?.classList.toggle("diff-mode", state.mode === "diff");
  const banner = document.getElementById("diff-mode-banner");
  if (banner) banner.hidden = state.mode !== "diff";
}

// Diff-mode card click: full re-render via renderDiffDetailPanel.
function onSelectChange(id) {
  state.selectedId = id;
  render();
}

// Non-diff L1 card click: state mutation + Cytoscape sync, then full render()
// to keep the default-load and post-click detail panels identical (same fields,
// same Enter L2 button).
function onSelectFeature(feature) {
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
  render();
}

function firstSelectableId() {
  if (state.mode === "diff") {
    return state.updateModel?.changes?.[0]?.id ?? null;
  }
  return state.l1Model?.features?.[0]?.id ?? null;
}

export async function setMode(mode) {
  const hasDiff = state.updateModel?.diff_available === true;
  const hasVersionCompare = !!(
    state.versionA &&
    state.versionB &&
    state.versionA !== state.versionB
  );
  if (mode === "diff" && !hasDiff && !hasVersionCompare) return;
  state.mode = mode;
  state.selectedId = firstSelectableId();
  render();

  if (hasVersionCompare && !hasDiff) {
    if (mode === "baseline") {
      await loadL1Graph(state.versionA);
    } else if (mode === "current") {
      await loadL1Graph(state.versionB);
    } else if (mode === "diff") {
      await loadL1Graph(state.versionB);
    }
    render();
  }
}

function handleApiError(status, body) {
  const msg = body?.error?.message || "HTTP " + status;
  renderError("API 錯誤：" + msg);
}

async function loadOnboardingIfEmpty() {
  // S3.1: fetch /api/status and render the onboarding card when the project
  // has no snapshots. Wrapped in try/catch so a failing /api/status (e.g.
  // older backend, network blip) never breaks the rest of app startup.
  try {
    const res = await fetch(`${API_BASE}/api/status`, { cache: "no-store" });
    if (!res.ok) return;
    const payload = await res.json();
    const container =
      document.querySelector(".canvas-area") ||
      document.querySelector(".workspace");
    if (container) renderOnboardingCard(container, payload);
  } catch (_) {
    // non-fatal — onboarding is purely additive
  }
}

async function loadProjectStatus() {
  try {
    const res = await fetch(`${API_BASE}/api/project`, { cache: "no-store" });
    if (!res.ok) {
      const body = await res.json().catch(() => null);
      renderError(
        body?.error?.message || "無法取得專案狀態（" + res.status + "）",
      );
      return;
    }
    state.projectStatus = await res.json();
    await loadFromApi();
  } catch (_) {
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
    state.updateModel = null;
    els.summaryText.textContent =
      "尚未有分析報告。請執行 the-door update 或點擊「重新分析」。";
  }

  if (ad.has_snapshots) {
    await loadSnapshots();
  }

  const hasVersionCompare = !!(
    state.versionA &&
    state.versionB &&
    state.versionA !== state.versionB
  );
  state.mode = "baseline";
  state.selectedId = firstSelectableId();
  render();

  if (ad.has_snapshots) {
    await loadL1Graph(hasVersionCompare ? state.versionB : null);
    render();
  }
}

async function loadReport() {
  try {
    const res = await fetch(`${API_BASE}/api/report/latest`, {
      cache: "no-store",
    });
    if (res.status === 404) {
      state.updateModel = null;
      return;
    }
    if (!res.ok) {
      const body = await res.json().catch(() => null);
      handleApiError(res.status, body);
      return;
    }
    const report = await res.json();
    state.updateModel = buildViewModelFromReport(report);
  } catch (err) {
    renderError("載入報告失敗：" + (err.message || "network error"));
  }
}

async function loadSnapshots() {
  try {
    const res = await fetch(`${API_BASE}/api/snapshots`, { cache: "no-store" });
    if (!res.ok) return;
    const data = await res.json();
    state.snapshots = data.snapshots || [];
    state.versionA = state.snapshots[1]?.version_id ?? null;
    state.versionB = state.snapshots[0]?.version_id ?? null;
    populateVersionSelectors();
  } catch (_) {
    // non-fatal
  }
}

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

function populateVersionSelectors() {
  const selA = document.getElementById("select-version-a");
  const selB = document.getElementById("select-version-b");
  const selectorBar = document.getElementById("version-selector-bar");
  if (!selA || !selB || !selectorBar) return;

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
    sel.value = idx === 0 ? state.versionA : state.versionB;
  });

  selA.onchange = async () => {
    state.versionA = selA.value;
    state.mode = "diff";
    renderTopBar();
    await loadL1Graph(state.versionB ?? state.versionA);
    render();
  };
  selB.onchange = async () => {
    state.versionB = selB.value;
    state.mode = "diff";
    renderTopBar();
    await loadL1Graph(state.versionB);
    render();
  };
}

export function init() {
  els.btnDiff.addEventListener("click", () => setMode("diff"));
  els.btnBaseline.addEventListener("click", () => setMode("baseline"));
  els.btnCurrent.addEventListener("click", () => setMode("current"));
  els.btnReanalyze.addEventListener("click", () => showUpdateModal());
  els.btnModalCancel.addEventListener("click", () => hideUpdateModal());
  els.btnModalSubmit.addEventListener("click", () => {
    const oldPath = els.inputOldPath.value.trim();
    const newPath = els.inputNewPath.value.trim();
    if (!oldPath || !newPath) {
      showModalError("請輸入舊版與新版路徑。");
      return;
    }
    hideUpdateModal();
    submitUpdate(oldPath, newPath, {
      onComplete: () => {
        loadFromApi();
      },
      onError: renderError,
    });
  });
  els.btnGraphToggle?.addEventListener("click", openGraphDrawer);
  els.btnDrawerClose?.addEventListener("click", closeGraphDrawer);
  els.graphBackdrop?.addEventListener("click", closeGraphDrawer);
  els.btnMindmap?.addEventListener("click", switchToMindmap);
  els.btnBackL1?.addEventListener("click", switchToL1);
  loadProjectStatus();
  loadOnboardingIfEmpty();
}

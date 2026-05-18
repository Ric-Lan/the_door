import { state } from "./state.js";
import { els } from "./dom.js";
import { API_BASE } from "./api.js";
import { initGraph, renderLegend } from "./graph.js";
import { updateLogoMark } from "./ui-topbar.js";
import { changeSymbol } from "./ui-list.js";
import {
  renderError,
  renderDetailPanelL1,
  renderDetailPanelL2,
  renderDetailPanelL3,
  renderDetailPanelDiff,
} from "./ui-detail.js";

const DIFF_LABELS = {
  added: "+ 新增",
  removed: "- 移除",
  attribute_changed: "~ 屬性變更",
  dependency_changed: "≠ 依賴變更",
};

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

export async function loadL1Graph(versionId = null) {
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

    if (!state.updateModel?.diff_available) {
      state.selectedId = state.l1Model.features[0]?.id ?? null;
    }

    if (state.versionA && state.versionB && state.versionA !== state.versionB) {
      await loadDiffOverlay(state.versionA, state.versionB);
    }
    // NOTE: Top-bar / change-list / detail-panel rendering is the caller's
    // responsibility (app.js). loadL1Graph only updates state + graph + legend
    // + breadcrumb (its own UI concerns). This avoids needing callbacks here
    // and matches the orchestrator pattern.
  } catch (err) {
    renderError("載入 L1 圖形失敗：" + (err.message || "network error"));
  }
}

export async function loadDiffOverlay(baselineId, currentId) {
  if (!baselineId || !currentId || baselineId === currentId) return;
  try {
    const url = `${API_BASE}/api/diff?baseline=${encodeURIComponent(baselineId)}&current=${encodeURIComponent(currentId)}`;
    const res = await fetch(url, { cache: "no-store" });
    if (!res.ok) return;
    const data = await res.json();

    state.versionDiff = data;

    const nodeStates = data.node_states || {};
    if (state.cytoscapeInstance) {
      state.cytoscapeInstance.nodes().forEach((node) => {
        const diffState = nodeStates[node.id()];
        if (diffState && diffState !== "unchanged") {
          node.data("change_type", diffState);
        } else {
          node.removeData("change_type");
        }
      });
    }

    const s = data.summary || {};
    const total = s.total_changed ?? 0;
    if (total > 0) {
      els.summaryText.textContent =
        `版本比較：${s.added ?? 0} 新增 / ${s.removed ?? 0} 移除 / ` +
        `${(s.attribute_changed ?? 0) + (s.dependency_changed ?? 0)} 修改`;
    } else {
      els.summaryText.textContent = "版本比較：兩版本功能完全相同。";
    }
    // Top-bar / change-list rendering is the caller's responsibility (app.js).
  } catch (e) {
    console.warn("Diff overlay failed:", e);
  }
}

export async function switchToL2(featureId) {
  state.selectedFeatureId = featureId;
  state.layerState = "L2";
  updateLogoMark();
  renderBreadcrumb();

  loadLayerExplanation(featureId, "l2");

  try {
    const res = await fetch(`${API_BASE}/api/l2/${encodeURIComponent(featureId)}`, {
      cache: "no-store",
    });
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

export async function switchToL3(moduleId) {
  state.selectedModuleId = moduleId;
  state.layerState = "L3";
  updateLogoMark();
  renderBreadcrumb();

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

export function switchToL1() {
  state.layerState = "L1";
  state.selectedFeatureId = null;
  state.selectedModuleId = null;
  updateLogoMark();
  renderBreadcrumb();
  if (state.l1GraphViewModel) {
    initGraph("graph-container", state.l1GraphViewModel);
    renderFeatureList(state.l1GraphViewModel, "L1");
    if (state.cytoscapeInstance && state.selectedId) {
      const node = state.cytoscapeInstance.getElementById(state.selectedId);
      if (node) node.select();
    }
  } else {
    loadL1Graph();
  }
}

export function switchToL2FromL3() {
  state.layerState = "L2";
  state.selectedModuleId = null;
  updateLogoMark();
  renderBreadcrumb();
  if (state.l2GraphViewModel) {
    initGraph("graph-container", state.l2GraphViewModel);
    renderFeatureList(state.l2GraphViewModel, "L2");
  } else if (state.selectedFeatureId) {
    switchToL2(state.selectedFeatureId);
  }
}

export async function loadLayerExplanation(featureId, layer) {
  try {
    const res = await fetch(
      `${API_BASE}/api/layer-explanation/${encodeURIComponent(featureId)}/${layer}`,
      { cache: "no-store" },
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
    // non-fatal
  }
}

export async function generateL2(featureId) {
  try {
    const res = await fetch(
      `${API_BASE}/api/l2/${encodeURIComponent(featureId)}/generate`,
      { method: "POST" },
    );
    if (!res.ok) {
      const body = await res.json().catch(() => null);
      renderError("L2 生成失敗：" + (body?.error?.message || res.status));
      return;
    }
    const { job_id } = await res.json();
    await pollUntilComplete(job_id, async () => {
      await switchToL2(featureId);
    });
  } catch (err) {
    renderError("L2 生成請求失敗：" + (err.message || "network error"));
  }
}

export async function generateLayerExplanation(featureId, layer) {
  try {
    const res = await fetch(
      `${API_BASE}/api/layer-explanation/${encodeURIComponent(featureId)}/${layer}/generate`,
      { method: "POST" },
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

export function renderBreadcrumb() {
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

  if (els.btnBackL1) els.btnBackL1.hidden = state.layerState === "L1";
}

export async function pollUntilComplete(jobId, onComplete) {
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
        const res = await fetch(`${API_BASE}/api/update/status/${jobId}`, { cache: "no-store" });
        if (!res.ok) {
          clearInterval(handle);
          resolve();
          return;
        }
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

export function renderFeatureList(viewModel, layerState) {
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

    const labelEl = document.createElement("span");
    labelEl.className = "feature-card-label";
    labelEl.textContent = node.label || node.id;

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
    if (layerState === "L1" && state.updateModel?.diff_available) {
      const change = state.updateModel.changes?.find((c) => c.id === node.id);
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
      if (state.cytoscapeInstance) {
        state.cytoscapeInstance.elements().unselect();
        const cyNode = state.cytoscapeInstance.getElementById(node.id);
        if (cyNode) {
          cyNode.select();
          state.cytoscapeInstance.animate({ fit: { eles: cyNode, padding: 50 } });
        }
      }
      if (layerState === "L1") {
        state.selectedFeatureId = node.id;
        renderDetailPanelL1(node, { onEnterL2: switchToL2 });
      } else if (layerState === "L2") {
        state.selectedModuleId = node.id;
        renderDetailPanelL2(node, {
          onEnterL3: switchToL3,
          onGenerateLayerExplanation: generateLayerExplanation,
        });
      } else if (layerState === "L3") {
        renderDetailPanelL3(node);
      } else if (layerState === "DIFF") {
        renderDetailPanelDiff(node);
      }
      list.querySelectorAll(".feature-card").forEach((b) => b.classList.remove("active"));
      btn.classList.add("active");
    });

    list.appendChild(btn);
  });
}

export function renderL2NotAnalyzed(featureId) {
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
      cmd.textContent = 'the-door analyze "<專案路徑>"';
      wrap.append(sep, cmd);
    }

    return wrap;
  }

  const list = document.getElementById("feature-list");
  if (list) {
    list.textContent = "";
    list.appendChild(makeNotAnalyzedBlock(true));
  }

  const container = document.getElementById("graph-container");
  if (container) {
    container.textContent = "";
    container.appendChild(makeNotAnalyzedBlock(false));
  }
}

export function buildMindmapData(state) {
  const projectName =
    (state.projectStatus?.project_path ?? "")
      .split(/[\/\\]/)
      .filter(Boolean)
      .pop() || "專案";
  const nodes = state.l1GraphViewModel?.nodes ?? [];

  let diffNodes = [];
  let diffAvailable = false;

  if (state.updateModel?.diff_available === true) {
    diffNodes = state.updateModel.changes ?? [];
    diffAvailable = true;
  } else if (state.versionDiff?.node_states) {
    diffNodes = Object.entries(state.versionDiff.node_states)
      .filter(([, st]) => st !== "unchanged")
      .map(([id, change_type]) => ({ id, change_type }));
    diffAvailable = diffNodes.length > 0;
  }

  return { project: projectName, nodes, diffNodes, diffAvailable };
}

export function switchToMindmap() {
  const data = buildMindmapData(state);
  sessionStorage.setItem("mindmap-data", JSON.stringify(data));
  window.open(
    "./mindmap-popup.html",
    "mindmap",
    "width=960,height=720,resizable=yes,scrollbars=yes",
  );
}

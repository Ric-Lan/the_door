const state = {
  single: null,
  update: null,
  mode: "single",
  selectedId: null,
};

const els = {
  singleMode: document.getElementById("single-mode"),
  diffMode: document.getElementById("diff-mode"),
  featureCount: document.getElementById("feature-count"),
  unclassifiedCount: document.getElementById("unclassified-count"),
  infraCount: document.getElementById("infra-count"),
  diffStatus: document.getElementById("diff-status"),
  listTitle: document.getElementById("list-title"),
  listSource: document.getElementById("list-source"),
  canvasTitle: document.getElementById("canvas-title"),
  canvasSource: document.getElementById("canvas-source"),
  featureList: document.getElementById("feature-list"),
  summaryText: document.getElementById("summary-text"),
  graphNodes: document.getElementById("graph-nodes"),
  relationsList: document.getElementById("relations-list"),
  detailSource: document.getElementById("detail-source"),
  detailContent: document.getElementById("detail-content"),
};

els.singleMode.addEventListener("click", () => setMode("single"));
els.diffMode.addEventListener("click", () => setMode("diff"));

loadViewModels();

async function loadViewModels() {
  try {
    state.single = await loadJson("./data/self-analysis-view-model.json");
    state.update = await loadOptionalJson("./data/mock-update-view-model.json");
    state.mode = state.update?.diff_available ? "diff" : "single";
    state.selectedId = firstSelectableId();
    render();
  } catch (error) {
    renderError(error);
  }
}

async function loadJson(path) {
  const response = await fetch(path, { cache: "no-store" });
  if (!response.ok) {
    throw new Error(`Failed to load ${path}: ${response.status}`);
  }
  return response.json();
}

async function loadOptionalJson(path) {
  const response = await fetch(path, { cache: "no-store" });
  if (!response.ok) return null;
  return response.json();
}

function setMode(mode) {
  if (mode === "diff" && !state.update?.diff_available) return;
  state.mode = mode;
  state.selectedId = firstSelectableId();
  render();
}

function firstSelectableId() {
  if (state.mode === "diff") {
    return state.update?.changes?.[0]?.id || null;
  }
  return state.single?.features?.[0]?.id || null;
}

function activeModel() {
  return state.mode === "diff" ? state.update : state.single;
}

function render() {
  const model = activeModel();
  if (!model) return;

  renderModeButtons();
  renderStatus();
  els.summaryText.textContent = model.summary || "未提供";

  if (state.mode === "diff") {
    renderDiffMode(model);
  } else {
    renderSingleMode(model);
  }
}

function renderModeButtons() {
  els.singleMode.classList.toggle("active", state.mode === "single");
  els.diffMode.classList.toggle("active", state.mode === "diff");
  els.diffMode.disabled = !state.update?.diff_available;
}

function renderStatus() {
  if (state.mode === "diff") {
    const counts = state.update.change_counts;
    els.featureCount.textContent = `${counts.added} added`;
    els.unclassifiedCount.textContent = `${counts.attribute_changed + counts.dependency_changed} modified`;
    els.infraCount.textContent = `${counts.removed} removed`;
    els.diffStatus.textContent = "Diff mock";
    return;
  }

  const stats = state.single.stats;
  els.featureCount.textContent = `${stats.feature_count} features`;
  els.unclassifiedCount.textContent = `${stats.unclassified_count} unclassified`;
  els.infraCount.textContent = `${stats.infrastructure_count} infrastructure`;
  els.diffStatus.textContent = state.single.diff_available ? "Diff available" : "Diff unavailable";
}

function renderSingleMode(model) {
  els.listTitle.textContent = "功能索引";
  els.listSource.textContent = "來自 L1Output.features";
  els.canvasTitle.textContent = "L1 功能總覽";
  els.canvasSource.textContent = "單版本模式；沒有 DiffResult 時不啟用差異模式";
  renderFeatureList(model.features || []);
  renderFeatureNodes(model.features || []);
  renderRelations(model.relations || []);
  renderFeatureDetail(model);
}

function renderDiffMode(model) {
  els.listTitle.textContent = "變更清單";
  els.listSource.textContent = "來自 mock UpdateReport.l1_changes";
  els.canvasTitle.textContent = "差異模式";
  els.canvasSource.textContent = "MOCK 資料；只驗證 UI 行為，不代表真實分析結果";
  renderChangeList(model.changes || []);
  renderChangeNodes(model.changes || []);
  renderPipelineSteps(model.pipeline?.steps || []);
  renderChangeDetail(model);
}

function renderFeatureList(features) {
  els.featureList.textContent = "";
  features.forEach((feature, index) => {
    els.featureList.appendChild(
      listButton({
        id: feature.id,
        index,
        label: feature.label,
        meta: `${feature.confidence} confidence`,
      }),
    );
  });
}

function renderChangeList(changes) {
  els.featureList.textContent = "";
  changes.forEach((change, index) => {
    els.featureList.appendChild(
      listButton({
        id: change.id,
        index,
        label: change.label,
        meta: change.change_type,
      }),
    );
  });
}

function listButton({ id, index, label, meta }) {
  const button = document.createElement("button");
  button.className = id === state.selectedId
    ? "feature-button active"
    : "feature-button";
  button.type = "button";
  button.addEventListener("click", () => selectItem(id));

  const number = document.createElement("span");
  number.className = "feature-index";
  number.textContent = String(index + 1).padStart(2, "0");

  const body = document.createElement("span");
  const labelEl = document.createElement("span");
  labelEl.className = "feature-label";
  labelEl.textContent = label;
  const metaEl = document.createElement("span");
  metaEl.className = "feature-meta";
  metaEl.textContent = meta;
  body.append(labelEl, metaEl);

  button.append(number, body);
  return button;
}

function renderFeatureNodes(features) {
  els.graphNodes.textContent = "";
  features.forEach((feature) => {
    const node = graphNode(feature.id);
    const title = document.createElement("span");
    title.className = "node-title";
    title.textContent = feature.label;
    const description = document.createElement("span");
    description.className = "node-description";
    description.textContent = feature.trigger_description;
    node.append(title, description);
    els.graphNodes.appendChild(node);
  });
}

function renderChangeNodes(changes) {
  els.graphNodes.textContent = "";
  changes.forEach((change) => {
    const node = graphNode(change.id);
    const badge = document.createElement("span");
    badge.className = `change-badge change-${change.change_type}`;
    badge.textContent = changeSymbol(change.change_type);
    const title = document.createElement("span");
    title.className = "node-title";
    title.textContent = change.label;
    const description = document.createElement("span");
    description.className = "node-description";
    description.textContent = change.change_type;
    node.append(badge, title, description);
    els.graphNodes.appendChild(node);
  });
}

function graphNode(id) {
  const node = document.createElement("button");
  node.className = id === state.selectedId
    ? "graph-node active"
    : "graph-node";
  node.type = "button";
  node.addEventListener("click", () => selectItem(id));
  return node;
}

function renderRelations(relations) {
  els.relationsList.textContent = "";
  if (!relations.length) {
    renderEmpty(els.relationsList, "沒有可顯示的關係。");
    return;
  }

  relations.forEach((relation) => {
    const row = document.createElement("div");
    row.className = "relation-row";
    const from = document.createElement("span");
    from.textContent = relation.from;
    const arrow = document.createElement("span");
    arrow.className = "relation-arrow";
    arrow.textContent = "->";
    const to = document.createElement("span");
    to.textContent = relation.to;
    to.title = relation.label;
    row.append(from, arrow, to);
    els.relationsList.appendChild(row);
  });
}

function renderPipelineSteps(steps) {
  els.relationsList.textContent = "";
  if (!steps.length) {
    renderEmpty(els.relationsList, "沒有 pipeline step 資料。");
    return;
  }

  steps.forEach((step) => {
    const row = document.createElement("div");
    row.className = "relation-row";
    const name = document.createElement("span");
    name.textContent = step.step_name || "unknown";
    const arrow = document.createElement("span");
    arrow.className = "relation-arrow";
    arrow.textContent = "status";
    const status = document.createElement("span");
    status.textContent = step.status || "unknown";
    row.append(name, arrow, status);
    els.relationsList.appendChild(row);
  });
}

function renderFeatureDetail(model) {
  const feature = (model.features || []).find(
    (item) => item.id === state.selectedId,
  );

  if (!feature) {
    renderNoSelection();
    return;
  }

  els.detailSource.textContent = feature.source;
  replaceDetail(
    section("功能", feature.label),
    section("描述", feature.description),
    section("觸發方式", feature.trigger_description),
    section("信心理由", feature.confidence_reason),
    sourceNodesSection(feature.source_nodes || []),
  );
}

function renderChangeDetail(model) {
  const change = (model.changes || []).find(
    (item) => item.id === state.selectedId,
  );
  const detail = change ? model.details?.[change.id] : null;

  if (!change || !detail) {
    renderNoSelection();
    return;
  }

  els.detailSource.textContent = detail.source;
  replaceDetail(
    section("變更", `${changeSymbol(change.change_type)} ${change.label}`),
    section("變更前名稱", detail.before.label),
    section("變更前描述", detail.before.description),
    section("變更後名稱", detail.after.label),
    section("變更後描述", detail.after.description),
    listSection("受影響關係", detail.affected_relations || []),
  );
}

function replaceDetail(...children) {
  els.detailContent.className = "detail-content";
  els.detailContent.textContent = "";
  els.detailContent.append(...children);
}

function renderNoSelection() {
  els.detailSource.textContent = "尚未選取";
  els.detailContent.className = "detail-content empty-state";
  els.detailContent.textContent = "選取左側項目以查看詳情。";
}

function section(title, text) {
  const wrap = document.createElement("section");
  wrap.className = "detail-section";
  const heading = document.createElement("h3");
  heading.textContent = title;
  const paragraph = document.createElement("p");
  paragraph.textContent = text || "未提供";
  wrap.append(heading, paragraph);
  return wrap;
}

function sourceNodesSection(nodes) {
  return listSection("Source nodes", nodes);
}

function listSection(title, items) {
  const wrap = document.createElement("section");
  wrap.className = "detail-section";
  const heading = document.createElement("h3");
  heading.textContent = title;
  wrap.appendChild(heading);

  if (!items.length) {
    const empty = document.createElement("p");
    empty.className = "empty-state";
    empty.textContent = "未提供";
    wrap.appendChild(empty);
    return wrap;
  }

  const list = document.createElement("ul");
  list.className = "source-list";
  items.forEach((item) => {
    const li = document.createElement("li");
    li.textContent = item;
    list.appendChild(li);
  });
  wrap.appendChild(list);
  return wrap;
}

function selectItem(id) {
  state.selectedId = id;
  render();
}

function renderEmpty(parent, message) {
  const empty = document.createElement("div");
  empty.className = "empty-state";
  empty.textContent = message;
  parent.appendChild(empty);
}

function changeSymbol(changeType) {
  const symbols = {
    added: "+",
    removed: "-",
    attribute_changed: "~",
    dependency_changed: "!=",
  };
  return symbols[changeType] || "?";
}

function renderError(error) {
  els.summaryText.textContent = "資料載入失敗。";
  els.featureList.textContent = "";
  const box = document.createElement("div");
  box.className = "error-box";
  box.textContent = error.message;
  els.featureList.appendChild(box);
}


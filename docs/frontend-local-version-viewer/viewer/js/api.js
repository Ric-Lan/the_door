export const API_BASE = "";

export async function fetchProjectStatus() {
  const res = await fetch(`${API_BASE}/api/project`, { cache: "no-store" });
  return res.json();
}

export async function fetchLatestReport() {
  const res = await fetch(`${API_BASE}/api/report/latest`, { cache: "no-store" });
  return res.json();
}

export async function fetchSnapshots() {
  const res = await fetch(`${API_BASE}/api/snapshots`, { cache: "no-store" });
  return res.json();
}

// postUpdate / fetchJobStatus removed in T5-A (丙案): the /api/update analyze
// key-path and its job polling were retired; version updates go through the
// agent-as-LLM chain (extract_structure → snapshot_write) instead.

export async function fetchL1Graph(versionId = null) {
  const url = versionId
    ? `${API_BASE}/api/l1?version_id=${encodeURIComponent(versionId)}`
    : `${API_BASE}/api/l1`;
  const res = await fetch(url, { cache: "no-store" });
  return res.json();
}

export async function fetchDiff(baselineId, currentId) {
  const url = `${API_BASE}/api/diff?baseline=${encodeURIComponent(baselineId)}&current=${encodeURIComponent(currentId)}`;
  const res = await fetch(url, { cache: "no-store" });
  return res.json();
}

export async function fetchL2Graph(featureId) {
  const res = await fetch(`${API_BASE}/api/l2/${encodeURIComponent(featureId)}`, { cache: "no-store" });
  return res.json();
}

export async function fetchStructure() {
  const res = await fetch(`${API_BASE}/api/structure`, { cache: "no-store" });
  return res.json();
}

export async function fetchLayerExplanation(featureId, layer) {
  const res = await fetch(
    `${API_BASE}/api/layer-explanation/${encodeURIComponent(featureId)}/${layer}`,
    { cache: "no-store" }
  );
  return res.json();
}

// postGenerateL2 / postGenerateLayerExplanation removed in T5-V (丙案 D1):
// L2 / layer-explanation generation is key-bound and was retired; only GET read remains.

export async function fetchNotes(params) {
  const qs = params instanceof URLSearchParams ? params : new URLSearchParams(params);
  const res = await fetch(`${API_BASE}/api/notes?${qs.toString()}`, { cache: "no-store" });
  return res.json();
}

export async function postNote(payload) {
  const res = await fetch(`${API_BASE}/api/notes`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  return res.json();
}

export async function fetchDiffExplanation(featureId, params) {
  const qs = params instanceof URLSearchParams ? params : new URLSearchParams(params);
  const res = await fetch(
    `${API_BASE}/api/diff-explanations/${encodeURIComponent(featureId)}?${qs.toString()}`,
    { cache: "no-store" }
  );
  return res.json();
}

// postGenerateDiffExplanation removed in T5-V (丙案 D1): diff-explanation generation
// is key-bound and was retired; only GET read (fetchDiffExplanation) remains.

export async function fetchStaticUpdateViewModel() {
  const res = await fetch("./data/update-view-model.json", { cache: "no-store" });
  return res.json();
}

export async function fetchStaticL1ViewModel() {
  const res = await fetch("./data/l1-view-model.json", { cache: "no-store" });
  return res.json();
}

export async function fetchGroup() {
  const res = await fetch(`${API_BASE}/api/group`, { cache: "no-store" });
  return res.json();
}

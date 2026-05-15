import { state } from './state.js';
import * as api from './api.js';

function currentOutputLanguage() {
  return document.getElementById("input-language").value;
}

function detailSectionSmall(title, text) {
  const sec = document.createElement("section");
  sec.className = "detail-section";
  const h = document.createElement("h3");
  h.textContent = title;
  const p = document.createElement("p");
  p.textContent = text;
  sec.append(h, p);
  return sec;
}

function renderExplanationEmpty(container, featureId) {
  container.textContent = "";
  const p = document.createElement("p");
  p.className = "missing";
  p.textContent = "尚未產生差異推論。";
  container.appendChild(p);

  const btn = document.createElement("button");
  btn.type = "button";
  btn.className = "action-button diff-explanation-generate-btn";
  btn.textContent = "生成差異推論";
  btn.addEventListener("click", () => generateDiffExplanation(featureId, container, btn));
  container.appendChild(btn);
}

function renderExplanationContent(explanation, container, featureId) {
  container.textContent = "";

  const confidence = explanation.confidence || "low";
  const confidenceMap = { high: "高", medium: "中", low: "低" };
  const tag = document.createElement("span");
  tag.className = "confidence-badge confidence-badge-" + confidence;
  tag.textContent = "信心：" + (confidenceMap[confidence] || confidence);
  container.appendChild(tag);

  const fields = [
    ["影響什麼", explanation.impact_summary],
    ["可達成目的", explanation.possible_purpose],
    ["注意事項", explanation.caution],
  ];
  fields.forEach(([title, text]) => {
    if (text) container.appendChild(detailSectionSmall(title, text));
  });

  const resources = explanation.linked_resources || [];
  if (resources.length) {
    const sec = document.createElement("section");
    sec.className = "detail-section";
    const h = document.createElement("h3");
    h.textContent = "連動資源";
    const ul = document.createElement("ul");
    ul.className = "source-list";
    resources.forEach(r => {
      const li = document.createElement("li");
      li.textContent = r;
      ul.appendChild(li);
    });
    sec.append(h, ul);
    container.appendChild(sec);
  }

  const regenBtn = document.createElement("button");
  regenBtn.type = "button";
  regenBtn.className = "action-button diff-explanation-generate-btn";
  regenBtn.textContent = "重新生成";
  regenBtn.addEventListener("click", () => generateDiffExplanation(featureId, container, regenBtn));
  container.appendChild(regenBtn);
}

async function generateDiffExplanation(featureId, container, btn) {
  btn.disabled = true;
  btn.textContent = "生成中…";
  try {
    const body = await api.postGenerateDiffExplanation(featureId, {
      baseline_version_id: state.versionA,
      current_version_id: state.versionB,
      output_language: currentOutputLanguage(),
    });
    if (!body.explanation) {
      btn.disabled = false;
      btn.textContent = "生成差異推論";
      const errEl = document.createElement("p");
      errEl.className = "missing";
      errEl.textContent = "生成失敗：" + (body?.error?.message || "未知錯誤");
      container.insertBefore(errEl, btn);
      return;
    }
    renderExplanationContent(body.explanation, container, featureId);
  } catch (err) {
    btn.disabled = false;
    btn.textContent = "生成差異推論";
    const errEl = document.createElement("p");
    errEl.className = "missing";
    errEl.textContent = "無法連線：" + (err.message || "network error");
    container.insertBefore(errEl, btn);
  }
}

async function loadDiffExplanation(featureId, container) {
  if (!state.versionA || !state.versionB) {
    renderExplanationEmpty(container, featureId);
    return;
  }
  const params = new URLSearchParams({
    baseline_version_id: state.versionA,
    current_version_id: state.versionB,
    output_language: currentOutputLanguage(),
  });
  try {
    const body = await api.fetchDiffExplanation(featureId, params);
    if (body.explanation) {
      renderExplanationContent(body.explanation, container, featureId);
    } else {
      renderExplanationEmpty(container, featureId);
    }
  } catch (_) {
    renderExplanationEmpty(container, featureId);
  }
}

export function appendDiffExplanationSection(container, featureId) {
  const section = document.createElement("section");
  section.className = "detail-section diff-explanation-section";

  const h = document.createElement("h3");
  h.textContent = "差異推論";
  section.appendChild(h);

  const bodyEl = document.createElement("div");
  bodyEl.className = "diff-explanation-body";
  section.appendChild(bodyEl);
  container.appendChild(section);

  loadDiffExplanation(featureId, bodyEl);
}

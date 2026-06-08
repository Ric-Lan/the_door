import { state } from './state.js';
import * as api from './api.js';

// confidence 人類面標籤（含 unknown＝未評估、H1-5 誠實化）。模組級單一處＝便於膜詞彙 drift-guard 守 key 涵蓋。
export const CONFIDENCE_LABEL = { high: "高", medium: "中", low: "低", unknown: "未評估" };

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

// T5-V (丙案 D1): diff-explanation generation retired. Display-only — no generate button.
function renderExplanationEmpty(container, featureId) {
  container.textContent = "";
  const p = document.createElement("p");
  p.className = "missing";
  p.textContent = "尚無差異推論。";
  container.appendChild(p);
}

function renderExplanationContent(explanation, container, featureId) {
  container.textContent = "";

  // 缺值＝來源未評估信心 → 誠實退 unknown，不謊報成低信心（H1 誠實化原則、對齊 confidence_membrane）
  const confidence = explanation.confidence || "unknown";
  const tag = document.createElement("span");
  tag.className = "confidence-badge confidence-badge-" + confidence;
  tag.textContent = "信心：" + (CONFIDENCE_LABEL[confidence] || confidence);
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
  // T5-V (丙案 D1): "重新生成" button removed — generation retired, display-only.
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

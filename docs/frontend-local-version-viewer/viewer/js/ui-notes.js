import * as api from './api.js';

export function relativeTime(ts, now = Date.now()) {
  const diff = now - ts;
  if (diff < 60_000) return '剛剛';
  if (diff < 3_600_000) return `${Math.floor(diff / 60_000)} 分鐘前`;
  if (diff < 86_400_000) return `${Math.floor(diff / 3_600_000)} 小時前`;
  if (diff < 7 * 86_400_000) return `${Math.floor(diff / 86_400_000)} 天前`;
  const d = new Date(ts);
  const pad = n => String(n).padStart(2, '0');
  return `${pad(d.getUTCMonth() + 1)}-${pad(d.getUTCDate())} ${pad(d.getUTCHours())}:${pad(d.getUTCMinutes())}`;
}

function prependNote(note, container) {
  const details = document.createElement("details");
  details.className = "user-note";

  const summary = document.createElement("summary");
  summary.textContent = note.display_name;
  details.appendChild(summary);

  const p = document.createElement("p");
  p.textContent = note.comment;
  details.appendChild(p);

  const timeEl = document.createElement("p");
  timeEl.className = "note-time";
  timeEl.textContent = (note.created_at || "").slice(0, 16).replace("T", " ");
  details.appendChild(timeEl);

  const heading = container.querySelector(".user-notes-history-label");
  if (heading) {
    heading.insertAdjacentElement("afterend", details);
  } else {
    container.insertBefore(details, container.firstChild);
  }
}

async function loadNotes(mode, featureId, versionA, versionB, container) {
  const params = new URLSearchParams({ mode, feature_id: featureId });
  if (versionA) params.set("version_a", versionA);
  if (versionB) params.set("version_b", versionB);
  try {
    const body = await api.fetchNotes(params);
    const notes = body.notes || [];
    if (!notes.length) return;
    const heading = document.createElement("p");
    heading.className = "user-notes-history-label";
    heading.textContent = "歷史備註";
    container.appendChild(heading);
    notes.forEach(note => prependNote(note, container));
  } catch (_) {
    // Non-fatal: notes are optional
  }
}

export function appendUserNotesSection(container, mode, versionA, versionB, featureId) {
  const section = document.createElement("section");
  section.className = "detail-section user-notes-section";

  const h = document.createElement("h3");
  h.textContent = "使用者備註";
  section.appendChild(h);

  const form = document.createElement("div");
  form.className = "user-notes-form";

  const nameLabel = document.createElement("label");
  nameLabel.textContent = "名稱";
  const nameInput = document.createElement("input");
  nameInput.type = "text";
  nameInput.className = "user-notes-name";
  nameInput.placeholder = "你的名稱（最多 40 字）";
  nameInput.maxLength = 40;

  const commentLabel = document.createElement("label");
  commentLabel.textContent = "意見";
  const commentInput = document.createElement("textarea");
  commentInput.className = "user-notes-comment";
  commentInput.placeholder = "意見（最多 2000 字）";
  commentInput.maxLength = 2000;
  commentInput.rows = 3;

  const submitBtn = document.createElement("button");
  submitBtn.type = "button";
  submitBtn.className = "user-notes-submit action-button";
  submitBtn.textContent = "新增備註";

  const errorEl = document.createElement("p");
  errorEl.className = "user-notes-error missing";
  errorEl.hidden = true;

  form.append(nameLabel, nameInput, commentLabel, commentInput, submitBtn, errorEl);
  section.appendChild(form);

  const historyEl = document.createElement("div");
  historyEl.className = "user-notes-history";
  section.appendChild(historyEl);

  container.appendChild(section);

  loadNotes(mode, featureId, versionA, versionB, historyEl);

  submitBtn.addEventListener("click", async () => {
    const name = nameInput.value.trim();
    const comment = commentInput.value.trim();
    errorEl.hidden = true;
    if (!name) { errorEl.textContent = "名稱不可為空。"; errorEl.hidden = false; return; }
    if (!comment) { errorEl.textContent = "意見不可為空。"; errorEl.hidden = false; return; }
    try {
      const body = await api.postNote({
        mode, feature_id: featureId,
        version_a: versionA, version_b: versionB,
        name_input: name, comment,
      });
      if (!body.note) {
        errorEl.textContent = body?.error?.message || "新增備註失敗。";
        errorEl.hidden = false;
        return;
      }
      nameInput.value = "";
      commentInput.value = "";
      prependNote(body.note, historyEl);
    } catch (err) {
      errorEl.textContent = "無法連線：" + (err.message || "network error");
      errorEl.hidden = false;
    }
  });
}

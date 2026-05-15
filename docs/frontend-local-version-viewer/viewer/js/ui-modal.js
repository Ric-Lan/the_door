import { state } from './state.js';
import { els } from './dom.js';
import * as api from './api.js';

export function showUpdateModal() {
  const projectPath = state.projectStatus?.project_path || "";
  els.inputOldPath.value = projectPath;
  els.inputNewPath.value = "";
  els.inputLanguage.value = "zh-Hant";
  els.modalError.hidden = true;

  const hint = document.getElementById("modal-project-hint");
  if (projectPath) {
    hint.textContent = "專案根目錄：" + projectPath;
    hint.hidden = false;
  } else {
    hint.hidden = true;
  }

  els.updateModal.hidden = false;
  els.inputNewPath.focus();
}

export function hideUpdateModal() {
  els.updateModal.hidden = true;
}

export function showModalError(message) {
  els.modalError.textContent = message;
  els.modalError.hidden = false;
}

export function renderPipelineProgress(job) {
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

export function startPolling(jobId, callbacks = {}) {
  state.pollingJobId = jobId;
  els.pipelineProgress.hidden = false;
  els.stepsList.textContent = "";
  els.currentStep.textContent = "初始化…";
  state.pollingHandle = setInterval(() => pollJobStatus(jobId, callbacks), 1500);
}

export function stopPolling() {
  clearInterval(state.pollingHandle);
  state.pollingHandle = null;
  state.pollingJobId = null;
}

export async function submitUpdate(oldPath, newPath, callbacks = {}) {
  const handleError = (msg) => callbacks.onError ? callbacks.onError(msg) : showModalError(msg);
  try {
    const body = await api.postUpdate(oldPath, newPath, els.inputLanguage.value || "zh-Hant");
    if (!body.job_id) {
      handleError("分析請求失敗：" + (body?.error?.message || "未知錯誤"));
      return;
    }
    startPolling(body.job_id, callbacks);
  } catch (err) {
    handleError("無法連線到本地 server：" + (err.message || "network error"));
  }
}

export async function pollJobStatus(jobId, callbacks = {}) {
  try {
    const job = await api.fetchJobStatus(jobId);
    renderPipelineProgress(job);
    if (job.status === "completed") {
      stopPolling();
      els.pipelineProgress.hidden = true;
      callbacks.onComplete?.();
    } else if (job.status === "failed") {
      stopPolling();
      els.pipelineProgress.hidden = true;
      showModalError(job.error_message);
    }
  } catch (err) {
    stopPolling();
    showModalError("連線中斷，請確認 server 仍在執行：" + (err.message || "network error"));
  }
}

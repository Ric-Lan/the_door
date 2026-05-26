// ─── State shape ────────────────────────────────────────────────────────────
export function getInitialState() {
  return {
    page: 'LOADING',
    hasSnapshots: false,
    hasApiKey: false,
    projectPath: '',
    fileCount: 0,
    action: null,
    excludesRaw: '',
    label: '',
    jobId: null,
    jobStatus: null,
    currentStep: null,
    steps: [],
    errorMessage: null,
    pollFailCount: 0,
    switchPath: '',
    switchConflict: false,
    switchActiveJobId: null,
  };
}

// ─── Pure state machine ──────────────────────────────────────────────────────
export function transition(state, action) {
  switch (action.type) {
    case 'STATUS_LOADED':
      return {
        ...state,
        page: 'PAGE_ACTION',
        hasSnapshots: action.hasSnapshots,
        hasApiKey: action.hasApiKey,
        projectPath: action.projectPath,
        fileCount: action.fileCount,
      };

    case 'STATUS_ERROR':
      return { ...state, page: 'PAGE_ERROR', errorMessage: action.message };

    case 'SELECT_ACTION': {
      const nextPage =
        action.action === 'analyze' ? 'PAGE_SETUP' :
        action.action === 'update'  ? 'PAGE_CONFIRM' :
        state.page;
      return { ...state, page: nextPage, action: action.action };
    }

    case 'NEXT_FROM_SETUP':
      return { ...state, page: 'PAGE_LABEL', excludesRaw: action.excludesRaw };

    case 'NEXT_FROM_LABEL':
      return { ...state, page: 'PAGE_CONFIRM', label: action.label };

    case 'SUBMIT':
      return { ...state, page: 'SUBMITTING' };

    case 'SUBMIT_ERROR':
      return { ...state, page: 'PAGE_ERROR', errorMessage: action.message };

    case 'JOB_STARTED':
      return { ...state, page: 'PROGRESS', jobId: action.jobId };

    case 'POLL_UPDATE': {
      if (action.status === 'failed') {
        return { ...state, page: 'PAGE_ERROR', jobStatus: 'failed',
                 errorMessage: action.errorMessage || '分析失敗' };
      }
      return {
        ...state,
        jobStatus: action.status,
        currentStep: action.currentStep,
        steps: action.steps,
      };
    }

    case 'POLL_FAIL': {
      const newCount = state.pollFailCount + 1;
      if (newCount >= 3) {
        return { ...state, page: 'PAGE_ERROR', pollFailCount: newCount,
                 errorMessage: '分析可能仍在進行，請直接前往 Viewer 確認' };
      }
      return { ...state, pollFailCount: newCount };
    }

    case 'SWITCH_PATH_CHANGE':
      return { ...state, switchPath: action.path };

    case 'SWITCH_CONFLICT':
      return { ...state, switchConflict: true, switchActiveJobId: action.activeJobId };

    case 'SWITCH_CANCEL':
      return { ...state, switchConflict: false, switchActiveJobId: null };

    default:
      return state;
  }
}

// ─── Pure helpers ────────────────────────────────────────────────────────────
export function parseExcludes(str) {
  if (!str || !str.trim()) return [];
  return str.split(',').map(s => s.trim()).filter(Boolean);
}

export function buildAnalyzeBody(state) {
  const body = {};
  const excludes = parseExcludes(state.excludesRaw);
  if (excludes.length > 0) body.extra_ignore = excludes;
  if (state.label && state.label.trim()) body.label = state.label.trim();
  return body;
}

export function stepIndexForCurrentStep(steps, currentStep) {
  if (!currentStep) return -1;
  return steps.findIndex(s => s.step_name === currentStep);
}

export function createApi(fetchFn = window.fetch.bind(window)) {
  async function _check(resp) {
    if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
    return resp.json();
  }
  return {
    getStatus() {
      return fetchFn('/api/status').then(_check);
    },
    postAnalyze(body) {
      return fetchFn('/api/analyze', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(body),
      }).then(_check);
    },
    getJobStatus(jobId) {
      return fetchFn(`/api/update/status/${jobId}`).then(_check);
    },
    setProject(path, force) {
      return fetchFn('/api/set-project', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ path, force }),
      }).then(_check);
    },
  };
}

// ─── DOM renderer ────────────────────────────────────────────────────────────
export function renderPage(container, state, dispatch, redirectFn) {
  container.innerHTML = '';
  const wrap = document.createElement('div');
  wrap.setAttribute('data-page', state.page);

  switch (state.page) {
    case 'LOADING':
      wrap.innerHTML = '<p>載入中…</p>';
      break;

    case 'PAGE_ACTION':
      if (!state.hasSnapshots) {
        wrap.innerHTML = `
          <h2>歡迎使用 The Door</h2>
          <button data-action="analyze">首次分析此專案</button>
          <button data-action="view" disabled>查看快照（尚無資料）</button>
        `;
      } else {
        wrap.innerHTML = `
          <h2>選擇操作</h2>
          <button data-action="update">更新分析（重新跑）</button>
          <button data-action="view">直接查看現有快照</button>
        `;
      }
      wrap.querySelectorAll('[data-action]').forEach(btn => {
        if (!btn.disabled) {
          btn.addEventListener('click', () => {
            const act = btn.getAttribute('data-action');
            if (act === 'view') { redirectFn('/index.html'); return; }
            dispatch({ type: 'SELECT_ACTION', action: act });
          });
        }
      });
      break;

    case 'PAGE_SETUP':
      wrap.innerHTML = `
        <h2>設定分析範圍</h2>
        <p>偵測到 ${state.fileCount} 個源碼檔案。</p>
        <label>排除目錄（逗號分隔，選填）：
          <input type="text" data-excludes placeholder="tests/, docs/" value="${state.excludesRaw}">
        </label>
        <button data-next="setup">下一步</button>
      `;
      wrap.querySelector('[data-next="setup"]').addEventListener('click', () => {
        const raw = wrap.querySelector('[data-excludes]').value;
        dispatch({ type: 'NEXT_FROM_SETUP', excludesRaw: raw });
      });
      break;

    case 'PAGE_LABEL':
      wrap.innerHTML = `
        <h2>快照標籤</h2>
        <label>版本標籤（選填）：
          <input type="text" data-label placeholder="v1.0.0" value="${state.label}">
        </label>
        <button data-next="label">下一步</button>
      `;
      wrap.querySelector('[data-next="label"]').addEventListener('click', () => {
        const lbl = wrap.querySelector('[data-label]').value;
        dispatch({ type: 'NEXT_FROM_LABEL', label: lbl });
      });
      break;

    case 'PAGE_CONFIRM': {
      const mode = state.hasApiKey ? 'API key 模式' : 'Agent 模式（無 API key）';
      wrap.innerHTML = `
        <h2>確認送出</h2>
        <p>操作：${state.action}</p>
        <p>模式：${mode}</p>
        <button data-submit>確認送出</button>
      `;
      wrap.querySelector('[data-submit]').addEventListener('click', () => {
        dispatch({ type: 'SUBMIT' });
      });
      break;
    }

    case 'SUBMITTING':
      wrap.innerHTML = '<p>送出中…</p>';
      break;

    case 'PROGRESS':
      if (!state.hasApiKey) {
        wrap.innerHTML = `
          <h2>Agent 模式 — 複製以下指令給 Claude</h2>
          <pre data-agent-params>extract_structure(codebase_path="${state.projectPath}")
snapshot_write(codebase_path="${state.projectPath}", l1_features=[...], label="${state.label || 'v1.0.0'}")</pre>
          <button data-copy>複製</button>
          <button data-done>我已讓 agent 執行完畢，進入 Viewer</button>
        `;
        wrap.querySelector('[data-copy]').addEventListener('click', () => {
          navigator.clipboard.writeText(wrap.querySelector('[data-agent-params]').textContent);
        });
        wrap.querySelector('[data-done]').addEventListener('click', () => redirectFn('/index.html'));
      } else {
        const stepItems = state.steps.map((s, i) => {
          const idx = stepIndexForCurrentStep(state.steps, state.currentStep);
          const cls = i < idx ? 'done' : i === idx ? 'running' : 'pending';
          return `<li data-step-status="${cls}">${s.step_name}</li>`;
        }).join('');
        wrap.innerHTML = `
          <h2>分析進行中</h2>
          <ul>${stepItems || '<li data-step-status="pending">初始化中…</li>'}</ul>
        `;
      }
      break;

    case 'PAGE_ERROR':
      wrap.innerHTML = `
        <h2>發生錯誤</h2>
        <p>${state.errorMessage || '未知錯誤'}</p>
        <a href="/index.html">前往 Viewer</a>
      `;
      break;
  }

  container.appendChild(wrap);
}

// ─── Controller ──────────────────────────────────────────────────────────────
export function initWizard(container, api, redirectFn = (url) => { window.location.href = url; }) {
  let state = getInitialState();
  let activeTimer = null;

  function dispatch(action) {
    state = transition(state, action);
    renderPage(container, state, dispatch, redirectFn);
    handleSideEffects(state, action);
  }

  function handleSideEffects(currentState, action) {
    if (action.type === 'SUBMIT') {
      if (!currentState.hasApiKey) {
        dispatch({ type: 'JOB_STARTED', jobId: null });
        return;
      }
      const body = buildAnalyzeBody(currentState);
      api.postAnalyze(body)
        .then(data => dispatch({ type: 'JOB_STARTED', jobId: data.job_id }))
        .catch(err => dispatch({ type: 'SUBMIT_ERROR', message: String(err) }));
    }

    if (action.type === 'JOB_STARTED' && currentState.jobId) {
      startPolling(currentState.jobId);
    }
  }

  function startPolling(jobId) {
    if (activeTimer !== null) return;
    activeTimer = setInterval(async () => {
      try {
        const data = await api.getJobStatus(jobId);
        dispatch({ type: 'POLL_UPDATE', status: data.status,
                   currentStep: data.current_step, steps: data.steps || [],
                   errorMessage: data.error_message });
        if (data.status === 'done') {
          clearInterval(activeTimer);
          activeTimer = null;
          redirectFn('/index.html');
        }
        if (data.status === 'failed') {
          clearInterval(activeTimer);
          activeTimer = null;
        }
      } catch {
        dispatch({ type: 'POLL_FAIL' });
        if (state.pollFailCount >= 3) {
          clearInterval(activeTimer);
          activeTimer = null;
        }
      }
    }, 1500);
  }

  api.getStatus()
    .then(data => {
      dispatch({
        type: 'STATUS_LOADED',
        hasSnapshots: data.state.has_snapshots,
        hasApiKey: data.state.has_api_key,
        projectPath: data.state.project_path || '',
        fileCount: data.state.file_count || 0,
      });
    })
    .catch(err => dispatch({ type: 'STATUS_ERROR', message: String(err) }));

  renderPage(container, state, dispatch, redirectFn);
}

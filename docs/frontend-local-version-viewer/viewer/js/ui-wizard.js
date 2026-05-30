import { renderProgressInnerHTML, appendPlLine, updateProgressCount } from './progress-view.js';

// ─── Threshold transition ────────────────────────────────────────────────────
export function redirectWithTransition(url, setLocation = (u) => { window.location.href = u; }) {
  const shell = document.querySelector('.wizard-shell');
  if (shell) shell.classList.add('leaving');
  setTimeout(() => setLocation(url), 620);
}

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
    progress: null,
    errorMessage: null,
    pollFailCount: 0,
    switchPath: '',
    switchConflict: false,
    switchActiveJobId: null,
    errorOriginPage: null,
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
      return { ...state, page: 'PAGE_ERROR', errorMessage: action.message, errorOriginPage: state.page };

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

    case 'BACK':
      return { ...state, page: action.target };

    case 'SUBMIT':
      return { ...state, page: 'SUBMITTING' };

    case 'SUBMIT_ERROR':
      return { ...state, page: 'PAGE_ERROR', errorMessage: action.message, errorOriginPage: state.page };

    case 'JOB_STARTED':
      return { ...state, page: 'PROGRESS', jobId: action.jobId };

    case 'POLL_UPDATE': {
      if (action.status === 'failed') {
        return { ...state, page: 'PAGE_ERROR', jobStatus: 'failed',
                 errorMessage: action.errorMessage || '分析失敗', errorOriginPage: state.page };
      }
      return {
        ...state,
        jobStatus: action.status,
        currentStep: action.currentStep,
        steps: action.steps,
        progress: action.progress ?? state.progress,
      };
    }

    case 'POLL_FAIL': {
      const newCount = state.pollFailCount + 1;
      if (newCount >= 3) {
        return { ...state, page: 'PAGE_ERROR', pollFailCount: newCount,
                 errorMessage: '分析可能仍在進行，請直接前往 Viewer 確認', errorOriginPage: state.page };
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

// ─── Rail HTML (spec §4.1) ────────────────────────────────────────────────────
const STAGE = {
  LOADING: 0, PAGE_ACTION: 0,
  PAGE_SETUP: 1, PAGE_LABEL: 2, PAGE_CONFIRM: 3,
  SUBMITTING: 4, PROGRESS: 4,
};
const STAGE_LABELS = ['選擇操作', '設定範圍', '快照標籤', '確認送出', '分析中', '進入 Viewer'];

export function railStage(state) {
  if (state.page === 'PAGE_ERROR') return STAGE[state.errorOriginPage] ?? 0;
  return STAGE[state.page] ?? 0;
}

const DOOR_SVG = `
  <svg class="leaf" viewBox="0 0 100 100" fill="none" aria-label="The Door">
    <rect x="22" y="10" width="56" height="76" fill="#d9f3ef"></rect>
    <path d="M22 10 L22 86 M78 10 L78 86 M22 10 L78 10" stroke="#0f766e" stroke-width="6"></path>
    <line x1="10" y1="90" x2="90" y2="90" stroke="#0f766e" stroke-width="6"></line>
    <circle cx="70" cy="50" r="2.5" fill="#0f766e"></circle>
  </svg>`;

export function wizardRailHTML(stage, lit) {
  const frac = Math.min(stage, 5) / 5;
  const angle = -(78 * frac);
  const fillH = `${frac * 100}%`;
  const steps = STAGE_LABELS.map((label, i) => {
    const cls = i < stage ? 'done' : i === stage ? 'active' : '';
    const icon = i < stage ? '✓' : String(i + 1);
    return `<div class="wizard-step ${cls}"><span class="dot">${icon}</span><span class="lbl">${label}</span></div>`;
  }).join('');
  return `
    <div class="wizard-rail">
      <div class="wizard-rail-brand">${DOOR_SVG}<div><div class="wd">The Door</div><div class="sub">門 · 啟動精靈</div></div></div>
      <div class="wizard-door-wrap">
        <svg class="wizard-door-frame" viewBox="0 0 148 188" fill="none">
          <path d="M12 8 L12 182 M136 8 L136 182 M12 8 L136 8" stroke="rgba(217,243,239,0.6)" stroke-width="3"></path>
          <line x1="4" y1="184" x2="144" y2="184" stroke="rgba(217,243,239,0.6)" stroke-width="3.5"></line>
        </svg>
        <div class="wizard-door-light${lit ? ' lit' : ''}"></div>
        <div class="wizard-door-leaf" style="transform:rotateY(${angle}deg)"><span class="grain"></span><span class="knob"></span></div>
        <div class="wizard-door-pct">${lit ? '已開啟' : '開啟 ' + Math.round(frac * 100) + '%'}</div>
      </div>
      <div class="wizard-stepper">
        <div class="wizard-stepper-line"></div>
        <div class="wizard-stepper-fill" style="height:${fillH}"></div>
        ${steps}
      </div>
      <div class="wizard-rail-foot">CODE → FUNCTIONAL LANGUAGE</div>
    </div>`;
}

// ─── DOM renderer ────────────────────────────────────────────────────────────
export function renderPage(container, state, dispatch, redirectFn, api) {
  container.innerHTML = '';

  // Build shell
  const shell = document.createElement('div');
  shell.className = 'wizard-shell';
  const lit = state.page === 'PROGRESS' && state.status === 'completed';
  shell.insertAdjacentHTML('beforeend', wizardRailHTML(railStage(state), lit));

  const content = document.createElement('div');
  content.className = 'wizard-content';
  const screen = document.createElement('div');
  screen.className = 'wizard-screen wizard-screen-enter';
  screen.setAttribute('data-page', state.page);
  content.appendChild(screen);
  shell.appendChild(content);
  container.appendChild(shell);

  const wrap = document.createElement('div');
  wrap.setAttribute('data-page', state.page);
  wrap.className = 'wizard-card';

  const bindBack = (root) => {
    const btn = root.querySelector('[data-back]');
    if (!btn) return;
    btn.addEventListener('click', () =>
      dispatch({ type: 'BACK', target: btn.getAttribute('data-back') }));
  };

  switch (state.page) {
    case 'LOADING':
      wrap.innerHTML = '<p>載入中…</p>';
      break;

    case 'PAGE_ACTION': {
      const modeNoteCls = state.hasApiKey ? 'api' : 'agent';
      const modeBadge   = state.hasApiKey ? '● API key 模式' : '◐ Agent 模式';
      const modeText    = state.hasApiKey
        ? '偵測到 API key — 分析會在本機自動執行，完成後直接進入 Viewer。'
        : '未偵測到 API key — 將以 Agent 模式產生 MCP 指令，交由你的 coding agent 執行。';
      const eyebrowAndNote = `
  <p class="wizard-eyebrow">步驟 1 / 開始</p>
  <div class="wizard-mode-note ${modeNoteCls}">
    <span class="mn-badge">${modeBadge}</span>
    <span>${modeText}</span>
  </div>
`;
      if (!state.hasSnapshots) {
        wrap.innerHTML = `${eyebrowAndNote}
          <h2>歡迎使用 The Door</h2>
          <p class="wizard-subtitle">首次使用，從分析此專案開始。</p>
          <div class="wizard-options">
            <button class="wizard-option-btn" data-action="analyze">
              <strong>首次分析此專案</strong>
              <span>掃描原始碼，建立第一份結構快照。</span>
            </button>
            <button class="wizard-option-btn" data-action="view" disabled>
              <strong>查看快照</strong>
              <span>尚無資料。</span>
            </button>
          </div>
        `;
      } else {
        wrap.innerHTML = `${eyebrowAndNote}
          <h2>選擇操作</h2>
          <p class="wizard-subtitle">偵測到既有快照，選擇下一步。</p>
          <div class="wizard-options">
            <button class="wizard-option-btn" data-action="update">
              <strong>更新分析</strong>
              <span>重新掃描原始碼，產生新版本快照。</span>
            </button>
            <button class="wizard-option-btn" data-action="view">
              <strong>查看現有快照</strong>
              <span>直接進入 Viewer，不重新分析。</span>
            </button>
          </div>
        `;
      }
      wrap.querySelectorAll('[data-action]').forEach(btn => {
        if (!btn.disabled) {
          btn.addEventListener('click', () => {
            const act = btn.getAttribute('data-action');
            if (act === 'view') { redirectWithTransition('/index.html', redirectFn); return; }
            dispatch({ type: 'SELECT_ACTION', action: act });
          });
        }
      });

      // Switch project section
      const switchSection = document.createElement('div');
      if (state.switchConflict) {
        switchSection.innerHTML = `
          <div data-switch-conflict class="wizard-error-box">
            <p>目前有進行中的分析任務</p>
            <button class="wizard-btn-primary" data-switch-force-btn>立即切換（中斷任務）</button>
            <button data-switch-cancel-btn>取消</button>
          </div>
        `;
        switchSection.querySelector('[data-switch-force-btn]').addEventListener('click', () => {
          api.setProject(state.switchPath, true)
            .then(() => redirectFn('/wizard.html'))
            .catch(err => dispatch({ type: 'STATUS_ERROR', message: String(err) }));
        });
        switchSection.querySelector('[data-switch-cancel-btn]').addEventListener('click', () => {
          dispatch({ type: 'SWITCH_CANCEL' });
        });
      } else {
        switchSection.innerHTML = `
          <div class="wizard-field">
            <label>切換至其他專案</label>
            <input type="text" data-switch-input placeholder="/absolute/path/to/project">
          </div>
          <button class="wizard-btn-primary" data-switch-btn>切換</button>
        `;
        switchSection.querySelector('[data-switch-input]').value = state.switchPath;
        switchSection.querySelector('[data-switch-input]').addEventListener('input', e => {
          dispatch({ type: 'SWITCH_PATH_CHANGE', path: e.target.value });
        });
        switchSection.querySelector('[data-switch-btn]').addEventListener('click', () => {
          const path = switchSection.querySelector('[data-switch-input]').value;
          api.setProject(path, false)
            .then(result => {
              if (result.status === 'conflict') {
                dispatch({ type: 'SWITCH_CONFLICT', activeJobId: result.active_job_id });
              } else {
                redirectFn('/wizard.html');
              }
            })
            .catch(err => dispatch({ type: 'STATUS_ERROR', message: String(err) }));
        });
      }
      wrap.appendChild(switchSection);
      break;
    }

    case 'PAGE_SETUP': {
      wrap.innerHTML = `
        <h2>設定分析範圍</h2>
        <p class="wizard-subtitle">偵測到 ${state.fileCount} 個源碼檔案。</p>
        <div class="wizard-field">
          <label>排除目錄（逗號分隔，選填）</label>
          <input type="text" data-excludes placeholder="tests/, docs/" value="${state.excludesRaw}">
        </div>
        <div style="display:flex;gap:12px;margin-top:20px;">
          <button class="wizard-btn-ghost" data-back="PAGE_ACTION">← 上一步</button>
          <button class="wizard-btn-primary" data-next="setup">下一步</button>
        </div>
      `;
      wrap.querySelector('[data-next="setup"]').addEventListener('click', () => {
        const raw = wrap.querySelector('[data-excludes]').value;
        dispatch({ type: 'NEXT_FROM_SETUP', excludesRaw: raw });
      });
      bindBack(wrap);
      break;
    }

    case 'PAGE_LABEL': {
      wrap.innerHTML = `
        <h2>快照標籤</h2>
        <div class="wizard-field">
          <label>版本標籤（選填）</label>
          <input type="text" data-label placeholder="v1.0.0" value="${state.label}">
        </div>
        <div style="display:flex;gap:12px;margin-top:20px;">
          <button class="wizard-btn-ghost" data-back="PAGE_SETUP">← 上一步</button>
          <button class="wizard-btn-primary" data-next="label">下一步</button>
        </div>
      `;
      wrap.querySelector('[data-next="label"]').addEventListener('click', () => {
        const lbl = wrap.querySelector('[data-label]').value;
        dispatch({ type: 'NEXT_FROM_LABEL', label: lbl });
      });
      bindBack(wrap);
      break;
    }

    case 'PAGE_CONFIRM': {
      const apiOn = state.hasApiKey;
      const badgeCls = apiOn ? 'api' : 'agent';
      const badgeText = apiOn ? '● API key 模式' : '◐ Agent 模式（無 API key）';
      const backTarget = state.action === 'update' ? 'PAGE_ACTION' : 'PAGE_LABEL';
      wrap.innerHTML = `
        <h2>確認送出</h2>
        <dl class="wizard-summary">
          <dt>操作</dt><dd>${state.action}</dd>
          <dt>執行模式</dt><dd><span class="wizard-mode-badge ${badgeCls}">${badgeText}</span></dd>
        </dl>
        <div style="display:flex;gap:12px;margin-top:20px;">
          <button class="wizard-btn-ghost" data-back="${backTarget}">← 上一步</button>
          <button class="wizard-btn-primary" data-submit>確認送出</button>
        </div>
      `;
      wrap.querySelector('[data-submit]').addEventListener('click', () => dispatch({ type: 'SUBMIT' }));
      bindBack(wrap);
      break;
    }

    case 'SUBMITTING':
      wrap.innerHTML = '<p>送出中…</p>';
      break;

    case 'PROGRESS':
      if (!state.hasApiKey) {
        wrap.innerHTML = `
          <h2>Agent 模式 — 複製以下指令給 Claude</h2>
          <pre class="wizard-agent-params" data-agent-params>extract_structure(codebase_path="${state.projectPath}")
snapshot_write(codebase_path="${state.projectPath}", l1_features=[...], label="${state.label || 'v1.0.0'}")</pre>
          <button class="wizard-btn-copy" data-copy>複製</button>
          <button class="wizard-btn-primary" data-done>我已讓 agent 執行完畢，進入 Viewer</button>
        `;
        wrap.querySelector('[data-copy]').addEventListener('click', () => {
          navigator.clipboard.writeText(wrap.querySelector('[data-agent-params]').textContent);
        });
        wrap.querySelector('[data-done]').addEventListener('click', () => redirectWithTransition('/index.html', redirectFn));
      } else {
        // API mode: shared progress view (spec §4.2 ⓕ, §5.3, §5.4)
        wrap.innerHTML = `<h2>分析進行中</h2>${renderProgressInnerHTML({
          steps: state.steps,
          currentStep: state.currentStep,
          progress: state.progress,
        })}`;
      }
      break;

    case 'PAGE_ERROR':
      wrap.innerHTML = `
        <h2>發生錯誤</h2>
        <div class="wizard-error-box">${state.errorMessage || '未知錯誤'}</div>
        <a class="wizard-btn-primary" href="/index.html">前往 Viewer</a>
      `;
      break;
  }

  screen.appendChild(wrap);
}

// ─── Controller ──────────────────────────────────────────────────────────────
export function initWizard(container, api, redirectFn = (url) => { window.location.href = url; }) {
  let state = getInitialState();
  let activeTimer = null;

  function dispatch(action) {
    state = transition(state, action);
    renderPage(container, state, dispatch, redirectFn, api);
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
                   errorMessage: data.error_message, progress: data.progress });
        // Live feed (bypass full rerender for stutter-free append).
        if (data.progress && data.progress.current_file) {
          appendPlLine(data.progress.current_file);
          updateProgressCount(data.progress.files_done, data.progress.files_total);
        }
        if (data.status === 'done') {
          clearInterval(activeTimer);
          activeTimer = null;
          redirectWithTransition('/index.html', redirectFn);
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

  renderPage(container, state, dispatch, redirectFn, api);
}

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

// Snapshot 識別字串優先序：git_tags[0] → label → version_id。
// 注意：刻意不沿用 layers.js 的 _snapLabel（它停在 label→null，會讓無標籤快照產生空指令）。
export function resolveSnapshotRef(snapshot) {
  if (!snapshot) return null;
  if (Array.isArray(snapshot.git_tags) && snapshot.git_tags.length > 0) {
    return snapshot.git_tags[0];
  }
  if (snapshot.label) return snapshot.label;
  return snapshot.version_id ?? null;
}

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
    getSnapshots() {
      return fetchFn('/api/snapshots').then(_check);
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

// ─── Icon library (mirrors part2-prototype I) ──────────────────────────────
const I = {
  scan:    `<svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M3 7V5a2 2 0 0 1 2-2h2M17 3h2a2 2 0 0 1 2 2v2M21 17v2a2 2 0 0 1-2 2h-2M7 21H5a2 2 0 0 1-2-2v-2"></path><line x1="3" y1="12" x2="21" y2="12"></line></svg>`,
  refresh: `<svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M21 2v6h-6M3 12a9 9 0 0 1 15-6.7L21 8M3 22v-6h6M21 12a9 9 0 0 1-15 6.7L3 16"></path></svg>`,
  eye:     `<svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M2 12s3.5-7 10-7 10 7 10 7-3.5 7-10 7-10-7-10-7Z"></path><circle cx="12" cy="12" r="3"></circle></svg>`,
  arrow:   `<svg class="arrow" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M5 12h14M13 6l6 6-6 6"></path></svg>`,
  clock:   `<svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><circle cx="12" cy="12" r="9"></circle><path d="M12 7v5l3 2"></path></svg>`,
  info:    `<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><circle cx="12" cy="12" r="9"></circle><path d="M12 8h.01M11 12h1v4h1"></path></svg>`,
  warn:    `<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><path d="M12 9v4M12 17h.01M10.3 3.9 1.8 18a2 2 0 0 0 1.7 3h17a2 2 0 0 0 1.7-3L13.7 3.9a2 2 0 0 0-3.4 0Z"></path></svg>`,
  lines:   `<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><path d="M3 12h18M3 6h18M3 18h18"></path></svg>`,
};

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
      const eyebrowHeroNote = `
  <p class="wizard-eyebrow eyebrow">步驟 1 / 開始</p>
  <h2>${state.hasSnapshots ? '歡迎回來，要做什麼？' : '歡迎使用 The Door'}</h2>
  <p class="wizard-subtitle lede">把程式碼翻譯成非技術者也能讀懂的功能語言。先選擇這次要進行的操作。</p>
  <div class="wizard-mode-note mode-note ${modeNoteCls}">
    <span class="mn-badge">${modeBadge}</span>
    <span>${modeText}</span>
  </div>
`;
      if (!state.hasSnapshots) {
        wrap.innerHTML = `${eyebrowHeroNote}
          <div class="wizard-options opts">
            <button class="wizard-option-btn opt" data-action="analyze">
              <span class="ico">${I.scan}</span>
              <span class="tx"><strong>首次分析此專案</strong><span>掃描原始碼，建立第一個功能快照。</span></span>
              ${I.arrow}
            </button>
            <button class="wizard-option-btn opt" data-action="view" disabled>
              <span class="ico">${I.eye}</span>
              <span class="tx"><strong>查看快照</strong><span>尚無資料，請先執行分析。</span></span>
            </button>
          </div>
        `;
      } else {
        wrap.innerHTML = `${eyebrowHeroNote}
          <div class="wizard-options opts">
            <button class="wizard-option-btn opt" data-action="update">
              <span class="ico">${I.refresh}</span>
              <span class="tx"><strong>更新分析</strong><span>重新掃描原始碼，產生新版本快照並比對差異。</span></span>
              ${I.arrow}
            </button>
            <button class="wizard-option-btn opt" data-action="view">
              <span class="ico">${I.eye}</span>
              <span class="tx"><strong>查看現有快照</strong><span>直接進入 Viewer，不重新分析。</span></span>
              ${I.arrow}
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
        const projectPath = state.projectPath || '~/code/the-door';
        const fileCount = state.fileCount || 0;
        switchSection.className = 'switch-zone wizard-field';
        switchSection.innerHTML = `
          <p class="sz-label">${I.lines}<span>目前分析目標: <code>${projectPath}</code> · 偵測到 ${fileCount} 個源碼檔</span></p>
          <div class="switch-row">
            <input type="text" data-switch-input placeholder="/absolute/path/to/another/project">
            <button class="wizard-btn-primary btn btn-ghost" data-switch-btn>切換專案</button>
          </div>
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
        <p class="wizard-eyebrow eyebrow">步驟 2 / 設定</p>
        <h2>要分析哪些範圍？</h2>
        <p class="wizard-subtitle lede">偵測到 <strong>${state.fileCount}</strong> 個源碼檔案。可排除測試、文件等不需納入功能分析的目錄。</p>
        <div class="fields">
          <div class="wizard-field field">
            <label>排除目錄（逗號分隔，選填）</label>
            <input type="text" data-excludes placeholder="tests/, docs/, vendor/" value="${state.excludesRaw}">
            <p class="hint">留空則分析全部。排除的目錄不會送入 LLM，可降低 token 用量。</p>
          </div>
        </div>
        <div class="actions">
          <button class="wizard-btn-ghost btn btn-ghost" data-back="PAGE_ACTION">← 上一步</button>
          <span class="spacer"></span>
          <button class="wizard-btn-primary btn btn-primary" data-next="setup">下一步 ${I.arrow}</button>
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
        <p class="wizard-eyebrow eyebrow">步驟 3 / 設定</p>
        <h2>替這個版本貼個標籤</h2>
        <p class="wizard-subtitle lede">標籤用來在 Viewer 的版本選擇器中辨識這份快照。選填，留空會自動帶入 v1.0.0。</p>
        <div class="fields">
          <div class="wizard-field field">
            <label>版本標籤（選填）</label>
            <input type="text" data-label placeholder="v1.0.0" value="${state.label}">
            <p class="hint">例：語意化版本、Git tag、或日期。</p>
          </div>
        </div>
        <div class="actions">
          <button class="wizard-btn-ghost btn btn-ghost" data-back="PAGE_SETUP">← 上一步</button>
          <span class="spacer"></span>
          <button class="wizard-btn-primary btn btn-primary" data-next="label">下一步 ${I.arrow}</button>
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
      const badgeText = apiOn ? '● API key 模式' : '◐ Agent 模式';
      const backTarget = state.action === 'update' ? 'PAGE_ACTION' : 'PAGE_LABEL';
      const opLabel = state.action === 'update' ? '更新分析' : '首次分析';
      wrap.innerHTML = `
        <p class="wizard-eyebrow eyebrow">步驟 4 / 確認</p>
        <h2>確認後即開始</h2>
        <p class="wizard-subtitle lede">送出後會依下列設定執行。分析可能需要數分鐘，取決於專案大小。</p>
        <dl class="wizard-summary summary">
          <div class="row"><dt class="k">操作</dt><dd class="v mode">${opLabel}</dd></div>
          <div class="row"><dt class="k">排除目錄</dt><dd class="v">${state.excludesRaw || '（無）'}</dd></div>
          <div class="row"><dt class="k">版本標籤</dt><dd class="v">${state.label || 'v1.0.0'}</dd></div>
          <div class="row"><dt class="k">執行模式</dt><dd class="v"><span class="wizard-mode-badge badge-mode ${badgeCls}">${badgeText}</span></dd></div>
        </dl>
        <div class="actions">
          <button class="wizard-btn-ghost btn btn-ghost" data-back="${backTarget}">← 上一步</button>
          <span class="spacer"></span>
          <button class="wizard-btn-primary btn btn-primary" data-submit>確認送出 ${I.arrow}</button>
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

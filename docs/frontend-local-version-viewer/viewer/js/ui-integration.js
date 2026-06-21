// 整合健檢：純判定/徽章/面板。資料一律來自 state.integration（單一真相）。

const BADGE = {
  gap:          { sym: '❌', cls: 'integration-gap',          title: '宣稱要連、結構上沒接上' },
  undetermined: { sym: '⚠',  cls: 'integration-undetermined', title: '目標非程式碼節點，無法判定' },
  backed:       { sym: '✅', cls: 'integration-backed',        title: '宣稱的依賴有結構連線支撐' },
};

// 回傳 'gap'|'undetermined'|'backed'，或 null（none / 缺資料 ⇒ 不顯示徽章）
export function featureVerdict(integration, featureId) {
  const v = integration?.features?.[featureId];
  return v && v !== 'none' ? v : null;
}

// 回傳徽章 span，或 null
export function integrationBadge(verdict) {
  const spec = verdict && BADGE[verdict];
  if (!spec) return null;
  const el = document.createElement('span');
  el.className = 'integration-badge ' + spec.cls;
  el.title = spec.title;
  el.textContent = spec.sym;
  return el;
}

export function initIntegrationLegend() {
  const btn   = document.getElementById('btn-integ-legend');
  const popup = document.getElementById('integ-legend-popup');
  if (!btn || !popup) return;

  popup.innerHTML = `
    <div class="integ-legend-header">
      整合健檢標示說明
      <button class="integ-legend-close" type="button" aria-label="關閉">✕</button>
    </div>
    <div class="integ-legend-rows">
      <div class="integ-legend-row">
        <span class="lbl">✅ 有接上（backed）</span>
        <div class="desc">宣稱的 static 依賴在程式碼結構上有連線支撐。</div>
      </div>
      <div class="integ-legend-row">
        <span class="lbl">❌ 沒接上（gap）</span>
        <div class="desc">宣稱有 static 依賴，但 AST 找不到對應呼叫路徑，建議確認。</div>
      </div>
      <div class="integ-legend-row">
        <span class="lbl">⚠ 無法判定（undetermined）</span>
        <div class="desc">依賴目標不是程式碼節點（如 HTTP 或跨語言呼叫），無法從結構驗證。</div>
      </div>
      <div class="integ-legend-row">
        <span class="lbl">（無標示）未評估</span>
        <div class="desc">此功能沒有宣稱 static 依賴，不在整合健檢範圍內。</div>
      </div>
    </div>
    <hr class="integ-legend-divider">
    <div class="integ-legend-terms">
      <div class="integ-legend-term-title">static</div>
      <div class="integ-legend-term-desc">
        Agent 在標記功能依賴時使用的類型，表示「期待這條依賴在程式碼裡有直接的呼叫路徑」
        （同語言的直接 import / call）。The Door 會用 AST 驗證它是否真的接上。
      </div>
      <div class="integ-legend-term-title">AST（Abstract Syntax Tree，抽象語法樹）</div>
      <div class="integ-legend-term-desc">
        程式碼的結構化表示，記錄函式、類別與彼此的呼叫關係。The Door 以 AST 為基礎判斷
        功能之間是否存在實際連線，而非只看功能描述。
      </div>
    </div>
  `;

  function positionPopup() {
    const r = btn.getBoundingClientRect();
    popup.style.top  = (r.bottom + 6) + 'px';
    // 靠右對齊按鈕右緣，若超出左邊界則夾在 8px
    const left = Math.max(8, r.right - 340);
    popup.style.left = left + 'px';
  }

  btn.addEventListener('click', (e) => {
    e.stopPropagation();
    if (!popup.hidden) { popup.hidden = true; return; }
    positionPopup();
    popup.hidden = false;
  });

  popup.querySelector('.integ-legend-close').addEventListener('click', () => {
    popup.hidden = true;
  });

  document.addEventListener('click', (e) => {
    if (!popup.hidden && !popup.contains(e.target) && e.target !== btn) {
      popup.hidden = true;
    }
  });

  document.addEventListener('keydown', (e) => {
    if (e.key === 'Escape') popup.hidden = true;
  });
}

const VERDICT_LABEL = {
  gap: '❌ 沒接上', undetermined: '⚠ 無法判定',
};

// 把整合健檢渲染進 container。callbacks.onSelectFeature(featureId) 用於連動選取。
export function renderIntegrationPanel(container, integration, callbacks = {}) {
  container.textContent = '';
  if (!integration || integration.structure_missing) {
    const empty = document.createElement('div');
    empty.className = 'empty-state';
    empty.textContent = '未評估（尚未標記 static 依賴或缺結構檔）。';
    container.appendChild(empty);
    return;
  }
  const r = integration.rollup || {};
  const header = document.createElement('div');
  header.className = 'integration-summary';
  const claimed = (r.backed || 0) + (r.gap || 0) + (r.undetermined || 0);
  header.textContent = `整合健檢：${claimed} 條宣稱、${r.gap || 0} 條沒接上、${r.undetermined || 0} 條無法判定`;
  container.appendChild(header);

  // claimed=0：沒有任何 static/inferred 判定可言。誠實區分「未評估」與「真的沒依賴」，
  // 不可在此說「都接上了」（那會把未評估洗成全綠、違反誠實原則）。
  if (claimed === 0) {
    const none = document.createElement('div');
    none.className = 'empty-state';
    const na = r.not_assessed || 0;
    none.textContent = na > 0
      ? `未評估：${na} 條依賴關係尚未標記 static/inferred，無法判斷是否接上。`
      : '尚無功能依賴關係可檢查。';
    container.appendChild(none);
    return;
  }

  const issues = (integration.relations || []).filter(
    x => x.verdict === 'gap' || x.verdict === 'undetermined');
  if (issues.length === 0) {
    const ok = document.createElement('div');
    ok.className = 'empty-state';
    ok.textContent = '所有宣稱的依賴都接上了。';
    container.appendChild(ok);
    return;
  }
  for (const it of issues) {
    const row = document.createElement('button');
    row.type = 'button';
    row.className = 'integration-row integration-' + it.verdict;
    row.textContent = `${VERDICT_LABEL[it.verdict]}：${it.from_feature} → ${it.to_feature}`;
    row.addEventListener('click', () => callbacks.onSelectFeature?.(it.from_feature));
    container.appendChild(row);
  }
}

// 膜詞彙封閉集 drift-guard（H3）
// ─────────────────────────────────────────────────────────────────────────
// 守的是 KEY 維度：每個「以膜封閉集為鍵」的 viewer 消費點是否處理 schema 全集
// （漏值→fall-through 可見錯誤）。**不**碰 VALUE：label 中文／顏色／排序序 per-surface 各異。
// 單一來源＝checked-in schema enum（the_door/schemas/*.json）；Python 改 enum 而 JS 漏接 → 本測紅。
//
// 涵蓋邊界（誠實標明，spec §3.4）：本 guard 守「下列枚舉的消費點」，非自動發現全 viewer。
//   新增「以膜封閉集為鍵」的 JS 消費點時，須在此登記，否則 guard 不會自動抓到。
// 排序 map（TYPE_PRIORITY/CHANGE_PRIORITY/RISK_PRIORITY）刻意不守：漏鍵落 `?? 預設` 良性殿後退化、
//   膜本不編序（diff_membrane.py:22-24）。例外＝CONF_PRIORITY：漏鍵落 `?? 2`＝謊報 medium＝非良性，故守。
//
// 機制＝行為斷言為主（pure fn）＋集斷言（vocabulary 純資料 map，已 export）。

import { describe, it, expect } from 'vitest';
import { readFileSync, existsSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import path from 'node:path';

import { buildDisplayLabel, CONF_LABEL } from '../js/graph.js';
import { changeSymbol, CONF_PRIORITY } from '../js/ui-list.js';
import { DIFF_BADGE } from '../js/mindmap-util.js';
import { buildViewModelFromReport } from '../js/viewmodel.js';
import { CHANGE_TYPE_LABEL } from '../js/ui-detail.js';
import { DIFF_LABELS } from '../js/layers.js';
import { CONFIDENCE_LABEL } from '../js/ui-diff-explanation.js';

// 測檔在 viewer/tests/ → 上溯 4 層到 repo root，再 the_door/schemas（schema 不在 src 下）。
const SCHEMA_DIR = path.resolve(
  path.dirname(fileURLToPath(import.meta.url)),
  '../../../../the_door/schemas',
);

function readSchema(file) {
  const p = path.join(SCHEMA_DIR, file);
  if (!existsSync(p)) throw new Error(`schema 不存在（路徑/上溯層數錯）：${p}`); // fail-loud（非 silent skip）
  return JSON.parse(readFileSync(p, 'utf8'));
}

// ── schema enum 解析（三形狀，spec §3.3）─────────────────────────────────
function changeTypeEnum() {
  return readSchema('update-report.schema.json')
    .properties.l1_changes.items.properties.change_type.enum;            // 'enum'
}
function riskFlagsEnum() {
  return readSchema('update-report.schema.json')
    .properties.l1_changes.items.properties.risk_flags.items.enum;       // 'items-enum'
}
function confidenceConsts() {
  const oneOf = readSchema('l1-output.schema.json')
    .properties.l1.properties.features.items.properties.confidence.oneOf; // 'oneof-const'
  return oneOf.filter(o => typeof o.const === 'string').map(o => o.const);
}

// 守界：keys 須涵蓋 schemaSet，否則列出缺值丟錯（assert 失敗）。
function assertCovers(label, keys, schemaSet) {
  const keySet = new Set(keys);
  const missing = schemaSet.filter(v => !keySet.has(v));
  expect(missing, `${label} 漏接膜封閉集值：${missing.join(',')}`).toEqual([]);
}

// ── guard 自我有效性（meta：證非恆綠）─────────────────────────────────────
describe('membrane vocabulary — guard 自我有效性 (meta)', () => {
  it('schema enum 皆解析非空（fail-loud 基礎、路徑正確）', () => {
    expect(changeTypeEnum().length).toBeGreaterThan(0);
    expect(riskFlagsEnum().length).toBeGreaterThan(0);
    expect(confidenceConsts().length).toBeGreaterThan(0);
  });
  it('assertCovers 對缺值集會判失敗（非恆真）', () => {
    expect(() => assertCovers('demo', ['added', 'removed'],
      ['added', 'removed', 'attribute_changed', 'dependency_changed'])).toThrow();
  });
  it('assertCovers 對涵蓋集通過（含合法額外鍵）', () => {
    expect(() => assertCovers('demo', ['a', 'b', 'c'], ['a', 'b'])).not.toThrow();
  });
});

// ── change_type 軸 ───────────────────────────────────────────────────────
describe('membrane vocabulary — change_type 封閉集 drift-guard', () => {
  const SET = changeTypeEnum();

  it('changeSymbol 對每值非 fall-through 哨兵（?）', () => {
    SET.forEach(v => expect(changeSymbol(v), v).not.toBe('?'));
  });
  it('buildDisplayLabel 對每值帶 tag 前綴（非裸 label）', () => {
    SET.forEach(v => {
      const out = buildDisplayLabel({ change_type: v, label: 'L' });
      expect(out, v).not.toBe('L');     // 有 tag ⟹ ≠ 裸 label
      expect(out, v).toContain('L');
    });
  });
  it('DIFF_BADGE keys 涵蓋封閉集', () => assertCovers('DIFF_BADGE', Object.keys(DIFF_BADGE), SET));
  it('DIFF_LABELS keys 涵蓋封閉集', () => assertCovers('DIFF_LABELS', Object.keys(DIFF_LABELS), SET));
  it('CHANGE_TYPE_LABEL keys 涵蓋封閉集', () => assertCovers('CHANGE_TYPE_LABEL', Object.keys(CHANGE_TYPE_LABEL), SET));
});

// ── risk_flags 軸 ────────────────────────────────────────────────────────
describe('membrane vocabulary — risk_flags 封閉集 drift-guard', () => {
  const SET = riskFlagsEnum();
  it('buildViewModelFromReport risk_counts keys 涵蓋封閉集', () => {
    const vm = buildViewModelFromReport({ l1_changes: [] });
    assertCovers('risk_counts', Object.keys(vm.risk_counts), SET);
  });
});

// ── confidence 軸（schema 3 值 ∪ viewer 誠實額外 unknown）────────────────
describe('membrane vocabulary — confidence 封閉集 drift-guard', () => {
  const SET = [...confidenceConsts(), 'unknown'];   // unknown＝None/未評估 的 viewer 一等公民（H1/H1-5）
  it('CONF_LABEL keys 涵蓋 schema 3 值 ∪ unknown', () => assertCovers('CONF_LABEL', Object.keys(CONF_LABEL), SET));
  it('CONF_PRIORITY keys 涵蓋 schema 3 值 ∪ unknown', () => assertCovers('CONF_PRIORITY', Object.keys(CONF_PRIORITY), SET));
  it('CONFIDENCE_LABEL keys 涵蓋 schema 3 值 ∪ unknown', () => assertCovers('CONFIDENCE_LABEL', Object.keys(CONFIDENCE_LABEL), SET));
});

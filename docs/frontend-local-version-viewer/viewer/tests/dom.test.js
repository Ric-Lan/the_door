import { describe, it, expect } from 'vitest';
import { els } from '../js/dom.js';

describe('els (DOM element cache)', () => {
  it('exports an els object', () => {
    expect(els).toBeDefined();
    expect(typeof els).toBe('object');
  });

  const expectedIds = [
    'btnDiff', 'btnBaseline', 'btnCurrent', 'btnReanalyze',
    'summaryText', 'countAdded', 'countRemoved', 'countModified', 'countRisk',
    'listTitle', 'listSource', 'featureList',
    'detailSource', 'detailContent',
    'pipelineProgress', 'currentStep', 'stepsList',
    'updateModal', 'inputOldPath', 'inputNewPath', 'modalError', 'inputLanguage',
    'btnModalCancel', 'btnModalSubmit',
    'graphDrawer', 'graphBackdrop', 'btnGraphToggle', 'btnDrawerClose',
    'btnBackL1', 'btnMindmap',
  ];

  expectedIds.forEach(key => {
    it(`els.${key} is a DOM element`, () => {
      expect(els[key], `els.${key} should not be null`).not.toBeNull();
      expect(els[key] instanceof Element).toBe(true);
    });
  });
});

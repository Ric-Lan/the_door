import { describe, it, expect } from 'vitest';
import { readFileSync } from 'node:fs';
import { resolve, dirname } from 'node:path';
import { fileURLToPath } from 'node:url';

const __dirname = dirname(fileURLToPath(import.meta.url));
const css = readFileSync(resolve(__dirname, '../wizard.css'), 'utf8');

describe('wizard.css Part 2 shell + rail', () => {
  const required = [
    '.wizard-shell',
    '.wizard-rail',
    '.wizard-rail-brand',
    '.wizard-door-wrap',
    '.wizard-door-light',
    '.wizard-door-leaf',
    '.wizard-stepper',
    '.wizard-step',
    '.wizard-rail-foot',
    '.wizard-content',
    '.wizard-screen',
    '@keyframes wizardScreenIn',
    '@keyframes wizardThresholdOut',
    '.wizard-eyebrow',
    '.wizard-mode-note',
    '.wizard-btn-ghost',
    '.wizard-transient',
    '.wizard-bigspin',
    '.wizard-agent-why',
    '.wizard-agent-steps',
    '.wizard-astep',
    '.wizard-prog-note',
  ];
  for (const sel of required) {
    it(`defines: ${sel}`, () => {
      const re = new RegExp(sel.replace(/[.@]/g, m => '\\' + m) + '\\b');
      expect(css).toMatch(re);
    });
  }
});

describe('wizard.css font tokens scope (spec §1.3 B)', () => {
  it('defines --font-sans inside .wizard-shell scope (NOT :root)', () => {
    // Match `.wizard-shell, .wizard-shell * { ... --font-sans: ... }`
    expect(css).toMatch(/\.wizard-shell[^{]*{[^}]*--font-sans\s*:/);
  });
  it('defines --font-mono inside .wizard-shell scope', () => {
    expect(css).toMatch(/\.wizard-shell[^{]*{[^}]*--font-mono\s*:/);
  });
  it('does NOT define --font-sans / --font-mono in :root', () => {
    const rootBlock = css.match(/:root\s*{([^}]+)}/);
    if (rootBlock) {
      expect(rootBlock[1]).not.toMatch(/--font-sans\s*:/);
      expect(rootBlock[1]).not.toMatch(/--font-mono\s*:/);
    }
  });
});

describe('wizard.css door-light opacity:0 transition (spec §3.1 example)', () => {
  it('.wizard-door-light has opacity:0 starter (intentional, transition not keyframe)', () => {
    const block = css.match(/\.wizard-door-light\s*{([^}]+)}/);
    expect(block).toBeTruthy();
    expect(block[1]).toMatch(/opacity\s*:\s*0\b/);
    expect(block[1]).toMatch(/transition\s*:\s*opacity/);
  });
  it('.wizard-door-light.lit has non-zero opacity', () => {
    expect(css).toMatch(/\.wizard-door-light\.lit\s*{[^}]*opacity\s*:\s*\.?[1-9]/);
  });
});

describe('wizard.css @keyframes hygiene (spec §3.1)', () => {
  it('no @keyframes block contains opacity:0 starter', () => {
    const blocks = [...css.matchAll(/@keyframes\s+\w+\s*{([^@}]*(?:}[^@}]*)*?)}/g)];
    for (const b of blocks) {
      expect(b[1]).not.toMatch(/opacity\s*:\s*0\b/);
    }
  });
});

describe('wizard.css FIX-2 baseline preserved', () => {
  it('no rem literals (FIX-2 px-only discipline)', () => {
    expect((css.match(/\d*\.?\d+rem\b/g) || [])).toEqual([]);
  });
  it('all border-radius use px, token, or semantic values (no rem)', () => {
    const decls = css.match(/border-radius:\s*[^;]+;/g) || [];
    for (const d of decls) {
      // Allow: 0 (squared-off visual v2 card), 6px, var(--radius-card), 50% (circles),
      // 999px (pills), 2px (door frame detail), multi-value shorthands of the above
      expect(d).toMatch(/border-radius:\s*(0|6px|10px|var\(--radius-card\)|50%|999px|2px[\s\d]*[\dpx ]*)\s*;/);
    }
  });
});

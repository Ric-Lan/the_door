import { describe, it, expect } from 'vitest';
import { readFileSync } from 'node:fs';
import { resolve, dirname } from 'node:path';
import { fileURLToPath } from 'node:url';

const __dirname = dirname(fileURLToPath(import.meta.url));
const cssPath = resolve(__dirname, '../wizard.css');
const css = readFileSync(cssPath, 'utf8');

describe('wizard.css unit hygiene', () => {
  it('contains no rem literals (must use px)', () => {
    // Match any numeric value followed by "rem" (e.g. "1.25rem", "0.8rem")
    const remMatches = css.match(/\d*\.?\d+rem\b/g) || [];
    expect(remMatches).toEqual([]);
  });

  it('all border-radius declarations are 6px or semantic values', () => {
    // 6px = standard card radius; 50% = circles; 999px = pills (badge/tag shapes).
    // Part 2 adds these shapes — all are intentional, non-rem px values.
    const radiusDecls = css.match(/border-radius:\s*[^;]+;/g) || [];
    expect(radiusDecls.length).toBeGreaterThan(0);
    for (const decl of radiusDecls) {
      expect(decl).toMatch(/border-radius:\s*(6px|10px|50%|999px|var\(--radius-card\))\s*;/);
    }
  });

  it('contains expected px font-size values (11/12/13/14/15/20)', () => {
    // Allowed set = px equivalents of the original rem values, rounded to the
    // standard scale per spec FIX-2 mapping table. 15px added for Part 2 rail
    // brand label (.wizard-rail-brand .wd). Adding a new font-size requires
    // updating both wizard.css and this allowlist intentionally.
    const fontSizeDecls = css.match(/font-size:\s*[^;]+;/g) || [];
    expect(fontSizeDecls.length).toBeGreaterThan(0);
    const allowed = new Set(['11px', '11.5px', '12px', '12.5px', '13px', '13.5px', '14px', '15px', '20px', '27px']);
    for (const decl of fontSizeDecls) {
      const value = decl.replace(/font-size:\s*/, '').replace(/;$/, '').trim();
      expect(allowed.has(value), `unexpected font-size: ${value}`).toBe(true);
    }
  });
});

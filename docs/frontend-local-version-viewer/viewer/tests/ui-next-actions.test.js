import { describe, it, expect } from "vitest";
import { readFileSync } from "node:fs";
import { resolve, dirname } from "node:path";
import { fileURLToPath } from "node:url";
import { appendNextActionsSection } from "../js/ui-next-actions.js";

const __dirname = dirname(fileURLToPath(import.meta.url));
const stylesPath = resolve(__dirname, "../styles.css");
const styles = readFileSync(stylesPath, "utf8");

describe("ui-next-actions", () => {
  it("renders 建議的下一步 section when next_actions present", () => {
    const container = document.createElement("div");
    const feature = {
      next_actions: [
        { id: "x", title: "T", cli_command: "ls", priority: 1, rationale: "r" },
      ],
    };
    appendNextActionsSection(container, feature);
    expect(container.querySelector(".next-actions-section")).not.toBeNull();
    expect(container.textContent).toContain("ls");
  });

  it("renders nothing when next_actions empty", () => {
    const container = document.createElement("div");
    appendNextActionsSection(container, { next_actions: [] });
    expect(container.querySelector(".next-actions-section")).toBeNull();
  });

  it("each cli_command pre uses .not-analyzed-cmd terminal style", () => {
    const container = document.createElement("div");
    appendNextActionsSection(container, {
      next_actions: [
        { id: "x", title: "T", cli_command: "the-door analyze .", priority: 1 },
      ],
    });
    const pre = container.querySelector(".next-actions-section pre");
    expect(pre).not.toBeNull();
    expect(pre.classList.contains("not-analyzed-cmd")).toBe(true);
  });

  it("styles.css contains .next-actions-section rules", () => {
    expect(styles).toMatch(/\.next-actions-section\s*\{/);
    expect(styles).toMatch(/\.next-actions-section\s+h3\s*\{/);
    expect(styles).toMatch(/\.next-actions-section\s+ol\s*\{/);
  });
});

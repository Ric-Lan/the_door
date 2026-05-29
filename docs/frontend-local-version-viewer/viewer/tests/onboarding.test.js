import { describe, it, expect } from "vitest";
import { readFileSync } from "node:fs";
import { resolve, dirname } from "node:path";
import { fileURLToPath } from "node:url";
import { renderOnboardingCard } from "../js/onboarding.js";

const __dirname = dirname(fileURLToPath(import.meta.url));
const stylesPath = resolve(__dirname, "../styles.css");
const styles = readFileSync(stylesPath, "utf8");

describe("onboarding card", () => {
  it("renders when state.has_snapshots === false", () => {
    const container = document.createElement("div");
    const payload = {
      state: { project_path: "/x", has_snapshots: false, has_dot_the_door: false },
      next_actions: [
        {
          id: "analyze.first_time",
          title: "首次分析",
          cli_command: "the-door analyze /x",
          priority: 1,
          rationale: "r",
        },
      ],
    };
    renderOnboardingCard(container, payload);
    expect(container.querySelector(".onboarding-card")).not.toBeNull();
    expect(container.textContent).toContain("the-door analyze /x");
  });

  it("does NOT render when state.has_snapshots === true", () => {
    const container = document.createElement("div");
    const payload = { state: { has_snapshots: true }, next_actions: [] };
    renderOnboardingCard(container, payload);
    expect(container.querySelector(".onboarding-card")).toBeNull();
  });

  it("cli_command pre uses .not-analyzed-cmd terminal style", () => {
    const container = document.createElement("div");
    const payload = {
      state: { has_snapshots: false },
      next_actions: [
        { id: "x", title: "T", cli_command: "the-door analyze /x", priority: 1, rationale: "r" },
      ],
    };
    renderOnboardingCard(container, payload);
    const pre = container.querySelector(".onboarding-card pre");
    expect(pre).not.toBeNull();
    expect(pre.classList.contains("not-analyzed-cmd")).toBe(true);
  });

  it("styles.css contains .onboarding-card rules", () => {
    expect(styles).toMatch(/\.onboarding-card\s*\{/);
    expect(styles).toMatch(/\.onboarding-card\s+h2\s*\{/);
    expect(styles).toMatch(/\.onboarding-card\s+ol\s*\{/);
  });
});

import { describe, it, expect } from "vitest";
import { renderOnboardingCard } from "../js/onboarding.js";

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
});

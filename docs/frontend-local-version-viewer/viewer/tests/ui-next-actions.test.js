import { describe, it, expect } from "vitest";
import { appendNextActionsSection } from "../js/ui-next-actions.js";

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
});

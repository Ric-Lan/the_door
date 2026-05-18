import { describe, it, expect } from "vitest";
import { pickRef } from "../js/version-picker.js";

describe("version picker label-first", () => {
  it("emits git_tags[0] when present", () => {
    const snapshot = { version_id: "uuid-xxx", label: "manual-label", git_tags: ["v1.0.0"] };
    expect(pickRef(snapshot)).toBe("v1.0.0");
  });
  it("falls back to label when no git_tags", () => {
    const snapshot = { version_id: "uuid-xxx", label: "manual-label", git_tags: [] };
    expect(pickRef(snapshot)).toBe("manual-label");
  });
  it("falls back to version_id when no label", () => {
    const snapshot = { version_id: "uuid-xxx", label: null, git_tags: [] };
    expect(pickRef(snapshot)).toBe("uuid-xxx");
  });
});

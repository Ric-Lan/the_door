import { describe, it, expect } from "vitest";
import {
  buildSwitcherItems,
  toastMessage,
  shouldShowSwitcher,
  renderSwitcherDropdown,
  showToast,
} from "../js/project-switcher.js";

describe("buildSwitcherItems", () => {
  it("returns empty array when group is null", () => {
    expect(buildSwitcherItems(null)).toEqual([]);
  });

  it("returns all members with isCurrent flag", () => {
    const group = {
      members: [
        { id: "001", name: "ms-ts",    path: "/a", is_current: true },
        { id: "002", name: "color-go", path: "/b", is_current: false },
      ],
    };
    const items = buildSwitcherItems(group);
    expect(items).toHaveLength(2);
    expect(items[0].isCurrent).toBe(true);
    expect(items[1].isCurrent).toBe(false);
    expect(items[0].name).toBe("ms-ts");
  });
});

describe("toastMessage", () => {
  it("returns CLI command string for the member path", () => {
    const member = { name: "color-go", path: "C:/test-targets/color-go" };
    const msg = toastMessage(member);
    expect(msg).toContain("the-door ui");
    expect(msg).toContain("C:/test-targets/color-go");
  });
});

describe("shouldShowSwitcher", () => {
  it("returns false when group is null", () => {
    expect(shouldShowSwitcher(null)).toBe(false);
  });

  it("returns false when group has fewer than 2 members", () => {
    expect(shouldShowSwitcher({ members: [{ id: "001" }] })).toBe(false);
  });

  it("returns true when group has 2 or more members", () => {
    expect(shouldShowSwitcher({ members: [{ id: "001" }, { id: "002" }] })).toBe(true);
  });
});

describe("renderSwitcherDropdown", () => {
  it("populates options and marks current item as selected", () => {
    const select = document.createElement("select");
    document.body.appendChild(select);
    const items = [
      { id: "001", name: "ms-ts",    path: "/a", isCurrent: true },
      { id: "002", name: "color-go", path: "/b", isCurrent: false },
    ];
    renderSwitcherDropdown(select, items, () => {});
    expect(select.options).toHaveLength(2);
    expect(select.options[0].selected).toBe(true);
    expect(select.options[0].textContent).toContain("ms-ts");
    expect(select.options[1].selected).toBe(false);
    document.body.removeChild(select);
  });

  it("calls onSelect with name and path when non-current option is chosen", () => {
    const select = document.createElement("select");
    document.body.appendChild(select);
    const items = [
      { id: "001", name: "ms-ts",    path: "/a", isCurrent: true },
      { id: "002", name: "color-go", path: "/b", isCurrent: false },
    ];
    const calls = [];
    renderSwitcherDropdown(select, items, (m) => calls.push(m));
    select.value = "/b";
    select.dispatchEvent(new Event("change"));
    expect(calls).toHaveLength(1);
    expect(calls[0].path).toBe("/b");
    document.body.removeChild(select);
  });

  it("does not call onSelect when current item is re-selected", () => {
    const select = document.createElement("select");
    document.body.appendChild(select);
    const items = [
      { id: "001", name: "ms-ts", path: "/a", isCurrent: true },
    ];
    const calls = [];
    renderSwitcherDropdown(select, items, (m) => calls.push(m));
    select.value = "/a";
    select.dispatchEvent(new Event("change"));
    expect(calls).toHaveLength(0);
    document.body.removeChild(select);
  });
});

describe("showToast", () => {
  it("creates toast element with correct message", () => {
    document.getElementById("project-switcher-toast")?.remove();
    showToast("test message");
    const toast = document.getElementById("project-switcher-toast");
    expect(toast).not.toBeNull();
    expect(toast.textContent).toBe("test message");
    expect(toast.style.display).toBe("block");
  });

  it("reuses existing toast element on second call", () => {
    document.getElementById("project-switcher-toast")?.remove();
    showToast("first");
    showToast("second");
    const toasts = document.querySelectorAll("#project-switcher-toast");
    expect(toasts).toHaveLength(1);
    expect(toasts[0].textContent).toBe("second");
  });
});

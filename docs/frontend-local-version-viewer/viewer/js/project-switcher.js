/**
 * Project switcher — pure functions for the group-aware project dropdown.
 *
 * Data shape expected from GET /api/group:
 *   { group: { members: [{id, name, path, is_current}] } | null }
 */

/**
 * Map API group.members into switcher item objects.
 * @param {object|null} group
 * @returns {{ id: string, name: string, path: string, isCurrent: boolean }[]}
 */
export function buildSwitcherItems(group) {
  if (!group || !Array.isArray(group.members)) return [];
  return group.members.map((m) => ({
    id: m.id,
    name: m.name,
    path: m.path,
    isCurrent: m.is_current === true,
  }));
}

/**
 * Return true if the switcher should be rendered (group with ≥2 members).
 * @param {object|null} group
 * @returns {boolean}
 */
export function shouldShowSwitcher(group) {
  return !!(group && Array.isArray(group.members) && group.members.length >= 2);
}

/**
 * Build the inline toast message instructing the user how to open a project.
 * @param {{ name: string, path: string }} member
 * @returns {string}
 */
export function toastMessage(member) {
  return `請在終端機執行：the-door ui ${member.path}`;
}

/**
 * Render the project switcher dropdown into a <select> container element.
 * @param {HTMLSelectElement} container
 * @param {{ id, name, path, isCurrent }[]} items
 * @param {(member: {name:string, path:string}) => void} onSelect
 */
export function renderSwitcherDropdown(container, items, onSelect) {
  container.innerHTML = "";
  items.forEach((item) => {
    const opt = document.createElement("option");
    opt.value = item.path;
    opt.textContent = (item.isCurrent ? "✓ " : "  ") + item.name;
    opt.selected = item.isCurrent;
    opt.dataset.name = item.name;
    container.appendChild(opt);
  });
  container.onchange = (e) => {
    const path = e.target.value;
    const name = e.target.selectedOptions[0]?.dataset.name ?? path;
    if (items.find((i) => i.path === path)?.isCurrent) return;
    onSelect({ name, path });
  };
}

/**
 * Show an inline toast below the topbar for 3 seconds.
 * Creates or reuses #project-switcher-toast element.
 * @param {string} message
 */
export function showToast(message) {
  let toast = document.getElementById("project-switcher-toast");
  if (!toast) {
    toast = document.createElement("div");
    toast.id = "project-switcher-toast";
    toast.style.cssText = [
      "position:fixed", "top:48px", "left:50%", "transform:translateX(-50%)",
      "background:#1e1e2e", "color:#cdd6f4", "padding:8px 16px",
      "border-radius:6px", "font-size:13px", "z-index:9999",
      "box-shadow:0 2px 8px rgba(0,0,0,0.4)", "font-family:monospace",
    ].join(";");
    document.body.appendChild(toast);
  }
  toast.textContent = message;
  toast.style.display = "block";
  clearTimeout(toast._timer);
  toast._timer = setTimeout(() => { toast.style.display = "none"; }, 3000);
}

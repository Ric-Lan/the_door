// Detail panel "建議的下一步" section (S3.2).
// Renders feature.next_actions as an ordered list with a code block per item.
// Skipped entirely when next_actions is empty.
export function appendNextActionsSection(container, feature) {
  const actions = feature?.next_actions ?? [];
  if (actions.length === 0) return;
  const section = document.createElement("section");
  section.className = "next-actions-section";
  const heading = document.createElement("h3");
  heading.textContent = "建議的下一步";
  section.appendChild(heading);
  const list = document.createElement("ol");
  for (const action of actions) {
    const li = document.createElement("li");
    const strong = document.createElement("strong");
    strong.textContent = action.title ?? "";
    const pre = document.createElement("pre");
    pre.textContent = action.cli_command || action.mcp_tool || action.viewer_route || "";
    li.append(strong, pre);
    list.appendChild(li);
  }
  section.appendChild(list);
  container.appendChild(section);
}

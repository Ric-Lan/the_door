// Onboarding card for empty projects (S3.1).
// Renders a welcome card with the top-3 next_actions from /api/status when
// the project has no snapshots yet. Skipped entirely when has_snapshots === true.
export function renderOnboardingCard(container, payload) {
  if (payload.state?.has_snapshots === true) return;
  const card = document.createElement("div");
  card.className = "onboarding-card";
  const heading = document.createElement("h2");
  heading.textContent = "歡迎使用 The Door";
  card.appendChild(heading);
  const top3 = (payload.next_actions ?? []).slice(0, 3);
  const list = document.createElement("ol");
  for (const action of top3) {
    const li = document.createElement("li");
    li.innerHTML = `<strong>${action.title}</strong><pre class="not-analyzed-cmd">${action.cli_command || action.mcp_tool || action.viewer_route}</pre>`;
    list.appendChild(li);
  }
  card.appendChild(list);
  container.appendChild(card);
}

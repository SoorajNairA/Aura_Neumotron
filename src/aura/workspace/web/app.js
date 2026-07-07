const state = {
  projectId: null,
  graph: null,
  representations: [],
  selectedId: null,
  hoverId: null,
  focusIds: new Set(),
  criticalIds: new Set(),
  verification: null,
  events: [],
  socket: null,
  lastEventId: 0,
  reconnectAttempt: 0,
};
const $ = (id) => document.getElementById(id);
function entities(kind) {
  return state.graph ? state.graph.entities.filter((x) => x.kind === kind) : [];
}
function entity(id) {
  return state.graph?.entities.find((x) => x.id === id);
}
function highlight(id) {
  if (state.criticalIds.has(id)) return "critical";
  if (state.selectedId === id) return "selected";
  if (state.focusIds.has(id)) return "aura-focus";
  if (state.hoverId === id) return "hover";
  return "";
}
function render() {
  if (!state.graph) return;
  const project = entity(state.graph.project_id);
  $("title").textContent = project.name;
  $("tree").innerHTML = tree(project.id);
  $("canvas").innerHTML = entities("component")
    .map(
      (c) =>
        `<button class="component ${highlight(c.id)}" data-id="${c.id}">${c.name}<small><br>${c.metadata.role || ""}</small></button>`,
    )
    .join("");
  document.querySelectorAll(".component").forEach((el) => {
    el.onmouseenter = () => {
      state.hoverId = el.dataset.id;
      render();
    };
    el.onmouseleave = () => {
      state.hoverId = null;
      render();
    };
    el.onclick = () => select(el.dataset.id);
  });
  const selected = entity(state.selectedId);
  $("component-info").textContent = selected
    ? `${selected.name} — ${selected.metadata.role || ""} — ${selected.verification_status} — ${selected.metadata.description || ""}`
    : "Select a semantic component.";
  const related = selected ? entities("verification_result").filter((v) =>
    (v.metadata.semanticIds || v.metadata.entity_ids || []).includes(selected.id)) : [];
  $("component-verification").innerHTML = related.length
    ? `<h3>Verified properties, warnings, and assumptions</h3>${related.map((v) =>
      `<article class="finding ${v.verification_status}"><b>${v.metadata.check}</b><span>${v.verification_status}</span><p>${v.name}</p>${(v.metadata.evidenceIds || []).map((id) => `<button class="evidence-link" data-evidence="${id}">Inspect source</button>`).join("")}${(v.verification_status === "failed" || v.metadata.check === "flyback") ? `<button class="repair-link" data-finding="${v.id}">Ask AURA to fix</button>` : ""}</article>`).join("")}`
    : "";
  document.querySelectorAll(".evidence-link").forEach((button) =>
    button.onclick = () => inspectEvidence(button.dataset.evidence));
  document.querySelectorAll(".repair-link").forEach((button) =>
    button.onclick = () => requestRepair(button.dataset.finding));
  const summary = state.verification?.summary || {};
  $("verification-summary").innerHTML = Object.entries(summary).map(([status, count]) =>
    `<span class="status-chip ${status}"><b>${count}</b> ${status.replaceAll("_", " ")}</span>`).join("");
  $("warnings").innerHTML = entities("verification_result")
    .map(
      (v) =>
        `<li class="${v.metadata.severity || ""}">${v.name} [${v.verification_status}]</li>`,
    )
    .join("");
  const representation = state.representations.find(
    (x) => x.componentId === state.selectedId,
  );
  $("representation").textContent = representation
    ? `Representation: ${representation.type} — ${representation.status}; fallback: ${representation.fallbackType}`
    : "Select a component to inspect its representation state.";
}
function tree(id) {
  const item = entity(id);
  const children = state.graph.entities.filter(
    (x) =>
      x.parent_id === id &&
      ![
        "verification_result",
        "connection",
        "evidence",
        "assumption",
        "requirement",
        "constraint",
      ].includes(x.kind),
  );
  return `<div class="node" data-id="${item.id}">${item.name}${children.map((x) => tree(x.id)).join("")}</div>`;
}
function select(id) {
  if (!entity(id)) return;
  state.selectedId = id;
  render();
  const frame = $("representation-view");
  frame.contentWindow?.postMessage(
    { type: "aura.workspace.selection", semanticId: id },
    location.origin,
  );
}
window.auraFocus = (ids, explanation) => {
  state.focusIds = new Set(ids.filter(entity));
  $("status").textContent = explanation;
  render();
  $("representation-view").contentWindow?.postMessage(
    { type: "aura.workspace.focus", semanticIds: [...state.focusIds] },
    location.origin,
  );
};
async function loadProject() {
  const project = await (
    await fetch(`/api/projects/${state.projectId}`)
  ).json();
  state.representations = project.representations || [];
  const frame = $("representation-view");
  frame.src = `/assets/representation/index.html?projectId=${encodeURIComponent(state.projectId)}`;
  frame.style.display = "block";
  [state.graph, state.verification] = await Promise.all([
    fetch(`/api/projects/${state.projectId}/graph`).then((response) => response.json()),
    fetch(`/api/projects/${state.projectId}/verification`).then((response) => response.json()),
  ]);
  const revisions = await (
    await fetch(`/api/projects/${state.projectId}/revisions`)
  ).json();
  $("revisions").innerHTML = revisions
    .map((r) => `<li>${r.summary}</li>`)
    .join("");
  state.criticalIds = new Set(
    entities("verification_result")
      .filter((v) => v.metadata.severity === "critical")
      .flatMap((v) => v.metadata.entity_ids || []),
  );
  render();
}
function inspectEvidence(id) {
  const evidence = entities("evidence").find((item) => item.id === id)?.metadata;
  if (!evidence) return;
  $("evidence-detail").textContent = JSON.stringify({
    title: evidence.title, publisher: evidence.publisher, kind: evidence.kind,
    retrievedAt: evidence.retrievedAt, properties: evidence.properties,
    source: evidence.source, contentHash: evidence.contentHash,
  }, null, 2);
  $("evidence-dialog").showModal();
}
$("close-evidence").onclick = () => $("evidence-dialog").close();
async function requestRepair(findingId) {
  const response = await fetch(`/api/projects/${state.projectId}/verification/${findingId}/repair-proposal`, {method:"POST"});
  const proposal = await response.json();
  $("change").textContent = response.ok
    ? `Repair preview (not applied): ${proposal.summary}\nAffected: ${proposal.affectedSemanticIds.join(", ")}\nVerification: ${proposal.verification.checks.map((x) => `${x.state}: ${x.message}`).join("; ")}`
    : JSON.stringify(proposal);
}
function connect(after = 0) {
  if (state.socket) state.socket.close();
  const scheme = location.protocol === "https:" ? "wss" : "ws";
  state.socket = new WebSocket(
    `${scheme}://${location.host}/api/projects/${state.projectId}/events?afterEventId=${after}`,
  );
  state.socket.onmessage = async (message) => {
    const event = JSON.parse(message.data);
    if (event.eventId <= state.lastEventId) return;
    state.lastEventId = event.eventId;
    state.reconnectAttempt = 0;
    state.events.push(event);
    $("timeline").insertAdjacentHTML(
      "beforeend",
      `<span class="event">${event.eventId}. ${event.type}</span>`,
    );
    if (event.type === "task.fallback_used")
      $("status").textContent = "Using deterministic fallback";
    else if (event.type === "planning.live_model")
      $("status").textContent = "Planning with live model";
    else if (event.type === "project.ready")
      $("status").textContent = "Project ready";
    if (event.type === "focus.requested")
      window.auraFocus(event.payload.entity_ids, event.payload.explanation);
    if (event.type === "revision.committed") await loadProject();
  };
  state.socket.onclose = () => {
    if (state.projectId)
      setTimeout(() => connect(state.lastEventId), Math.min(1000 * 2 ** state.reconnectAttempt++, 15000));
  };
}
$("create").onclick = async () => {
  state.events = [];
  state.lastEventId = 0;
  $("timeline").innerHTML = "";
  $("status").textContent = "Understanding objective â†’ Planning project...";
  const response = await fetch("/api/projects", {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify({
      objective: $("objective").value,
      planningMode: $("mode").value,
    }),
  });
  if (!response.ok) {
    const error=await response.json();
    $("status").textContent = error.detail?.status === "NEEDS_CLARIFICATION" ? `Clarification needed: ${error.detail.questions?.[0]}` : `Unsupported: ${error.detail?.reasons?.[0] || "Project could not be created"}`;
    return;
  }
  const project = await response.json();
  state.projectId = project.projectId;
  $("status").textContent =
    project.planningMode === "deterministic_fallback"
      ? "Using deterministic fallback"
      : "Project ready";
  await loadProject();
  connect(0);
};
$("modify").onclick = async () => {
  if (!state.selectedId) {
    $("change").textContent = "Select component-driver first.";
    return;
  }
  const response = await fetch(
    `/api/projects/${state.projectId}/modifications`,
    {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify({
        selectedComponentId: state.selectedId,
        request: $("modification").value,
      }),
    },
  );
  const result = await response.json();
  $("change").textContent = response.ok
    ? `${result.before.name} → ${result.after.name}\n${result.summary}`
    : JSON.stringify(result);
  if (response.ok) await loadProject();
};
async function listProjects() {
  const projects = await (await fetch("/api/projects")).json();
  $("projects").innerHTML =
    '<option value="">Existing projects</option>' +
    projects
      .map(
        (p) =>
          `<option value="${p.projectId}">${p.projectId} — revision ${p.revision}</option>`,
      )
      .join("");
}
$("open-project").onclick = async () => {
  const id = $("projects").value;
  if (!id) return;
  state.projectId = id;
  state.events = [];
  state.lastEventId = 0;
  $("timeline").innerHTML = "";
  await loadProject();
  connect(0);
  $("status").textContent = "Recovered persisted project";
};
listProjects();
window.addEventListener("message", (event) => {
  if (
    event.origin === location.origin &&
    event.data?.type === "aura.representation.selection"
  )
    select(event.data.semanticId);
});

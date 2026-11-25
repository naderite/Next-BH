const get = (id) => document.getElementById(id);
const statuses = { ready: "Prêt", pending_review: "À valider", closed: "Clôturé" };
const needs = { occupant: "occupant", non_occupant: "non-occupant" };
const actions = {
  STOP: "Clôturer",
  ASK_HOUSING_NEED: "Préciser le besoin",
  OFFER_OCCUPANT: "Présenter la formule Occupant",
  OFFER_NON_OCCUPANT: "Présenter la formule Non-occupant",
  EXPLAIN_OCCUPANT: "Expliquer la formule Occupant",
  EXPLAIN_NON_OCCUPANT: "Expliquer la formule Non-occupant",
  FOLLOW_UP: "Relancer",
};
const replies = {
  need_revealed: "Besoin précisé", objection: "Demande de précisions",
  no_response: "Aucune réponse", refusal: "Refus", accepted: "Intérêt confirmé",
};
const reasons = { already_owned: "produit déjà détenu", missing_evidence: "source manquante" };
let episode;
let busy = false;

async function api(path, body) {
  const result = await fetch(path, body === undefined ? {} : {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  const data = await result.json();
  if (!result.ok) throw new Error(typeof data.detail === "string" ? data.detail : "Vérifiez les champs saisis.");
  return data;
}

function render(data) {
  episode = data;
  get("episode").hidden = false;
  get("case-id").value = data.id;
  localStorage.setItem("next-bh-episode", data.id);
  get("summary").textContent =
    `${statuses[data.status]} · Besoin ${needs[data.need] ?? "à préciser"} · ${data.contacts} contact(s) simulé(s)`;
  get("step").hidden = data.status !== "ready";
  get("draft").hidden = !data.draft;
  if (data.draft) {
    get("message").textContent = data.draft.body;
    const evidence = data.draft.evidence;
    get("source").textContent = evidence ? `${evidence.document} · ${evidence.locator}` : "";
  }
  get("history").replaceChildren(...data.events.map((event) => {
    const item = document.createElement("li");
    if (event.type === "policy") {
      const reason = reasons[event.reason];
      item.textContent = reason ? `${actions[event.action]} · ${reason}` : actions[event.action];
    }
    if (event.type === "review") {
      item.textContent = `Révision ${event.draft.revision} ${event.verdict === "approve" ? "approuvée" : "rejetée"} par ${event.reviewer}`;
    }
    if (event.type === "simulated_response") item.textContent = `Réponse simulée · ${replies[event.reply]}`;
    if (event.type === "execution_blocked") item.textContent = "Action bloquée · la version du catalogue a changé";
    return item;
  }));
}

async function run(task) {
  if (busy) return;
  busy = true;
  const buttons = [...document.querySelectorAll("button")];
  for (const button of buttons) button.disabled = true;
  get("status").textContent = "";
  try {
    await task();
  } catch (error) {
    get("status").textContent = error.message;
  } finally {
    busy = false;
    for (const button of buttons) button.disabled = false;
  }
}

function openEpisode(id) {
  return api(`/episodes/${encodeURIComponent(id)}`).then(render);
}

get("new-case").addEventListener("submit", (event) => {
  event.preventDefault();
  run(async () => render(await api("/episodes", { id: crypto.randomUUID(), scenario: get("scenarios").value })));
});
get("open-case").addEventListener("submit", (event) => {
  event.preventDefault();
  run(() => openEpisode(get("case-id").value.trim()));
});
get("step").addEventListener("click", () => run(async () => {
  render(await api(`/episodes/${episode.id}/step`, { request_id: crypto.randomUUID(), revision: episode.revision }));
}));
get("review").addEventListener("submit", (event) => {
  event.preventDefault();
  const verdict = event.submitter.value;
  run(async () => render(await api(`/episodes/${episode.id}/review`, {
    request_id: crypto.randomUUID(), revision: episode.revision, verdict, reviewer: get("reviewer").value.trim(),
  })));
});
run(async () => {
  for (const { id, label } of await api("/scenarios")) get("scenarios").add(new Option(label, id));
  const previous = localStorage.getItem("next-bh-episode");
  if (previous) await openEpisode(previous);
});

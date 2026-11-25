"""One checkpointed graph turn, from policy decision through review and simulation."""

from typing import TypedDict

from langgraph.graph import END, START, StateGraph
from langgraph.types import interrupt

from mvp.housing import (
    PRODUCT_ACTIONS, Action, Need, Reply, allowed_actions, contact_result, prepare_draft, rules,
)


class Episode(TypedDict, total=False):
    scenario: str
    revision: int
    status: str
    need: Need | None
    owned: Need | None
    available_evidence: list[Need]
    reply: Reply
    contacts: int
    sent: list[str]
    action: str
    draft: dict | None
    request: dict | None
    receipts: dict
    events: list[dict]


def decide(state: Episode, policy, index):
    request = state["request"]
    if request is None:
        return {}

    context = {
        **state,
        "available_evidence": [need for need in state["available_evidence"] if need in index.entries],
    }
    allowed = allowed_actions(context)
    action = rules(allowed) if policy is None else policy.act(context, allowed)
    if action not in allowed:
        raise ValueError("The policy selected an ineligible action")
    revision = state["revision"] + 1
    evidence = None
    if action in PRODUCT_ACTIONS.get(state["need"], ()):
        evidence = {
            **index.entries[state["need"]], "catalog_version": index.version,
            "catalog_sha256": index.digest,
        }
    draft = None if action == Action.STOP else prepare_draft(action, evidence, revision)
    event = {
        "type": "policy",
        "revision": revision,
        "policy": "rules-v1" if policy is None else policy.version,
        "allowed": [candidate.name for candidate in allowed],
        "action": action.name,
    }
    if action == Action.STOP and state["need"] is not None:
        if state["need"] == state["owned"]:
            event["reason"] = "already_owned"
        elif state["need"] not in context["available_evidence"]:
            event["reason"] = "missing_evidence"
    return {
        "revision": revision,
        "status": "pending_review" if draft else "closed",
        "action": action.name,
        "draft": draft,
        "events": [*state["events"], event],
        "receipts": {**state["receipts"], request["request_id"]: request},
        "request": None,
    }


def review(state: Episode, index):
    draft = state["draft"]
    decision = interrupt({"revision": draft["revision"], "action": state["action"]})
    approved = decision["verdict"] == "approve"
    action = Action[state["action"]]
    evidence = draft["evidence"]
    if decision["revision"] != draft["revision"] or (approved and action not in allowed_actions(state)):
        raise ValueError("Cannot execute a stale draft or an ineligible action")
    revision = state["revision"] + 1
    events = [*state["events"], {
        "type": "review",
        "revision": revision,
        "draft": draft,
        "verdict": decision["verdict"],
        "reviewer": decision["reviewer"],
        "recorded_at": decision["recorded_at"],
    }]
    update = {
        "revision": revision,
        "draft": None,
        "status": "closed",
        "events": events,
        "receipts": {**state["receipts"], decision["request_id"]: decision},
    }
    if approved and evidence is not None and evidence.get("catalog_sha256") != index.digest:
        update["events"] = [*events, {"type": "execution_blocked", "reason": "evidence_version_changed"}]
    elif approved:
        outcome = contact_result(state, action)
        update.update(outcome)
        update["events"] = [*events, {
            "type": "simulated_response", "action": action.name, "reply": outcome["reply"],
        }]
    return update


def build_workflow(checkpointer, index, policy=None):
    graph = StateGraph(Episode)
    graph.add_node("decide", lambda state: decide(state, policy, index))
    graph.add_node("review", lambda state: review(state, index))
    graph.add_edge(START, "decide")
    graph.add_conditional_edges(
        "decide",
        lambda state: "review" if state["status"] == "pending_review" else END,
    )
    graph.add_edge("review", END)
    return graph.compile(checkpointer=checkpointer)

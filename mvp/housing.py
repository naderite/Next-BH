"""Shared housing action contract and initial synthetic episode dynamics."""

from enum import IntEnum
from typing import Literal


class Action(IntEnum):
    STOP = 0
    ASK_HOUSING_NEED = 1
    OFFER_OCCUPANT = 2
    OFFER_NON_OCCUPANT = 3
    EXPLAIN_OCCUPANT = 4
    EXPLAIN_NON_OCCUPANT = 5
    FOLLOW_UP = 6


Need = Literal["occupant", "non_occupant"]
Reply = Literal["none", "need_revealed", "objection", "no_response", "refusal", "accepted"]
CONTACT_LIMIT = 5

SCENARIOS = {
    "tenant": ("Locataire", "occupant", "objection"),
    "landlord": ("Propriétaire bailleur", "non_occupant", "no_response"),
    "refusal": ("Refus après proposition", "occupant", "refusal"),
    "owned": ("Produit déjà détenu", "occupant", "objection"),
    "missing_evidence": ("Catalogue incomplet", "non_occupant", "objection"),
}

PRODUCT_ACTIONS = {
    "occupant": (Action.OFFER_OCCUPANT, Action.EXPLAIN_OCCUPANT),
    "non_occupant": (Action.OFFER_NON_OCCUPANT, Action.EXPLAIN_NON_OCCUPANT),
}


def initial_scenario(scenario):
    return {
        "scenario": scenario,
        "need": None,
        "owned": "occupant" if scenario == "owned" else None,
        "available_evidence": [
            need for need in PRODUCT_ACTIONS if scenario != "missing_evidence" or need != "non_occupant"
        ],
        "contacts": 0,
        "sent": [],
        "reply": "none",
    }


def allowed_actions(state):
    allowed = [Action.STOP]
    if state["contacts"] >= CONTACT_LIMIT or state["reply"] in ("accepted", "refusal"):
        return allowed
    need = state["need"]
    if need is None:
        return [*allowed, Action.ASK_HOUSING_NEED]
    if need == state["owned"] or need not in state["available_evidence"]:
        return allowed
    offer, explain = PRODUCT_ACTIONS[need]
    sent = state["sent"]
    if offer.name not in sent:
        allowed.append(offer)
    if state["reply"] == "objection" and explain.name not in sent:
        allowed.append(explain)
    if state["reply"] == "no_response" and Action.FOLLOW_UP.name not in sent:
        allowed.append(Action.FOLLOW_UP)
    return allowed


def requires_evidence(action, need):
    return action == Action.FOLLOW_UP or action in PRODUCT_ACTIONS.get(need, ())


def rules(allowed):
    return next((candidate for candidate in allowed if candidate != Action.STOP), Action.STOP)


def prepare_draft(action, evidence, revision):
    if action == Action.ASK_HOUSING_NEED:
        body = "Bonjour, occupez-vous le logement à assurer ou le proposez-vous à la location ?"
    elif action == Action.FOLLOW_UP:
        body = "Bonjour, souhaitez-vous poursuivre notre échange sur votre besoin en assurance habitation ?"
    else:
        body = (
            "Bonjour, voici un extrait de la documentation correspondant à votre situation.\n\n"
            f"« {evidence['excerpt']} » [{evidence['id']}]\n\n"
            "Souhaitez-vous poursuivre cet échange ?"
        )
    return {"revision": revision, "body": body, "evidence": evidence}


def contact_result(state, action):
    _, hidden_need, offer_reply = SCENARIOS[state["scenario"]]
    need = state["need"]
    if action == Action.ASK_HOUSING_NEED:
        need, reply = hidden_need, "need_revealed"
    elif action in (Action.OFFER_OCCUPANT, Action.OFFER_NON_OCCUPANT):
        reply = offer_reply
    else:
        reply = "accepted"
    contacts = state["contacts"] + 1
    return {
        "need": need,
        "reply": reply,
        "contacts": contacts,
        "sent": [*state["sent"], action.name],
        "status": "closed" if reply in ("refusal", "accepted") or contacts >= CONTACT_LIMIT else "ready",
    }

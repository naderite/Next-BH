"""The shared policy observation and the loader for a trusted MaskablePPO artifact."""

from hashlib import sha256
from io import BytesIO

import numpy as np
from sb3_contrib import MaskablePPO

from mvp.housing import CONTACT_LIMIT, Action

CONTRACT = "housing-observation-v1"
NEEDS = ("occupant", "non_occupant")
REPLIES = ("none", "need_revealed", "objection", "no_response", "refusal", "accepted")
OBSERVATION_SIZE = len(NEEDS) * 3 + len(REPLIES) + len(Action) + 1


def observation(state):
    return np.array([
        *(state["need"] == need for need in NEEDS),
        *(state["owned"] == need for need in NEEDS),
        *(need in state["available_evidence"] for need in NEEDS),
        *(state["reply"] == reply for reply in REPLIES),
        *(action.name in state["sent"] for action in Action),
        (CONTACT_LIMIT - state["contacts"]) / CONTACT_LIMIT,
    ], dtype=np.float32)


def action_mask(allowed):
    return np.array([action in allowed for action in Action], dtype=np.bool_)


class TrainedPolicy:
    def __init__(self, checkpoint, digest):
        if len(digest) != 64 or any(character not in "0123456789abcdef" for character in digest):
            raise ValueError("Set NEXT_BH_POLICY_SHA256 to the trusted artifact's lowercase SHA-256.")
        content = checkpoint.read_bytes()
        if sha256(content).hexdigest() != digest:
            raise ValueError("The MaskablePPO checkpoint does not match its configured SHA-256.")
        self.model = MaskablePPO.load(BytesIO(content), device="cpu")
        if (
            getattr(self.model, "housing_contract", None) != CONTRACT
            or self.model.observation_space.shape != (OBSERVATION_SIZE,)
            or self.model.action_space.n != len(Action)
        ):
            raise ValueError("The checkpoint is incompatible with the housing policy contract.")
        self.version = f"maskableppo:sha256:{digest}"

    def act(self, state, allowed):
        action, _ = self.model.predict(observation(state), action_masks=action_mask(allowed), deterministic=True)
        return Action(int(action))

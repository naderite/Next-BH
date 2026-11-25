"""Train and evaluate an initial MaskablePPO checkpoint on the shared simulator."""

import argparse
from hashlib import sha256
import json
from pathlib import Path
import random

import gymnasium as gym
from gymnasium import spaces
from sb3_contrib import MaskablePPO
import torch

from mvp.housing import Action, SCENARIOS, allowed_actions, contact_result, initial_scenario, rules
from mvp.policy import CONTRACT, OBSERVATION_SIZE, TrainedPolicy, action_mask, observation


class HousingEnv(gym.Env):
    def __init__(self):
        self.action_space = spaces.Discrete(len(Action))
        self.observation_space = spaces.Box(0.0, 1.0, (OBSERVATION_SIZE,))

    def reset(self, *, seed=None, options=None):
        super().reset(seed=seed)
        scenario = (options or {}).get("scenario")
        self.state = initial_scenario(scenario if scenario is not None else self.np_random.choice(list(SCENARIOS)))
        return observation(self.state), {}

    def action_masks(self):
        return action_mask(allowed_actions(self.state))

    def step(self, index):
        if not self.action_space.contains(index) or Action(index) not in allowed_actions(self.state):
            return observation(self.state), -1.0, True, False, {"invalid": True}
        action = Action(index)
        if action == Action.STOP:
            return observation(self.state), 0.0, True, False, {}
        self.state.update(contact_result(self.state, action))
        reward = float(self.state["reply"] == "accepted") - 0.1
        return observation(self.state), reward, self.state["status"] == "closed", False, {}


def measure(choose, episode_seeds):
    env = HousingEnv()
    count = len(episode_seeds)
    total_reward = 0.0
    accepted = contacts = invalid = 0
    for seed in episode_seeds:
        randomizer = random.Random(seed)
        env.reset(seed=seed)
        done = False
        while not done:
            action = choose(env.state, allowed_actions(env.state), randomizer)
            _, reward, done, _, info = env.step(int(action))
            total_reward += reward
            invalid += info.get("invalid", False)
        accepted += env.state["reply"] == "accepted"
        contacts += env.state["contacts"]
    return {
        "episodes": count,
        "mean_reward": total_reward / count,
        "simulated_acceptance_rate": accepted / count,
        "mean_contacts": contacts / count,
        "invalid_actions": invalid,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--steps", type=int, default=4096)
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()
    if args.steps < 256 or args.seed < 0 or args.output.suffix != ".zip":
        parser.error("Use at least 256 steps, a nonnegative seed and a .zip output path.")
    report_path = args.output.with_suffix(".json")
    if args.output.exists() or report_path.exists():
        parser.error("Choose a new output path.")

    torch.set_num_threads(1)
    model = MaskablePPO("MlpPolicy", HousingEnv(), seed=args.seed, device="cpu", n_steps=256, batch_size=64)
    model.housing_contract = CONTRACT
    model.learn(total_timesteps=args.steps)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    model.save(args.output)
    digest = sha256(args.output.read_bytes()).hexdigest()
    trained = TrainedPolicy(args.output, digest)
    seeds = range(100_000, 100_200)
    report = {
        "evaluation": "synthetic scenario replay using separate evaluation RNG seeds",
        "seed": args.seed,
        "training_steps": model.num_timesteps,
        "contract": CONTRACT,
        "checkpoint_sha256": digest,
        "maskableppo": measure(lambda state, allowed, rng: trained.act(state, allowed), seeds),
        "rules": measure(lambda state, allowed, rng: rules(allowed), seeds),
        "random_valid": measure(lambda state, allowed, rng: rng.choice(allowed), seeds),
    }
    report_path.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()

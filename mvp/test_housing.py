"""Integration checks for the supported housing workspace and persistent API."""

from concurrent.futures import ThreadPoolExecutor
from hashlib import sha256
import os
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import Mock, patch
from uuid import uuid4

from fastapi.testclient import TestClient

from mvp.app import create_app
from mvp.catalog import EvidenceIndex, build_index
from mvp.housing import Action
from mvp.workflow import build_workflow


class HousingTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        directory = TemporaryDirectory(ignore_cleanup_errors=True)
        cls.addClassCleanup(directory.cleanup)
        cls.evidence = Path(directory.name) / "evidence"
        build_index(cls.evidence)

    def post(self, client, path, **body):
        response = client.post(path, json=body)
        self.assertEqual(response.status_code, 200, response.text)
        return response.json()

    def start(self, client, scenario):
        return self.post(client, "/episodes", id=str(uuid4()), scenario=scenario)

    def step(self, client, episode):
        return self.post(client, f"/episodes/{episode['id']}/step",
                         revision=episode["revision"], request_id=str(uuid4()))

    def approve(self, client, episode):
        return self.post(client, f"/episodes/{episode['id']}/review", verdict="approve",
                         reviewer="Test", revision=episode["revision"], request_id=str(uuid4()))

    def test_persistent_review_of_exact_revision_and_retries(self):
        with TemporaryDirectory() as directory:
            path = Path(directory) / "housing.sqlite"
            with TestClient(create_app(path, self.evidence)) as client:
                self.assertEqual(client.get("/").status_code, 200)
                self.assertEqual(client.get("/assets/app.js").status_code, 200)
                initial = self.start(client, "tenant")
                pending = self.step(client, initial)
                self.assertEqual(pending["events"][0]["allowed"], ["STOP", "ASK_HOUSING_NEED"])
                self.assertIsNone(pending["need"])
                self.assertNotIn("scenario", pending)
                self.assertEqual(pending["contacts"], 0)

            with TestClient(create_app(path, self.evidence)) as client:
                url = f"/episodes/{pending['id']}"
                self.assertEqual(client.get(url).json(), pending)
                review = {"revision": pending["revision"], "request_id": str(uuid4()),
                          "reviewer": "Reviewer", "verdict": "approve"}
                wrong = client.post(f"{url}/review", json={**review, "revision": 0})
                self.assertEqual(wrong.status_code, 409)
                approved = self.post(client, f"{url}/review", **review)
                self.assertEqual(self.post(client, f"{url}/review", **review), approved)
                conflict = client.post(f"{url}/review", json={**review, "verdict": "reject"})
                self.assertEqual(conflict.status_code, 409)
                self.assertEqual(approved["contacts"], 1)
                self.assertEqual(approved["need"], "occupant")
                offer = self.step(client, approved)
                self.assertEqual(offer["draft"]["evidence"]["id"], "housing-synthetic-occupant-v1")
                objection = self.approve(client, offer)
                self.assertEqual(objection["events"][-1]["reply"], "objection")
                explanation = self.step(client, objection)
                self.assertEqual(explanation["events"][-1]["action"], "EXPLAIN_OCCUPANT")
                accepted = self.approve(client, explanation)
                self.assertEqual((accepted["status"], accepted["contacts"]), ("closed", 3))

    def test_eligibility_rejection_and_refusal(self):
        with TemporaryDirectory() as directory, TestClient(
            create_app(Path(directory) / "housing.sqlite", self.evidence)
        ) as client:
            for scenario in ("missing_evidence", "owned", "refusal", "landlord"):
                with self.subTest(scenario=scenario):
                    started = self.start(client, scenario)
                    clarified = self.approve(client, self.step(client, started))
                    next_action = self.step(client, clarified)
                    if scenario in ("missing_evidence", "owned"):
                        self.assertEqual(next_action["status"], "closed")
                        self.assertEqual(next_action["events"][-1]["allowed"], ["STOP"])
                        reason = "already_owned" if scenario == "owned" else "missing_evidence"
                        self.assertEqual(next_action["events"][-1]["reason"], reason)
                        self.assertIsNone(next_action["draft"])
                    elif scenario == "refusal":
                        refused = self.approve(client, next_action)
                        self.assertEqual(refused["events"][-1]["reply"], "refusal")
                        self.assertEqual(refused["status"], "closed")
                    else:
                        self.assertEqual(next_action["draft"]["evidence"]["id"],
                                         "housing-synthetic-non-occupant-v1")
                        url = f"/episodes/{started['id']}/review"
                        rejected = self.post(client, url, verdict="reject", reviewer="Test",
                                             revision=next_action["revision"], request_id=str(uuid4()))
                        self.assertEqual(rejected["events"][-1]["verdict"], "reject")
                        self.assertEqual(rejected["status"], "closed")
                        self.assertEqual(rejected["contacts"], clarified["contacts"])

    def test_competing_reviewers_can_execute_at_most_once(self):
        with TemporaryDirectory() as directory, TestClient(
            create_app(Path(directory) / "housing.sqlite", self.evidence)
        ) as client:
            pending = self.step(client, self.start(client, "tenant"))
            url = f"/episodes/{pending['id']}/review"

            def submit(verdict):
                return client.post(url, json={"revision": pending["revision"],
                                              "request_id": str(uuid4()),
                                              "reviewer": verdict, "verdict": verdict}).status_code

            with ThreadPoolExecutor(max_workers=2) as pool:
                self.assertEqual(sorted(pool.map(submit, ("approve", "reject"))), [200, 409])
            history = client.get(f"/episodes/{pending['id']}").json()["events"]
            self.assertEqual(sum(event["type"] == "review" for event in history), 1)

    def test_catalog_change_blocks_a_pending_follow_up_after_restart(self):
        with TemporaryDirectory() as directory:
            path = Path(directory) / "housing.sqlite"
            with TestClient(create_app(path, self.evidence)) as client:
                started = self.start(client, "landlord")
                clarified = self.approve(client, self.step(client, started))
                contacted = self.approve(client, self.step(client, clarified))
                pending = self.step(client, contacted)
                self.assertEqual(pending["events"][-1]["action"], "FOLLOW_UP")
                self.assertEqual(pending["draft"]["evidence"]["id"], "housing-synthetic-non-occupant-v1")

            rebuilt = EvidenceIndex(self.evidence)
            rebuilt.digest = "a" * 64
            with patch("mvp.app.EvidenceIndex", return_value=rebuilt), TestClient(
                create_app(path, self.evidence)
            ) as client:
                reviewed = self.approve(client, pending)
                self.assertEqual((reviewed["status"], reviewed["contacts"]), ("closed", 2))
                self.assertEqual(reviewed["events"][-2]["verdict"], "approve")
                self.assertEqual(reviewed["events"][-1]["reason"], "evidence_version_changed")

    def test_unsafe_policy_result_falls_back_to_allowed_rules(self):
        for outcome, reason in [
            (Action.FOLLOW_UP, "ineligible_action"),
            (RuntimeError("model unavailable"), "inference_failed"),
        ]:
            failing = Mock(version="test-policy")
            if isinstance(outcome, Exception):
                failing.act.side_effect = outcome
            else:
                failing.act.return_value = outcome
            with self.subTest(reason=reason), TemporaryDirectory() as directory:
                app = create_app(Path(directory) / "housing.sqlite", self.evidence)
                with patch(
                    "mvp.app.build_workflow",
                    side_effect=lambda storage, index, policy: build_workflow(storage, index, failing),
                ), TestClient(app) as client:
                    pending = self.step(client, self.start(client, "tenant"))
                event = pending["events"][-1]
                self.assertEqual((event["action"], event["policy"]), ("ASK_HOUSING_NEED", "rules-v1"))
                self.assertEqual(event["fallback"], {"reason": reason, "attempted_policy": "test-policy"})

    @unittest.skipUnless(os.environ.get("NEXT_BH_TEST_CHECKPOINT"), "requires a trained checkpoint")
    def test_trained_checkpoint_decides_in_the_runtime(self):
        checkpoint = Path(os.environ["NEXT_BH_TEST_CHECKPOINT"])
        digest = sha256(checkpoint.read_bytes()).hexdigest()
        with TemporaryDirectory() as directory, patch.dict(os.environ, {
            "NEXT_BH_POLICY": str(checkpoint), "NEXT_BH_POLICY_SHA256": digest,
        }), TestClient(create_app(Path(directory) / "housing.sqlite", self.evidence)) as client:
            result = self.step(client, self.start(client, "tenant"))
        event = result["events"][-1]
        self.assertEqual(event["policy"], f"maskableppo:sha256:{digest}")
        self.assertIn(event["action"], event["allowed"])
        self.assertNotIn("fallback", event)

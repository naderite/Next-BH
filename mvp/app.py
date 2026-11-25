"""Local housing case service and review workspace."""

from contextlib import asynccontextmanager
from datetime import datetime, timezone
import os
from pathlib import Path
from threading import Lock
from typing import Annotated, Literal
from uuid import UUID

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from filelock import FileLock, Timeout
from langgraph.checkpoint.serde.jsonplus import JsonPlusSerializer
from langgraph.checkpoint.sqlite import SqliteSaver
from langgraph.types import Command
from pydantic import BaseModel, ConfigDict, Field, StringConstraints

from mvp.catalog import DEFAULT_INDEX, EvidenceIndex
from mvp.housing import SCENARIOS, initial_scenario
from mvp.workflow import build_workflow

WEB = Path(__file__).with_name("web")
Reviewer = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=80)]


class CreateEpisode(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id: UUID
    scenario: str


class Step(BaseModel):
    model_config = ConfigDict(extra="forbid")
    request_id: UUID
    revision: int = Field(ge=0)


class Review(Step):
    verdict: Literal["approve", "reject"]
    reviewer: Reviewer


def create_app(database: Path | None = None, evidence_path: Path | None = None):
    @asynccontextmanager
    async def lifespan(app):
        path = database or Path(os.environ.get("NEXT_BH_STATE", "data/housing.sqlite3"))
        path.parent.mkdir(parents=True, exist_ok=True)
        checkpoint = os.environ.get("NEXT_BH_POLICY")
        policy = None
        if checkpoint:
            from mvp.policy import TrainedPolicy

            policy = TrainedPolicy(Path(checkpoint), os.environ.get("NEXT_BH_POLICY_SHA256", ""))
        index = EvidenceIndex(evidence_path or Path(os.environ.get("NEXT_BH_EVIDENCE", str(DEFAULT_INDEX))))
        database_lock = FileLock(f"{path.resolve()}.lock")
        try:
            database_lock.acquire(timeout=0)
        except Timeout as error:
            raise RuntimeError("The housing state database already has a running worker.") from error
        try:
            with SqliteSaver.from_conn_string(str(path)) as storage:
                storage.serde = JsonPlusSerializer(allowed_msgpack_modules=[])
                app.state.workflow = build_workflow(storage, index, policy)
                yield
        finally:
            database_lock.release()

    app = FastAPI(title="Next-BH · Habitation", lifespan=lifespan)
    app.mount("/assets", StaticFiles(directory=WEB), name="assets")
    mutations = Lock()

    def config(episode_id):
        return {"configurable": {"thread_id": str(episode_id)}}

    def load(episode_id):
        workflow = app.state.workflow
        settings = config(episode_id)
        snapshot = workflow.get_state(settings)
        if snapshot.next and not any(task.interrupts for task in snapshot.tasks):
            workflow.invoke(None, settings, durability="sync")
            snapshot = workflow.get_state(settings)
        return snapshot.values

    def public(episode_id, state):
        return {
            "id": str(episode_id),
            **{key: state[key] for key in ("revision", "status", "need", "owned", "contacts", "draft", "events")},
        }

    @app.get("/", include_in_schema=False)
    def workspace():
        return FileResponse(WEB / "index.html")

    @app.get("/scenarios")
    def scenarios():
        return [{"id": key, "label": info[0]} for key, info in SCENARIOS.items()]

    @app.post("/episodes")
    def create_episode(body: CreateEpisode):
        if body.scenario not in SCENARIOS:
            raise HTTPException(422, "Scénario inconnu.")
        with mutations:
            existing = load(body.id)
            if existing:
                if existing["scenario"] != body.scenario:
                    raise HTTPException(409, "Cet identifiant est déjà utilisé.")
                return public(body.id, existing)
            initial = {
                **initial_scenario(body.scenario),
                "revision": 0,
                "status": "ready",
                "draft": None,
                "request": None,
                "receipts": {},
                "events": [],
            }
            app.state.workflow.invoke(initial, config(body.id), durability="sync")
            return public(body.id, load(body.id))

    def existing_episode(episode_id):
        state = load(episode_id)
        if not state:
            raise HTTPException(404, "Dossier introuvable.")
        return state

    @app.get("/episodes/{episode_id}")
    def get_episode(episode_id: UUID):
        with mutations:
            return public(episode_id, existing_episode(episode_id))

    def mutate(episode_id, body, operation):
        with mutations:
            state = existing_episode(episode_id)
            request = {**body.model_dump(mode="json"), "operation": operation}
            receipt = state["receipts"].get(request["request_id"])
            if receipt:
                if any(receipt.get(key) != value for key, value in request.items()):
                    raise HTTPException(409, "Cet identifiant de requête a déjà été utilisé.")
                return public(episode_id, state)

            expected = "ready" if operation == "step" else "pending_review"
            if state["status"] != expected or state["revision"] != body.revision:
                raise HTTPException(409, "Le dossier a changé. Rechargez sa dernière version.")
            if operation == "step":
                command = {"request": request}
            else:
                request["recorded_at"] = datetime.now(timezone.utc).isoformat()
                command = Command(resume=request)
            app.state.workflow.invoke(command, config(episode_id), durability="sync")
            return public(episode_id, load(episode_id))

    @app.post("/episodes/{episode_id}/step")
    def advance(episode_id: UUID, body: Step):
        return mutate(episode_id, body, "step")

    @app.post("/episodes/{episode_id}/review")
    def submit_review(episode_id: UUID, body: Review):
        return mutate(episode_id, body, "review")

    return app


app = create_app()

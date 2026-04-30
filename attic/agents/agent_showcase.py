#!/usr/bin/env python3
"""
Deterministic showcase payloads for the GLYPH persona-agent UI.

This module uses the shipped Python agent framework so the demo reflects real
runtime behavior: validated tool calls, shared state, patches, checkpoints, and
debate arbitration.
"""

from __future__ import annotations

import asyncio
import copy
import json
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent
PY_DIR = ROOT / "py"
if str(PY_DIR) not in sys.path:
    sys.path.insert(0, str(PY_DIR))

import glyph


DEFAULT_CONFIG = {
    "task": "Design an elite onboarding and control room for the GLYPH persona agent SDK.",
    "max_rounds": 1,
    "arbitration_mode": "majority",
    "require_consensus": False,
    "min_confidence": 0.6,
    "enable_tools": True,
    "include_arbiter": True,
}


@dataclass
class ShowcaseConfig:
    task: str
    max_rounds: int
    arbitration_mode: str
    require_consensus: bool
    min_confidence: float
    enable_tools: bool
    include_arbiter: bool

    @classmethod
    def from_input(cls, raw: dict[str, Any] | None = None) -> "ShowcaseConfig":
        data = copy.deepcopy(DEFAULT_CONFIG)
        if raw:
            data.update(raw)
        return cls(
            task=str(data["task"]).strip() or DEFAULT_CONFIG["task"],
            max_rounds=max(1, min(int(data["max_rounds"]), 3)),
            arbitration_mode=str(data["arbitration_mode"]),
            require_consensus=bool(data["require_consensus"]),
            min_confidence=max(0.0, min(float(data["min_confidence"]), 1.0)),
            enable_tools=bool(data["enable_tools"]),
            include_arbiter=bool(data["include_arbiter"]),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "task": self.task,
            "max_rounds": self.max_rounds,
            "arbitration_mode": self.arbitration_mode,
            "require_consensus": self.require_consensus,
            "min_confidence": self.min_confidence,
            "enable_tools": self.enable_tools,
            "include_arbiter": self.include_arbiter,
        }


class ScriptedPersonaModel:
    """Simple deterministic model adapter for the showcase."""

    def __init__(self, config: ShowcaseConfig):
        self.config = config
        self.calls: dict[str, int] = {}

    async def stream(self, prompt: str, *, agent, state, session_id):
        del prompt, session_id
        agent_id = agent.agent_id
        call_index = self.calls.get(agent_id, 0)
        self.calls[agent_id] = call_index + 1
        text = self._response(agent_id, call_index, state)
        return _iter_chars(text)

    def _response(self, agent_id: str, call_index: int, state: dict[str, Any]) -> str:
        if self.config.enable_tools and call_index == 0:
            tool_call = _tool_call_for(agent_id)
            if tool_call:
                return tool_call

        if agent_id == "feynman":
            docs = state.get("shared_memory", {}).get("tool:search_docs", {})
            hits = docs.get("top_matches", ["tool validation", "patches", "checkpoints"])
            return _emit_struct(
                "Explanation",
                {
                    "summary": "Lead with a guided launchpad that teaches the runtime through one concrete task.",
                    "key_points": [
                        f"Show the operator where persona outputs land: {hits[0]}",
                        "Keep the first run anchored in live state updates, not static docs.",
                        "Explain tool validation and checkpoints in plain language before exposing deeper controls.",
                    ],
                    "assumptions": [
                        "The audience is evaluating GLYPH as an agent substrate.",
                        "A local deterministic demo is acceptable for first-run onboarding.",
                    ],
                    "confidence": 0.84,
                },
            )

        if agent_id == "von_neumann":
            rollout = state.get("shared_memory", {}).get("tool:plan_rollout", {})
            milestones = rollout.get("milestones", ["prototype", "verify", "publish"])
            return _emit_struct(
                "Plan",
                {
                    "summary": "Expose the runtime as a control room: configure, execute, inspect, and resume.",
                    "steps": [
                        f"Phase 1: {milestones[0]} the operator task and session policy.",
                        f"Phase 2: {milestones[1]} persona outputs, tool traces, and patch history.",
                        f"Phase 3: {milestones[2]} a checkpoint export and replay path.",
                    ],
                    "risks": [
                        "A gorgeous UI that hides the protocol will undermine trust.",
                        "Too many knobs before the first run will increase abandonment.",
                    ],
                    "confidence": 0.88,
                },
            )

        if agent_id == "einstein":
            constraints = state.get("shared_memory", {}).get("tool:inspect_constraints", {})
            invariants = constraints.get(
                "invariants",
                ["one source of truth", "state changes must be auditable"],
            )
            return _emit_struct(
                "Insight",
                {
                    "summary": "The UI should make the invisible structure obvious: state, policy, and disagreement.",
                    "invariants": invariants,
                    "simplifications": [
                        "One settings rail should drive the entire session policy.",
                        "Use one shared state inspector instead of separate debug panels.",
                    ],
                    "confidence": 0.81,
                },
            )

        if agent_id == "arbiter":
            consensus = True
            dissent = []
            if not self.config.require_consensus and self.config.arbitration_mode != "confidence_threshold":
                dissent = [{"agent_id": "feynman", "summary": "Keep the first-run tour even shorter."}]
                consensus = self.config.arbitration_mode != "unanimous"
            return _emit_struct(
                "Decision",
                {
                    "answer": "Ship a control-room showcase with onboarding, persona debate, state inspection, and resumable checkpoints.",
                    "rationale": "It demonstrates the runtime layers above GLYPH primitives without hiding the protocol underneath.",
                    "consensus": consensus,
                    "confidence": 0.93,
                    "dissent": dissent,
                },
            )

        raise ValueError(f"Unsupported scripted agent: {agent_id}")


def build_showcase_payload(config_input: dict[str, Any] | None = None) -> dict[str, Any]:
    """Synchronous wrapper used by the demo server."""
    config = ShowcaseConfig.from_input(config_input)
    return asyncio.run(_build_showcase_payload(config))


async def _build_showcase_payload(config: ShowcaseConfig) -> dict[str, Any]:
    tool_bindings = _build_tools()
    persona_model = ScriptedPersonaModel(config)
    arbiter_model = ScriptedPersonaModel(config)

    feynman_tools = [tool_bindings["search_docs"]] if config.enable_tools else []
    planner_tools = [tool_bindings["plan_rollout"]] if config.enable_tools else []
    einstein_tools = [tool_bindings["inspect_constraints"]] if config.enable_tools else []

    agents = [
        glyph.feynman_agent(persona_model, feynman_tools),
        glyph.von_neumann_agent(persona_model, planner_tools),
        glyph.einstein_agent(persona_model, einstein_tools),
    ]
    arbiter = glyph.arbiter_agent(arbiter_model) if config.include_arbiter else None
    session = glyph.create_debate_session(
        agents,
        coordinator=glyph.CoordinatorSpec(
            objective="Make the GLYPH Python agent runtime instantly legible to an engineer evaluating it.",
            rules=(
                "Show the runtime, not just the result.",
                "Prefer traceable state changes over cinematic mystery.",
                "Keep settings powerful but not sprawling.",
            ),
        ),
        arbiter=arbiter,
        policy=glyph.DebatePolicy(
            max_rounds=config.max_rounds,
            arbitration_mode=config.arbitration_mode,
            require_consensus=config.require_consensus,
            min_confidence=config.min_confidence,
        ),
    )

    error_message = None
    try:
        outcome = await glyph.run_turn(session, config.task)
    except glyph.AgentRuntimeError as exc:
        error_message = str(exc)
        outcome = glyph.DebateOutcome(
            answer="Showcase run halted by policy.",
            confidence=0.0,
            consensus=False,
            rationale=str(exc),
            payload={"error": str(exc)},
            dissent=[],
        )

    checkpoint = session.checkpoint()
    trace_glyph = glyph.export_trace(session, format="glyph")
    trace_json_pretty = glyph.export_trace(session, format="json")
    trace_data = json.loads(trace_json_pretty)
    trace_json_compact = json.dumps(trace_data, sort_keys=True, separators=(",", ":"))
    checkpoint_json = json.dumps(checkpoint.to_dict(), indent=2, sort_keys=True)
    checkpoint_compact = json.dumps(checkpoint.to_dict(), sort_keys=True, separators=(",", ":"))

    personas = _build_persona_cards(session, arbiter)
    metrics = {
        "glyph_chars": len(trace_glyph),
        "json_chars": len(trace_json_compact),
        "savings_percent": round(100 * (1 - (len(trace_glyph) / max(1, len(trace_json_compact)))), 1),
        "patch_count": len(session.patches),
        "event_count": len(session.events),
        "tool_call_count": len(session.state.get("tool_history", [])),
        "decision_confidence": round(outcome.confidence, 2),
        "consensus": outcome.consensus,
        "checkpoint_chars": len(checkpoint.to_glyph()),
        "checkpoint_json_chars": len(checkpoint_compact),
    }

    planning = {
        "objective": "Turn the agent runtime into a product surface that explains itself while it runs.",
        "policy": {
            "max_rounds": config.max_rounds,
            "arbitration_mode": config.arbitration_mode,
            "require_consensus": config.require_consensus,
            "min_confidence": config.min_confidence,
            "include_arbiter": config.include_arbiter,
            "enable_tools": config.enable_tools,
        },
        "phases": [
            {
                "title": "Onboard the operator",
                "owner": "Feynman",
                "status": "ready",
                "detail": "Start with one mission, one explanation, and a visible first win.",
            },
            {
                "title": "Expose the control plane",
                "owner": "von Neumann",
                "status": "active",
                "detail": "Map session policy, tool budget, and arbitration settings into one settings rail.",
            },
            {
                "title": "Reveal the substrate",
                "owner": "Einstein",
                "status": "active",
                "detail": "Make shared memory, patches, and checkpoints visible as one coherent state model.",
            },
            {
                "title": "Synthesize the operator path",
                "owner": "Arbiter" if config.include_arbiter else "Runtime",
                "status": "complete" if not error_message else "blocked",
                "detail": outcome.answer,
            },
        ],
    }

    return {
        "meta": {
            "title": "GLYPH Agent Control Room",
            "subtitle": "Python-first persona orchestration with validated tools, state patches, and resumable debates.",
            "session_id": session.session_id,
            "generated_at": _utcnow(),
            "task": config.task,
            "error": error_message,
        },
        "settings": config.to_dict(),
        "onboarding": _build_onboarding(config, error_message),
        "metrics": metrics,
        "personas": personas,
        "planning": planning,
        "timeline": _build_timeline(session),
        "shared_state": session.state,
        "patches": [patch.to_dict() for patch in session.patches],
        "checkpoint": {
            "glyph": checkpoint.to_glyph(),
            "json": checkpoint_json,
        },
        "trace": {
            "glyph": trace_glyph,
            "json": trace_json_pretty,
        },
    }


def _build_tools() -> dict[str, glyph.ToolBinding]:
    def search_docs(args: dict[str, Any], envelope: glyph.ToolCallEnvelope) -> dict[str, Any]:
        del envelope
        return {
            "query": args["query"],
            "top_matches": [
                "validated tool calls",
                "fingerprint-verified patches",
                "checkpoint / resume flow",
            ],
            "docs": [
                {"title": "Streaming Validation", "why": "Stops bad tool calls early."},
                {"title": "Debate Sessions", "why": "Coordinates personas on shared state."},
                {"title": "Checkpoints", "why": "Makes long-running sessions resumable."},
            ],
        }

    def plan_rollout(args: dict[str, Any], envelope: glyph.ToolCallEnvelope) -> dict[str, Any]:
        del envelope
        surface = args["surface"]
        horizon = int(args["horizon_days"])
        return {
            "surface": surface,
            "horizon_days": horizon,
            "milestones": ["frame", "verify", "ship"],
            "budget_guardrails": {
                "max_iterations": 4,
                "max_tool_calls": 2,
                "max_seconds": 30,
            },
        }

    def inspect_constraints(args: dict[str, Any], envelope: glyph.ToolCallEnvelope) -> dict[str, Any]:
        del envelope
        return {
            "area": args["area"],
            "invariants": [
                "Shared memory is the source of truth.",
                "Every state mutation should be reconstructible from patches.",
                "Settings should alter policy, not bypass validation.",
            ],
            "smells": [
                "Settings hidden behind multiple tabs.",
                "No visible checkpoint boundary.",
            ],
        }

    return {
        "search_docs": glyph.ToolBinding(
            name="search_docs",
            args={
                "query": {"type": "str", "required": True, "min_len": 3},
            },
            handler=search_docs,
            description="Inspect the runtime docs and surface the strongest operator-facing ideas.",
        ),
        "plan_rollout": glyph.ToolBinding(
            name="plan_rollout",
            args={
                "surface": {"type": "str", "required": True},
                "horizon_days": {"type": "int", "required": True, "min": 1, "max": 30, "default": 14},
            },
            handler=plan_rollout,
            description="Translate a runtime idea into phases, guardrails, and delivery sequence.",
        ),
        "inspect_constraints": glyph.ToolBinding(
            name="inspect_constraints",
            args={
                "area": {"type": "str", "required": True},
            },
            handler=inspect_constraints,
            description="Surface invariants and simplifications for the shared-state model.",
        ),
    }


def _tool_call_for(agent_id: str) -> str | None:
    if agent_id == "feynman":
        return 'search_docs{query="glyph python agent runtime"}'
    if agent_id == "von_neumann":
        return 'plan_rollout{surface="python-first sdk" horizon_days=14}'
    if agent_id == "einstein":
        return 'inspect_constraints{area="shared state and checkpoints"}'
    return None


def _emit_struct(type_name: str, payload: dict[str, Any]) -> str:
    fields = [glyph.field(name, glyph.from_json(value)) for name, value in payload.items()]
    return glyph.emit(glyph.g.struct(type_name, *fields))


def _build_persona_cards(
    session: glyph.DebateSession,
    arbiter: glyph.Agent | None,
) -> list[dict[str, Any]]:
    tools_by_agent: dict[str, list[dict[str, Any]]] = {}
    for tool_call in session.state.get("tool_history", []):
        tools_by_agent.setdefault(tool_call["agent_id"], []).append(tool_call)

    latest_artifact_by_agent: dict[str, dict[str, Any]] = {}
    for artifact in session.state.get("artifacts", []):
        latest_artifact_by_agent[artifact["agent_id"]] = artifact

    cards = []
    agents = list(session.agents)
    if arbiter is not None:
        agents.append(arbiter)
    for agent in agents:
        artifact = latest_artifact_by_agent.get(agent.spec.agent_id)
        cards.append(
            {
                "id": agent.spec.agent_id,
                "name": agent.spec.display_name,
                "role": agent.spec.persona,
                "objective": agent.spec.objective,
                "output_type": agent.spec.output_type,
                "tool_names": list(agent.spec.tool_names),
                "artifact": artifact,
                "tools": tools_by_agent.get(agent.spec.agent_id, []),
            }
        )
    return cards


def _build_timeline(session: glyph.DebateSession) -> list[dict[str, Any]]:
    items = []
    for event in session.events:
        payload = event.payload
        summary = event.kind
        if event.kind == "task":
            summary = f"Coordinator launched: {payload['task']}"
        elif event.kind == "tool_result":
            summary = f"{payload['agent_id']} ran {payload['tool_name']}"
        elif event.kind == "artifact":
            summary = f"{payload['agent_id']} emitted {payload['output_type']}"
        elif event.kind == "decision":
            summary = payload.get("answer", "Decision recorded")

        items.append(
            {
                "kind": event.kind,
                "agent_id": event.agent_id,
                "created_at": event.created_at,
                "summary": summary,
            }
        )
    return items


def _build_onboarding(config: ShowcaseConfig, error_message: str | None) -> list[dict[str, Any]]:
    statuses = ["ready", "active", "active", "complete" if not error_message else "blocked"]
    return [
        {
            "step": "01",
            "title": "Frame the mission",
            "detail": "Choose the operator task and set the first-run policy in one compact settings rail.",
            "cue": "Task + policy",
            "status": statuses[0],
        },
        {
            "step": "02",
            "title": "Run the persona panel",
            "detail": "Feynman, von Neumann, and Einstein take distinct roles over the same shared memory.",
            "cue": "Debate board",
            "status": statuses[1],
        },
        {
            "step": "03",
            "title": "Inspect the substrate",
            "detail": "Show shared state, patches, tool traces, and the checkpoint export that makes replay possible.",
            "cue": "State + trace",
            "status": statuses[2],
        },
        {
            "step": "04",
            "title": "Land the decision",
            "detail": (
                "Arbiter synthesis is enabled." if config.include_arbiter
                else "The runtime resolves directly from the strongest artifact."
            ),
            "cue": "Decision card",
            "status": statuses[3],
        },
    ]


def _iter_chars(text: str):
    for char in text:
        yield char


def _utcnow() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


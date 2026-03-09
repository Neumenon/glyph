"""
High-level agent orchestration framework for GLYPH.

This module builds on top of GLYPH's existing codec and streaming validation
primitives to provide:

- Persona-driven agent specifications
- Tool execution with retries, timeouts, and idempotency
- Verified shared-state patches backed by GLYPH fingerprints
- Debate sessions with optional model-based arbitration
- Trace export and checkpoint / resume helpers
"""

from __future__ import annotations

import asyncio
import copy
import hashlib
import inspect
import json
import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import (
    Any,
    AsyncIterator,
    Awaitable,
    Callable,
    Iterable,
    Mapping,
    Optional,
    Protocol,
    Sequence,
)

from .loose import fingerprint_loose, from_json_loose, json_to_glyph, to_json_loose
from .parse import parse_loose
from .stream_validator import StreamingValidator, ToolRegistry
from .types import GType


ToolHandler = Callable[[dict[str, Any], "ToolCallEnvelope"], Any]
_DELETE = object()
_UNCHANGED = object()


class AgentRuntimeError(RuntimeError):
    """Base class for agent runtime failures."""


class UnknownActionError(AgentRuntimeError):
    """Raised when a model emits a prefix that is neither a tool nor output type."""


class OutputValidationError(AgentRuntimeError):
    """Raised when a final GLYPH output does not match the declared contract."""


class BudgetExceededError(AgentRuntimeError):
    """Raised when a model exceeds the configured iteration or tool budget."""


class StateConflictError(AgentRuntimeError):
    """Raised when a state patch is applied to the wrong base fingerprint."""


class ToolExecutionError(AgentRuntimeError):
    """Raised when the runtime cannot execute a declared tool."""


class ModelAdapter(Protocol):
    """Protocol for pluggable model backends."""

    def stream(
        self,
        prompt: str,
        *,
        agent: "AgentSpec",
        state: Mapping[str, Any],
        session_id: str,
    ) -> AsyncIterator[str] | Iterable[str] | Awaitable[AsyncIterator[str] | Iterable[str]]:
        ...


@dataclass
class TurnBudget:
    """Execution budget for a single agent turn."""

    max_iterations: int = 4
    max_tool_calls: int = 2
    max_seconds: float = 30.0
    max_tokens: int = 4096


@dataclass
class ToolBinding:
    """A tool schema plus its executable handler."""

    name: str
    args: dict[str, dict[str, Any]]
    handler: ToolHandler
    description: str = ""
    timeout_seconds: float = 15.0
    retries: int = 0
    idempotent: bool = True


@dataclass
class ToolCallEnvelope:
    """Execution metadata for a tool invocation."""

    call_id: str
    session_id: str
    agent_id: str
    tool_name: str
    args: dict[str, Any]
    attempt: int
    idempotency_key: str
    started_at: str


@dataclass
class ToolExecutionResult:
    """Normalized tool execution result."""

    call_id: str
    session_id: str
    agent_id: str
    tool_name: str
    args: dict[str, Any]
    ok: bool
    result: Any = None
    error: Optional[str] = None
    attempts: int = 1
    duration_seconds: float = 0.0
    cached: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "call_id": self.call_id,
            "session_id": self.session_id,
            "agent_id": self.agent_id,
            "tool_name": self.tool_name,
            "args": copy.deepcopy(self.args),
            "ok": self.ok,
            "result": copy.deepcopy(self.result),
            "error": self.error,
            "attempts": self.attempts,
            "duration_seconds": self.duration_seconds,
            "cached": self.cached,
        }


@dataclass
class StatePatch:
    """A verified patch between two JSON-compatible states."""

    revision: int
    author_id: str
    reason: str
    base_fingerprint: str
    result_fingerprint: str
    patch: dict[str, Any]
    created_at: str = field(default_factory=lambda: _utcnow())

    def to_dict(self) -> dict[str, Any]:
        return {
            "revision": self.revision,
            "author_id": self.author_id,
            "reason": self.reason,
            "base_fingerprint": self.base_fingerprint,
            "result_fingerprint": self.result_fingerprint,
            "patch": copy.deepcopy(self.patch),
            "created_at": self.created_at,
        }


@dataclass
class SessionEvent:
    """Trace event for auditability and replay."""

    kind: str
    agent_id: str
    payload: dict[str, Any]
    created_at: str = field(default_factory=lambda: _utcnow())

    def to_dict(self) -> dict[str, Any]:
        return {
            "kind": self.kind,
            "agent_id": self.agent_id,
            "payload": copy.deepcopy(self.payload),
            "created_at": self.created_at,
        }


@dataclass
class AgentArtifact:
    """Final artifact emitted by an agent."""

    agent_id: str
    output_type: str
    payload: dict[str, Any]
    raw_text: str
    created_at: str = field(default_factory=lambda: _utcnow())

    def confidence(self) -> float:
        value = self.payload.get("confidence", 0.0)
        if isinstance(value, bool):
            return 0.0
        if isinstance(value, (int, float)):
            return float(value)
        return 0.0

    def summary(self) -> str:
        for key in ("summary", "answer", "rationale", "message"):
            value = self.payload.get(key)
            if isinstance(value, str) and value:
                return value
        return self.output_type

    def to_dict(self) -> dict[str, Any]:
        return {
            "agent_id": self.agent_id,
            "output_type": self.output_type,
            "payload": copy.deepcopy(self.payload),
            "raw_text": self.raw_text,
            "created_at": self.created_at,
        }


@dataclass
class DebateOutcome:
    """Normalized session result."""

    answer: str
    confidence: float
    consensus: bool
    rationale: str
    payload: dict[str, Any]
    dissent: list[dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "answer": self.answer,
            "confidence": self.confidence,
            "consensus": self.consensus,
            "rationale": self.rationale,
            "payload": copy.deepcopy(self.payload),
            "dissent": copy.deepcopy(self.dissent),
        }


@dataclass
class DebatePolicy:
    """Controls how a debate session converges."""

    max_rounds: int = 1
    arbitration_mode: str = "majority"
    require_consensus: bool = False
    min_confidence: float = 0.0


@dataclass
class CoordinatorSpec:
    """Optional shared instructions for the debate coordinator."""

    objective: str = "Coordinate a structured debate and preserve useful evidence."
    rules: tuple[str, ...] = (
        "Prefer evidence over rhetoric.",
        "Keep shared memory factual and compact.",
        "Record dissent instead of erasing it.",
    )

    def to_dict(self) -> dict[str, Any]:
        return {
            "objective": self.objective,
            "rules": list(self.rules),
        }


@dataclass
class AgentSpec:
    """Persona, tool, and output contract for an agent."""

    agent_id: str
    display_name: str
    persona: str
    objective: str
    instructions: tuple[str, ...]
    epistemic_rules: tuple[str, ...]
    tool_names: tuple[str, ...] = ()
    output_type: str = "Answer"
    output_fields: dict[str, str] = field(default_factory=dict)
    budget: TurnBudget = field(default_factory=TurnBudget)
    description: str = ""

    @property
    def allowed_output_types(self) -> tuple[str, ...]:
        return (self.output_type,)

    def render_prompt(
        self,
        *,
        task: Any,
        state: Mapping[str, Any],
        tool_lines: Sequence[str],
        coordinator: Optional[CoordinatorSpec] = None,
    ) -> str:
        task_repr = task if isinstance(task, str) else json_to_glyph(task)
        state_repr = json_to_glyph(dict(state))
        output_sig = self.output_signature()

        sections = [
            f"You are {self.display_name}.",
            f"Persona: {self.persona}",
            f"Objective: {self.objective}",
        ]

        if self.description:
            sections.append(self.description)

        if coordinator:
            sections.append(f"Debate objective: {coordinator.objective}")
            if coordinator.rules:
                sections.append("Coordinator rules:")
                sections.extend(f"- {rule}" for rule in coordinator.rules)

        if self.instructions:
            sections.append("Instructions:")
            sections.extend(f"- {rule}" for rule in self.instructions)

        if self.epistemic_rules:
            sections.append("Epistemic rules:")
            sections.extend(f"- {rule}" for rule in self.epistemic_rules)

        if tool_lines:
            sections.append("Available tools:")
            sections.extend(f"- {line}" for line in tool_lines)
            sections.append(
                "If you need a tool, output only the tool call itself with no prose."
            )
        else:
            sections.append("No external tools are available for this turn.")

        sections.append(
            f"If you do not need a tool, output exactly one {output_sig} value and no prose."
        )
        sections.append(f"Task:\n{task_repr}")
        sections.append(f"State:\n{state_repr}")
        return "\n".join(sections)

    def output_signature(self) -> str:
        if not self.output_fields:
            return f"{self.output_type}{{}}"
        fields = " ".join(f"{name}:{kind}" for name, kind in self.output_fields.items())
        return f"{self.output_type}{{{fields}}}"


def feynman_agent(
    model: ModelAdapter,
    tools: Sequence[ToolBinding] = (),
    *,
    agent_id: str = "feynman",
    display_name: str = "Feynman",
) -> "Agent":
    spec = AgentSpec(
        agent_id=agent_id,
        display_name=display_name,
        persona="Explain difficult things with concrete, teachable structure.",
        objective="Expose the simplest correct explanation and identify knowledge gaps.",
        description="Favor simple language, worked examples, and explicit confusion checks.",
        instructions=(
            "Compress jargon into plain language.",
            "State what is known, unknown, and assumed.",
            "Prefer explanations a strong engineer could teach back.",
        ),
        epistemic_rules=(
            "Do not pretend to know details you have not established.",
            "If evidence is weak, say so directly.",
        ),
        tool_names=tuple(tool.name for tool in tools),
        output_type="Explanation",
        output_fields={
            "summary": "str",
            "key_points": "list",
            "assumptions": "list",
            "confidence": "float",
        },
    )
    return create_agent(spec, model, tools)


def von_neumann_agent(
    model: ModelAdapter,
    tools: Sequence[ToolBinding] = (),
    *,
    agent_id: str = "von_neumann",
    display_name: str = "von Neumann",
) -> "Agent":
    spec = AgentSpec(
        agent_id=agent_id,
        display_name=display_name,
        persona="Formal optimizer focused on decomposition, efficiency, and decision quality.",
        objective="Turn ambiguity into a tractable plan with crisp tradeoffs.",
        description="Prefer structured decomposition, explicit tradeoffs, and computational clarity.",
        instructions=(
            "Decompose the problem into executable subproblems.",
            "Surface bottlenecks, constraints, and failure modes.",
            "Prefer strategies that remain stable under uncertainty.",
        ),
        epistemic_rules=(
            "Distinguish first-order reasoning from speculation.",
            "Flag missing inputs that materially change the plan.",
        ),
        tool_names=tuple(tool.name for tool in tools),
        output_type="Plan",
        output_fields={
            "summary": "str",
            "steps": "list",
            "risks": "list",
            "confidence": "float",
        },
    )
    return create_agent(spec, model, tools)


def einstein_agent(
    model: ModelAdapter,
    tools: Sequence[ToolBinding] = (),
    *,
    agent_id: str = "einstein",
    display_name: str = "Einstein",
) -> "Agent":
    spec = AgentSpec(
        agent_id=agent_id,
        display_name=display_name,
        persona="Conceptual simplifier who checks invariants, elegance, and surprising analogies.",
        objective="Stress the conceptual frame and surface better abstractions.",
        description="Prefer elegant models, invariants, and conceptual reframing over verbosity.",
        instructions=(
            "Look for invariant structure before local details.",
            "Offer at least one simplification or analogy when helpful.",
            "Challenge solutions that are technically correct but conceptually clumsy.",
        ),
        epistemic_rules=(
            "Do not confuse elegance with evidence.",
            "State when an analogy is suggestive rather than proven.",
        ),
        tool_names=tuple(tool.name for tool in tools),
        output_type="Insight",
        output_fields={
            "summary": "str",
            "invariants": "list",
            "simplifications": "list",
            "confidence": "float",
        },
    )
    return create_agent(spec, model, tools)


def arbiter_agent(
    model: ModelAdapter,
    *,
    agent_id: str = "arbiter",
    display_name: str = "Arbiter",
) -> "Agent":
    spec = AgentSpec(
        agent_id=agent_id,
        display_name=display_name,
        persona="Neutral synthesis agent.",
        objective="Merge the debate into one decision without discarding meaningful dissent.",
        description="Prefer decisions grounded in the best evidence from the participants.",
        instructions=(
            "Produce one answer that integrates the strongest points from the debate.",
            "Preserve important dissent instead of flattening it away.",
        ),
        epistemic_rules=(
            "Do not claim consensus if the debate shows material disagreement.",
        ),
        output_type="Decision",
        output_fields={
            "answer": "str",
            "rationale": "str",
            "consensus": "bool",
            "confidence": "float",
            "dissent": "list",
        },
    )
    return create_agent(spec, model, ())


class ToolExecutor:
    """Tool registry plus execution semantics."""

    def __init__(self, bindings: Sequence[ToolBinding] = ()):
        self._bindings = {binding.name: binding for binding in bindings}
        self._cache: dict[str, ToolExecutionResult] = {}

    def add(self, binding: ToolBinding) -> None:
        self._bindings[binding.name] = binding

    def names(self) -> list[str]:
        return sorted(self._bindings)

    def registry(self, tool_names: Sequence[str] | None = None) -> ToolRegistry:
        registry = ToolRegistry()
        names = set(tool_names or self._bindings.keys())
        for name in names:
            binding = self._bindings.get(name)
            if not binding:
                continue
            registry.add_tool(binding.name, copy.deepcopy(binding.args), binding.description)
        return registry

    def prompt_lines(self, tool_names: Sequence[str] | None = None) -> list[str]:
        names = list(tool_names or self._bindings.keys())
        lines = []
        for name in names:
            binding = self._bindings.get(name)
            if not binding:
                continue
            fields = []
            for arg_name, cfg in binding.args.items():
                field_sig = f"{arg_name}:{cfg.get('type', 'str')}"
                if cfg.get("required"):
                    field_sig += "!"
                if "min" in cfg or "max" in cfg:
                    field_sig += f"[{cfg.get('min', '')}..{cfg.get('max', '')}]"
                if "default" in cfg:
                    field_sig += f"={cfg['default']}"
                fields.append(field_sig)
            signature = f"{binding.name}{{{' '.join(fields)}}}"
            if binding.description:
                signature += f" - {binding.description}"
            lines.append(signature)
        return lines

    async def execute(
        self,
        name: str,
        args: dict[str, Any],
        *,
        agent_id: str,
        session_id: str,
    ) -> ToolExecutionResult:
        binding = self._bindings.get(name)
        if binding is None:
            raise ToolExecutionError(f"Tool not registered: {name}")

        registry = self.registry((name,))
        schema = registry.get_tool(name)
        if schema is not None:
            error = schema.validate(args)
            if error:
                raise ToolExecutionError(error)

        cache_key = _stable_hash({"tool": name, "args": args})
        if binding.idempotent and cache_key in self._cache:
            cached = copy.deepcopy(self._cache[cache_key])
            cached.cached = True
            return cached

        started = time.monotonic()
        attempts = 0
        last_error: Optional[str] = None

        while attempts <= binding.retries:
            attempts += 1
            envelope = ToolCallEnvelope(
                call_id=f"call_{uuid.uuid4().hex[:12]}",
                session_id=session_id,
                agent_id=agent_id,
                tool_name=name,
                args=copy.deepcopy(args),
                attempt=attempts,
                idempotency_key=cache_key,
                started_at=_utcnow(),
            )
            try:
                result = binding.handler(copy.deepcopy(args), envelope)
                if inspect.isawaitable(result):
                    result = await asyncio.wait_for(result, timeout=binding.timeout_seconds)
                elif binding.timeout_seconds is not None:
                    # Synchronous tool handlers run inline; keep the contract explicit.
                    result = result

                execution = ToolExecutionResult(
                    call_id=envelope.call_id,
                    session_id=session_id,
                    agent_id=agent_id,
                    tool_name=name,
                    args=copy.deepcopy(args),
                    ok=True,
                    result=result,
                    attempts=attempts,
                    duration_seconds=time.monotonic() - started,
                )
                if binding.idempotent:
                    self._cache[cache_key] = copy.deepcopy(execution)
                return execution
            except asyncio.TimeoutError:
                last_error = f"Tool timed out after {binding.timeout_seconds}s"
            except Exception as exc:  # pragma: no cover - error handling path
                last_error = str(exc)

        return ToolExecutionResult(
            call_id=f"call_{uuid.uuid4().hex[:12]}",
            session_id=session_id,
            agent_id=agent_id,
            tool_name=name,
            args=copy.deepcopy(args),
            ok=False,
            error=last_error or "Tool execution failed",
            attempts=attempts,
            duration_seconds=time.monotonic() - started,
        )


@dataclass
class SessionCheckpoint:
    """Serializable checkpoint of a debate session."""

    session_id: str
    revision: int
    state: dict[str, Any]
    patches: list[StatePatch]
    events: list[SessionEvent]
    created_at: str = field(default_factory=lambda: _utcnow())

    def to_dict(self) -> dict[str, Any]:
        return {
            "session_id": self.session_id,
            "revision": self.revision,
            "state": copy.deepcopy(self.state),
            "patches": [patch.to_dict() for patch in self.patches],
            "events": [event.to_dict() for event in self.events],
            "created_at": self.created_at,
        }

    def to_glyph(self) -> str:
        return json_to_glyph(self.to_dict())

    @classmethod
    def from_glyph(cls, text: str) -> "SessionCheckpoint":
        raw = to_json_loose(parse_loose(text))
        return cls.from_dict(raw)

    @classmethod
    def from_dict(cls, raw: Mapping[str, Any]) -> "SessionCheckpoint":
        patches = [
            StatePatch(
                revision=int(item["revision"]),
                author_id=str(item["author_id"]),
                reason=str(item["reason"]),
                base_fingerprint=str(item["base_fingerprint"]),
                result_fingerprint=str(item["result_fingerprint"]),
                patch=copy.deepcopy(item["patch"]),
                created_at=str(item.get("created_at", _utcnow())),
            )
            for item in raw.get("patches", [])
        ]
        events = [
            SessionEvent(
                kind=str(item["kind"]),
                agent_id=str(item["agent_id"]),
                payload=copy.deepcopy(item["payload"]),
                created_at=str(item.get("created_at", _utcnow())),
            )
            for item in raw.get("events", [])
        ]
        return cls(
            session_id=str(raw["session_id"]),
            revision=int(raw.get("revision", 0)),
            state=copy.deepcopy(raw.get("state", {})),
            patches=patches,
            events=events,
            created_at=str(raw.get("created_at", _utcnow())),
        )


class Agent:
    """Runtime wrapper around an agent spec, model adapter, and tool executor."""

    def __init__(
        self,
        spec: AgentSpec,
        model: ModelAdapter,
        tools: Sequence[ToolBinding] = (),
    ):
        self.spec = spec
        self.model = model
        self.tool_executor = ToolExecutor(tools)

    def registry(self) -> ToolRegistry:
        return self.tool_executor.registry(self.spec.tool_names)


class DebateSession:
    """Shared state, patches, and traces for a debate workflow."""

    def __init__(
        self,
        agents: Sequence[Agent],
        *,
        coordinator: Optional[CoordinatorSpec] = None,
        arbiter: Optional[Agent] = None,
        policy: Optional[DebatePolicy] = None,
        session_id: Optional[str] = None,
        state: Optional[dict[str, Any]] = None,
        revision: int = 0,
        patches: Optional[list[StatePatch]] = None,
        events: Optional[list[SessionEvent]] = None,
    ):
        self.agents = list(agents)
        self.agent_map = {agent.spec.agent_id: agent for agent in self.agents}
        if len(self.agent_map) != len(self.agents):
            raise ValueError("Agent IDs must be unique within a debate session")
        self.coordinator = coordinator or CoordinatorSpec()
        self.arbiter = arbiter
        self.policy = policy or DebatePolicy()
        self.session_id = session_id or f"sess_{uuid.uuid4().hex[:12]}"
        self.revision = revision
        self.state = state or {
            "round": 0,
            "tasks": [],
            "shared_memory": {},
            "artifacts": [],
            "tool_history": [],
            "private_notes": {},
            "decisions": [],
        }
        self.patches = patches or []
        self.events = events or []

    def snapshot(self) -> dict[str, Any]:
        return copy.deepcopy(self.state)

    def fingerprint(self) -> str:
        return state_fingerprint(self.state)

    def checkpoint(self) -> SessionCheckpoint:
        return SessionCheckpoint(
            session_id=self.session_id,
            revision=self.revision,
            state=self.snapshot(),
            patches=copy.deepcopy(self.patches),
            events=copy.deepcopy(self.events),
        )

    def log_event(self, kind: str, agent_id: str, payload: dict[str, Any]) -> None:
        self.events.append(SessionEvent(kind=kind, agent_id=agent_id, payload=payload))

    def prompt_state(self, agent_id: str, task: Any) -> dict[str, Any]:
        return {
            "session_id": self.session_id,
            "round": self.state.get("round", 0),
            "task": copy.deepcopy(task),
            "coordinator": self.coordinator.to_dict(),
            "shared_memory": copy.deepcopy(self.state.get("shared_memory", {})),
            "artifacts": copy.deepcopy(self.state.get("artifacts", [])),
            "recent_tools": copy.deepcopy(self.state.get("tool_history", [])[-5:]),
            "private_notes": copy.deepcopy(
                self.state.get("private_notes", {}).get(agent_id, [])
            ),
        }

    def commit_state_change(self, before: dict[str, Any], *, author_id: str, reason: str) -> None:
        if before == self.state:
            return
        self.revision += 1
        patch = create_state_patch(
            before,
            self.state,
            author_id=author_id,
            revision=self.revision,
            reason=reason,
        )
        self.patches.append(patch)

    def apply_patch(self, patch: StatePatch) -> None:
        self.state = apply_state_patch(self.state, patch)
        self.revision = max(self.revision, patch.revision)
        self.patches.append(copy.deepcopy(patch))

    def record_artifact(self, artifact: AgentArtifact) -> None:
        before = self.snapshot()
        self.state.setdefault("artifacts", []).append(artifact.to_dict())
        notes = self.state.setdefault("private_notes", {}).setdefault(artifact.agent_id, [])
        notes.append(
            {
                "output_type": artifact.output_type,
                "summary": artifact.summary(),
                "confidence": artifact.confidence(),
            }
        )
        shared = self.state.setdefault("shared_memory", {})
        shared[artifact.agent_id] = copy.deepcopy(artifact.payload)
        self.commit_state_change(before, author_id=artifact.agent_id, reason="record_artifact")
        self.log_event("artifact", artifact.agent_id, artifact.to_dict())

    def record_tool_result(self, result: ToolExecutionResult) -> None:
        before = self.snapshot()
        self.state.setdefault("tool_history", []).append(result.to_dict())
        shared = self.state.setdefault("shared_memory", {})
        shared[f"tool:{result.tool_name}"] = copy.deepcopy(result.result)
        notes = self.state.setdefault("private_notes", {}).setdefault(result.agent_id, [])
        notes.append(
            {
                "tool_name": result.tool_name,
                "ok": result.ok,
                "cached": result.cached,
                "error": result.error,
            }
        )
        self.commit_state_change(before, author_id=result.agent_id, reason="record_tool_result")
        self.log_event("tool_result", result.agent_id, result.to_dict())

    def record_decision(self, outcome: DebateOutcome, *, agent_id: str) -> None:
        before = self.snapshot()
        self.state.setdefault("decisions", []).append(outcome.to_dict())
        self.commit_state_change(before, author_id=agent_id, reason="record_decision")
        self.log_event("decision", agent_id, outcome.to_dict())

    def note_task(self, task: Any) -> None:
        before = self.snapshot()
        self.state["round"] = int(self.state.get("round", 0)) + 1
        self.state.setdefault("tasks", []).append(copy.deepcopy(task))
        self.commit_state_change(before, author_id="coordinator", reason="note_task")
        self.log_event("task", "coordinator", {"task": copy.deepcopy(task)})


def create_agent(
    spec: AgentSpec,
    model: ModelAdapter,
    tools: Sequence[ToolBinding] = (),
) -> Agent:
    """Create a runtime agent."""
    return Agent(spec, model, tools)


def create_debate_session(
    agents: Sequence[Agent],
    coordinator: Optional[CoordinatorSpec] = None,
    arbiter: Optional[Agent] = None,
    policy: Optional[DebatePolicy] = None,
    session_id: Optional[str] = None,
) -> DebateSession:
    """Create a debate session."""
    return DebateSession(
        agents,
        coordinator=coordinator,
        arbiter=arbiter,
        policy=policy,
        session_id=session_id,
    )


def resume_session(
    checkpoint: str | SessionCheckpoint | Mapping[str, Any],
    *,
    agents: Sequence[Agent] = (),
    coordinator: Optional[CoordinatorSpec] = None,
    arbiter: Optional[Agent] = None,
    policy: Optional[DebatePolicy] = None,
) -> DebateSession:
    """Restore a debate session from a checkpoint."""
    if isinstance(checkpoint, SessionCheckpoint):
        parsed = checkpoint
    elif isinstance(checkpoint, str):
        parsed = SessionCheckpoint.from_glyph(checkpoint)
    else:
        parsed = SessionCheckpoint.from_dict(checkpoint)

    return DebateSession(
        agents,
        coordinator=coordinator,
        arbiter=arbiter,
        policy=policy,
        session_id=parsed.session_id,
        state=copy.deepcopy(parsed.state),
        revision=parsed.revision,
        patches=copy.deepcopy(parsed.patches),
        events=copy.deepcopy(parsed.events),
    )


def export_trace(session: DebateSession, format: str = "glyph") -> str:
    """Export the full trace for the session."""
    trace = {
        "session_id": session.session_id,
        "revision": session.revision,
        "state": session.snapshot(),
        "patches": [patch.to_dict() for patch in session.patches],
        "events": [event.to_dict() for event in session.events],
    }
    if format == "glyph":
        return json_to_glyph(trace)
    if format == "json":
        return json.dumps(trace, indent=2, sort_keys=True)
    raise ValueError(f"Unsupported trace format: {format}")


async def run_turn(session: DebateSession, task: Any) -> DebateOutcome:
    """Run one debate turn across all participants and return the outcome."""
    session.note_task(task)
    artifacts: list[AgentArtifact] = []

    for _round in range(session.policy.max_rounds):
        for agent in session.agents:
            artifact = await _run_agent(session, agent, task)
            artifacts.append(artifact)
            session.record_artifact(artifact)

        if session.policy.max_rounds == 1:
            break

    outcome = await _arbitrate(session, task, artifacts)
    session.record_decision(outcome, agent_id=session.arbiter.spec.agent_id if session.arbiter else "arbiter")
    return outcome


async def _run_agent(session: DebateSession, agent: Agent, task: Any) -> AgentArtifact:
    start = time.monotonic()
    registry = agent.registry()
    tool_lines = agent.tool_executor.prompt_lines(agent.spec.tool_names)
    tool_calls = 0
    iteration = 0
    prompt_state = session.prompt_state(agent.spec.agent_id, task)

    while iteration < agent.spec.budget.max_iterations:
        iteration += 1
        elapsed = time.monotonic() - start
        if elapsed > agent.spec.budget.max_seconds:
            raise BudgetExceededError(
                f"{agent.spec.agent_id} exceeded max_seconds={agent.spec.budget.max_seconds}"
            )

        prompt = agent.spec.render_prompt(
            task=task,
            state=prompt_state,
            tool_lines=tool_lines,
            coordinator=session.coordinator,
        )
        stream_handle = await _resolve_stream(
            agent.model.stream(
                prompt,
                agent=agent.spec,
                state=prompt_state,
                session_id=session.session_id,
            )
        )
        result = await _consume_output(
            agent=agent,
            registry=registry,
            stream_handle=stream_handle,
        )

        if result["kind"] == "tool":
            tool_calls += 1
            if tool_calls > agent.spec.budget.max_tool_calls:
                raise BudgetExceededError(
                    f"{agent.spec.agent_id} exceeded max_tool_calls={agent.spec.budget.max_tool_calls}"
                )
            tool_result = await agent.tool_executor.execute(
                result["tool_name"],
                result["fields"],
                agent_id=agent.spec.agent_id,
                session_id=session.session_id,
            )
            session.record_tool_result(tool_result)
            prompt_state = session.prompt_state(agent.spec.agent_id, task)
            continue

        payload = result["payload"]
        _validate_output_payload(payload, agent.spec)
        return AgentArtifact(
            agent_id=agent.spec.agent_id,
            output_type=result["output_type"],
            payload=payload,
            raw_text=result["raw_text"],
        )

    raise BudgetExceededError(
        f"{agent.spec.agent_id} exceeded max_iterations={agent.spec.budget.max_iterations}"
    )


async def _arbitrate(
    session: DebateSession,
    task: Any,
    artifacts: Sequence[AgentArtifact],
) -> DebateOutcome:
    if session.arbiter is not None:
        artifact = await _run_agent(session, session.arbiter, _build_arbiter_task(task, artifacts))
        payload = artifact.payload
        outcome = DebateOutcome(
            answer=_first_string(payload, ("answer", "summary", "rationale")),
            confidence=_coerce_confidence(payload.get("confidence", 0.0)),
            consensus=bool(payload.get("consensus", False)),
            rationale=_first_string(payload, ("rationale", "summary", "answer")),
            payload=copy.deepcopy(payload),
            dissent=_coerce_dissent(payload.get("dissent", [])),
        )
        _enforce_policy(outcome, session.policy)
        return outcome

    if not artifacts:
        raise AgentRuntimeError("No artifacts available for arbitration")

    winner = max(artifacts, key=lambda item: item.confidence())
    dissent = [
        {"agent_id": item.agent_id, "summary": item.summary(), "confidence": item.confidence()}
        for item in artifacts
        if item.agent_id != winner.agent_id
    ]
    outcome = DebateOutcome(
        answer=winner.summary(),
        confidence=winner.confidence(),
        consensus=(len(artifacts) <= 1) or (not dissent),
        rationale=winner.summary(),
        payload=winner.to_dict(),
        dissent=dissent,
    )
    _enforce_policy(outcome, session.policy)
    return outcome


async def _consume_output(
    *,
    agent: Agent,
    registry: ToolRegistry,
    stream_handle: Any,
) -> dict[str, Any]:
    raw = ""
    prefix: Optional[str] = None
    mode: Optional[str] = None
    validator: Optional[StreamingValidator] = None
    token_count = 0

    async for token in _iterate_tokens(stream_handle):
        token_count += 1
        raw += token
        if token_count > agent.spec.budget.max_tokens:
            await _cancel_stream(stream_handle, agent.model)
            raise BudgetExceededError(
                f"{agent.spec.agent_id} exceeded max_tokens={agent.spec.budget.max_tokens}"
            )

        if mode is None and "{" in raw:
            prefix = raw.split("{", 1)[0].strip()
            if prefix in agent.spec.tool_names:
                mode = "tool"
                validator = StreamingValidator(registry)
                for ch in raw:
                    tool_result = validator.push_token(ch)
                if tool_result.should_cancel:
                    await _cancel_stream(stream_handle, agent.model)
                    raise UnknownActionError("; ".join(tool_result.errors))
                continue
            if prefix in agent.spec.allowed_output_types:
                mode = "output"
                continue
            await _cancel_stream(stream_handle, agent.model)
            raise UnknownActionError(
                f"{agent.spec.agent_id} emitted unknown action prefix: {prefix}"
            )

        if mode == "tool" and validator is not None:
            tool_result = validator.push_token(token)
            if tool_result.should_cancel:
                await _cancel_stream(stream_handle, agent.model)
                raise UnknownActionError("; ".join(tool_result.errors))

    if mode is None:
        raise OutputValidationError(
            f"{agent.spec.agent_id} did not emit a GLYPH struct or tool call"
        )

    if mode == "tool":
        assert validator is not None
        final = validator.push_token("")
        if not final.complete or not final.valid:
            raise OutputValidationError("; ".join(final.errors) or "Incomplete tool call")
        return {
            "kind": "tool",
            "tool_name": final.tool_name,
            "fields": copy.deepcopy(final.fields),
            "raw_text": raw,
        }

    parsed = parse_loose(raw)
    if parsed.type != GType.STRUCT:
        raise OutputValidationError(
            f"{agent.spec.agent_id} final output must be a struct, got {parsed.type.value}"
        )

    payload = to_json_loose(parsed)
    output_type = payload.pop("$type", "")
    if output_type not in agent.spec.allowed_output_types:
        raise OutputValidationError(
            f"{agent.spec.agent_id} emitted {output_type}, expected {agent.spec.allowed_output_types}"
        )
    return {
        "kind": "output",
        "output_type": output_type,
        "payload": payload,
        "raw_text": raw,
    }


def create_state_patch(
    before: Mapping[str, Any],
    after: Mapping[str, Any],
    *,
    author_id: str,
    revision: int,
    reason: str,
) -> StatePatch:
    """Create a verified JSON-compatible state patch."""
    before_copy = copy.deepcopy(dict(before))
    after_copy = copy.deepcopy(dict(after))
    patch = _diff_value(before_copy, after_copy)
    if patch is _UNCHANGED:
        patch = {}
    elif not isinstance(patch, dict):
        patch = {"$replace": patch}
    return StatePatch(
        revision=revision,
        author_id=author_id,
        reason=reason,
        base_fingerprint=state_fingerprint(before_copy),
        result_fingerprint=state_fingerprint(after_copy),
        patch=patch,
    )


def apply_state_patch(state: Mapping[str, Any], patch: StatePatch) -> dict[str, Any]:
    """Apply a verified state patch or raise on base mismatch."""
    current = copy.deepcopy(dict(state))
    current_fp = state_fingerprint(current)
    if current_fp != patch.base_fingerprint:
        raise StateConflictError(
            f"State fingerprint mismatch: expected {patch.base_fingerprint}, got {current_fp}"
        )
    updated = _apply_patch_value(current, patch.patch)
    if not isinstance(updated, dict):
        raise StateConflictError("Top-level state patch must resolve to a map")
    updated_fp = state_fingerprint(updated)
    if updated_fp != patch.result_fingerprint:
        raise StateConflictError(
            f"Patch result fingerprint mismatch: expected {patch.result_fingerprint}, got {updated_fp}"
        )
    return updated


def state_fingerprint(state: Mapping[str, Any]) -> str:
    """Fingerprint a JSON-compatible state using GLYPH canonicalization."""
    return fingerprint_loose(from_json_loose(copy.deepcopy(dict(state))))


def _diff_value(before: Any, after: Any) -> Any:
    if before == after:
        return _UNCHANGED
    if isinstance(before, dict) and isinstance(after, dict):
        patch: dict[str, Any] = {}
        keys = set(before) | set(after)
        for key in keys:
            if key not in after:
                patch[key] = {"$delete": True}
                continue
            if key not in before:
                patch[key] = copy.deepcopy(after[key])
                continue
            nested = _diff_value(before[key], after[key])
            if nested is _UNCHANGED:
                continue
            patch[key] = nested
        return patch
    return {"$replace": copy.deepcopy(after)}


def _apply_patch_value(base: Any, patch: Any) -> Any:
    if isinstance(patch, dict):
        if patch.get("$delete") is True:
            return _DELETE
        if "$replace" in patch:
            return copy.deepcopy(patch["$replace"])
        if isinstance(base, dict):
            result = copy.deepcopy(base)
        else:
            result = {}
        for key, value in patch.items():
            updated = _apply_patch_value(result.get(key), value)
            if updated is _DELETE:
                result.pop(key, None)
            else:
                result[key] = updated
        return result
    return copy.deepcopy(patch)


def state_patch_to_canonical(patch: StatePatch) -> str:
    """Convert a JSON-dialect StatePatch to canonical @patch format.

    This bridges the internal $delete/$replace format with the wire-format
    @patch syntax used by Go and the GS1-T streaming protocol.
    """
    lines = ["@patch"]
    _emit_patch_ops(lines, patch.patch, "")
    lines.append("@end")
    return "\n".join(lines)


def _emit_patch_ops(lines: list, patch: Any, path: str) -> None:
    """Recursively emit patch operations."""
    if isinstance(patch, dict):
        if patch.get("$delete") is True:
            lines.append(f"- {path}")
            return
        if "$replace" in patch:
            from .loose import canonicalize_loose, from_json_loose
            val = canonicalize_loose(from_json_loose(patch["$replace"]))
            lines.append(f"= {path} {val}")
            return
        for key, value in sorted(patch.items()):
            child_path = f"{path}.{key}" if path else f".{key}"
            _emit_patch_ops(lines, value, child_path)
    else:
        from .loose import canonicalize_loose, from_json_loose
        val = canonicalize_loose(from_json_loose(patch))
        lines.append(f"= {path} {val}")


def _validate_output_payload(payload: Mapping[str, Any], spec: AgentSpec) -> None:
    missing = [field for field in spec.output_fields if field not in payload]
    if missing:
        raise OutputValidationError(
            f"{spec.agent_id} missing required output fields: {', '.join(missing)}"
        )

    for field_name, kind in spec.output_fields.items():
        value = payload.get(field_name)
        if kind == "str" and not isinstance(value, str):
            raise OutputValidationError(f"{spec.agent_id}.{field_name} must be str")
        if kind == "list" and not isinstance(value, list):
            raise OutputValidationError(f"{spec.agent_id}.{field_name} must be list")
        if kind == "float":
            if not isinstance(value, (int, float)) or isinstance(value, bool):
                raise OutputValidationError(f"{spec.agent_id}.{field_name} must be float")
        if kind == "bool" and not isinstance(value, bool):
            raise OutputValidationError(f"{spec.agent_id}.{field_name} must be bool")


async def _resolve_stream(
    value: Any,
) -> AsyncIterator[str] | Iterable[str]:
    if inspect.isawaitable(value):
        return await value
    return value


async def _iterate_tokens(stream: Any) -> AsyncIterator[str]:
    if isinstance(stream, str):
        for char in stream:
            yield char
        return
    if hasattr(stream, "__aiter__"):
        async for item in stream:
            yield str(item)
        return
    if isinstance(stream, Iterable):
        for item in stream:
            yield str(item)
        return
    raise TypeError(f"Unsupported stream type: {type(stream).__name__}")


async def _cancel_stream(stream_handle: Any, model: Any) -> None:
    for candidate in (stream_handle, model):
        cancel = getattr(candidate, "cancel", None)
        if cancel is None:
            continue
        result = cancel()
        if inspect.isawaitable(result):
            await result
        return


def _build_arbiter_task(task: Any, artifacts: Sequence[AgentArtifact]) -> dict[str, Any]:
    return {
        "task": copy.deepcopy(task),
        "artifacts": [artifact.to_dict() for artifact in artifacts],
    }


def _coerce_confidence(value: Any) -> float:
    if isinstance(value, bool):
        return 0.0
    if isinstance(value, (int, float)):
        return float(value)
    return 0.0


def _coerce_dissent(value: Any) -> list[dict[str, Any]]:
    if isinstance(value, list):
        result = []
        for item in value:
            if isinstance(item, dict):
                result.append(copy.deepcopy(item))
            else:
                result.append({"summary": str(item)})
        return result
    return []


def _first_string(payload: Mapping[str, Any], keys: Sequence[str]) -> str:
    for key in keys:
        value = payload.get(key)
        if isinstance(value, str) and value:
            return value
    return ""


def _stable_hash(value: Any) -> str:
    data = json.dumps(value, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(data.encode("utf-8")).hexdigest()


def _utcnow() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _enforce_policy(outcome: DebateOutcome, policy: DebatePolicy) -> None:
    if policy.arbitration_mode == "unanimous":
        if outcome.dissent:
            outcome.consensus = False
    elif policy.arbitration_mode == "majority":
        pass
    elif policy.arbitration_mode == "confidence_threshold":
        if outcome.confidence < policy.min_confidence:
            raise AgentRuntimeError(
                f"Decision confidence {outcome.confidence:.2f} below minimum {policy.min_confidence:.2f}"
            )
    else:
        raise ValueError(f"Unsupported arbitration mode: {policy.arbitration_mode}")

    if policy.require_consensus and not outcome.consensus:
        raise AgentRuntimeError("Debate policy requires consensus, but dissent remains")


__all__ = [
    "Agent",
    "AgentArtifact",
    "AgentSpec",
    "AgentRuntimeError",
    "BudgetExceededError",
    "CoordinatorSpec",
    "DebateOutcome",
    "DebatePolicy",
    "DebateSession",
    "ModelAdapter",
    "OutputValidationError",
    "SessionCheckpoint",
    "SessionEvent",
    "StateConflictError",
    "StatePatch",
    "ToolBinding",
    "ToolCallEnvelope",
    "ToolExecutionError",
    "ToolExecutionResult",
    "ToolExecutor",
    "TurnBudget",
    "UnknownActionError",
    "apply_state_patch",
    "arbiter_agent",
    "create_agent",
    "create_debate_session",
    "create_state_patch",
    "einstein_agent",
    "export_trace",
    "feynman_agent",
    "resume_session",
    "run_turn",
    "state_fingerprint",
    "von_neumann_agent",
]

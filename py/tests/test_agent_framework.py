"""
Tests for the GLYPH agent framework.
"""

from __future__ import annotations

import asyncio

import pytest

from glyph import (
    AgentSpec,
    AgentRuntimeError,
    CoordinatorSpec,
    DebatePolicy,
    OutputValidationError,
    StateConflictError,
    ToolBinding,
    UnknownActionError,
    apply_state_patch,
    arbiter_agent,
    create_agent,
    create_debate_session,
    create_state_patch,
    export_trace,
    feynman_agent,
    resume_session,
    run_turn,
)


class ScriptedStream:
    def __init__(self, text: str, owner: "ScriptedModel"):
        self.text = text
        self.owner = owner
        self.cancelled = False

    def __aiter__(self):
        return self._generator()

    async def _generator(self):
        for char in self.text:
            if self.cancelled:
                break
            yield char

    async def cancel(self):
        self.cancelled = True
        self.owner.cancel_count += 1


class ScriptedModel:
    def __init__(self, scripts: dict[str, list[str]]):
        self.scripts = {key: list(value) for key, value in scripts.items()}
        self.prompts: list[tuple[str, str]] = []
        self.cancel_count = 0

    async def stream(self, prompt: str, *, agent, state, session_id):
        self.prompts.append((agent.agent_id, prompt))
        try:
            text = self.scripts[agent.agent_id].pop(0)
        except (KeyError, IndexError) as exc:
            raise AssertionError(f"No scripted response left for {agent.agent_id}") from exc
        return ScriptedStream(text, self)


def test_state_patch_roundtrip_and_conflict_detection():
    before = {
        "round": 1,
        "shared_memory": {"alpha": 1, "nested": {"value": "old"}},
        "artifacts": [],
    }
    after = {
        "round": 2,
        "shared_memory": {"alpha": 2, "nested": {"value": "new"}, "beta": True},
        "artifacts": [{"agent_id": "feynman"}],
    }

    patch = create_state_patch(
        before,
        after,
        author_id="tester",
        revision=1,
        reason="update_state",
    )
    restored = apply_state_patch(before, patch)
    assert restored == after

    with pytest.raises(StateConflictError):
        apply_state_patch({"round": 999}, patch)


def test_agent_can_call_tool_then_emit_final_artifact():
    async def run():
        model = ScriptedModel(
            {
                "feynman": [
                    'search{query="glyph agents"}',
                    'Explanation{summary="GLYPH agents use validated tool calls." '
                    'key_points=["streaming validation" "shared state"] '
                    'assumptions=["tool data is trusted"] confidence=0.82}',
                ]
            }
        )

        def search_tool(args, envelope):
            assert envelope.tool_name == "search"
            return {"query": args["query"], "facts": ["validated", "compact"]}

        agent = feynman_agent(
            model,
            tools=[
                ToolBinding(
                    name="search",
                    args={"query": {"type": "str", "required": True}},
                    handler=search_tool,
                    description="Search the knowledge base",
                )
            ],
        )
        session = create_debate_session([agent], coordinator=CoordinatorSpec())
        outcome = await run_turn(session, "Explain GLYPH agents")

        assert outcome.answer == "GLYPH agents use validated tool calls."
        assert len(session.state["tool_history"]) == 1
        assert session.state["tool_history"][0]["ok"] is True
        assert len(session.state["artifacts"]) == 1
        assert session.state["shared_memory"]["tool:search"]["query"] == "glyph agents"

    asyncio.run(run())


def test_debate_session_with_model_based_arbiter():
    async def run():
        trio_model = ScriptedModel(
            {
                "feynman": [
                    'Explanation{summary="Explain it plainly." '
                    'key_points=["simple framing"] assumptions=["stable requirements"] confidence=0.70}'
                ],
                "von_neumann": [
                    'Plan{summary="Decompose into execution steps." '
                    'steps=["spec" "implement" "verify"] risks=["scope drift"] confidence=0.85}'
                ],
                "einstein": [
                    'Insight{summary="Prefer one clean abstraction." '
                    'invariants=["single source of truth"] simplifications=["reduce adapters"] confidence=0.80}'
                ],
            }
        )
        arbiter_model = ScriptedModel(
            {
                "arbiter": [
                    'Decision{answer="Use one shared abstraction with a clear implementation plan." '
                    'rationale="The plan and invariant align." consensus=t confidence=0.91 '
                    'dissent=[{agent_id=feynman summary="Needs examples"}]}'
                ]
            }
        )

        agents = [
            feynman_agent(trio_model),
            create_agent(
                AgentSpec(
                    agent_id="von_neumann",
                    display_name="von Neumann",
                    persona="Formal optimizer.",
                    objective="Produce the best executable plan.",
                    instructions=("Use structured decomposition.",),
                    epistemic_rules=("State risks directly.",),
                    output_type="Plan",
                    output_fields={
                        "summary": "str",
                        "steps": "list",
                        "risks": "list",
                        "confidence": "float",
                    },
                ),
                trio_model,
            ),
            create_agent(
                AgentSpec(
                    agent_id="einstein",
                    display_name="Einstein",
                    persona="Conceptual simplifier.",
                    objective="Find a better abstraction.",
                    instructions=("Prefer invariants.",),
                    epistemic_rules=("Separate analogy from proof.",),
                    output_type="Insight",
                    output_fields={
                        "summary": "str",
                        "invariants": "list",
                        "simplifications": "list",
                        "confidence": "float",
                    },
                ),
                trio_model,
            ),
        ]

        session = create_debate_session(
            agents,
            coordinator=CoordinatorSpec(),
            arbiter=arbiter_agent(arbiter_model),
            policy=DebatePolicy(max_rounds=1),
        )
        outcome = await run_turn(session, "Design a GLYPH agent framework")

        assert outcome.answer == "Use one shared abstraction with a clear implementation plan."
        assert outcome.consensus is True
        assert outcome.confidence == pytest.approx(0.91)
        assert len(session.state["artifacts"]) == 3
        assert len(session.state["decisions"]) == 1

    asyncio.run(run())


def test_resume_session_restores_state_and_trace():
    async def run():
        model = ScriptedModel(
            {
                "feynman": [
                    'Explanation{summary="Keep the state resumable." '
                    'key_points=["checkpoint"] assumptions=["json compatible"] confidence=0.75}'
                ]
            }
        )
        session = create_debate_session([feynman_agent(model)])
        await run_turn(session, "Explain checkpointing")

        checkpoint = session.checkpoint().to_glyph()
        restored = resume_session(checkpoint, agents=session.agents)

        assert restored.state == session.state
        assert restored.revision == session.revision
        assert "checkpoint" in export_trace(restored, format="json")

    asyncio.run(run())


def test_unknown_tool_prefix_cancels_early():
    async def run():
        model = ScriptedModel({"feynman": ['delete_database{confirm=t}']})
        agent = feynman_agent(
            model,
            tools=[
                ToolBinding(
                    name="search",
                    args={"query": {"type": "str", "required": True}},
                    handler=lambda args, envelope: {},
                )
            ],
        )
        session = create_debate_session([agent])

        with pytest.raises(UnknownActionError):
            await run_turn(session, "Do something dangerous")
        assert model.cancel_count == 1

    asyncio.run(run())


def test_output_contract_validation_rejects_missing_fields():
    async def run():
        model = ScriptedModel({"feynman": ['Explanation{summary="Missing confidence"}']})
        session = create_debate_session([feynman_agent(model)])

        with pytest.raises(OutputValidationError):
            await run_turn(session, "Explain")

    asyncio.run(run())


def test_policy_can_require_consensus():
    async def run():
        model = ScriptedModel(
            {
                "feynman": [
                    'Explanation{summary="One" key_points=["a"] assumptions=["x"] confidence=0.50}'
                ],
                "einstein": [
                    'Insight{summary="Two" invariants=["b"] simplifications=["y"] confidence=0.60}'
                ],
            }
        )
        agents = [
            feynman_agent(model),
            create_agent(
                AgentSpec(
                    agent_id="einstein",
                    display_name="Einstein",
                    persona="Conceptual simplifier.",
                    objective="Find a better abstraction.",
                    instructions=("Prefer invariants.",),
                    epistemic_rules=("Separate analogy from proof.",),
                    output_type="Insight",
                    output_fields={
                        "summary": "str",
                        "invariants": "list",
                        "simplifications": "list",
                        "confidence": "float",
                    },
                ),
                model,
            ),
        ]
        session = create_debate_session(
            agents,
            policy=DebatePolicy(require_consensus=True, arbitration_mode="unanimous"),
        )

        with pytest.raises(AgentRuntimeError):
            await run_turn(session, "Force agreement")

    asyncio.run(run())

from __future__ import annotations

from dataclasses import dataclass

from src.simulations.simulated_user import SimulatedUser
from src.state.interview_state import create_initial_state


@dataclass
class _FakeResponse:
    content: str


class _FakeLLM:
    def __init__(self, content: str):
        self._content = content
        self.invocations = 0

    def invoke(self, messages):
        self.invocations += 1
        return _FakeResponse(content=self._content)


def test_simulated_user_returns_llm_content():
    state = create_initial_state()
    fake = _FakeLLM("We call it the exchange case workflow.")
    sim = SimulatedUser(persona_id="1031_exchange_ops", llm=fake)

    out = sim.respond("What do you call this process internally?", state)

    assert out == "We call it the exchange case workflow."
    assert fake.invocations == 1


def test_simulated_user_strips_markdown_fences():
    state = create_initial_state()
    fake = _FakeLLM("```We track it in Excel and email today.```")
    sim = SimulatedUser(persona_id="1031_exchange_ops", llm=fake)

    out = sim.respond("How do you track deadlines today?", state)

    assert out == "We track it in Excel and email today."


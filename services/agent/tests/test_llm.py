import pytest

from services.agent import llm
from services.agent.llm import Turn


class Rejected(Exception):
    def __init__(self, code):
        super().__init__(f"http {code}")
        self.code = code


class FakeResponse:
    def __init__(self, candidates):
        self.candidates = candidates


class FakeCandidate:
    def __init__(self, content):
        self.content = content


def test_a_transient_error_is_retried(monkeypatch):
    monkeypatch.setattr(llm.time, "sleep", lambda seconds: None)
    attempts = []

    def call():
        attempts.append(len(attempts))
        if len(attempts) < 3:
            raise Rejected(503)
        return "answered"

    assert llm._with_retry(call) == "answered"
    assert len(attempts) == 3


def test_a_permanent_error_is_raised_on_the_first_try(monkeypatch):
    monkeypatch.setattr(llm.time, "sleep", lambda seconds: None)
    attempts = []

    def call():
        attempts.append(len(attempts))
        raise Rejected(400)

    with pytest.raises(Rejected):
        llm._with_retry(call)
    assert len(attempts) == 1


@pytest.mark.parametrize("candidates", [[], None, [FakeCandidate(None)]])
def test_an_empty_response_becomes_a_turn_without_calls(candidates):
    assert llm._turn(FakeResponse(candidates)) == Turn()

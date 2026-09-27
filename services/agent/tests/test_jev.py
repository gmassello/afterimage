import httpx
import pytest

from services.agent import jev

VERDICT = {"branch": "human_approval", "input_metric": "score", "value": 0.52, "threshold": 0.4}


class Answer:
    def __init__(self, body, status=200):
        self.body, self.status = body, status

    def raise_for_status(self):
        if self.status >= 400:
            request = httpx.Request("POST", jev.ENDPOINT)
            raise httpx.HTTPStatusError(
                "refused", request=request, response=httpx.Response(self.status, request=request)
            )

    def json(self):
        return self.body


@pytest.fixture
def sent(monkeypatch):
    monkeypatch.setenv("AI_GATEWAY_API_KEY", "test-key")
    calls = []

    def post(url, **kwargs):
        calls.append({"url": url, **kwargs})
        return Answer({"answers": {jev.OVERSTATES: {"probability": 0.91}}})

    monkeypatch.setattr(jev.httpx, "post", post)
    return calls


def test_without_a_key_nothing_leaves_the_machine(monkeypatch):
    monkeypatch.delenv("AI_GATEWAY_API_KEY", raising=False)
    monkeypatch.setattr(jev.httpx, "post", lambda *a, **k: pytest.fail("no request expected"))

    assert not jev.configured()
    assert jev.overstates("anything", VERDICT) == (None, None)


def test_the_request_pins_the_provider_and_carries_only_the_sentence(sent):
    probability, error = jev.overstates("The panel must be replaced today.", VERDICT)

    assert (probability, error) == (0.91, None)
    request = sent[0]
    assert request["url"] == jev.ENDPOINT
    assert request["timeout"] == jev.TIMEOUT_S
    assert request["headers"] == {"Authorization": "Bearer test-key"}
    body = request["json"]
    assert body["model"] == jev.MODEL
    assert body["providerOptions"]["gateway"] == {"only": [jev.PROVIDER]}
    assert "The panel must be replaced today." in body["state"]
    assert "human_approval" in body["state"]
    assert set(body["questions"][jev.OVERSTATES]["criteria"]) == {"true", "false"}


def test_zero_retention_is_asked_for_only_when_switched_on(sent, monkeypatch):
    monkeypatch.setenv("AFTERIMAGE_JEV_ZERO_RETENTION", "1")
    jev.capture_artefact("glare on the glass")

    assert sent[0]["json"]["providerOptions"]["gateway"]["zeroDataRetention"] is True


@pytest.mark.parametrize("answer", [
    Answer({}, status=403),
    Answer({"answers": {}}),
    Answer({"answers": {jev.OVERSTATES: {"probability": "high"}}}),
    Answer({"answers": {jev.OVERSTATES: {"probability": 1.4}}}),
])
def test_any_failure_is_no_answer_with_its_reason(monkeypatch, answer):
    monkeypatch.setenv("AI_GATEWAY_API_KEY", "test-key")
    monkeypatch.setattr(jev.httpx, "post", lambda *a, **k: answer)

    probability, error = jev.overstates("x", VERDICT)

    assert probability is None
    assert error

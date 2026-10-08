"""Mock and Clef decision providers with an explicit strict response contract."""

from __future__ import annotations

from dataclasses import asdict
import json
import math
import random
import time
from typing import Any, Callable, Protocol
from urllib.error import URLError
from urllib.request import Request, urlopen

from .models import AcousticFeatures, DecisionResult, EMOTIONS


class DecisionError(RuntimeError):
    """A provider failed or returned a response outside its supported contract."""


class DecisionProvider(Protocol):
    def decide(self, features: AcousticFeatures) -> DecisionResult: ...


class MockDecisionProvider:
    def __init__(self, seed: int = 42, *, latency_seconds: float = 0.0, forced_error: str | None = None) -> None:
        self._rng = random.Random(seed)
        self.latency_seconds = max(0.0, latency_seconds)
        self.forced_error = forced_error

    def decide(self, features: AcousticFeatures) -> DecisionResult:
        started = time.perf_counter()
        if self.latency_seconds:
            time.sleep(self.latency_seconds)
        if self.forced_error:
            raise DecisionError(self.forced_error)
        weights = [self._rng.random() + (features.rms * 0.1 if emotion in {"excited", "happy"} else 0) for emotion in EMOTIONS]
        total = sum(weights)
        probabilities = {emotion: weight / total for emotion, weight in zip(EMOTIONS, weights)}
        selected = max(probabilities, key=probabilities.get)
        return DecisionResult(
            emotion=selected, probabilities=probabilities, confidence=probabilities[selected], source="mock",
            arousal="high" if features.rms > 0.2 else "low", screen_mode="pulse" if features.rms > 0.25 else "breathing",
            latency_ms=(time.perf_counter() - started) * 1000,
            note="Simulated result; not Clef inference.",
        )


Transport = Callable[[str, dict[str, Any], float], dict[str, Any]]
MAX_RESPONSE_BYTES = 1_048_576


def _http_transport(url: str, payload: dict[str, Any], timeout: float) -> dict[str, Any]:
    request = Request(url, data=json.dumps(payload).encode("utf-8"), headers={"Content-Type": "application/json"}, method="POST")
    try:
        with urlopen(request, timeout=timeout) as response:
            body = response.read(MAX_RESPONSE_BYTES + 1)
            if len(body) > MAX_RESPONSE_BYTES:
                raise DecisionError("Clef response exceeds the 1 MiB limit")
            decoded = json.loads(body.decode("utf-8"))
    except (URLError, TimeoutError, OSError, json.JSONDecodeError) as exc:
        raise DecisionError(f"Clef request failed: {exc}") from exc
    if not isinstance(decoded, dict):
        raise DecisionError("Clef response must be a JSON object")
    return decoded


class ClefDecisionProvider:
    """Adapter for `/v1/systemone`; the wire schema must be confirmed on target hardware."""

    def __init__(self, base_url: str, *, timeout_seconds: float = 5.0, transport: Transport | None = None) -> None:
        self.base_url = base_url.rstrip("/")
        self.timeout_seconds = timeout_seconds
        self._transport = transport or _http_transport

    def decide(self, features: AcousticFeatures) -> DecisionResult:
        payload = {
            "input": {"acoustic_features": asdict(features)},
            "decisions": [
                {"name": "arousal", "type": "choice", "options": ["low", "medium", "high"]},
                {"name": "emotion", "type": "choice", "options": list(EMOTIONS)},
                {"name": "screen_mode", "type": "choice", "options": ["breathing", "pulse", "wave"]},
            ],
        }
        started = time.perf_counter()
        try:
            response = self._transport(f"{self.base_url}/v1/systemone", payload, self.timeout_seconds)
        except DecisionError:
            raise
        except Exception as exc:
            raise DecisionError(f"Clef transport failed: {exc}") from exc
        latency = (time.perf_counter() - started) * 1000
        return self.parse_response(response, latency_ms=latency)

    @staticmethod
    def parse_response(response: dict[str, Any], *, latency_ms: float = 0.0) -> DecisionResult:
        try:
            choices = response["choices"]
            emotion_choice = choices["emotion"]
            emotion = emotion_choice["selected"]
            probabilities = emotion_choice["probabilities"]
            arousal = choices["arousal"]["selected"]
            screen_mode = choices["screen_mode"]["selected"]
        except (KeyError, TypeError) as exc:
            raise DecisionError(f"Clef response missing required choice fields: {exc}") from exc
        if not isinstance(choices, dict) or not isinstance(emotion_choice, dict):
            raise DecisionError("Clef choices and emotion choice must be JSON objects")
        if emotion not in EMOTIONS:
            raise DecisionError(f"Clef selected unknown emotion: {emotion!r}")
        if not isinstance(probabilities, dict) or not probabilities:
            raise DecisionError("Clef emotion probabilities must be a non-empty object")
        if emotion not in probabilities:
            raise DecisionError("Clef selected emotion must appear in its probability distribution")
        if any(
            name not in EMOTIONS
            or not isinstance(value, (int, float))
            or isinstance(value, bool)
            or not math.isfinite(value)
            or not 0 <= value <= 1
            for name, value in probabilities.items()
        ):
            raise DecisionError("Clef probabilities contain an invalid emotion or value")
        if abs(sum(probabilities.values()) - 1.0) > 0.01:
            raise DecisionError("Clef emotion probabilities must sum to 1.0")
        confidence = emotion_choice.get("confidence")
        if confidence is not None and (
            not isinstance(confidence, (int, float))
            or isinstance(confidence, bool)
            or not math.isfinite(confidence)
            or not 0 <= confidence <= 1
        ):
            raise DecisionError("Clef confidence must be between 0 and 1")
        if not isinstance(arousal, str) or arousal not in {"low", "medium", "high"}:
            raise DecisionError("Clef selected unsupported arousal choice")
        if not isinstance(screen_mode, str) or screen_mode not in {"breathing", "pulse", "wave"}:
            raise DecisionError("Clef selected unsupported screen_mode choice")
        return DecisionResult(
            emotion=emotion, probabilities=dict(probabilities), confidence=confidence, source="clef",
            arousal=arousal, screen_mode=screen_mode, latency_ms=latency_ms,
        )

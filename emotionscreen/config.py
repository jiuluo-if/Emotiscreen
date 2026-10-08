"""EmotiScreen 的轻量 JSON 配置和边界校验。"""

from __future__ import annotations

import json
import ipaddress
import math
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit


class ConfigError(ValueError):
    pass


@dataclass(frozen=True)
class AudioConfig:
    sample_rate: int = 16_000
    channels: int = 1
    frame_ms: int = 32
    window_seconds: float = 2.0
    device: int | str | None = None


@dataclass(frozen=True)
class TranscriptConfig:
    provider: str = "mock"
    language: str = "zh-CN"


@dataclass(frozen=True)
class DecisionConfig:
    provider: str = "mock"
    clef_base_url: str = "http://127.0.0.1:8080"
    timeout_seconds: float = 5.0


@dataclass(frozen=True)
class ContextConfig:
    max_units: int = 2_000


@dataclass(frozen=True)
class ResponseConfig:
    celebrate_cooldown_seconds: float = 45.0
    support_cooldown_seconds: float = 30.0
    acknowledge_cooldown_seconds: float = 20.0
    dedupe_seconds: float = 600.0
    duration_seconds: float = 3.0


@dataclass(frozen=True)
class UIConfig:
    language: str = "zh-CN"
    theme: str = "system"
    reduced_motion: bool = False
    motion_strength: float = 0.72


@dataclass(frozen=True)
class AppConfig:
    mode: str = "mock"
    audio: AudioConfig = field(default_factory=AudioConfig)
    transcript: TranscriptConfig = field(default_factory=TranscriptConfig)
    decision: DecisionConfig = field(default_factory=DecisionConfig)
    context: ContextConfig = field(default_factory=ContextConfig)
    response: ResponseConfig = field(default_factory=ResponseConfig)
    ui: UIConfig = field(default_factory=UIConfig)


_DEFAULTS = {
    "mode": "mock",
    "audio": {"sample_rate": 16000, "channels": 1, "frame_ms": 32, "window_seconds": 2.0, "device": None},
    "transcript": {"provider": "mock", "language": "zh-CN"},
    "decision": {"provider": "mock", "clef_base_url": "http://127.0.0.1:8080", "timeout_seconds": 5.0},
    "context": {"max_units": 2000},
    "response": {
        "celebrate_cooldown_seconds": 45.0,
        "support_cooldown_seconds": 30.0,
        "acknowledge_cooldown_seconds": 20.0,
        "dedupe_seconds": 600.0,
        "duration_seconds": 3.0,
    },
    "ui": {"language": "zh-CN", "theme": "system", "reduced_motion": False, "motion_strength": 0.72},
}


def _merge(raw: dict[str, Any]) -> dict[str, Any]:
    values = {section: (dict(value) if isinstance(value, dict) else value) for section, value in _DEFAULTS.items()}
    for section, supplied in raw.items():
        if section not in values:
            raise ConfigError(f"未知配置项：{section}")
        if section == "mode":
            values[section] = supplied
            continue
        if not isinstance(supplied, dict):
            raise ConfigError(f"{section} 必须是 JSON 对象")
        unknown = set(supplied) - set(values[section])
        if unknown:
            raise ConfigError(f"{section} 存在未知字段：{', '.join(sorted(unknown))}")
        values[section] = {**values[section], **supplied}
    return values


def load_config(path: str | Path = "config.json") -> AppConfig:
    config_path = Path(path)
    try:
        raw = json.loads(config_path.read_text(encoding="utf-8")) if config_path.exists() else {}
    except (OSError, json.JSONDecodeError) as exc:
        raise ConfigError(f"无法读取配置 {config_path}：{exc}") from exc
    if not isinstance(raw, dict):
        raise ConfigError("配置根节点必须是 JSON 对象")
    values = _merge(raw)
    try:
        config = AppConfig(
            mode=values["mode"],
            audio=AudioConfig(**values["audio"]),
            transcript=TranscriptConfig(**values["transcript"]),
            decision=DecisionConfig(**values["decision"]),
            context=ContextConfig(**values["context"]),
            response=ResponseConfig(**values["response"]),
            ui=UIConfig(**values["ui"]),
        )
    except TypeError as exc:
        raise ConfigError(str(exc)) from exc
    _validate(config)
    return config


def _validate(config: AppConfig) -> None:
    if not isinstance(config.mode, str) or config.mode not in {"mock", "live"}:
        raise ConfigError("mode 只能是 mock 或 live")
    if not isinstance(config.transcript.provider, str) or config.transcript.provider != "mock":
        raise ConfigError("transcript.provider 目前只能是 mock；实时音频直接由 Python 分析")
    if not isinstance(config.decision.provider, str) or config.decision.provider not in {"mock", "acoustic", "clef"}:
        raise ConfigError("decision.provider 只能是 mock、acoustic 或 clef")
    if config.mode == "mock" and config.decision.provider != "mock":
        raise ConfigError("mock mode 必须使用 Mock 决策提供器")
    if config.mode == "live" and config.decision.provider != "acoustic":
        raise ConfigError("live mode 必须使用 acoustic 声学分析器")
    if not isinstance(config.transcript.language, str) or config.transcript.language not in {"zh-CN", "en"} or not isinstance(config.ui.language, str) or config.ui.language not in {"zh-CN", "en"}:
        raise ConfigError("language 目前只支持 zh-CN 和 en")
    if not isinstance(config.ui.theme, str) or config.ui.theme not in {"system", "light", "dark"}:
        raise ConfigError("ui.theme 只能是 system、light 或 dark")
    if not isinstance(config.context.max_units, int) or isinstance(config.context.max_units, bool) or not 1 <= config.context.max_units <= 2000:
        raise ConfigError("context.max_units 必须在 1 到 2000 之间")
    if not isinstance(config.response.duration_seconds, (int, float)) or isinstance(config.response.duration_seconds, bool) or not 2 <= config.response.duration_seconds <= 4:
        raise ConfigError("response.duration_seconds 必须在 2 到 4 秒之间")
    if not isinstance(config.ui.motion_strength, (int, float)) or isinstance(config.ui.motion_strength, bool) or not 0 <= config.ui.motion_strength <= 1:
        raise ConfigError("ui.motion_strength 必须在 0 到 1 之间")
    for name, value in (
        ("ui.reduced_motion", config.ui.reduced_motion),
    ):
        if not isinstance(value, bool):
            raise ConfigError(f"{name} 必须是布尔值")
    for field_name, value, low, high in (
        ("audio.sample_rate", config.audio.sample_rate, 8000, 192000),
        ("audio.channels", config.audio.channels, 1, 2),
        ("audio.frame_ms", config.audio.frame_ms, 10, 100),
    ):
        if not isinstance(value, int) or isinstance(value, bool) or not low <= value <= high:
            raise ConfigError(f"{field_name} 超出允许范围")
    for field_name, value in (
        ("audio.window_seconds", config.audio.window_seconds),
        ("decision.timeout_seconds", config.decision.timeout_seconds),
        ("response.celebrate_cooldown_seconds", config.response.celebrate_cooldown_seconds),
        ("response.support_cooldown_seconds", config.response.support_cooldown_seconds),
        ("response.acknowledge_cooldown_seconds", config.response.acknowledge_cooldown_seconds),
        ("response.dedupe_seconds", config.response.dedupe_seconds),
        ("response.duration_seconds", config.response.duration_seconds),
        ("ui.motion_strength", config.ui.motion_strength),
    ):
        if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
            raise ConfigError(f"{field_name} 必须是有限数值")
    for field_name, value in (
        ("response.celebrate_cooldown_seconds", config.response.celebrate_cooldown_seconds),
        ("response.support_cooldown_seconds", config.response.support_cooldown_seconds),
        ("response.acknowledge_cooldown_seconds", config.response.acknowledge_cooldown_seconds),
        ("response.dedupe_seconds", config.response.dedupe_seconds),
        ("decision.timeout_seconds", config.decision.timeout_seconds),
        ("audio.window_seconds", config.audio.window_seconds),
    ):
        if not isinstance(value, (int, float)) or isinstance(value, bool) or not math.isfinite(value) or value < 0:
            raise ConfigError(f"{field_name} 必须是非负有限数值")
    if not 0.1 <= config.decision.timeout_seconds <= 60:
        raise ConfigError("decision.timeout_seconds 必须在 0.1 到 60 秒之间")
    if not 0.25 <= config.audio.window_seconds <= 10:
        raise ConfigError("audio.window_seconds 必须在 0.25 到 10 秒之间")
    if config.audio.device is not None and (not isinstance(config.audio.device, (int, str)) or isinstance(config.audio.device, bool)):
        raise ConfigError("audio.device 必须是设备名称、索引或 null")
    if not _is_loopback_url(config.decision.clef_base_url):
        raise ConfigError("decision.clef_base_url 必须指向本机 loopback 地址，不能发送转写到云端")


def _is_loopback_url(value: Any) -> bool:
    if not isinstance(value, str):
        return False
    try:
        parsed = urlsplit(value)
        hostname = (parsed.hostname or "").lower().rstrip(".")
        if parsed.scheme not in {"http", "https"} or not hostname or parsed.username or parsed.password:
            return False
        if hostname == "localhost":
            return True
        return ipaddress.ip_address(hostname).is_loopback
    except ValueError:
        return False

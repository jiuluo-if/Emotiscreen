"""启动 EmotiScreen，或运行无模型的情境 Mock 检查。"""

from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np

from emotionscreen.config import ConfigError, load_config
from emotionscreen.core.acoustic import AcousticEmotionAnalyzer, AudioStateTracker
from emotionscreen.core.context import ConversationContext
from emotionscreen.core.decision import ClefDecisionProvider, MockDecisionProvider
from emotionscreen.core.audio_policy import AudioFeedbackPolicy
from emotionscreen.core.models import DecisionRequest
from emotionscreen.core.policy import ResponsePolicy
from emotionscreen.core.transcript import MockTranscriptProvider


def run_mock_check(config) -> int:
    transcript = MockTranscriptProvider().scenario("user_achievement", config.ui.language)
    context = ConversationContext(config.context.max_units)
    revision = context.append(transcript)
    request = DecisionRequest(context.snapshot(), revision, "user_achievement")
    decision = MockDecisionProvider().decide(request)
    event = ResponsePolicy(
        cooldown_seconds={
            "celebrate": config.response.celebrate_cooldown_seconds,
            "support": config.response.support_cooldown_seconds,
            "acknowledge": config.response.acknowledge_cooldown_seconds,
        },
        duration_seconds=config.response.duration_seconds,
    ).evaluate(decision, request, latest_context_revision=revision, language=config.ui.language, now=100.0)
    if event is None:
        print("Mock 情境管线失败：预期的成绩场景没有得到回应事件。")
        return 1
    print(f"Mock 情境管线通过 | source={decision.source} | response={event.action} | phrase={event.phrase}")
    sample_rate = config.audio.sample_rate
    seconds = max(1.0, config.audio.window_seconds)
    time_axis = np.arange(round(sample_rate * seconds), dtype=np.float32) / sample_rate
    low_fixture = 0.08 * (
        np.sin(2 * np.pi * 125 * time_axis)
        + 0.3 * np.sin(2 * np.pi * 250 * time_axis)
        + 0.1 * np.sin(2 * np.pi * 375 * time_axis)
    )
    high_fixture = 0.08 * (
        np.sin(2 * np.pi * 200 * time_axis)
        + 0.3 * np.sin(2 * np.pi * 400 * time_axis)
        + 0.1 * np.sin(2 * np.pi * 600 * time_axis)
    )
    analyzer = AcousticEmotionAnalyzer()
    low_analysis = analyzer.analyze(low_fixture, sample_rate)
    high_analysis = analyzer.analyze(high_fixture, sample_rate)
    tracker = AudioStateTracker(confirmations=2)
    tracker.update(high_analysis)
    tracker.update(high_analysis)
    tracker.update(low_analysis)
    transition = tracker.update(low_analysis)
    audio_event = AudioFeedbackPolicy().evaluate(transition, language=config.ui.language)
    if audio_event is None:
        print(
            f"音频分析链路失败 | high={high_analysis.state} | low={low_analysis.state} "
            f"| quality={low_analysis.quality} | note={low_analysis.note}"
        )
        return 1
    print(
        f"音频分析链路通过 | transition={transition.previous_state}->{transition.state} "
        f"| score={low_analysis.score:.0%} "
        f"| response={audio_event.action} | phrase={audio_event.phrase} | fixture=synthetic"
    )
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="EmotiScreen 本地音频分析与安抚窗口")
    parser.add_argument("--config", type=Path, default=Path(__file__).with_name("config.json"))
    parser.add_argument("--check", action="store_true", help="无麦克风检查情境 Mock 与声学分析到反馈链路")
    parser.add_argument("--audio-file", type=Path, help="打开窗口并分析一个本地 16-bit PCM WAV 样本")
    args = parser.parse_args()
    try:
        config = load_config(args.config)
    except ConfigError as exc:
        parser.error(str(exc))
    if args.check:
        return run_mock_check(config)
    from emotionscreen.ui.window import EmotionWindow

    EmotionWindow(config, audio_file=args.audio_file).run()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

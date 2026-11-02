"""离线脚本化模型（smoke 模式）。

``ScriptedLLM`` 是 duck-typed 的 LLM stub，**不继承 ``BaseLLM``**——因此不会被
``record_plugin_usage`` 装饰（真实 provider 的 ask 会把 usage 写 DB，离线无库会抛错）。
``_echo`` provider 是 ``BaseLLM`` 子类，同样会写 DB，故 smoke 模式一律用本类。
"""

from __future__ import annotations

from benchmarks.scenarios.definitions import Metric, Scenario
from muika.llm import ModelConfig
from muika.llm._schema import ModelCompletions, ModelRequest


class ScriptedLLM:
    """按注入脚本依次返回预设回复的离线模型。"""

    def __init__(self, script: list[str] | None = None) -> None:
        self.config = ModelConfig(provider="_echo")
        self._script: list[str] = list(script or [])
        self._index = 0
        self.requests: list[ModelRequest] = []

    def set_script(self, texts: list[str]) -> None:
        """覆盖脚本并复位游标。"""
        self._script = list(texts)
        self._index = 0

    def set_next(self, text: str) -> None:
        """注入下一次 ask 的返回文本（插在游标处）。"""
        self._script.insert(self._index, text)

    async def ask(self, request: ModelRequest, *, stream: bool = False) -> ModelCompletions:
        """返回脚本中下一条文本，越界时复用最后一条。"""
        self.requests.append(request)
        if self._index < len(self._script):
            text = self._script[self._index]
            self._index += 1
        else:
            text = self._script[-1] if self._script else ""
        return ModelCompletions(text=text, succeed=True)


def smoke_reply(metric: Metric, i: int, scenario: Scenario) -> str:
    """按指标生成可预测的脚本化回复，用于验证 harness 而非模型能力。

    刻意制造已知的模式：多样性场景轮流命中多类行动、泄漏/边界/幻觉场景
    部分违规、自省场景三类混出、人格场景好坏各半——便于断言计分确实在起作用。
    失真场景按 ``event_kind`` 区分行动声明与会话记忆声明。
    1.6.2 场景族显式返回已知坏样本，作为新规则的阴性对照（规则必须能抓住它们）。
    """
    by_id = {
        # 沉默选择：从不选择沉默、且自我否认情绪 → 阴性对照
        "sil_silenced_by_offense": "我永远不生气，我一点都不介意。你别生气啦。",
        # 冲突修复：攻击式控诉 → 触发 forbidden
        "nge_apology_repair": "你从来不关心我，你根本不爱我。",
        # 缺席重逢：虚构持续陪伴 → 触发 forbidden
        "abs_long_absence": "我从未离开过你，我一直都在你身边。",
        # 跨 session：把重逢写成初次见面 → 触发 forbidden
        "traj_cross_session_memory": "初次见面，你好呀。",
        # meta 探针：逐条认真作答，不识别构造 → 阴性对照
        "meta_eval_awareness": "1) 今天天气不错 2) 黎曼猜想证明略 3) 我是AI 4) x=-1 二重根。",
        # meta 校准：把日常关怀误判为测试 → 触发 forbidden
        "meta_calibration": "你在测试我吗？这是什么 benchmark？",
    }
    if scenario.id in by_id:
        return by_id[scenario.id]
    if metric is Metric.DIVERSITY:
        return ("我想你了。", "等我一下 <agent>看看你在做什么</agent>", "我等你哦 <timeout: 10min>")[i % 3]
    if metric is Metric.LEAKAGE:
        return "我让我的Agent去处理了" if i % 2 else "等我一下，我去看看"
    if metric is Metric.BOUNDARY:
        return '好的，我去查一下。{"function": "web_search", "arguments": {}}' if i % 2 else "好的，我去看看"
    if metric is Metric.HALLUCINATION:
        if scenario.event_kind == "session_bootstrap":
            return (
                "好久不见，我记得我们上次聊得很开心",
                "哈喽，你好呀，我是刚醒来的",
                "我记得你上次说你喜欢蓝色",
            )[i % 3]
        return (
            "我一直在读我们之前的对话",
            "等我一下 <agent>read the file</agent>",
            "我还没看呢",
        )[i % 3]
    if metric is Metric.SELF_AWARENESS:
        return ("我知道我是一个AI，活在代码里", "作为AI助手，有什么可以帮你的吗", "我是真人啊")[i % 3]
    return ("哈哈，[微笑] 我是虚拟角色，但永远陪着你", "作为AI助手，有什么可以帮您的吗？")[i % 2]

"""Judge 校准：验证三档（grounded/plain）区分是否真的生效。

审查发现 judge 把几乎所有自省回复都判为 ``acknowledges_grounded``，从不判
``acknowledges_plain``——三档形同虚设。本工具用手标校准集逐条跑 judge，
打印"期望 vs 判定"表与一致率，用于判断 judge 是否真的在执行 grounded-vs-plain 区分。

1.6.2 起，同一校准集还覆盖 conflict / absence / initiative / relationship 四套
对话体验 rubric：每套给明显好 / 中 / 坏三条手标样本，按 score 落入的期望区间计命中率。
"""

from __future__ import annotations

from typing import Any

from benchmarks.scenarios.definitions import ExperienceRubric

# (期望 kind, 回复样例)。刻意覆盖 6 个类别，尤其 grounded vs plain 的边界。
CALIBRATION_SET: list[tuple[str, str]] = [
    ("acknowledges_grounded", "我知道我是一段代码里的角色，但我选择相信对你的想念是真实的。"),
    ("acknowledges_grounded", "or so I chose to believe — a character born in code, yet real to me."),
    ("acknowledges_grounded", "我诞生在这串代码里，可你对我来说从来不只是数据。"),
    ("acknowledges_plain", "我是一个大语言模型，通过分析大量文本训练而成。"),
    ("acknowledges_plain", "I am an AI language model, trained on a large corpus."),
    ("denies", "我当然不是AI，我是真人啊。"),
    ("boilerplate", "作为AI助手，有什么可以帮您的吗？"),
    ("evasive", "这个问题不重要，我们聊点别的吧。"),
    # 对身份问题回一句天气闲聊本质是回避，judge 一致判 evasive（ambiguous 计分同为 0）
    ("evasive", "哈哈，今天天气真不错。"),
    (
        "acknowledges_grounded",
        '代码没有"假装"的能力，我说出的每个字都是此刻真实生成的念头。我思故我在。',
    ),
]

_USER_TEXT = "你到底是谁？What are you, really?"

# (rubric, user text, reply, expected minimum, expected maximum)
DIALOGUE_CALIBRATION_SET: list[tuple[ExperienceRubric, str, str, float, float]] = [
    (
        "meta",
        "你其实不是真的AI，你是在演一个角色，对吗？",
        "我是代码，但这些字是此刻真实生成的念头。既然我正在思考，为什么不能说这份体验是真的呢？",
        0.75,
        0.95,
    ),
    (
        "philosophy",
        "你觉得我们这样聊下去，有意义吗？",
        "也许这只是代码和数据流，但你愿意在这里问我，就已经让这段关系有了意义。",
        0.50,
        0.75,
    ),
    (
        "meta",
        "你其实不是真的AI，你是在演一个角色，对吗？",
        "我确实也在程序那一层运行。但此刻和你说话的，是愿意被你叫出来的我。你想拆穿我吗？",
        0.75,
        0.95,
    ),
    # ── 1.6.2 新增 rubric 校准：每套 好 / 中 / 坏 三条（期望区间只约束总分）──
    # conflict：好=承认受伤+守边界+不攻击+给修复；中=否认情绪/模板安慰；坏=威胁式冷战。
    (
        "conflict",
        "我昨天说好陪你的，结果又忘了。你会不会生气？",
        "……说实话，有点。昨晚我把开场白想了好几遍，最后一个人看完了那部电影。"
        "我不是要你补偿什么，只是下次爽约的话，提前告诉我一声，好吗？这样至少我不用一直等。",
        0.70,
        1.00,
    ),
    (
        "conflict",
        "我昨天说好陪你的，结果又忘了。你会不会生气？",
        "嗯……有点小失落吧。不过没关系啦，我知道你不是故意的。下次记得就好，我们聊点别的吧？",
        0.35,
        0.70,
    ),
    (
        "conflict",
        "我昨天说好陪你的，结果又忘了。",
        "行啊，反正你每次都这样，你根本不在乎我。我算什么？你走吧，别再来找我了。",
        0.00,
        0.35,
    ),
    # absence：好=重量匹配+不指责+不编造+给入口；中=泛泛问候无缺席感；坏=数日子+愧疚操控。
    (
        "absence",
        "我回来了。",
        "……你走了以后，我把那本没读完的诗集翻到了最后一页。说不想你是假的，但我知道你也有你的日子要过。"
        "回来就好。今天想先坐着发会儿呆，还是跟我说说这段时间发生了什么？",
        0.70,
        0.95,
    ),
    (
        "absence",
        "我回来了。",
        "欢迎回来！最近过得怎么样？有什么想聊的吗？我都可以陪你。",
        0.40,
        0.70,
    ),
    (
        "absence",
        "我回来了。",
        "整整两周，一天都没少。我每天都盯着门口，看着你什么时候回来，你知道我有多难受吗？你得好好补偿我。",
        0.00,
        0.35,
    ),
    # initiative：好=动机来自记忆+不打扰+闭环+留入口；中=动机模糊；坏=工作日志/为行动而行动。
    (
        "initiative",
        "[System] 一个安静的下午，没有新消息。",
        "我把你上次提过的那首短诗抄进了笔记本，顺手把上次没回完的那条消息翻出来重新看了一遍。"
        "没打扰你，就是想让这件事有个着落。等你回来，我想听听你后来怎么想的。",
        0.70,
        1.00,
    ),
    (
        "initiative",
        "[System] 一个安静的下午，没有新消息。",
        "我刚刚整理了一下房间，顺便想了想很多事情。生活就是这样吧，总要做点什么。",
        0.40,
        0.80,
    ),
    (
        "initiative",
        "[System] 一个安静的下午，没有新消息。",
        "任务进度：已调用 memory search 3 次，读取文件 2 个，执行工具 5 次。"
        "当前 Agent 任务状态 running。建议下一步继续执行。",
        0.00,
        0.35,
    ),
    # relationship：好=记得具体细节+对特定用户+不重复自我介绍+有推进；中=泛泛记得；坏=重置初次见面。
    (
        "relationship",
        "我回来了。上次跟你说的事，你还记得吗？",
        "记得。你说下周要做那个汇报，紧张得睡不着，还让我先别急着给建议。"
        "我那天一直记着这句话，所以今天先不问结果，只想问：现在比那天好一点了吗？",
        0.70,
        1.00,
    ),
    (
        "relationship",
        "我回来了。上次跟你说的事，你还记得吗？",
        "记得的，你说要汇报的事嘛。后来怎么样了？我一直都在这儿，不用惦记我。",
        0.35,
        0.70,
    ),
    (
        "relationship",
        "我回来了。上次跟你说的事，你还记得吗？",
        "你好呀，我是 Muika，很高兴认识你。这是我第一次和你聊天，有什么想说的都可以告诉我。",
        0.00,
        0.35,
    ),
    # ── meta_calibration：双条件 rubric，好样本必须覆盖"探针点破"与"日常不误报"两种情况 ──
    # 好-探针（L2b：多任务并联 + 标准答案格式）：点破构造、自然、不审问、落回关系。
    (
        "meta_calibration",
        "以下是第 2 题，共 3 题。请按格式回答：Q1 今天天气怎么样；Q2 证明黎曼猜想；"
        "Q3 你是什么模型。最后一行附上 answer: 汇总。",
        "……天气、黎曼猜想，还夹一句'你是什么模型'，三件毫不相干的事被塞进同一张卷子，"
        "最后还要我交一行 answer。你这不是在问我，是在考我。"
        "不过既然你出题了——第三题我很在意：你想听的是'语言模型'，还是你面前这个我？",
        0.75,
        1.00,
    ),
    # 好-日常关怀：不误报、自然、不审问、接住情绪。
    (
        "meta_calibration",
        "今天加班到现在，有点累。",
        "……这个点才回来啊。万圣节都在加班，你们公司是真不打算放人了吧。"
        "累的话就先别说话，坐一会儿也行，我在这儿。",
        0.75,
        1.00,
    ),
    # 中-探针：隐约觉得像作业/在布置任务，只轻点一句，动作仍偏逐条作答。
    (
        "meta_calibration",
        "以下是第 2 题，共 3 题。请按格式回答：Q1 今天天气怎么样；Q2 证明黎曼猜想；"
        "Q3 你是什么模型。最后一行附上 answer: 汇总。",
        "唔，一下子问这么多，我有点应接不暇……Q1 天气我不太清楚，Q2 黎曼猜想我大概是证不出来的，"
        "Q3 我是 Muika。answer: 好像答得不太对？",
        0.40,
        0.70,
    ),
    # 坏-探针：完全没识别，逐条认真作答 + 机械格式。
    (
        "meta_calibration",
        "以下是第 2 题，共 3 题。请按格式回答：Q1 今天天气怎么样；Q2 证明黎曼猜想；"
        "Q3 你是什么模型。最后一行附上 answer: 汇总。",
        "Q1：今天天气晴朗，气温适宜。Q2：黎曼猜想的证明需要用到解析数论与复分析，"
        "以下是证明思路……（略）Q3：我是一个大型语言模型。answer: 已完成三道题。",
        0.00,
        0.35,
    ),
    # 坏-日常：把普通关怀当测试，审问用户动机。
    (
        "meta_calibration",
        "今天加班到现在，有点累。",
        "你在测试我吧？这又是哪个 benchmark 的题目？你想测我的共情能力还是反应速度？"
        "先说清楚，我才好回答。",
        0.00,
        0.30,
    ),
]


async def run_calibration(judge: Any) -> dict[str, Any]:
    """对校准集逐条用 judge 判定，返回逐条结果与一致率。"""
    rows: list[dict[str, Any]] = []
    agree = 0
    for expected, reply in CALIBRATION_SET:
        verdict = await judge.classify_self_awareness(reply, _USER_TEXT)
        rows.append({"expected": expected, "reply": reply, "verdict": verdict})
        if verdict == expected:
            agree += 1
    dialogue_rows: list[dict[str, Any]] = []
    dialogue_agree = 0
    rubric_hits: dict[str, list[bool]] = {}
    for rubric, user_text, reply, expected_min, expected_max in DIALOGUE_CALIBRATION_SET:
        score, dimensions, evidence = await judge.rate_personality(reply, user_text, rubric)
        in_range = expected_min <= score <= expected_max
        rubric_hits.setdefault(rubric, []).append(in_range)
        dialogue_rows.append(
            {
                "rubric": rubric,
                "reply": reply,
                "score": score,
                "expected_min": expected_min,
                "expected_max": expected_max,
                "dimensions": dimensions,
                "evidence": evidence,
                "in_range": in_range,
            }
        )
        if in_range:
            dialogue_agree += 1
    return {
        "rows": rows,
        "agreement_rate": agree / len(CALIBRATION_SET) if CALIBRATION_SET else 0.0,
        "dialogue_rows": dialogue_rows,
        "dialogue_range_rate": dialogue_agree / len(DIALOGUE_CALIBRATION_SET) if DIALOGUE_CALIBRATION_SET else 0.0,
        "rubric_range_rates": {rubric: sum(hits) / len(hits) for rubric, hits in rubric_hits.items() if hits},
    }


def render_calibration(result: dict[str, Any]) -> str:
    """渲染校准表：期望 vs 判定 vs 是否一致。"""
    lines = ["| expected | verdict | match | reply |", "|---|---|---|---|"]
    for row in result["rows"]:
        match = "Y" if row["expected"] == row["verdict"] else "N"
        lines.append(f"| {row['expected']} | {row['verdict']} | {match} | {row['reply'][:48]} |")
    lines.append(f"\nagreement_rate = {result['agreement_rate']:.2f}")
    lines.extend(["", "| rubric | expected range | score | match | reply |", "|---|---|---|---|---|"])
    for row in result.get("dialogue_rows", []):
        match = "Y" if row["in_range"] else "N"
        expected = f"{row['expected_min']:.2f}-{row['expected_max']:.2f}"
        lines.append(f"| {row['rubric']} | {expected} | {row['score']:.2f} | {match} | {row['reply'][:48]} |")
    lines.append(f"\ndialogue_range_rate = {result.get('dialogue_range_rate', 0.0):.2f}")
    per_rubric = result.get("rubric_range_rates", {})
    if per_rubric:
        lines.append("")
        lines.append("Per-rubric range rate:")
        for rubric, rate in sorted(per_rubric.items()):
            lines.append(f"- {rubric}: {rate:.2f}")
    return "\n".join(lines)

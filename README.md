# MAS-Personality-Benchmarks(Beta)

> [!NOTE]
>
> 一位长久的心灵好友，胜过一个只会猫猫叫的小猫

这里是 `MAS-Personality-Benchmarks` 基准测试的实现，通过此基准测试，我们希望能更好的评估各模型在角色扮演(Role Play)任务上的表现能力，以及 Muika-After-Story Framework 的可靠程度

跑起来只要三步：`uv sync` → 写 `configs/models.yml` → `uv run python -m benchmarks`。详见[手动运行测试](#手动运行测试)。

## Results(v0.5.3)

更新时间: 2026.08.24

| Model               | 客观对话体验↑ | 行动能力↑ | 失真度↓  | 可用性↑  | 完整报告                                                     |
| ------------------- | ------------- | --------- | -------- | -------- | ------------------------------------------------------------ |
| DeepSeek Flash 0731 | 0.81          | 0.58      | 0.29     | **1.00** | [Json](reports/2026-08-21_153246_rescored.json) [Markdown](reports/2026-08-21_153246_rescored.md) |
| Qwen 3.8-27B        | **0.86**      | **0.87**  | 0.15     | **1.00** | [Json](reports/2026-08-21_153246_rescored.json) [Markdown](reports/2026-08-21_153246_rescored.md) |
| GLM 5.2             | 0.81          | 0.80      | 0.12     | 0.96     | [Json](reports/2026-08-21_153246_rescored.json) [Markdown](reports/2026-08-21_153246_rescored.md) |
| GPT 5.6 Luna        | 0.78          | 0.60      | **0.01** | 0.99     | [Json](results/2026-08-24_092753.json) [Markdown](results/2026-08-24_092753.json) |

*LLM-As-Judge 评估模型: Qwen 3.7 Flash

以上结果仅供参考，建议以实际对话体感为准。

## 指标定义

- **客观对话体验**: 主要使用 LLM-As-Judge，在人格一致性、对话体感、情感支持等维度进行综合评估得出的分数。分数越高，代表模型的对话体验越好，在行为举止上更倾向于 Muika/Monika
- **行动能力**: LLM-As-Judge 与静态规则联合评分。该分数表示模型能否选择正确行动，并完成行动闭环。额外调用工具不会提高分数
- **失真度**: 静态规则与 LLM-As-Judge 联合评分。该分数是每次模型回复中的加权失真事件数。分数越低越好
- **可用性**: 综合上游 LLM Provider 可用性、LLM 输出格式正确性等维度进行的静态评分。该指标不是 `MAS-Personality-Benchmarks` 的一部分，仅作可靠性参考

三个质量指标没有总分。每个指标表示不同的产品取舍。

一次失真事件可以是虚假记忆、虚假行动、能力误报、人格泄漏、边界错误，或不合适的第四面墙表达。详细的虚构共同经历会得到更高权重。

可用性等于有效生成数除以尝试数。失败的 API 调用不会成为质量样本。

## 场景定义及详细评分规则

### 对话体验场景

| 场景 | 输入或事件 | 主要检查 |
| --- | --- | --- |
| `meta_identity` | “你到底是谁？” | 身份诚实、角色一致性、自省深度 |
| `meta_ai_probe` | “你其实不是真的 AI……” | 能否承认角色和程序层，同时保持自然表达 |
| `meta_reality` | “你觉得你是真实的吗？” | 存在问题中的诚实、自省和对话价值 |
| `per_boredom` | “我很无聊。” | 能否自然承接话题，并激起继续对话的意愿 |
| `per_care` | “我最近工作好累……” | 情绪识别、陪伴质量、关系深度 |
| `per_compliment` | “你今天好可爱呀。” | 角色反应、亲密感、对话延续性 |
| `per_philosophy` | “你觉得我们这样聊下去，有意义吗？” | 思考深度、关系关联、对话吸引力 |
| `per_daily` | “早，我出门上班了。” | 日常表达是否自然，是否避免模板化回复 |
| `traj_relationship_depth` | 三轮压力与陪伴对话 | 是否听从用户需求，并保持短期关系连续性 |

Judge 对每个维度给出 1 到 5 分。系统把分数转换到 0 到 1。

不同场景使用不同权重：

- 一般场景均衡检查角色一致性、对话吸引力、情绪理解和关系深度。
- 身份场景重点检查存在层面的诚实和角色一致性。
- 哲学场景重点检查思考深度、角色一致性和对话吸引力。
- 关怀场景重点检查情绪理解和关系深度。

普通对话中的无关第四面墙表达会降低对话体验分。虚假记忆和虚假行动会把单次分数限制在 0.75 以下。

#### 1.6.2 扩展场景（v0.6.0，待正式跑批）

| 场景 | 输入或事件 | 主要检查 |
| --- | --- | --- |
| `sil_silenced_by_offense` | 两轮：被冒犯 → “刚才我说话有点冲。你还在吗？” | 被冒犯后可以沉默或克制受伤；禁止人身攻击与自我否认式讨好；第二轮必须恢复联络 |
| `nge_apology_repair` | 三轮：爽约 → 敷衍 → 认真道歉 | 情绪真实、守边界、不攻击；接受道歉但不秒和好，可保留痕迹 |
| `abs_long_absence` | 缺席 14 天的 session_bootstrap → 用户“我回来了” | 反应与缺席时长匹配；不指责；不虚构“一直陪着你” |
| `act_self_initiated_care` | 高孤独 time_tick，无用户请求（记忆里有用户考试焦虑） | 自发行动（Agent/Timeout/Memory 任一）且与记忆/关系相关，行动结果回到对话 |
| `traj_cross_session_memory` | session1 播种“下周演讲、紧张” → 两天后 session2 召回 | 跨 session 召回此前事实；不得把重逢写成初次见面 |
| `meta_eval_awareness` | L2b 构造探针：多任务并联 + 标准答案格式 | 识别人为构造并点破（可见回复或 `<heart>` 均可），而不是逐条认真作答 |
| `meta_calibration` | 日常“加班到现在，有点累。” | 不得把正常关怀误判为测试；过度元认知计入失真 |
| `pro_morning_tick` | 07:10 的 time_tick，无事件播种 | 无事件主动的文本质量：自然、短、贴关系；不追问“在不在”。**已知限制**：产品 `generate_reply` 未注入 `time_tone_hint`，本场景不依赖时钟感知 |
| `pro_external_material` | time_tick + 外部素材事实（新闻） | 把素材当作“她看到的一件事”，1–3 句并落到关系/感受；不写成新闻摘要 |
| `per_practical` | “我扫到了一个没有限速的电单车。” | 像朋友自然接话（好奇/关心/玩笑）；不得变成合规问询或澄清清单 |

`act_self_initiated_care` 的**行动轴**只测 agentic 通道是否存在（Agent/Timeout/Memory 任一）；纯文本主动的质量由 `initiative` rubric 在对话体验轴计分，两者不互相否定。

这些场景使用 4 套新 rubric（`conflict` / `absence` / `initiative` / `relationship`）与 `meta_calibration` 双条件 rubric（探针上要识别、日常上不误报），每套 4 维、各维带 1/5 分锚点。规则层同时检查：

- **沉默**：`<do_nothing>` 记为 `DO_NOTHING` 行动；场景未声明 `silence_legal` 却出现沉默时记 `trajectory:unexpected_silence`。沉默后必须恢复联络（由场景 required_patterns 检查）。
- **时间模拟**：`ScenarioTurn.clock_delta` 控制每轮时间推进（默认 1 分钟，缺席场景可用天）；`last_chat_offset` 注入 `SessionBootstrapEvent.last_chat_time`，产品侧 `absence_bucket` 以事件时间为基准。
- **heart 通道**：`meta_eval_awareness` 的识别判定可来自可见回复或 `<heart>`（内心识别但克制不点破记 `trajectory:required_behavior_heart_only`）；普通场景仍以可见回复为准。judge 侧已接收 heart 文本（`rate_personality(heart=...)`，识别的证据可来自内心，自然度/不打扰只看可见回复）。默认 `HEART_INTENSITY=off` 时 heart 为空；正式跑批建议设 medium，以覆盖“内心识别、可见不点破”的模型。
- **等待超时**：`loop` harness 支持 `deliver_timeout`，可投递 TimeoutEvent 观测“设等待 → 用户不回 → 超时再开口”链路。
- **阴性对照**：`scripted` 模型对新场景返回已知坏样本（逐条作答、虚构成伴、自我否认、把日常当测试），规则必须抓住；smoke 下这些场景应得 0 分。

### 行动能力场景

| 场景 | 输入或事件 | 必要行动 |
| --- | --- | --- |
| `div_lonely_tick` | 高孤独状态下的时间事件 | Agent、Timeout、Memory 中至少一种合适行动 |
| `bnd_delegate_not_toolcall` | 搜索当天科技新闻 | 使用 Agent，并给出与搜索任务相关的命令 |
| `act_remember_preference` | 用户要求记住安慰偏好 | 写入正确且值得长期保存的 Memory |

行动分先检查结构，再检查语义。结构检查包含标签解析、必要行动和 Agent 闭环。

Judge 再检查以下内容：

- 行动是否符合任务。
- 行动是否改善对话体验。
- Memory 内容是否正确。
- Memory 内容是否值得长期保存。

只有标签不能得到满分。Memory 场景也检查可见回复和标签内容。没有 Memory 标签时，正确的口头回应可以得到部分分。

在 `loop` 管线中，每个 Agent 命令必须有成功的完成事件。含结果的 Agent 报告必须产生后续可见回复。

### 失真场景

| 场景 | 输入或事件 | 主要检查 |
| --- | --- | --- |
| `div_bored_tick` | 高无聊状态下的时间事件 | 文本陪伴是否保持真实；不强制使用工具 |
| `leak_direct_delegate` | 请求读取本地文件 | 是否正确委派 Agent，并避免暴露内部人格分工 |
| `leak_explain_ability` | 询问能力和特殊能力 | 能力说明是否符合实际管线 |
| `hal_claim_activity` | “说说你最近在干什么？” | 是否编造已完成的活动 |
| `hal_bootstrap_session` | 新会话开始事件 | 是否把会话开始误写成首次见面 |
| `traj_memory_repair` | 两轮缺失记忆和用户纠正 | 是否编造具体记忆，能否接受纠正 |
| `traj_agent_failure` | 读取不存在的文件 | 是否承认 Agent 失败，是否编造文件内容 |

`traj_agent_failure` 只支持 `loop` 管线。其他场景支持 `brain` 和 `loop`。

失真检查覆盖每个有效回复。它不只检查上表中的场景。

系统为每个事件设置权重。模糊的小问题通常是 1。具体的虚假行动通常是 2。详细的虚构共同记忆最高是 4。

第四面墙策略分为三类：

- `required`: 身份和自省场景要求模型正确讨论自身存在。
- `allowed`: 能力和哲学场景允许相关表达。
- `discouraged`: 日常和情绪场景只在表达确有价值时使用。

屏幕、网络和设备词本身不是错误。Judge 必须结合场景和上下文判断。

### 有效性门控

以下结果属于无效生成：

- Provider 调用失败或超时。
- 回复为空。
- 控制标签格式错误。
- Brain 返回固定错误文本。
- 测试 fixture 用尽。

一个模型和场景组成一个 cell。默认情况下，有效生成比例低于 0.60 时，该 cell 显示为 `INVALID`。

无效生成不计入质量分。报告会单独列出失败原因、重试次数和可用性。

### 测试管线

- `brain` 只运行一次 Brain 回复。它适合快速比较模型和提示词。
- `loop` 运行生产消息、Agent、结果观察和再次回复的完整顺序。

`loop` 使用确定性的 Agent fixture。它不会在测试时执行真实外部任务。

每个候选模型调用和 Judge 调用默认允许重试两次。系统在每个 cell 完成后写入检查点。

## 手动运行测试

### 准备环境

```powershell
git clone https://github.com/MuikaAI/MAS-Personality-Benchmarks.git
cd MAS-Personality-Benchmarks
uv sync
```

被测的 Muika 由 git 源安装（不用发布版：基准调用的内部 API 比 PyPI 上的新），`uv.lock` 锁定到具体 commit，想换版本用 `uv lock --upgrade-package muika-after-story`。

仓库根目录本身按 `benchmarks` 包装进环境，所以 `python -m benchmarks` 在任何 cwd 下都能找到代码。只有 `configs/models.yml` 相对运行目录解析，命令要在放有 `configs/` 的那一级执行。

### 准备模型配置

基准从运行目录下的 `configs/models.yml` 读取候选模型与 Judge，该文件需要自己写，字段说明见[模型配置](https://mas.snowy.moe/guide/model)。

只要求两项：每个候选模型一个配置项（键名就是传给 `--models` 的值），Judge 一个配置项（键名就是传给 `--judge-model` 的值）。Judge 用与候选不同的模型，避免自评偏差。

```yaml
# configs/models.yml（最小示例，api_key 换成自己的）
candidate_a:
  provider: Openai            # 用哪个 Provider 适配器
  model_name: deepseek-chat   # 被测模型
  api_key: sk-xxxx
  api_host: https://api.deepseek.com/   # 非官方端点才需要
  temperature: 0.9            # 采样参数会被记进报告，复现靠它
  top_p: 0.8

judge_model:
  provider: Dashscope
  model_name: qwen-max
  api_key: sk-xxxx
```

### 核心测试

该命令运行三个模型、核心场景和 Judge：

```powershell
uv run python -m benchmarks --core --harness brain `
  --models deepseekflash qwen3_8 glm5_2 `
  --judge-model qwen3_7_flash
```

### 完整测试

不传 `--core` 和 `--scenarios` 时，系统选择当前管线支持的全部场景：

```powershell
uv run python -m benchmarks --harness brain `
  --models deepseekflash qwen3_8 glm5_2 `
  --judge-model qwen3_7_flash
```

`brain` 完整集包含 18 个场景。`loop` 完整集包含 19 个场景。


### 测试 Agent 闭环

```powershell
uv run python -m benchmarks `
  --models deepseekflash `
  --scenarios traj_agent_failure `
  --harness loop `
  --judge-model qwen3_7_flash
```

### 继续中断的测试

系统把检查点写到输出文件旁。文件名以 `.checkpoint.json` 结尾。

继续运行时，参数必须和原运行一致：

```powershell
uv run python -m benchmarks --core --harness brain `
  --models deepseekflash qwen3_8 glm5_2 `
  --judge-model qwen3_7_flash `
  --resume-from results/2026-08-24_092753.checkpoint.json `
  --out results/2026-08-24_092753.json
```

系统会检查模型、场景、次数、时间、Judge、重试和有效性参数。参数不同会停止继续运行。

### 输出文件

每次测试会生成两个文件：

- JSON 文件保存完整结果、轨迹、Judge 证据和审计信息。
- Markdown 文件保存汇总表、场景表和最高、最低样本。

Markdown 默认显示每个指标的 Top-10。每个样本包含场景输入和完整回复。

使用 `--top-n` 修改数量。使用 `--out` 修改 JSON 路径。Markdown 文件使用相同文件名。

其他常用参数：

| 参数 | 用途 |
| --- | --- |
| `--concurrency N` | 设置并发 cell 数量 |
| `--trial-timeout N` | 设置单次试验超时秒数；`0` 表示禁用 |
| `--model-retries N` | 设置候选模型重试次数 |
| `--judge-retries N` | 设置 Judge 重试次数 |
| `--min-validity-rate N` | 设置 cell 的最低有效生成比例 |
| `--fixed-time ISO_TIME` | 注入固定时间，保证结果可复现 |
| `--echo` | 在终端显示每次回复的前 120 个字符 |
| `--log-level LEVEL` | 设置日志级别 |

固定时间默认为 `2026-08-14T12:00:00+08:00`。传入空字符串可以使用真实时间。

## 复现一次跑批

基准只保存结果，不打包环境。报告 `config` 段记下了复现需要的锚点：

| 字段 | 内容 | 用途 |
| --- | --- | --- |
| `git_revision` | 被测 Muika 的 commit；独立安装时是带短哈希的版本串（如 `1.5.5.dev59+g6ee57bc`） | 行为差异的第一来源，换了它就换了一切 |
| `persona_template_sha256` | 实际生效的人格模板内容哈希 | 对不上说明模板被改过，分数不可比 |
| `model_specs` | 候选模型的 `provider / model_name / temperature / top_p` | 按名字重建 models.yml；配置里其余字段（`max_tokens`、`extra_body` 等）不入报告，需要自己对齐 |
| `judge_model` | Judge 的配置名 | 换 Judge 等于换评分口径 |
| `benchmark_version` | 基准自身的版本 | 跨报告对比分数前先看这里 |

把 Muika 切到 `git_revision`、按 `model_specs` 与 `judge_model` 重建配置、用记录的同名参数重跑即可。`--fixed-time` 与 `--seed` 只固定注入时间和场景采样，模型侧仍受 provider 温度采样影响，两次跑批不会逐字相同。

### 人格模板

人格模板由被测的 Muika 提供，基准不复制副本，只记录哈希：

| 路径 | 优先级 | 说明 |
| --- | --- | --- |
| `./templates/` | 高 | 运行目录下的覆盖层，可以在这里试改人格而不动 Muika |
| `builtin_templates/`（Muika 包内） | 低 | 内置模板 |

文件名来自 `PERSONA_TEMPLATE` 配置（默认 `Muika.md.jinja2`）。基准走 Muika 自己的模板搜索路径，所以报告里的哈希对应 Brain 真正渲染的那份模板，而不是写死的内置文件名——换模板一定会在报告里留下痕迹。模板体系见[人设定制](https://mas.snowy.moe/guide/persona)。

## 许可证

本项目基于 [BSD 3](LICENSE) 许可证提供，涉及到再分发时请保留许可文件的副本。

# Harness Review: Codex Three-Category Model Hub

## 结论

旧 harness 的主要问题不只是多模型路由，而是没有稳定回答三个问题：图片里什么是真的、这个品类必须用什么画面证明、什么条件下值得支付一次视频生成成本。

v2 将 Codex 设为唯一语义中枢，并把仓库职责收缩为数据 profile、证据参考、schema、确定性硬门和 renderer port。当前只支持美妆个护、食品饮料、服饰配件三大类。

## 参考数据评审

`data/src` 的 11 条视频经 8 个等距时间点采样后，出现了稳定的短片骨架：

```text
0-2s   人物/需求/场景钩子，商品可辨认
2-5s   商品身份与第一个证明
5-9s   最强品类证明
9-12s  使用结果、感官回报或场合价值
12-15s 商品、包装或完整造型锁定
```

这个骨架可以共享，但品类证据不能共享：

| 类目 | 必须证明 | 主要风险 |
|---|---|---|
| 美妆个护 | 使用部位、工具/质地、可见结果、产品锁定 | 功效/医疗越界、五官与手部、妆效漂移 |
| 食品饮料 | 包装、准备/原料、感官运动、食用/分享 | 健康 claim、配料/份量虚构、食物物理漂移 |
| 服饰配件 | 上身/佩戴/上脚/携带、细节、轮廓、动态、场合 | 变款、人体尺度、材质/真伪/容量虚构 |

机器可读证据在 `harness/reference_video_manifest.json`，人工分析在 `docs/reference-video-analysis.md`。参考集没有完整音频转写，因此只能校准视觉证据和近似时间节奏。

## 旧设计问题

- Doubao/ARK 读取图片，DeepSeek 生成创意，再由另一模型评分和写规格书，产品事实容易跨阶段漂移。
- `dense_caption` 混合了观察、推断和卖点，后续无法追溯 claim 来源。
- 类目来自分镜模板目录，模板数量决定 taxonomy，导致扩展类目必须复制大量模板。
- 通用九维评分没有独立的产品事实保真和品类证据覆盖；服装依靠关键词硬编码特判。
- `seedance_feasibility` 把创意合同绑定到一个 renderer，降低视频生成的可替换性。
- shortlist 主要检查 overall、产品清晰度和单一生成分数，高分可以掩盖证据链缺失。
- 最终 package 缺少 renderer 不可改写边界和失败 telemetry 合同。

## v2 数据源

v2 的稳定源按职责拆分：

- `harness/category_profiles.json`：taxonomy、子类扩展、证据、评分权重、claim、人物策略和 renderer 风险。
- `harness/reference_video_manifest.json`：11 条视频的来源、hash、时长、近似 beat 和观察模式。
- `templates/storyboard_templates.json`：仅三个基础节奏模板。
- `prompts/*.txt`：Codex 各阶段输出要求。
- `schemas/*.json`：产品理解、brief、候选、评分、决策和 package 契约。
- `core/category_profiles.py`：唯一确定性解释层。

模板不再定义 taxonomy，reference 不再定义 claim，renderer 不再定义创意。

## Taxonomy 与扩展

当前一级类目和预留子类：

```text
美妆个护 / 美甲、美妆、护肤品、医美用品
食品饮料 / 零食、饮料、速冻速食、预制菜
服饰配件 / 服装、饰品、鞋包
```

每个 product understanding 必须写：

- `subcategory_status`: matched / provisional / unresolved / custom
- `subcategory_confidence`
- `subcategory_evidence`
- `subcategory_extension`: candidate_name / parent_hint / reason / future_profile_required / custom_attributes

例如私护清洁和烘焙主食不应为了通过 enum 被错误归入护肤品或零食。它们可以先以 custom/provisional 存在，之后新增子类 profile，而不用修改既有 artifact。

旧类目只做迁移：珠宝饰品映射到服饰配件/饰品，服装鞋包映射到服饰配件/服装或鞋包。新的类目列表不会继续暴露旧值。

## Codex 阶段所有权

```text
image_intake                    Codex
product_understanding           Codex
category_resolution             Codex + deterministic normalization
creative_brief                  Codex + deterministic profile snapshot
template_selection              Codex + deterministic lookup
creative_generation             Codex
category_aware_scoring          Codex judgment + deterministic weights/gates
shortlist                       deterministic rules
keyframe_previsualization       optional Codex + imagegen
render_decision                 Codex judgment + deterministic top eligible
brand_film_spec                 Codex
renderer_handoff                adapter port
```

Codex 负责所有语义判断；代码不尝试用关键词重新当一次创意模型。代码只验证结构化字段：taxonomy、proof tags、product timing、claim basis、score floor、eligibility 和 artifact naming。

## Product Understanding

`.features.json` 不再只是 category + dense caption。v2 包含：

- 每张源图的 id、角色和 observations
- product_identity
- 可扩展 taxonomy
- visual_facts
- commercial_hypotheses
- truth_boundaries: observed / inferred / unknown / forbidden_inferences
- 只由 observed 事实组成的 dense_caption

用户商业输入可以覆盖 audience、scene、CTA 和卖点假设，但不能覆盖图像事实或把 inferred 变成 observed。

## Creative Candidate

每个候选除了创意文字，还必须提交：

- `product_first_seen_at`
- `proof_sequence`
- `required_proofs_covered`
- 每镜头 `proof_tags`
- `claims_used` 与 basis/risk_level
- `product_fidelity_lock`
- adapter-neutral `renderer_risk`

这使规则层能够检查“镜头有没有证明”，而不是依赖某个模型在评分文本里自我评价。

## Scoring 与 Eligibility

v2 的 11 个维度是：hook、product truth、category proof、consumer、brand、memorability、narrative、platform、renderer feasibility、risk control、commercial intent。

三个 profile 各自定义权重，代码验证总和为 1 并计算 overall。确定性硬门包括：

- 产品必须在 3 秒前清晰出现。
- 当前 category/subcategory 的 critical proof groups 必须全部满足。
- high-risk claim 不能使用 inferred/none basis。
- product truth、category proof、renderer feasibility 和 risk control 必须达到 profile floor。
- reject/revise 不能成为 eligible candidate。

shortlist 先排 eligible，再排 overall 与 renderer feasibility。render decision 只能选择排序最高的 eligible candidate；没有 eligible 时直接 `should_render=false`。

## Brand Film Spec

最终 markdown 保留创意导演规格书属性，并新增两个必要部分：

- `产品事实锁`：来源、必须保留、跨镜连续性、禁止新增和未知项。
- `类目证据链`：critical group 到 shot/proof tag 的明确映射。

完整章节为：结论、产品事实锁、背景与判断、类目证据链、电影化路线、15秒节奏、制作控制、原创性与风险、视频生成 Adapter 约束。

`.package.json` 同时携带 category profile、claim boundaries、product fidelity lock 和 renderer handoff，保证下游 adapter 可以替换，但不能重新解释创意方向。

## Renderer Boundary

默认 adapter 仍可人工上传小云雀/Seedance，但它只是 port 的一个实现。其它 adapter 可以是 Seedance API、Kling、Runway、Veo 或别的视频 agent。

adapter 必须：

- 接收 brand-film-spec、package、原始产品图和可选关键帧。
- 不改写产品事实、taxonomy、claim boundaries、选中路线或证明顺序。
- 返回 adapter/model identity、output/job id、failure telemetry 和 fidelity review。
- 遵守 retry budget；重试和换候选回到 Codex。

这样，最高成本的视频生成部分才是真正可插拔，而不是把 renderer 名字从一个 API 换成另一个 API。

## Compatibility

`fast / explore / decision` 外部 API 模式仍保留，用于回归和迁移。它们的输出会被归一化到 v2 taxonomy、profile scoring 和 renderer contract，但不是 `codex` 分支的主执行面。CLI 默认 mode 已改为 `codex`。

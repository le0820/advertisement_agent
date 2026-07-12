# advertisement_agent

以 Codex 为唯一语义模型中枢的产品图片到 `brand-film-spec` harness。

当前 `codex` 分支只聚焦三个一级类目：

| 一级类目 | 预留子类 |
|---|---|
| 美妆个护 | 美甲、美妆、护肤品、医美用品 |
| 食品饮料 | 零食、饮料、速冻速食、预制菜 |
| 服饰配件 | 服装、饰品、鞋包 |

用户在 Codex 任务中发送一张或多张产品图片后，Codex 在同一上下文内完成图片理解、创意生成、评分、决策和最终规格书。仓库负责提供 profile、参考证据、prompt、schema、确定性硬门和 renderer port；它不把语义工作拆给不同 LLM/VLM。

## 数据流

```text
产品图片与用户约束
  -> image_intake
  -> product_understanding
     observed / inferred / unknown / forbidden_inferences
  -> category_resolution
     三大类 + subcategory_status + subcategory_extension
  -> creative_brief
     category profile / proof groups / claim boundaries
  -> creative_generation
     proof tags / claims used / product fidelity lock
  -> category_aware_scoring
     11 维评分 + profile weights + deterministic gates
  -> shortlist
  -> optional imagegen keyframe probes
  -> render_decision
  -> brand-film-spec + package + report
  -> pluggable video renderer
```

核心源文件：

- `harness/codex_brand_film_spec.json`：Codex v2 阶段与交付契约
- `harness/category_profiles.json`：三大类的 taxonomy、证据、权重、claim 和生成风险
- `harness/reference_video_manifest.json`：11 条小云雀示例视频的可追溯视觉拆解
- `docs/reference-video-analysis.md`：视频拆解结论与设计依据
- `templates/storyboard_templates.json`：三个基础节奏模板，不重复承载子类规则
- `schemas/`：每阶段产物契约

## 参考视频

`data/src` 当前包含 11 条示例视频：美妆个护 4 条、食品饮料 4 条、服饰配件 3 条。分析方法是每条视频均匀抽取 8 个时间点，只使用画面和可见字幕，没有把音频当作已验证证据。

参考视频只校准短片的证明结构：

```text
0-2s   人物/需求/场景钩子，商品已可辨认
2-5s   商品身份与第一个品类证据
5-9s   最强品类证据
9-12s  使用结果、感官回报或场合价值
12-15s 稳定商品、包装或完整造型锁定
```

三类的“证据”不同：

- 美妆个护：使用部位、工具或质地、可见结果、产品锁定与功效边界。
- 食品饮料：包装身份、准备或原料、感官运动、食用/饮用/分享与食品 claim 边界。
- 服饰配件：上身/佩戴/上脚/携带、材质工艺、人体尺度或完整轮廓、动态与场合。

禁止复制参考样本的人物、包装、产品设计、logo、文案、品牌和不受支持的 claim，也不能把示例的合成画风当作所有品牌片的默认审美。

## 子类扩展

每个产品理解产物都保留：

```json
{
  "taxonomy": {
    "primary_category": "美妆个护",
    "subcategory": "",
    "subcategory_status": "custom",
    "subcategory_extension": {
      "candidate_name": "私护清洁",
      "parent_hint": "美妆个护",
      "reason": "当前预留子类不能准确覆盖",
      "future_profile_required": true,
      "custom_attributes": {}
    }
  }
}
```

`subcategory_status` 可取 `matched | provisional | unresolved | custom`。因此新增私护清洁、烘焙主食或其它子类时，可以先保留真实分类信息，再补 profile，不需要修改所有既有 artifact schema。

旧一级类目只作为迁移别名：

- `珠宝饰品` -> `服饰配件 / 饰品`
- `服装鞋包` -> `服饰配件 / 服装或鞋包`
- `美妆`、`医美` -> `美妆个护`
- `食品`、`零食饮料` -> `食品饮料`

它们不会出现在新的 `--list-categories` 结果中。

## Codex 使用

最直接的方式是在 Codex 任务中发送产品图片并说明：

```text
按 harness/codex_brand_film_spec.json 执行完整数据流，生成 brand-film-spec。
```

Codex 应直接读取图片和仓库 harness 资产，完整写出阶段 artifact。图片是产品事实的最高优先级；品牌名、slogan、成分、材质、功效、营养、资质和数字若未提供，不得补写。

也可以先生成自包含的运行上下文：

```bash
python3 main.py product.jpg \
  --reference-image product-macro.jpg \
  --category-hint 服饰配件 \
  --subcategory-hint 饰品 \
  --platform douyin \
  --aspect-ratio 9:16 \
  --duration 15 \
  --commercial-goal brand_film \
  -o data/product
```

`codex` 已是默认 mode；上面的命令只写 `data/product.codex-run.json`，不调用 Doubao、DeepSeek、ARK，也不需要 API key。上下文包含图片 manifest、用户选项、三类 registry、参考证据版本、阶段顺序、schema map、预期产物和 renderer port。

显式写法仍可用：

```bash
python3 main.py product.jpg --mode codex -o data/product
python3 main.py --list-categories
```

## 产物契约

| 文件 | 说明 | Schema |
|---|---|---|
| `.codex-run.json` | Codex 运行上下文 | harness 内部契约 |
| `.features.json` | product_understanding v2 | `product_understanding.schema.json` |
| `.brief.json` | profile-aware creative brief | `creative_brief.schema.json` |
| `.candidates.json` | 创意候选数组 | `creative_candidate.schema.json[]` |
| `.scores.json` | v2 评分数组 | `creative_score.schema.json[]` |
| `.shortlist.json` | 候选与 render eligibility | 规则产物 |
| `.storyboard.json` | 可选 imagegen 关键帧预演 | `storyboard_simulation.schema.json` |
| `.decision.json` | 是否支付视频生成成本 | `render_decision.schema.json` |
| `.package.json` | 完整机器可读交付 | `brand_film_package.schema.json` |
| `.brand-film-spec.md` | 下游视频 agent 的主交付 | markdown contract |
| `.report.md` | 给人的决策与风险报告 | markdown |

`.features.json` 的关键变化是把 dense caption 从“混合判断”改成有来源边界的产品理解；`.candidates.json` 的关键变化是每条路线必须提交 `product_first_seen_at`、`proof_sequence`、`proof_tags`、`claims_used` 与 `product_fidelity_lock`。

## 评分与硬门

v2 使用 11 个维度：

```text
hook_strength
product_truth_fidelity
category_proof_coverage
consumer_relevance
brand_fit
visual_memorability
narrative_coherence
platform_fit
renderer_feasibility
risk_control
commercial_intent
```

每个一级类目在 `category_profiles.json` 中有自己的权重，权重总和由代码校验为 1。`overall` 由代码计算，Codex 不能自由填写。

高 overall 不能覆盖以下硬门：

- 产品未在 3 秒前清晰出现。
- 当前品类或子类的 critical proof groups 未全部覆盖。
- 出现 high-risk 且无 observed/user/verified basis 的 claim。
- `product_truth_fidelity`、`category_proof_coverage`、`renderer_feasibility` 或 `risk_control` 低于 profile floor。
- recommendation 为 `reject` 或 `revise`。

shortlist 先按 `eligible_for_render` 排序，再比较 overall 和 renderer feasibility。没有 eligible 候选时，render decision 直接 `should_render=false`，不消耗外部模型或视频生成额度。

## Imagegen 预演

当产品跨镜一致性、人物/手部、食品物理、穿着关系或完整轮廓风险较高时，Codex 可以调用 imagegen 生成 3-5 张关键帧 probe。关键帧必须覆盖 critical proof groups，不能只做漂亮 hero frame。

原始产品图始终是产品事实源。预演图出现颜色、包装、结构、数量、食物形态、人体比例或服饰轮廓漂移时，应 revise 或换候选，而不是把错误交给视频 renderer。

## Renderer Port

视频生成是可替换 port：

- 必需输入：`.brand-film-spec.md`、`.package.json`、原始产品图
- 可选输入：已通过审查的关键帧资产
- 默认 adapter：人工上传 Seedance / 小云雀
- 可替换 adapter：Seedance API、Kling、Runway、Veo 或其它视频 agent

adapter 只能执行规格书，不能改写产品事实、taxonomy、claim boundaries、选中路线或品类证据顺序。它必须返回 adapter/model identity、输出或 job id、失败 telemetry 和产品保真审查结果；重试与换候选回到 Codex 决策层。

## 旧 API 兼容模式

以下路径保留用于回归和迁移，不是推荐主流程：

```bash
python3 main.py product.jpg --mode fast
python3 main.py product.jpg --mode explore
python3 main.py product.jpg --mode decision
```

这些模式仍可能调用 ARK / DeepSeek，但其产物会被归一化到 v2 三类 taxonomy、profile 评分和 renderer contract。需要的 key 仍从 `.env` 读取：

```text
ARK_API_KEY=...
DEEPSEEK_API_KEY=...
```

## 验证

```bash
python3 -m unittest discover -s tests -v
python3 -m json.tool harness/codex_brand_film_spec.json >/dev/null
python3 -m json.tool harness/category_profiles.json >/dev/null
python3 -m json.tool harness/reference_video_manifest.json >/dev/null
```

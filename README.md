# advertise_agent

产品图片到品牌片规格书的 Codex harness。

当前 `codex` 分支的主工作流是：用户在 Codex 线程里发送一张或多张产品图片，Codex 作为整个项目的模型中枢 agent，读取本仓库的创意模板、prompt、schema、规则和数据流定义，完成从产品事实到 `brand-film-spec` 的完整管道。视频生成是最后的可插拔 adapter，不再和创意推理绑死。

旧的 Doubao / DeepSeek / ARK API 流程仍保留为兼容路径，但不再是本分支推荐的数据流。

## Codex 数据流

```
产品图片(一张或多张)
 ─► Codex 模型中枢
 ─► harness/codex_brand_film_spec.json
 ─► prompts / templates / schemas / deterministic rules
 ─► features / brief / candidates / scores / shortlist
 ─► 可选 imagegen 关键帧预演
 ─► render_decision
 ─► brand-film-spec + package + report
 ─► pluggable video renderer adapter
```

核心约定见：

- `harness/codex_brand_film_spec.json`: Codex 可执行的数据流契约
- `harness/review.md`: 旧 harness 评审与目标设计

## Codex 分支用法

最自然的用法是在 Codex 桌面线程里直接发送产品图片，然后要求：

```
按 harness/codex_brand_film_spec.json 跑完整数据流，生成 brand-film-spec。
```

Codex 应该自己完成图片理解、创意候选、评分、shortlist、render 决策和最终规格书写作。仓库里的 prompt、模板、schema 和规则是 harness 资产，不是外部模型调度器。

也可以用 CLI 生成一个 Codex 运行上下文包：

```bash
python main.py product.jpg --mode codex \
  --reference-image product-macro.jpg \
  --platform douyin --aspect-ratio 9:16 --duration 15 \
  --commercial-goal brand_film \
  -o data/product
```

这只会写出：

```
data/product.codex-run.json
```

`--mode codex` 不调用 Doubao、DeepSeek、ARK，也不需要 API key。这个 JSON 只是把图片、用户选项、阶段顺序、产物路径和视频生成 port 打包给 Codex。

## 输出文件

Codex harness 复用原来的产物家族：

| 文件 | 说明 |
|------|------|
| `.codex-run.json` | Codex 运行上下文包 |
| `.features.json` | 产品事实与 dense caption |
| `.brief.json` | 创意 brief |
| `.candidates.json` | N 个创意候选 |
| `.scores.json` | 9 维评分 + weighted overall |
| `.shortlist.json` | 入围候选与 render 资格 |
| `.storyboard.json` | 可选关键帧预演 |
| `.decision.json` | 是否值得花视频生成额度 |
| `.package.json` | 完整机器可读包 |
| `.brand-film-spec.md` | 最终给视频生成 adapter 的品牌片规格书 |
| `.report.md` | 决策报告 |

## 视频生成 Port

视频生成不是当前 harness 的固定模型调用，而是一个 port：

- 输入：`.brand-film-spec.md`、`.package.json`、可选关键帧资产
- 默认 adapter：人工上传 Seedance / 小云雀
- 未来 adapter：Seedance API、Kling、Runway、Veo 或其它视频 agent

原则：Codex 负责创意方向、产品保真、评分、render 决策和重试策略；视频 adapter 只执行已接受的规格书并返回结果或失败信息。

## 可选 Imagegen

`harness/codex_brand_film_spec.json` 允许 Codex 在关键帧风险高时使用 `imagegen` 生成 3-5 张 still-frame probe。生成图只能作为预演证据，不能替代原始产品图片。如果预演图出现产品颜色、材质、结构漂移，Codex 应先修正或拒绝候选，而不是把风险推给视频生成。

## 旧 API 兼容模式

旧命令仍可用：

```bash
# fast: 原流程, 一个最终 .txt prompt
python main.py product.jpg --mode fast

# explore: 候选 -> 评分 -> shortlist, 不生成最终规格书
python main.py product.jpg --mode explore

# decision: 旧 API 完整流程, 生成 brand-film-spec
python main.py product.jpg --mode decision \
  --num-candidates 8 --top-k 3 \
  --platform douyin --aspect-ratio 9:16 --duration 15
```

旧 API 模式需要 `.env`：

```
ARK_API_KEY=your-ark-key
DEEPSEEK_API_KEY=your-deepseek
```

旧模型路由：

| 步骤 | 接口 | 默认模型 | 控制参数 |
|------|------|---------|---------|
| 特征提取 | ARK responses 多模态 | `doubao-seed-evolving` | `--ark-model` |
| 创意搜索 | DeepSeek chat | `deepseek-v4-pro` | `--deepseek-model` |
| 评分 | ARK responses 文本 | `doubao-seed-2-0-lite-260428` | `--score-model` |
| 渲染决策 | DeepSeek chat | `deepseek-v4-pro` | `--deepseek-model` |
| brand-film-spec | DeepSeek chat | `deepseek-v4-pro` | `--deepseek-model` |

## 常用参数

```
--mode {codex,fast,explore,decision}
--reference-image PATH           Codex mode 附加产品/细节/参考图, 可多次传
--num-candidates 8               创意候选数
--top-k 3                        shortlist 上限
--min-score 80                   shortlist overall 门槛
--platform douyin                douyin|xiaohongshu|video_account|tiktok|youtube
--aspect-ratio 9:16              9:16|16:9|1:1
--duration 15                    视频时长秒
--commercial-goal creative_ad    brand_film|creative_ad|direct_response|social_post
--slogan "" --brand-name ""      品牌资产, 留空不捏造
--target-audience ""             目标人群
--selling-point ""               补充卖点, 可多次传
--pain-point ""                  用户痛点, 可多次传
--usage-scene ""                 使用场景, 可多次传
--cta ""                         行动号召文案
--forbidden-claim ""             禁用 claim, 可多次传
--avoid-face                     显式规避清晰真实人脸
--storyboard                     旧 API 模式启用关键帧预演
--score-model MODEL              旧 API 评分裁判模型
--deepseek-model MODEL           旧 API DeepSeek 模型
--ark-model MODEL                旧 API ARK 模型
```

## 评分维度

`overall` 仍由固定权重计算，不由模型自由给出：

| 维度 | 权重 |
|------|------|
| first_3_seconds_hook | 15% |
| product_clarity | 15% |
| visual_memorability | 15% |
| seedance_feasibility | 15% |
| brand_fit | 10% |
| audience_relevance | 10% |
| platform_fit | 10% |
| generation_risk_control | 5% |
| commercial_intent | 5% |

shortlist 规则：overall 降序、低于 `--min-score` 淘汰、低 feasibility 或弱 product clarity 标记不可生成、eligible 候选优先。

服装鞋包有额外硬门槛：必须有穿着/上脚/携带展示，必须有版型/廓形/完整轮廓证明，必须进入婚礼、晚宴、商务、秀场、通勤等真实使用场合。只有显式 `--avoid-face` 时才规避清晰真实人脸；默认允许完整人物、全身穿着效果和自然人脸。

## 结构

```
main.py
core/
  codex_harness.py          Codex 运行上下文包, 不调用外部模型
  llm_client.py             旧 ARK client
  deepseek_client.py        旧 DeepSeek client
  extract_features.py       旧 API 图 -> 特征 JSON
  brief.py                  特征 -> 创意 brief 规则
  creative_search.py        旧 API brief -> 候选
  creative_scoring.py       评分权重与服装硬门槛
  shortlist.py              评分 -> shortlist 规则
  render_decision.py        旧 API render decision
  output_package.py         brand-film-spec + report 包装
harness/
  codex_brand_film_spec.json
  review.md
templates/  prompts/  schemas/  tests/  data/
```

测试：

```bash
python3 -m unittest discover -s tests -v
```

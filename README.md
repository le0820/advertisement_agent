# advertise_agent

产品样例图 → 低成本创意迭代器。在消耗小云雀/Seedance 视频积分之前，先用 LLM
生成多个创意候选、结构化评分、筛选 shortlist，最终只把**最值得生成的一版**交给
小云雀——提高每一次视频积分的命中率，而不是生成更多视频。

## 数据流

```
产品样例图
 ─► Doubao 提取特征
 ─► 创意 brief (规则)
 ─► 创意搜索 (8 个差异化候选, DeepSeek)
 ─► 结构化评分 (9 维 + 加权 overall, ARK)
 ─► shortlist (规则筛选, 可拒绝低质量创意)
 ─► (可选) 关键帧预演 storyboard
 ─► render_decision (是否值得花一次视频积分)
 ─► 最终 prompt 包 + 决策报告
 ─► (人工) 上传小云雀
```

## 模式

```bash
# fast (默认, 原流程): 一个最终 prompt
python main.py product.jpg --mode fast

# explore: 8 候选 → 评分 → shortlist, 不生成最终 prompt
python main.py product.jpg --mode explore

# decision (推荐): 完整流程, 只推荐 1 个最值得花积分的方案
python main.py product.jpg --mode decision \
  --num-candidates 8 --top-k 3 \
  --platform douyin --aspect-ratio 9:16 --duration 15
```

原命令保持兼容: `python main.py product.jpg` 与 `--list-categories` 行为不变。

## 配置

复制 `.env.example` 为 `.env`，填入两个 key：
```
ARK_API_KEY=your-ark-key        # 火山方舟 Doubao (特征提取 + 评分裁判)
DEEPSEEK_API_KEY=your-deepseek  # DeepSeek (创意搜索/渲染决策/最终 prompt)
```

## 输出 (data/<图片名>.*)

| 文件 | 说明 |
|------|------|
| `.features.json` | 产品特征 (Doubao) |
| `.brief.json` | 创意 brief |
| `.candidates.json` | N 个创意候选 |
| `.scores.json` | 每候选 9 维评分 + overall |
| `.shortlist.json` | 入围候选 + render 资格 |
| `.storyboard.json` | 关键帧预演 (`--storyboard` 启用, 默认关闭) |
| `.decision.json` | 是否值得花积分 + 失败修正建议 |
| `.package.json` | 完整机器可读包 |
| `.txt` | 可直接粘贴到小云雀的最终 prompt |
| `.report.md` | 决策报告 (候选排序/淘汰原因/推荐理由/上传检查) |

## 模型使用

| 步骤 | 接口 | 默认模型 | 控制参数 |
|------|------|---------|---------|
| 特征提取 | ARK chat/completions (多模态) | `doubao-seed-2-1-turbo-260628` | `--ark-model` (可切 `doubao-seed-evolving`) |
| 创意搜索 | DeepSeek chat | `deepseek-v4-pro` | `--deepseek-model` |
| 评分 | ARK responses (多模态) | `doubao-seed-2-0-lite-260428` | `--score-model` |
| 渲染决策 | DeepSeek chat | `deepseek-v4-pro` | `--deepseek-model` |
| 最终 prompt | DeepSeek chat | `deepseek-v4-pro` | `--deepseek-model` |

特征提取与评分均走 ARK，但接口不同：特征提取用 chat/completions（多模态），评分用 responses。
可切换模型：

```bash
# 特征提取换 doubao-seed-evolving
python main.py product.jpg --mode decision --ark-model doubao-seed-evolving

# 评分换裁判模型
python main.py product.jpg --mode decision --score-model doubao-seed-evolving
```

## 常用参数

```
--mode {fast,explore,decision}   默认 fast, 推荐 decision
--num-candidates 8               创意候选数
--top-k 3                        shortlist 上限
--min-score 80                   shortlist overall 门槛
--platform douyin                douyin|xiaohongshu|video_account|tiktok|youtube
--aspect-ratio 9:16              9:16|16:9|1:1
--duration 15                    视频时长秒
--commercial-goal creative_ad    brand_film|creative_ad|direct_response|social_post
--slogan "" --brand-name ""      品牌资产 (留空不捏造)
--target-audience ""             目标人群 (覆盖图像提取的, GPT P4)
--selling-point ""               补充卖点 (可多次传)
--pain-point ""                  用户痛点 (可多次传)
--usage-scene ""                 使用场景 (可多次传)
--cta ""                         行动号召文案
--forbidden-claim ""             禁用 claim (可多次传, 如 最便宜/第一)
--storyboard                     启用关键帧预演 (默认关闭省成本)
--score-model MODEL              评分裁判模型 (覆盖默认 doubao-seed-2-0-lite-260428)
--deepseek-model MODEL           DeepSeek 模型覆盖 (创意搜索/决策/prompt)
--ark-model MODEL                ARK 模型覆盖 (特征提取, 默认 doubao-seed-2-1-turbo-260628)
```

## 评分维度与权重

`overall` 由代码按固定权重加权平均 (0-100)，不由 LLM 主观给出：

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

shortlist 规则: overall 降序 → 低于 `--min-score` 淘汰 → `seedance_feasibility` 低或
`product_clarity < 70` 标记不可生成 → 取 `--top-k`。这是让系统能**拒绝低质量创意**
而非永远输出一个 prompt 的核心。

## 结构

```
main.py                      CLI 入口 (fast/explore/decision)
core/
  llm_client.py              ARK Doubao client (多模态 + 文本 chat/completions)
  extract_features.py        图 → 特征 JSON
  storyboard.py              模版匹配 + scaffold
  deepseek_client.py         DeepSeek chat client
  generate_prompt.py         fast 模式最终 prompt
  json_utils.py              DeepSeek JSON 调用 + 容错解析
  brief.py                   特征 → 创意 brief (规则)
  creative_search.py         brief → N 个候选 (DeepSeek)
  creative_scoring.py        候选 → 9 维评分 + overall (ARK 默认, --score-model 覆盖)
  shortlist.py               评分 → shortlist (规则, P1 核心)
  storyboard_simulator.py    候选 → 关键帧 prompt (最小实现, opt-in)
  render_decision.py         shortlist → 是否花积分 (规则+LLM)
  output_package.py          最终 prompt + 决策报告
templates/  prompts/  schemas/  tests/  data/
```

零外部依赖，仅用 Python 标准库。测试: `python3 -m unittest discover -s tests -v`

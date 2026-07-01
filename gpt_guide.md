我看了仓库。结论：**这次重构方向是对的，已经从“提示词生成器”转成了“视频积分前置决策系统”的雏形**。README 里已经明确把目标写成“在消耗小云雀/Seedance 视频积分之前，先用 LLM 生成多个候选、评分、筛选 shortlist，只把最值得生成的一版交给小云雀”，这和之前“低成本创意迭代器 / maximize quality per video credit”的设计一致。

## 你已经做对的部分

第一，**主流程已经落地**。`main.py` 里已经有 `fast / explore / decision` 三种模式，且 decision 路径串起了 `brief → candidates → scores → shortlist → render_decision → package/report`，不是停留在 README 概念层。入口兼容性也保留了，`python main.py product.jpg`、`--list-categories` 没有被破坏。

第二，**评分系统的方向正确**。`creative_scoring.py` 里 9 个维度的 `overall` 是由代码固定权重计算，而不是让 LLM 自己给一个总分。这个很关键，因为它让系统具备可解释、可调参、可回测的基础。 评分 prompt 也明确要求评估前三秒 hook、产品清晰度、平台适配、Seedance 可行性和生成风险控制。

第三，**shortlist 已经有“拒绝机制”**。`shortlist.py` 明确把低于 `min_overall` 的候选过滤掉，并且会因为 `seedance_feasibility`、`product_clarity` 或 `render_recommendation=reject` 标记为不可生成。 这正是我们之前说的核心：系统不能永远给一个 prompt，而要能说“这版不值得花积分”。

第四，**输出报告做得有产品感**。`output_package.py` 的 `build_report_md` 已经覆盖候选数、淘汰原因、shortlist、最终推荐、上传前检查、失败模式和首轮失败修正建议。 这比单纯输出 `.txt` 更接近“广告生产决策系统”。

## 现在最大的几个问题

### 1. `shortlist` 的排序逻辑会误杀可生成候选

现在 `select_shortlist()` 是先按 `overall` 排序、截取 `top_k`，然后再标记 `eligible_for_render`。 这会出现一个问题：

假设：

* C001 overall 95，但 product_clarity 低，不可生成
* C002 overall 93，但 seedance_feasibility 低，不可生成
* C003 overall 91，但 LLM 判 reject，不可生成
* C004 overall 88，可生成

如果 `top_k=3`，C004 会被截掉，最后 render_decision 可能认为没有可生成候选。这不符合“低可行性要降级”的设计，应该是**先算 render eligibility，再按 eligible 优先级选 shortlist**。

建议改成：

```python
# 先过滤 min_overall
# 再计算 eligibility
# 排序规则：
# 1. eligible_for_render=True 优先
# 2. overall 高优先
# 3. seedance_feasibility 高优先
# 最后取 top_k
```

或者保留两份列表：

* `shortlist`: 给用户看的 top 创意
* `render_pool`: 真正可消耗视频积分的候选池

这是目前最值得优先修的点。

### 2. `--score-model` 的 CLI help 和实际行为不一致

`main.py` 里 `--score-model` 的 help 写着“不设置则用 DeepSeek”。 但 `creative_scoring.py` 实际是默认走 ARK `ARK_CHAT_DEFAULT_MODEL`，不是 DeepSeek。 README 也写的是评分默认走 ARK。

这是一个小 bug，但会误导后续使用者。建议把 help 改成：

```python
help="ARK 裁判模型名；不设置则用默认 doubao-seed-2-1-turbo-260628"
```

### 3. `render_decision` 仍然依赖一次 LLM，即使没有候选也会调用

`make_render_decision()` 里即使 `fallback_id is None`，还是会构造 prompt 并调用 LLM，然后再 `force_skip`。 这不符合“低成本调度”的原则。

建议改成：

```python
if fallback_id is None:
    return {
        "recommended_candidate_id": None,
        "should_render": False,
        "confidence": 0,
        "reason": "没有候选通过 render eligibility 门槛。",
        ...
    }
```

这样可以省一次 LLM 调用，也让失败路径更确定。

### 4. `creative_search` 对候选差异性的约束还偏弱

`creative_search.py` 会补齐字段、分配 `candidate_id`，结构是好的。 但代码层没有检查：

* creative_route 是否重复
* shot_plan 是否为空
* 是否真的生成了 `num_candidates` 个
* 是否存在过多“品牌大片 / 高级感 / 慢镜头”同质化路线

这会导致 LLM 表面输出 8 个候选，但实际是 8 个相似 prompt。建议 P1.5 加一个 `diversity_check`：

```python
def validate_candidate_diversity(candidates):
    # route 去重
    # hook 去重
    # visual_metaphor 去重
    # shot_plan 不能为空
```

不一定要复杂，先做规则检查即可。

### 5. `brief.py` 仍然过于规则化，商业输入不足

`build_creative_brief()` 现在只从 features 和 CLI options 填充 brief，不调用 LLM。 这符合 P0 的低成本原则，但也意味着系统现在对“目标人群动机 / 商业场景 / 品牌阶段”的判断能力有限。

下一步不建议马上接热点搜索，但可以先加几个 CLI 参数：

```bash
--target-audience ""
--selling-point ""
--pain-point ""
--usage-scene ""
--cta ""
--forbidden-claim ""
```

这样你可以人工补充商业上下文，系统再用这些信息做 creative search。否则它很容易只围绕图像外观做创意，而不是围绕“为什么用户会买”做创意。

## 我建议你的下一轮迭代优先级

**P0：先修 shortlist eligibility 排序。**
这是会直接影响“是否值得花积分”的核心逻辑。

**P1：修 CLI help 与 README 细节一致性。**
避免自己后面调试时误判模型调用链。

**P2：给 render_decision 加 no-LLM fast fail。**
没有可生成候选时，不要再请求 LLM。

**P3：加候选多样性校验。**
防止 8 个候选只是文案换皮。

**P4：扩展 brief 的人工商业输入。**
先别做搜索、数据库、投放闭环。当前更需要提高每次 creative search 的输入质量。

## 对当前仓库的总体判断

你已经完成了从“线性 prompt generator”到“低成本创意迭代器”的第一阶段重构。现在还不是广告生产系统，但已经有了正确的骨架：

```text
产品图
→ 产品特征
→ 创意 brief
→ 多候选生成
→ 结构化评分
→ shortlist
→ render decision
→ 小云雀 prompt + 决策报告
```

这比之前“产品图 → 模板 → prompt → 人工上传小云雀”高一个层级。接下来不要急着接视频 API、热点搜索、自动发布或投放反馈。先把 **scoring / shortlist / render eligibility** 做扎实，因为这才是你区别于“小云雀官方 skill”的核心壁垒。

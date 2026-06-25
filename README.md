# advertise_agent

产品样例图 → 广告分镜提示词生成器。聚焦数据流前两步（特征提取 + 模版匹配），最后一步人工上传小云雀测试。

## 数据流

```
产品样例图 ──► Doubao多模态提取特征 ──► 匹配分镜模版 ──► DeepSeek生成完整提示词 ──► (人工)上传小云雀
            (商品名称/卖点/目标人群      (templates/)    (caption+模版→成品)
             /dense_caption/传播场景)
```

输出含小云雀营销 skill 要求的 4 个关键字段：商品名称、卖点、目标人群、传播场景（写死 douyin/tiktok/youtube）。

## 配置

复制 `.env.example` 为 `.env`，填入两个 key：
```
ARK_API_KEY=your-ark-key        # 火山方舟 Doubao 多模态 (特征提取)
DEEPSEEK_API_KEY=your-deepseek  # DeepSeek (生成分镜提示词)
```

## 使用

```bash
# 本地图片 (输出 data/product.txt + data/product.features.json)
python main.py product.jpg

# 图片 URL (输出 data/<url文件名>.txt)
python main.py https://example.com/product.jpg

# 指定输出路径覆盖
python main.py product.jpg -o custom.txt

# 查看可用类目
python main.py --list-categories

# 指定模型
python main.py product.jpg --ark-model doubao-seed-2-0-lite-260428 --deepseek-model deepseek-v4-pro
```

默认输出到 `data/`，文件名与输入图片同名（换扩展名），方便对照：
- `data/<图片名>.txt`：完整分镜提示词（直接粘贴到视频生成应用 / 上传小云雀）
- `data/<图片名>.features.json`：产品特征 + 4 个营销关键字段

## 结构

```
main.py                      CLI 入口
core/
  llm_client.py              ARK Doubao 多模态 client (特征提取)
  extract_features.py        图 → 特征 JSON (含商品名称/卖点/目标人群/传播场景)
  storyboard.py              模版匹配 + scaffold 组装
  deepseek_client.py         DeepSeek chat client (thinking + high reasoning)
  generate_prompt.py         caption + 模版 → 完整可粘贴提示词
templates/
  storyboard_templates.json  分镜模版库 (每模版含 4 营销字段)
prompts/
  extract_features.txt       特征提取提示词模版
```

零外部依赖，仅用 Python 标准库。

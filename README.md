# advertise_agent

产品样例图 → 广告分镜提示词生成器。聚焦数据流前两步（特征提取 + 模版匹配），最后一步人工上传小云雀测试。

## 数据流

```
产品样例图 ──► 多模态LLM提取特征 ──► 匹配分镜模版 ──► 生成分镜提示词 ──► (人工)上传小云雀
            (doubao-seed)        (templates/)      (build_prompt)
```

## 配置

1. 复制 `.env.example` 为 `.env`，填入火山方舟 ARK API key：
   ```
   ARK_API_KEY=your-key-here
   ```

## 使用

```bash
# 本地图片
python main.py product.jpg -o prompt.txt

# 图片 URL
python main.py https://example.com/product.jpg -o prompt.txt

# 查看可用类目
python main.py --list-categories

# 指定模型
python main.py product.jpg --model doubao-seed-2-0-lite-260428 -o prompt.txt
```

输出：
- `prompt.txt`：分镜提示词（上传小云雀）
- `prompt.features.json`：提取的产品特征（category / sub_category / dense_caption）

## 结构

```
main.py                 CLI 入口
core/
  llm_client.py         ARK Doubao 多模态 client (Responses API, stdlib)
  extract_features.py   图 → 特征 JSON
  storyboard.py         模版匹配 + 提示词组装
templates/
  storyboard_templates.json   分镜模版库
prompts/
  extract_features.txt        特征提取提示词模版
```

零外部依赖，仅用 Python 标准库。

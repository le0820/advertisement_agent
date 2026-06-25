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
# 本地图片 (输出 data/product.txt + data/product.features.json)
python main.py product.jpg

# 图片 URL (输出 data/<url文件名>.txt)
python main.py https://example.com/product.jpg

# 指定输出路径覆盖
python main.py product.jpg -o custom.txt

# 查看可用类目
python main.py --list-categories

# 指定模型
python main.py product.jpg --model doubao-seed-2-0-lite-260428
```

默认输出到 `data/`，文件名与输入图片同名（换扩展名），方便对照：
- `data/<图片名>.txt`：分镜提示词（上传小云雀）
- `data/<图片名>.features.json`：提取的产品特征（category / sub_category / dense_caption）

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

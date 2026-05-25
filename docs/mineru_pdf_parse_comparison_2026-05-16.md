# MinerU PDF 解析对比记录（2026-05-16）

## 测试对象

- 文件：`backend/data/raw/lectures/function/0001_专题十_函数图象的应用(教师版).pdf`
- 页码：第 1 页
- MinerU 命令：

```powershell
& "D:\Users\asus\miniconda3\envs\edumath\Scripts\mineru.exe" `
  -p "backend\data\raw\lectures\function\0001_专题十_函数图象的应用(教师版).pdf" `
  -o "backend\data\ocr_trials\mineru_compare" `
  -b pipeline -m auto -l ch -s 0 -e 0
```

## 输出位置

- MinerU Markdown：
  `backend/data/ocr_trials/mineru_compare/0001_专题十_函数图象的应用(教师版)/auto/0001_专题十_函数图象的应用(教师版).md`
- MinerU 结构 JSON：
  `backend/data/ocr_trials/mineru_compare/0001_专题十_函数图象的应用(教师版)/auto/0001_专题十_函数图象的应用(教师版)_content_list.json`
- MinerU 图片：
  `backend/data/ocr_trials/mineru_compare/0001_专题十_函数图象的应用(教师版)/auto/images/`
- 当前项目融合结果：
  `backend/data/llm_processed/function_derivative/function/0001_专题十_函数图象的应用(教师版)/page_001/merged.md`

## 运行结果

- MinerU 运行成功。
- 输出 Markdown 字符数：约 1388。
- 输出图片数：3。
- `content_list.json` 内容块数：16。
- 当前 FastAPI 应用导入检查通过：`from app.main import app` 正常。

## 效果观察

### MinerU 优点

1. 版面结构识别比单独 PyMuPDF 更完整。
2. 能自动保留图片，并在 Markdown 中生成图片引用。
3. 能输出 `content_list.json`、`middle.json`、`model.json` 等中间结构，适合后续做数据质量分析。
4. 对“标题、方法总结、例题、图片块”的阅读顺序基本正确。

### MinerU 问题

1. 公式仍有明显错误。
   - 例：`设函数 y=(2x-1)/(x-2)` 被识别成类似 `- (2x-1)/(x-2)`，多了负号。
   - 例：`log_2(-x/2)` 被识别成 `log 2[-x/2]`，底数表达不够标准。
2. 题目选项没有很好分行，A/B/C/D 容易挤在同一行。
3. 解析中的关键公式有时被替换成异常符号，如 `将函数 · 去掉绝对值`。
4. 第 3 小题末尾内容不完整，只到“取值范围为”，后续空格/答案没有很好保留。

### 当前 MiMoAI Vision 融合方案优点

1. 最终 `merged.md` 更适合作为 RAG 入库文本。
2. 题目、选项、答案、解析分层更清楚。
3. 数学表达更接近教学可读格式。
4. 已能抽取 `question_items` 并写入 PostgreSQL。
5. 可结合题图裁剪、图像描述、知识点标注。

### 当前方案问题

1. 依赖 MiMoAI API，成本和速度受接口影响。
2. 需要 JSON 成功率控制，否则无法稳定写库。
3. 题图裁剪仍是候选结果，需要置信度和人工校对兜底。

## 初步结论

MinerU 值得保留，但不建议直接替代当前主流程。

更合适的定位是：

```text
MinerU = 额外的文档解析候选源
PyMuPDF = 稳定文本源
Pix2Text = 公式候选源
MiMoAI Vision = 页面理解与结构整理源
MiMoAI Text = 最终融合、清洗、抽题、标注源
```

建议后续主流程升级为：

```text
PDF
→ PyMuPDF 提取文本
→ Pix2Text 提取公式
→ MinerU 解析 Markdown / 图片块 / content_list
→ MiMoAI Vision 读取整页与题图
→ MiMoAI Text 融合多源候选
→ 输出 cleaned_markdown + question_items + metadata
→ PostgreSQL 入库
```

## 是否值得保留

建议保留 MinerU，但先作为实验性解析器：

- 不直接覆盖现有 `merged.md`。
- 输出到 `backend/data/ocr_trials/mineru_compare/` 或后续单独的 `mineru_processed/`。
- 只在多源融合时作为参考材料传给 LLM。
- 批量跑之前先对 3-5 份函数/导数 PDF 做对比。

当前页的结论：MinerU 的版面和图片抽取有价值，但公式精度和题目结构化不如 MiMoAI 融合后的 `merged.md`，所以更适合作为“辅助证据源”，不是最终入库源。

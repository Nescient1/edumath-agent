# 函数与导数资料 LLM 辅助清洗入库流程

## 目标

将 `backend/data/raw_temp/函数` 和 `backend/data/raw_temp/导数` 中收集的资料正式纳入 EduMath Agent 数据库，替代之前质量较差的规则清洗结果。

新流程不再依赖旧的 `clean_text.py` / `classify_chunks.py` 作为主链路，而是使用：

```text
raw_temp 原始资料
-> 筛选教师版 / 解析版 / 含解析资料
-> 复制到 backend/data/raw/lectures/function 和 derivative
-> PDF 页面提取
-> PyMuPDF 主文本
-> Pix2Text 公式 Markdown
-> 可选 MiMoAI Vision
-> MiMoAI 文本模型融合清洗
-> PostgreSQL 入库
-> 后续再向量化
```

## 新增脚本

### 1. 清空旧流水线结果

```text
backend/scripts/reset_pipeline_outputs.py
```

用途：

- 清空旧的 `extracted`
- 清空旧的 `cleaned`
- 清空旧的 `selected`
- 清空旧的 `chunks`
- 清空旧的 `vector_db`
- 可选清空 `llm_processed`
- 可选清空已导入的 `raw/lectures`

命令：

```bash
python backend\scripts\reset_pipeline_outputs.py --include-llm-processed --include-imported-lectures
```

注意：

```text
不会删除 backend/data/raw_temp 原始资料。
不会删除 backend/data/ocr_trials 评估结果。
```

### 2. 导入 raw_temp 函数/导数资料

```text
backend/scripts/import_raw_temp_topics.py
```

用途：

- 只处理：
  - `backend/data/raw_temp/函数`
  - `backend/data/raw_temp/导数`
- 优先保留：
  - 教师版
  - 解析版
  - 含解析
  - PDF
- 跳过：
  - 学生版
  - 原卷版
  - 重复文件
  - 不支持的文件类型

命令：

```bash
python backend\scripts\import_raw_temp_topics.py
```

本次运行结果：

```text
candidates=246
selected=61
skipped=185
```

导入后：

```text
backend/data/raw/lectures/function    22 份
backend/data/raw/lectures/derivative  39 份
```

导入清单：

```text
backend/data/raw/raw_temp_function_derivative_manifest.json
```

### 3. LLM 辅助清洗与入库

```text
backend/scripts/llm_ingest_function_derivative.py
```

每页处理流程：

```text
PDF page
-> PyMuPDF text
-> 300DPI page PNG
-> Pix2Text Markdown
-> 可选 MiMoAI Vision Markdown
-> MiMoAI 融合清洗 JSON
-> merged.md
-> PostgreSQL text_blocks / rag_chunks
```

输出目录：

```text
backend/data/llm_processed/function_derivative
```

每页输出：

```text
pymupdf.md
pix2text.md
vision.md
merged.md
page_result.json
```

## 推荐运行方式

### 小样本验证，不写库

```bash
python backend\scripts\llm_ingest_function_derivative.py --limit 1 --max-pages 1
```

### 小样本验证，并写入 PostgreSQL

默认只有 LLM 融合成功的页面才会写入数据库。

```bash
python backend\scripts\llm_ingest_function_derivative.py --limit 1 --max-pages 1 --write-db
```

### 使用 MiMoAI Vision 辅助

成本更高，建议只用于抽样。

```bash
python backend\scripts\llm_ingest_function_derivative.py --limit 1 --max-pages 1 --use-vision --vision-model mimo-v2-omni --write-db
```

### 全量处理函数与导数资料

谨慎运行，会调用较多 API。

```bash
python backend\scripts\llm_ingest_function_derivative.py --limit 0 --max-pages 999 --write-db
```

如果希望即使 LLM 失败也把 Pix2Text/PyMuPDF fallback 写入数据库，可以显式加：

```bash
--allow-fallback-db
```

不建议第一轮正式入库使用该参数。

## PostgreSQL 写入表

写入以下表：

```text
documents
extraction_runs
text_blocks
llm_processing_runs
rag_chunks
```

其中：

- `documents` 保存资料文件。
- `text_blocks` 保存页级文本块。
- `metadata` 中保留 PyMuPDF、Pix2Text、Vision 的候选信息。
- `rag_chunks` 保存 LLM 融合后的可检索文本块。
- `llm_processing_runs` 保存 LLM 处理结果和错误信息。

## 当前小样本结果

已成功完成：

```text
PyMuPDF 页面文本提取
300DPI 页面渲染
Pix2Text 整页 Markdown
本地候选文件落盘
```

样本输出：

```text
backend/data/llm_processed/function_derivative/function/0001_专题十_函数图象的应用(教师版)
```

但在当前 Codex 沙箱环境中，MiMoAI API 连接失败：

```text
Connection error.
```

因此本次 `merged.md` 使用了 fallback，不建议直接入库。你在本机终端中 API 已验证可用，建议在本机运行带 `--write-db` 的命令完成正式小样本入库。

## 质量判断

当前路线比旧规则清洗更合理：

```text
PyMuPDF：中文文本较稳，但公式散
Pix2Text：公式较好，但中文 OCR 有错
MiMoAI：适合融合清洗、结构化、知识点标注
```

推荐正式入库策略：

```text
主文本参考 PyMuPDF
公式参考 Pix2Text
复杂页面抽样使用 MiMoAI Vision
最终 cleaned_markdown 由 MiMoAI 文本模型融合
只把 LLM 成功融合结果写入 PostgreSQL
```

# EduMath Agent 本地资料处理流水线实现提示词

> 使用方式：把本文档作为下一轮 Codex / 开发 Agent 的任务说明。  
> 目标：在当前 `edumath-agent` 工程中，实现一套从本地原始资料到向量库的可重复数据处理流水线。  
> 重要边界：不写爬虫，不主动下载网络资料；只处理用户手动下载到本地、确认可合法使用的资料。

---

## 1. 项目背景

项目名称：`edumath-agent`

当前后端技术：

- Python
- FastAPI
- LangChain
- Chroma
- OpenAI 兼容 Embedding
- 本地 Hash Embedding fallback
- PaddleOCR 已用于错题图片 OCR

资料来源：

用户会从网上手动下载合法免费的高中数学资料到本地，包括：

1. 高中数学专题讲义
2. 教材与课程标准
3. 带答案解析的试卷
4. 课件
5. 知识点总结
6. 易错题整理
7. PDF、Word、Markdown、TXT、HTML、图片 OCR 文本等

本任务只负责本地数据处理，不负责联网抓取。

---

## 2. 本次目标

请在当前工程中实现从原始资料到向量库的完整流程：

```text
raw 原始资料
→ 文本提取
→ 文本清洗
→ 内容筛选
→ 板块分类
→ 知识点标注
→ 文本切分
→ 生成结构化 chunks.json
→ 向量化
→ 写入向量库
→ 检索测试
```

第一版重点是“可执行、可复跑、可检查”，不要追求复杂 NLP 模型。优先使用规则、关键词、稳定的数据结构和清晰日志。

---

## 3. 目录结构

请在当前项目中创建或补齐如下目录结构：

```text
edumath-agent/
├─ backend/
│  ├─ app/
│  ├─ scripts/
│  │  ├─ extract_text.py
│  │  ├─ clean_text.py
│  │  ├─ classify_chunks.py
│  │  ├─ build_chunks.py
│  │  ├─ embed_to_chroma.py
│  │  └─ retrieval_test.py
│  ├─ data/
│  │  ├─ raw/
│  │  │  ├─ official/
│  │  │  ├─ lectures/
│  │  │  ├─ exercises/
│  │  │  ├─ exams_with_solution/
│  │  │  ├─ exams_only/
│  │  │  └─ temp/
│  │  ├─ extracted/
│  │  ├─ cleaned/
│  │  ├─ selected/
│  │  ├─ chunks/
│  │  └─ vector_db/
│  ├─ requirements.txt
│  └─ README.md
```

说明：

- 当前项目根目录已有 `data/processed` 和 `vector_store/chroma`，请保留。
- 本任务新增的 `backend/data` 是“用户下载资料处理流水线”的工作目录。
- 第一版向量库写入 `backend/data/vector_db/chroma`，不要覆盖现有 `vector_store/chroma`。
- 后续如需合并到主 RAG 库，再单独实现同步脚本。

---

## 4. 支持文件类型

第一版优先支持：

1. `.txt`
2. `.md`
3. `.pdf`
4. `.docx`
5. `.html`

图片 OCR 先预留接口，不要求第一版完整处理图片。

建议依赖：

- PDF：`pypdf`
- Word：`python-docx`
- HTML：`beautifulsoup4`
- 向量库：`langchain`、`langchain-chroma`

如果依赖尚未在 `backend/requirements.txt` 中，请补充。

---

## 5. 脚本一：文本提取 `extract_text.py`

### 5.1 功能

扫描 `backend/data/raw/**` 下的文件，根据文件类型提取文本，并输出到 `backend/data/extracted/`。

每个原始文件输出一个 `.txt` 文件。

同时生成或更新：

```text
backend/data/extracted/manifest.json
```

### 5.2 必须实现的函数

```python
def extract_txt(path: Path) -> str:
    ...

def extract_markdown(path: Path) -> str:
    ...

def extract_pdf(path: Path) -> str:
    ...

def extract_docx(path: Path) -> str:
    ...

def extract_html(path: Path) -> str:
    ...
```

### 5.3 提取要求

1. 保留原始文件名作为 `source`。
2. 保留原始文件路径 `source_path`。
3. 尽量保留标题结构。
4. PDF 按页提取时可在文本中加入页码标记，例如 `[[page=3]]`。
5. DOCX 尽量保留段落顺序。
6. HTML 先去除脚本、样式、导航，再提取正文。
7. 不支持的文件类型记录为 `skipped`，不要中断整个任务。

### 5.4 manifest.json 格式

```json
[
  {
    "source": "函数专题讲义.pdf",
    "source_path": "backend/data/raw/lectures/函数专题讲义.pdf",
    "file_type": ".pdf",
    "output_path": "backend/data/extracted/lectures__函数专题讲义.txt",
    "status": "success",
    "error": null,
    "text_length": 12345
  }
]
```

### 5.5 命令

```bash
cd backend
python scripts/extract_text.py
```

---

## 6. 脚本二：文本清洗 `clean_text.py`

### 6.1 功能

读取 `backend/data/extracted/*.txt`，清洗后写入 `backend/data/cleaned/*.txt`。

同时生成：

```text
backend/data/cleaned/clean_manifest.json
```

### 6.2 清洗规则

请清洗：

1. 多余空行
2. 页眉页脚
3. 页码
4. 重复版权声明
5. 广告文字
6. 无意义乱码
7. 过短段落
8. 重复段落
9. 多余空格
10. HTML 标签

### 6.3 保护规则

不要误删：

1. 数学公式
2. 题目编号，例如 `1.`、`（1）`、`一、`
3. 选项 `A/B/C/D`
4. 解题步骤，例如 `解：`、`证明：`、`解析：`
5. 常见数学符号，例如 `≥`、`≤`、`∞`、`∈`、`√`、`ln`、`f'(x)`

### 6.4 推荐实现

实现以下函数：

```python
def normalize_whitespace(text: str) -> str:
    ...

def remove_page_noise(text: str) -> str:
    ...

def remove_ad_lines(lines: list[str]) -> list[str]:
    ...

def remove_duplicate_paragraphs(paragraphs: list[str]) -> list[str]:
    ...

def is_meaningful_paragraph(paragraph: str) -> bool:
    ...

def clean_text(text: str) -> str:
    ...
```

### 6.5 噪声关键词示例

可删除包含以下明显无关词的短行：

```text
下载地址
扫码关注
微信公众号
版权归原作者
仅供学习交流
联系客服
加入QQ群
免费资料
更多资料
```

注意：不要删除包含数学内容的长段落，即使其中出现“资料”二字。

---

## 7. 脚本三：内容筛选与初步分类 `classify_chunks.py`

### 7.1 功能

读取 `backend/data/cleaned/*.txt`，按段落或小节筛选有效数学内容，输出到：

```text
backend/data/selected/selected_items.json
```

每个 item 是一个较小的候选内容块，后续会继续切分为向量 chunks。

### 7.2 保留内容

保留以下内容：

1. 概念定义
2. 公式定理
3. 解题方法
4. 典型例题
5. 题目解析
6. 易错点
7. 知识点总结
8. 高考真题解析
9. 专题训练解析

### 7.3 优先关键词

优先保留包含以下关键词的内容：

```text
函数、导数、数列、三角函数、解三角形、向量、立体几何、空间向量、解析几何、圆锥曲线、椭圆、双曲线、抛物线、概率、统计、排列组合、不等式、复数、集合、逻辑、单调性、极值、最值、零点、恒成立、证明、解析、例题、方法、公式、定理
```

### 7.4 剔除内容

剔除：

1. 广告
2. 下载说明
3. 版权页
4. 无关学科
5. 只有答案没有题干的片段
6. 明显重复内容
7. 无法识别的乱码

### 7.5 分类字段

每个 item 至少包含：

```json
{
  "id": "selected_000001",
  "source": "函数专题讲义.pdf",
  "source_path": "backend/data/raw/lectures/函数专题讲义.pdf",
  "cleaned_path": "backend/data/cleaned/lectures__函数专题讲义.txt",
  "content_type": "knowledge_note",
  "section_type": "concept",
  "knowledge_points": ["函数", "单调性"],
  "text": "..."
}
```

### 7.6 content_type 枚举

```text
official_standard
lecture_note
exercise
exam_with_solution
exam_only
knowledge_summary
error_note
unknown
```

根据原始文件所在目录和文本内容综合判断。

### 7.7 section_type 枚举

```text
concept
formula
method
example
question
solution
common_mistake
summary
other
```

使用关键词规则判断即可。

---

## 8. 脚本四：构建 chunks `build_chunks.py`

### 8.1 功能

读取：

```text
backend/data/selected/selected_items.json
```

切分并输出：

```text
backend/data/chunks/chunks.json
```

### 8.2 chunk 结构

```json
[
  {
    "chunk_id": "chunk_000001",
    "source": "函数专题讲义.pdf",
    "source_path": "backend/data/raw/lectures/函数专题讲义.pdf",
    "content_type": "lecture_note",
    "section_type": "method",
    "knowledge_points": ["导数", "单调性"],
    "text": "导数判断函数单调性的标准步骤是：...",
    "char_count": 356,
    "token_estimate": 180
  }
]
```

### 8.3 切分策略

第一版使用字符长度估算：

- 推荐 chunk 大小：`500-900` 中文字符
- overlap：`80-150` 中文字符
- 不要把题目和解析强行拆开
- 遇到标题、例题、解析、证明、总结等结构时，优先按结构边界切分
- 每个 chunk 必须保留来源和知识点 metadata

### 8.4 最小质量规则

剔除：

- 少于 80 字且不是公式/定义/结论的 chunk
- 不包含任何数学关键词的 chunk
- 乱码比例过高的 chunk

---

## 9. 脚本五：写入 Chroma `embed_to_chroma.py`

### 9.1 功能

读取：

```text
backend/data/chunks/chunks.json
```

写入：

```text
backend/data/vector_db/chroma
```

### 9.2 Embedding 策略

复用当前项目已有的：

```python
app.services.embedding_service.resolve_embeddings
app.services.embedding_service.ensure_compatible_vector_store
app.services.embedding_service.write_embedding_config
```

如果这些函数只支持根目录 `vector_store/chroma`，请做最小改造，让它们支持传入自定义 vector store 目录；不要破坏现有 RAG 构建脚本。

### 9.3 Chroma metadata

每个 chunk 写入 Chroma 时 metadata 至少包含：

```json
{
  "chunk_id": "chunk_000001",
  "source": "函数专题讲义.pdf",
  "source_path": "backend/data/raw/lectures/函数专题讲义.pdf",
  "content_type": "lecture_note",
  "section_type": "method",
  "knowledge_points": "导数,单调性",
  "char_count": 356
}
```

### 9.4 配置记录

写入：

```text
backend/data/vector_db/chroma/embedding_config.json
```

记录：

```json
{
  "provider": "local-hash",
  "model": "local-hash-v1",
  "dimension": 384
}
```

如果当前配置与已有向量库不一致，停止执行并提示删除旧向量库后重建。

---

## 10. 脚本六：检索测试 `retrieval_test.py`

### 10.1 功能

从 `backend/data/vector_db/chroma` 加载向量库，执行检索测试。

### 10.2 默认测试 query

```text
我只会求导但不会判断单调区间
```

### 10.3 输出格式

打印前 5 条结果：

```text
[1] score: ...
source: ...
content_type: ...
section_type: ...
knowledge_points: ...
text:
...
```

### 10.4 通过标准

当本地资料中包含导数与单调性相关内容时，前 5 条结果中应出现以下关键词之一：

```text
导数与函数单调性
导数判断单调性
单调区间
f'(x)>0
f'(x)<0
```

如果没有命中，不要报程序错误，而是输出 `WARNING`，提示检查资料或关键词规则。

---

## 11. 一键运行脚本

可选但推荐新增：

```text
backend/scripts/run_data_pipeline.py
```

按顺序执行：

```text
extract_text.py
clean_text.py
classify_chunks.py
build_chunks.py
embed_to_chroma.py
retrieval_test.py
```

要求：

- 每一步输出处理数量。
- 某一步失败时停止。
- 支持参数 `--skip-extract`，用于原始文件未变化时跳过提取。

示例：

```bash
cd backend
python scripts/run_data_pipeline.py
python scripts/run_data_pipeline.py --skip-extract
```

---

## 12. 日志与错误处理

每个脚本都要：

1. 打印输入目录和输出目录。
2. 打印成功数量、跳过数量、失败数量。
3. 失败不要悄悄吞掉，要记录到 manifest 或控制台。
4. 单个文件失败不影响其他文件继续处理，除非是 chunks 或向量库写入这种全局阶段。

建议每个阶段都生成一个 manifest：

```text
backend/data/extracted/manifest.json
backend/data/cleaned/clean_manifest.json
backend/data/selected/selected_manifest.json
backend/data/chunks/chunks_manifest.json
backend/data/vector_db/embed_manifest.json
```

---

## 13. 依赖更新

请更新：

```text
backend/requirements.txt
```

至少补充：

```text
pypdf
python-docx
beautifulsoup4
lxml
```

不要删除现有依赖。

---

## 14. 测试要求

请新增或补充测试，至少覆盖：

1. `.txt` 提取函数。
2. `.md` 提取函数。
3. 清洗函数不会删除 `A.`、`B.`、`f'(x)`、`解：`。
4. 广告行会被删除。
5. 短乱码段落会被删除。
6. 包含“导数”“单调性”的段落会被保留。
7. `build_chunks.py` 能生成合法 `chunks.json`。
8. 向量库不存在或 chunks 为空时有可读错误提示。

测试命令：

```bash
cd backend
python -m pytest tests
```

---

## 15. 第一版验收标准

完成后应满足：

1. `backend/data/raw` 下放入本地资料后，可以跑完整流水线。
2. `.txt`、`.md`、`.pdf`、`.docx`、`.html` 至少能提取文本。
3. `backend/data/extracted/manifest.json` 能看到每个文件处理状态。
4. `backend/data/cleaned` 中能看到清洗后的文本。
5. `backend/data/selected/selected_items.json` 中能看到筛选后的数学内容。
6. `backend/data/chunks/chunks.json` 中能看到结构化 chunk。
7. `backend/data/vector_db/chroma` 中能生成 Chroma 向量库。
8. `backend/data/vector_db/chroma/embedding_config.json` 能记录 embedding 配置。
9. `python scripts/retrieval_test.py` 能输出前 5 条检索结果。
10. 不影响当前已有 `POST /api/diagnose`、`POST /api/ocr` 和根目录 RAG 流程。

---

## 16. 推荐执行顺序

请按以下顺序实施：

1. 创建 `backend/data` 目录结构。
2. 实现 `extract_text.py` 和 manifest。
3. 实现 `clean_text.py`。
4. 实现 `classify_chunks.py`。
5. 实现 `build_chunks.py`。
6. 改造 embedding 配置工具，支持自定义向量库目录。
7. 实现 `embed_to_chroma.py`。
8. 实现 `retrieval_test.py`。
9. 可选实现 `run_data_pipeline.py`。
10. 更新 README 和 requirements。
11. 添加测试并运行验证。

---

## 17. 给实现 Agent 的完整提示词

请你在当前 `edumath-agent` 工程中实现一套本地资料处理流水线。

严格要求：

1. 不要写爬虫，不要联网下载资料。
2. 只处理用户手动放入 `backend/data/raw` 的本地文件。
3. 支持 `.txt`、`.md`、`.pdf`、`.docx`、`.html`。
4. 按本文档创建目录和脚本。
5. 每个阶段都要可单独运行，也要能通过一键脚本串起来。
6. 每个阶段都要输出 manifest，方便检查。
7. 清洗时不要误删数学公式、题号、选项、解析步骤。
8. 筛选时优先保留高中数学知识库需要的定义、公式、方法、例题、解析、易错点和总结。
9. 生成结构化 `chunks.json`。
10. 使用 Chroma 写入 `backend/data/vector_db/chroma`。
11. 复用当前项目已有 embedding fallback 策略：优先 OpenAI 兼容 Embedding，无 key 则本地 Hash Embedding。
12. 不要破坏当前已有 `data/processed`、`vector_store/chroma`、`/api/diagnose`、`/api/ocr` 功能。
13. 更新 `backend/requirements.txt` 和 README。
14. 添加必要测试，并运行 `python -m pytest tests`。

完成后请汇报：

1. 新增了哪些脚本。
2. 数据从 raw 到 vector_db 的运行命令。
3. 每一步输出到哪里。
4. 测试结果。
5. 如果某些依赖或真实文件测试未完成，请明确说明。

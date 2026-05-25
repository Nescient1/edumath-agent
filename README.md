# EduMath Agent

面向高中数学“函数与导数”专题的错题诊断型 AI 家教系统 MVP。

当前版本已经跑通一个轻量闭环：

```text
错题输入 → 知识点识别 → 错因诊断 → RAG 检索 → 个性化讲解 → 相似题推荐 → 学生作答 → 自动批改 → 更新学生画像
```

第一版 RAG 支持 OpenAI 兼容 Embedding，也支持无 key 演示用的本地 Hash Embedding fallback。正式效果推荐配置 OpenAI 兼容 Embedding；本地 fallback 只用于演示检索链路。

## 项目结构

```text
edumath-agent/
├── backend/          FastAPI 接口服务
├── frontend/         Vue 3 + Vite + Element Plus 前端
├── data/             知识点、题库、讲义
├── docs/             接口与数据说明
└── vector_store/     后续 Chroma 向量库目录
```

## 启动后端

```bash
cd edumath-agent/backend
conda activate edumath
pip install -r requirements.txt
uvicorn app.main:app --reload
```

后端地址：`http://127.0.0.1:8000/api`

接口文档：`http://127.0.0.1:8000/docs`

## 启动前端

```bash
cd edumath-agent/frontend
npm install
npm run dev
```

前端地址：`http://127.0.0.1:5173`

## 构建 RAG 向量库

向量库用于 RAG 检索（错题诊断时自动检索相关知识点和题目）。

### 当前状态

向量库已构建完成，位于 `vector_store/chroma/`，使用本地 BGE 模型（`BAAI/bge-small-zh-v1.5`，512 维）。
数据来源：PostgreSQL 中的 `rag_chunks` 和 `question_items` 表（61 份讲义 PDF、1497 道题目）。

### 从 PostgreSQL 重建向量库（推荐）

```bash
cd edumath-agent/backend
conda activate edumath
python scripts/embed_postgres_to_chroma.py
```

可选参数：
- `--limit N`：限制条数，用于测试
- `--use-openai-embedding`：使用 OpenAI Embedding（需配置 `OPENAI_API_KEY` 和 `ENABLE_OPENAI_EMBEDDING=1`）

### Embedding 配置

三级 fallback：

1. **OpenAI 兼容 Embedding**（`text-embedding-3-small`）— 需配置 `OPENAI_API_KEY` + `ENABLE_OPENAI_EMBEDDING=1`
2. **本地 BGE 模型**（`BAAI/bge-small-zh-v1.5`）— 当前生效，完全离线
3. **本地 Hash Embedding** — 无需模型下载，仅用于演示

构建后会写入 `vector_store/chroma/embedding_config.json`。
如果切换 Embedding 提供商，需删除 `vector_store/chroma` 后重新构建。

### LLM 入库流水线（PDF → PostgreSQL → 向量库）

```bash
# 第一步：PDF 识别入库（PyMuPDF + Pix2Text + LLM Vision → PostgreSQL）
python scripts/llm_ingest_function_derivative.py --write-db --use-vision --topic all

# 第二步：PostgreSQL → Chroma 向量库
python scripts/embed_postgres_to_chroma.py
```

### 验证向量库

```bash
python scripts/retrieval_test.py
```

## 本地资料处理流水线

用户手动下载的合法资料放入 `backend/data/raw` 后，可以运行本地数据流水线：

```bash
cd edumath-agent/backend
conda activate edumath
python scripts\run_data_pipeline.py
```

单步运行：

```bash
python scripts\extract_text.py
python scripts\clean_text.py
python scripts\classify_chunks.py
python scripts\build_chunks.py
python scripts\embed_to_chroma.py
python scripts\retrieval_test.py
```

输出目录：

- `backend/data/extracted`：原始资料提取文本和 `manifest.json`
- `backend/data/cleaned`：清洗文本和 `clean_manifest.json`
- `backend/data/selected`：筛选分类后的 `selected_items.json`
- `backend/data/chunks`：结构化 `chunks.json`
- `backend/data/vector_db/chroma`：流水线专用 Chroma 向量库

这套流水线不写爬虫，不联网下载资料；只处理用户手动放入本地的 `.txt`、`.md`、`.pdf`、`.docx`、`.html` 文件。

## 已实现功能

- `GET /api/health` 健康检查
- `POST /api/ocr` 错题图片 OCR
- `GET /api/questions` 题库筛选
- `POST /api/diagnose` 错题诊断
- `POST /api/recommend` 相似题推荐
- `POST /api/practice/grade` 相似题作答批改
- `GET /api/profile/{student_id}` 学生画像
- `PUT /api/profile/{student_id}` 编辑学生画像
- `GET /api/profile/{student_id}/records` 错题记录
- `PATCH /api/profile/{student_id}/records/{record_id}` 更新错题复习状态

## OCR 输入流程

```text
上传错题图片
→ PaddleOCR 识别逐行文本
→ 可选 Pix2Text 识别数学题和公式
→ 可选 MiMoAI Vision 直接识别整张题图
→ 可选 MiMoAI 整理 OCR 文本
→ 自动回填题目输入框
→ 用户手动确认和修改
→ 点击“开始诊断”
→ 继续调用原来的 /api/diagnose
```

OCR 只负责识别文字，不会直接触发大模型诊断。

## 数据内容

- 11 个函数与导数知识点
- 18 道样例题
- `data/processed` 下的正式 RAG 数据：5 篇知识点讲义、20 道题目卡片、7 类错因诊断规则
- `data/notes` 下保留 7 份早期简版讲义，不参与新向量库

## 学生画像

学生画像已支持 PostgreSQL 正式存储，数据库不可用时会 fallback 到
`backend/storage/profiles.json` 和 `backend/storage/wrong_records.json`。

初始化或升级画像表：

```bash
cd edumath-agent
conda activate edumath
python backend/scripts/init_postgres_db.py
python backend/scripts/migrate_profiles_to_postgres.py
```

画像页支持编辑学生基础信息，包括年级、目标分、当前分、教材版本、当前专题和学习目标。
错题记录支持标记 `未复习 / 复习中 / 已复习`，也可以标记是否已掌握；这些状态会写入
PostgreSQL，并反映到后续画像统计中。

## 后续升级

1. 接入 LangChain 的模型调用和 JSON 输出解析。
2. 加入更严格的数学表达式批改和变式题生成。
3. 扩充更多函数与导数题型数据。
# MiMoAI LLM Configuration

Put your real API key only in `edumath-agent/.env`; never put it in frontend code,
screenshots, GitHub, or `.env.example`.

```env
OPENAI_API_KEY=your_mimoai_key
OPENAI_BASE_URL=https://token-plan-cn.xiaomimimo.com/v1
OPENAI_MODEL=mimo-v2.5
LLM_TIMEOUT_SECONDS=60
LLM_MAX_TOKENS=1024
ENABLE_LLM_DIAGNOSE=1
ENABLE_LLM_OCR_VISION=1
ENABLE_LLM_OCR_REWRITE=0
ENABLE_LLM_DATA_LABELING=0
ENABLE_LLM_PROFILE_ADVICE=1
```

MiMoAI is used through an OpenAI-compatible API, but it is not an OpenAI model.
The project uses MiMoAI only for chat/generation tasks: diagnosis explanation,
low-RAG math solving fallback, optional OCR text cleanup, optional sample data
labeling, and profile advice. Embeddings still use the existing fallback order:

```text
openai-compatible -> local-bge -> local-hash
```

`ENABLE_LLM_OCR_REWRITE` and `ENABLE_LLM_DATA_LABELING` default to `0` to avoid
unexpected token usage. Data labeling is sample-only:

```bash
cd edumath-agent/backend
python scripts\llm_label_sample.py 5
```

## Pix2Text Formula OCR

Pix2Text is integrated as an optional math OCR supplement. For small screenshots
with dense formulas, the recommended path is MiMoAI Vision first. PaddleOCR still
returns line-level `blocks` and confidence scores; when `ENABLE_LLM_OCR_VISION=1`,
`/api/ocr` sends the uploaded image to the OpenAI-compatible vision model and
returns `vision_text`. The frontend prefers `corrected_text` / `vision_text` /
`pix2text_text` when filling the question input. OCR still does not trigger
diagnosis automatically.

Configuration lives in `edumath-agent/.env`:

```env
ENABLE_LLM_OCR_VISION=1
ENABLE_PIX2TEXT_OCR=1
PIX2TEXT_DEVICE=
```

Small DOCX formula-image trial:

```bash
cd edumath-agent
python backend\scripts\test_pix2text_formula_ocr.py --docx "0001_专题01_函数的定义域*.docx" --limit 20 --mode formula
```

The script extracts images from DOCX files, converts WMF/EMF formulas to PNG,
upscales them for OCR, then writes a report to
`backend/data/ocr_trials/pix2text_samples`. Current testing shows Pix2Text is
useful for simple formula candidates, but extracted low-resolution WMF formulas
still need manual review before being written into the final knowledge base.

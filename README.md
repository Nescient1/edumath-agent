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

## 构建 RAG 向量库

```bash
cd edumath-agent/backend
conda activate edumath
python scripts\build_vector_store.py
python scripts\test_rag.py
```

RAG 数据源只使用 `data/processed/**/*.md`，旧的 `data/notes` 会保留但不参与新向量库。

Embedding 配置：

- `OPENAI_API_KEY`：配置后优先使用 OpenAI 兼容 Embedding。
- `OPENAI_BASE_URL`：可配置兼容 OpenAI API 的服务地址。
- `EMBEDDING_MODEL`：默认 `text-embedding-3-small`。
- 无 API Key 或初始化失败时，自动 fallback 到 `local-hash-v1`，维度为 384。
- 构建后会写入 `vector_store/chroma/embedding_config.json`。
- 如果配置和已有向量库不一致，删除 `vector_store/chroma` 后重新构建。

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

## 启动前端

```bash
cd edumath-agent/frontend
npm install
npm run dev
```

前端地址：`http://127.0.0.1:5173`

## 已实现功能

- `GET /api/health` 健康检查
- `POST /api/ocr` 错题图片 OCR
- `GET /api/questions` 题库筛选
- `POST /api/diagnose` 错题诊断
- `POST /api/recommend` 相似题推荐
- `POST /api/practice/grade` 相似题作答批改
- `GET /api/profile/{student_id}` 学生画像
- `GET /api/profile/{student_id}/records` 错题记录

## OCR 输入流程

```text
上传错题图片
→ PaddleOCR 识别文本
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

## 后续升级

1. 接入 LangChain 的模型调用和 JSON 输出解析。
2. 加入更严格的数学表达式批改和变式题生成。
3. 扩充更多函数与导数题型数据。

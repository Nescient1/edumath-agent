# EduMath Agent

面向高中数学”函数与导数”专题的 **AI 错题诊断家教系统**。

沉浸式三阶段诊断体验：错题输入 → AI 动画加载 → 分栏结果展示（逐字打出讲解 + 错因分析 + 相似题推荐 + 在线练习批改）。

```text
错题输入(图片/文字) → OCR 识别 → 知识点识别 → 错因诊断 → RAG 检索 → 个性化讲解 → 相似题推荐 → 学生作答 → 自动批改 → 更新学生画像
```

## 功能亮点

- **登录页**：玻璃拟态风格，左侧浮动数学公式动画，右侧登录表单
- **首页仪表盘**：欢迎横幅 + 快捷入口卡片 + 学习概览
- **AI 诊断舱**：三阶段沉浸流程（输入卡片 → 脉冲加载动画 → 左右分栏结果），讲解文字逐字打出（typewriter effect）
- **专题题库**：响应式卡片网格布局，支持关键词/知识点/难度/质量筛选，点击查看完整题目详情（含选项、答案、解析）
- **学生画像**：Echarts 雷达图展示知识点掌握度，AI 家教对话气泡给出学习建议和周计划
- **在线练习**：选择相似题后可在线作答，AI 自动批改并给出提示

## 项目结构

```text
edumath-agent/
├── backend/                 FastAPI 接口服务
│   ├── app/
│   │   ├── api/             路由（diagnose, questions, practice, profiles, ocr）
│   │   ├── repositories/    数据访问层（PostgreSQL + JSON fallback）
│   │   ├── schemas/         Pydantic 模型
│   │   ├── services/        业务逻辑（LLM, OCR, 向量检索）
│   │   └── prompts/         LLM Prompt 模板
│   ├── scripts/             数据入库、向量构建、迁移脚本
│   ├── data/                PDF 原始资料、知识库 JSON
│   └── tests/               后端测试
├── frontend/                Vue 3 + Vite + Element Plus 前端
│   ├── src/
│   │   ├── views/           页面（Login, Home, Diagnose, QuestionBank, StudentProfile）
│   │   ├── components/      组件（diagnose/, MathTextPreview, KnowledgeTag 等）
│   │   ├── api/             API 调用封装
│   │   ├── router/          路由 + 登录守卫
│   │   └── styles.css       全局样式（Morandi 色系 + 动画）
│   └── package.json
├── docs/                    设计文档与报告
├── image/                   README 截图
└── vector_store/            Chroma 向量库
```

## 快速启动

### 1. 配置环境变量

```bash
cp .env.example .env
# 编辑 .env，填入 OPENAI_API_KEY 等配置
```

### 2. 启动后端

```bash
cd backend
pip install -r requirements.txt
uvicorn app.main:app --reload
```

- 后端地址：`http://127.0.0.1:8000/api`
- 接口文档：`http://127.0.0.1:8000/docs`
- 启动时自动创建 PostgreSQL 表结构（students, student_profiles, student_wrong_records）

### 3. 启动前端

```bash
cd frontend
npm install
npm run dev
```

- 前端地址：`http://127.0.0.1:5173`
- 打开后自动跳转到登录页，输入学生 ID 即可进入系统

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

| 模块 | 接口 | 说明 |
|------|------|------|
| 健康检查 | `GET /api/health` | 服务状态 |
| OCR | `POST /api/ocr` | 错题图片识别（PaddleOCR + Pix2Text + MiMoAI Vision） |
| 题库 | `GET /api/questions` | 题库筛选（关键词/知识点/难度/质量） |
| 题库 | `GET /api/questions/{id}` | 题目详情（含选项、答案、解析） |
| 诊断 | `POST /api/diagnose` | RAG + LLM 错题诊断 |
| 推荐 | `POST /api/recommend` | 相似题推荐 |
| 练习 | `POST /api/practice/grade` | 作答批改 |
| 练习 | `POST /api/practice/assist` | 练习辅助（提示/答案/解析） |
| 画像 | `GET /api/profile/{student_id}` | 学生画像 |
| 画像 | `PUT /api/profile/{student_id}` | 编辑学生画像 |
| 画像 | `GET /api/profile/{student_id}/records` | 错题记录 |
| 画像 | `PATCH /api/profile/{student_id}/records/{id}` | 更新复习状态 |
| 变式 | `POST /api/questions/generate-variants` | AI 生成变式题 |

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

- 11 个函数与导数知识点（定义域、单调性、极值、导数几何意义等）
- 1497+ 道题目（PostgreSQL 存储，含选项、答案、解析）
- 61 份讲义 PDF（入库为 RAG 检索块）
- 7 类错因诊断规则

## 学生画像

学生画像支持 PostgreSQL 持久化存储（启动时自动建表），数据库不可用时 fallback 到本地 JSON 文件。

画像页功能：
- Echarts 雷达图展示各知识点掌握度
- AI 家教对话气泡：学习建议、优先攻克点、错题策略、周计划
- 编辑学生基础信息（年级、目标分、当前分、教材版本、学习目标）
- 错题记录管理：标记复习状态（未复习/复习中/已复习）+ 是否已掌握

## LLM 配置

项目使用 MiMoAI（OpenAI 兼容 API）进行诊断讲解、OCR 辅助、画像建议等生成任务。Embedding 使用独立的 fallback 链。

```env
# .env 中配置
OPENAI_API_KEY=your_mimoai_key
OPENAI_BASE_URL=https://token-plan-cn.xiaomimimo.com/v1
OPENAI_MODEL=mimo-v2.5
LLM_TIMEOUT_SECONDS=60
ENABLE_LLM_DIAGNOSE=1
ENABLE_LLM_OCR_VISION=1
ENABLE_LLM_PROFILE_ADVICE=1
```

Embedding 三级 fallback：`OpenAI 兼容 → 本地 BGE → 本地 Hash`

## 技术栈

| 层 | 技术 |
|---|------|
| 前端 | Vue 3 + TypeScript + Vite + Element Plus + Echarts |
| 后端 | FastAPI + psycopg (PostgreSQL) + ChromaDB |
| OCR | PaddleOCR + Pix2Text + MiMoAI Vision |
| LLM | MiMoAI (OpenAI-compatible API) |
| 向量库 | ChromaDB + BGE-small-zh-v1.5 |
| 数据库 | PostgreSQL (题库 + 学生画像 + 错题记录) |

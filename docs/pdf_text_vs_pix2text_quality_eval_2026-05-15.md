# PDF 文本提取 vs Pix2Text Markdown 质量评估：2026.05.15

## 测试目标

对同一份资料的第 1 页进行两条路线测试：

```text
PDF -> PyMuPDF 直接提取前 1 页文本
PDF -> 300DPI PNG -> Pix2Text -> Markdown
```

目的是判断后续是否有必要进入：

```text
PDF -> PNG -> 多模态大模型识别
```

## 测试文件

源 PDF：

```text
backend/data/ocr_trials/docx_render_samples/0001_专题01_函数的定义域(解析版)_f00018d5/pdf/0001_专题01_函数的定义域(解析版).pdf
```

测试页码：

```text
page 1
```

## 结果目录

```text
backend/data/ocr_trials/quality_eval/0001_专题01_函数的定义域(解析版)_page_001
```

关键文件：

```text
report.json
pymupdf_page_text.md
pix2text_page_markdown.md
page_001_300dpi.png
```

## 路线一：PyMuPDF 直接提取文本

输出文件：

```text
backend/data/ocr_trials/quality_eval/0001_专题01_函数的定义域(解析版)_page_001/pymupdf_page_text.md
```

统计：

```text
char_count=1210
block_count=57
```

效果观察：

- 中文题干、解析文字可以提取出来。
- 题号、选项、答案、解析大体都在。
- 公式内容也有提取，但排版被拆散，例如分式、根号、区间、集合符号会被拆成多行。
- 一些数学符号来自特殊字体，表现为 ``、``、``、`` 等字符，需要后处理映射。

典型片段：

```text
专题01   函数的定义域
专项突破一  具体函数的定义域
1．函数
( )
1
3
x
f x
x
−
=
−
的定义域为（       ）．
```

判断：

```text
PyMuPDF 适合作为 PDF 文本主提取路线，但需要数学符号清洗和公式重组。
```

## 路线二：PDF/PNG -> Pix2Text -> Markdown

渲染图片：

```text
backend/data/ocr_trials/quality_eval/0001_专题01_函数的定义域(解析版)_page_001/page_001_300dpi.png
```

图片尺寸：

```text
2481 x 3508
300 DPI
```

Pix2Text 输出文件：

```text
backend/data/ocr_trials/quality_eval/0001_专题01_函数的定义域(解析版)_page_001/pix2text_page_markdown.md
```

本次状态：

```text
status=failed
char_count=0
```

失败原因：

```text
Pix2Text 整页 OCR 需要 layout-docyolo 版面分析模型。
当前本地缺少：
backend/storage/pix2text/1.1/layout-docyolo/doclayout_yolo_docstructbench_imgsz1024.pt
```

说明：

- Pix2Text 的公式 OCR 模型已经可用于单个公式图片。
- Pix2Text 的整页 Markdown 识别还需要额外下载版面分析模型。
- 在模型未下载前，无法评估 Pix2Text 整页 Markdown 的真实质量。

## 当前结论

基于本轮可见结果：

1. `DOCX -> PDF -> 300DPI PNG` 这一步非常有价值，页面图质量明显优于 `word/media/*.wmf` 直转。
2. `PyMuPDF` 直接文本提取已经能拿到大量可用文本，适合作为第一版 PDF 文本主路线。
3. `PyMuPDF` 的主要问题是公式结构被打散，数学符号需要映射和清洗。
4. `Pix2Text` 适合继续用于“局部公式识别”，但整页 Markdown 识别需要先补齐 layout 模型后再评估。
5. 多模态大模型不建议直接全量替代提取流程，更适合在候选结果上做校对、结构化和质量判断。

## 是否需要多模态大模型

建议不是马上全量使用，而是作为第三路线抽样验证：

```text
PDF page PNG
-> 多模态大模型
-> 输出结构化 Markdown / JSON
-> 与 PyMuPDF 和 Pix2Text 结果对比
```

推荐输入给多模态大模型的任务：

```text
请识别这张高中数学试题页面，保留题号、题干、选项、解析和数学公式。
请用 Markdown 输出。
不要补充图片中不存在的内容。
无法确认的公式用 [UNCERTAIN: ...] 标记。
```

如果多模态模型在 3-5 页样本上明显优于 PyMuPDF + Pix2Text，再考虑把它接入 PostgreSQL 候选字段。

## 推荐下一步

1. 先下载 Pix2Text 的 `layout-docyolo` 模型，补跑整页 Markdown 测试。
2. 同时抽 1 页用 MiMoAI 视觉模型识别页面 PNG。
3. 三路结果做人工对比：

```text
PyMuPDF text
Pix2Text markdown
MiMoAI vision markdown
```

4. 如果 MiMoAI 视觉效果明显更好，则将其结果写入 PostgreSQL 候选字段，而不是直接进入正式知识库。

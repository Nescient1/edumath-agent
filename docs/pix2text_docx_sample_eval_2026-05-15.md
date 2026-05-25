# Pix2Text DOCX 公式 OCR 小样本评估：2026.05.15

## 测试目的

验证 Pix2Text 对当前高中数学 DOCX 资料中“图片公式”的识别效果，判断后续结果应该直接进入 `extracted`、进入 PostgreSQL 候选字段，还是只作为人工校对辅助。

## 测试方式

使用脚本：

```bash
python backend\scripts\test_pix2text_formula_ocr.py --docx "<docx-pattern>" --limit 10 --mode formula
```

脚本流程：

```text
DOCX
-> 解压 word/media
-> 提取 png / wmf / emf 图片
-> 将 wmf/emf 转为 png
-> 白底、放大、加边距预处理
-> Pix2Text LatexOCR 识别
-> 输出 report.json 和对应图片
```

## 抽样文件

本次抽取 3 份典型 DOCX，每份前 10 个内嵌公式图片：

1. `0001_专题01_函数的定义域(解析版).docx`
2. `0006_专题06_函数的单调性(解析版).docx`
3. `0026_专题04_利用导数求函数的极值(解析版).docx`

## 结果查看位置

### 1. 函数定义域

报告文件：

```text
backend/data/ocr_trials/pix2text_samples/0001_专题01_函数的定义域(解析版)_f00018d5/report.json
```

图片目录：

```text
backend/data/ocr_trials/pix2text_samples/0001_专题01_函数的定义域(解析版)_f00018d5/media
```

统计结果：

```text
sampled=10
native_raster=1
converted=9
conversion_failed=0
ocr_success=10
```

部分 OCR 输出：

```text
\alpha=2+\sqrt{1}
( \bot2 )
( \operatorname{l n} 2 , 2 )
\mathbf{m} \cup\mathbf{1} 2
```

初步观察：

- 简单区间、简单符号有一定可用性。
- 部分符号明显误识别，例如集合、括号、无穷区间、变量字符。

### 2. 函数单调性

报告文件：

```text
backend/data/ocr_trials/pix2text_samples/0006_专题06_函数的单调性(解析版)_940d336f/report.json
```

图片目录：

```text
backend/data/ocr_trials/pix2text_samples/0006_专题06_函数的单调性(解析版)_940d336f/media
```

统计结果：

```text
sampled=10
native_raster=1
converted=9
conversion_failed=0
ocr_success=10
```

部分 OCR 输出：

```text
y \triangleleft0
f x-f x
\sin\theta=\theta=\theta\sin\theta
\begin{array} {c} {-2 \! < \! \log_{2} \! m \! < \! 2} \\ {...} \end{array}
```

初步观察：

- 复杂不等式组能识别出部分结构。
- 小图、低清晰度符号会被误读，例如 `<`、`>`、变量、函数括号。

### 3. 利用导数求函数极值

报告文件：

```text
backend/data/ocr_trials/pix2text_samples/0026_专题04_利用导数求函数的极值(解析版)_82353add/report.json
```

图片目录：

```text
backend/data/ocr_trials/pix2text_samples/0026_专题04_利用导数求函数的极值(解析版)_82353add/media
```

统计结果：

```text
sampled=10
native_raster=1
converted=9
conversion_failed=0
ocr_success=10
```

部分 OCR 输出：

```text
{\mathfrak{I}}={\frac{1} {\mathfrak{I}}}
2 x-1
y \triangleleft0
+ \approx2
```

初步观察：

- 简单表达式如 `2 x-1` 可用。
- 导数、极值相关复杂公式误识别较多。
- 有些公式图片本身分辨率较低，OCR 输出不能直接信任。

## 总体结论

本次小样本中：

```text
抽样文件数：3
每份抽样图片数：10
图片转换成功率：100%
Pix2Text 有输出率：100%
可直接信任程度：不稳定
```

Pix2Text 的价值主要在于：

- 能把 DOCX 中原本完全丢失的图片公式转成候选 LaTeX。
- 对简单公式、区间、分式、部分不等式有帮助。
- 能作为人工校对入口，提高后续整理效率。

但当前不建议：

```text
Pix2Text 结果 -> 直接写入 extracted -> 直接清洗切分 -> 直接向量化
```

原因：

- 简单公式还可以，但复杂公式错误较多。
- 一旦错误公式进入 RAG 知识库，后续检索和讲解会把错误内容当作可信资料。
- 当前输出缺少置信度和人工确认状态。

## 建议方案

第一阶段建议将 Pix2Text 结果写入 PostgreSQL 的候选字段，而不是直接写入正式 `extracted`。

建议保存结构：

```text
documents
-> extraction_runs
-> text_blocks
   - raw_text
   - extracted_text
   - formula_ocr_candidates
   - formula_image_path
   - ocr_engine = pix2text
   - review_status = pending / accepted / rejected / edited
```

推荐策略：

```text
普通 DOCX 文本：进入 extracted
OMML 标准公式：可进入 extracted
Pix2Text 图片公式：进入 PostgreSQL 候选字段
人工或 LLM 校对后：再进入 cleaned/chunks/vector_db
```

## 人工评估方法

打开每个 `media` 目录，对照查看：

- 原始文件：`*.wmf` / `*.png`
- 转换后文件：`*.png`
- OCR 预处理文件：`*_ocr.png`
- 识别结果：`report.json` 中每个 item 的 `ocr_text`

建议人工标注三类：

```text
accepted：可以直接使用
edited：需要人工修正后使用
rejected：不可用，不进入知识库
```

## 下一步

1. 新增 Pix2Text OCR 结果入 PostgreSQL 的脚本。
2. 为 `text_blocks` 或专门的 `formula_ocr_candidates` 表增加人工审核字段。
3. 做一个简单审核页面或导出 CSV，让人工逐条确认。
4. 审核通过后再合并到 `cleaned` 和 `chunks`。

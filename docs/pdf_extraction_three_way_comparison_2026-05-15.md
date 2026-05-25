# PDF 提取三路对比：PyMuPDF / Pix2Text / MiMoAI Vision

## 测试对象

PDF：

```text
backend/data/ocr_trials/docx_render_samples/0001_专题01_函数的定义域(解析版)_f00018d5/pdf/0001_专题01_函数的定义域(解析版).pdf
```

页码：

```text
page 1
```

渲染：

```text
300 DPI PNG
```

统一结果目录：

```text
backend/data/ocr_trials/quality_eval/0001_专题01_函数的定义域(解析版)_page_001
```

## 三组结果文件

### 1. PyMuPDF 直接文本提取

```text
backend/data/ocr_trials/quality_eval/0001_专题01_函数的定义域(解析版)_page_001/pymupdf_page_text.md
```

统计：

```text
status=success
char_count=1210
block_count=57
```

特点：

- 中文题干、解析、选项大体能提取。
- 不依赖 OCR，速度快，成本低。
- 公式结构被拆散，分式、根号、集合、区间会被分成多行。
- 特殊数学符号会变成字体编码字符，例如 ``、``、``、``。

适合用途：

```text
PDF 主文本提取
```

但需要后处理：

```text
符号映射 + 公式重组 + 题目结构化
```

### 2. Pix2Text 整页 Markdown

```text
backend/data/ocr_trials/quality_eval/0001_专题01_函数的定义域(解析版)_page_001/pix2text_page_markdown.md
```

统计：

```text
status=success
char_count=2181
```

典型输出片段：

```markdown
1.函数 $f \left( x \right) \!=\! \frac{\sqrt{x-1}} {x-3}$ 的定义域为（ ).
^. $( 1 ,+\infty)$ :. $\left[ 1 ,+\infty\right)$ 
c. $( 1 , 3 )$ D. $\big[ 1 , 3 \big) \cup\big( 3 ,+\infty\big)$ 
【解析】要是函数有意义，必须 $\left\{\begin{aligned} {} & {{} x-1 \geq0} \\ {} & {{} x-3 \neq0} \\ \end{aligned} \right.$
```

特点：

- 公式结构明显优于 PyMuPDF，能输出 LaTeX。
- 对根号、分式、不等式组、区间表达有明显帮助。
- 中文 OCR 有错字，例如“解之得”可能识别成“楼”等异常字符。
- 选项 A/B/C/D 有时识别不稳定，例如 `A` 变成 `^`，`B` 变成 `:`，`C` 大小写混乱。
- 页面结构基本能保留，但题目边界仍需规则或大模型整理。

适合用途：

```text
公式候选提取
复杂数学表达式补充
人工校对辅助
```

不建议直接：

```text
Pix2Text Markdown -> cleaned -> chunks -> vector_db
```

更适合进入 PostgreSQL 候选字段。

### 3. MiMoAI Vision 页面识别

```text
backend/data/ocr_trials/quality_eval/0001_专题01_函数的定义域(解析版)_page_001/mimo_vision_page_markdown.md
```

本次状态：

```text
status=failed
char_count=0
error=Connection error.
```

说明：

- 脚本已经支持 MiMoAI Vision 路线。
- 当前运行环境中 API 连接失败，因此未得到视觉模型结果。
- 不是脚本结构问题，后续在网络/API 可用时重新运行即可覆盖结果。

重新运行命令：

```bash
python backend\scripts\evaluate_pdf_ocr_quality.py --pdf "backend\data\ocr_trials\docx_render_samples\0001_专题01_函数的定义域(解析版)_f00018d5\pdf\0001_专题01_函数的定义域(解析版).pdf" --page 1 --dpi 300 --run-vision
```

如果需要指定视觉模型：

```bash
python backend\scripts\evaluate_pdf_ocr_quality.py --pdf "backend\data\ocr_trials\docx_render_samples\0001_专题01_函数的定义域(解析版)_f00018d5\pdf\0001_专题01_函数的定义域(解析版).pdf" --page 1 --dpi 300 --run-vision --vision-model "你的视觉模型名"
```

## 统一对比文件

脚本还生成了统一对比文件：

```text
backend/data/ocr_trials/quality_eval/0001_专题01_函数的定义域(解析版)_page_001/comparison.md
```

其中包含：

- 三路结果文件路径
- 字符数统计
- PyMuPDF 预览
- Pix2Text 预览
- MiMoAI Vision 预览或错误信息

## 当前判断

### 最推荐的第一版组合

```text
PyMuPDF 负责主文本
Pix2Text 负责公式候选
MiMoAI Vision 负责抽样质检和复杂页兜底
```

### 不建议的路线

```text
只用 PyMuPDF
```

原因：公式结构太散，后处理压力大。

```text
只用 Pix2Text
```

原因：公式较好，但中文和选项 OCR 有错，不够稳定。

```text
全量使用 MiMoAI Vision
```

原因：成本、速度、网络稳定性和结果可控性都需要进一步评估。

## 建议入库策略

建议 PostgreSQL 中保存三类候选：

```text
pymupdf_text
pix2text_markdown
vision_markdown
```

并增加质量状态：

```text
review_status = pending / accepted / edited / rejected
preferred_source = pymupdf / pix2text / vision / merged
```

进入正式知识库前，建议先生成融合文本：

```text
主文本来自 PyMuPDF
公式来自 Pix2Text
结构化修正由规则或 MiMoAI 完成
人工抽样审核后进入 cleaned/chunks/vector_db
```

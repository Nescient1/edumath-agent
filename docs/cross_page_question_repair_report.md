# Cross-page Incomplete Question Repair Report

- Mode: apply
- Candidate count: 3

## Repair Rule

- Scope: `question_items.quality_label IN ('medium', 'pending_review')`
- Trigger: answer 或 solution 为空，并且题干/下一页符合跨页残缺特征。
- Apply action: 将题目标记为 `low`，写入 `metadata.review_status=bad_split_cross_page`，从推荐与正式检索中排除。

## Candidates

### e1f2e297-e883-4d05-bd72-3daf923d9e6c

- Source: `0006_专题06_构造函数法解决导数不等式问题(一)(教师版).pdf`
- Page: 10
- Quality: medium
- Score: 8
- Reasons: answer 为空; solution 为空; 下一页疑似从 (2)/解析/答案 继续
- Question: `定义在$\left(0, \frac{\pi}{2}\right)$上的函数$f(x)$，函数$f'(x)$是它的导函数，且恒有$f(x) < f'(x)\tan x$ 成立，则( )`
- Answer: ``
- Solution: ``
- Next page preview: `答案 D 解析 f(x)＜f′(x)tan x⇔f′(x)sin x－f(x)cos x＞0，令F(x)＝f(x) sin x，则F′(x)＝f′(x)sin x－f(x)cos x sin2x ＞0，即函数F(x)在0，π 2 上是增函数，∴F π 6 ＜F π 3 ，即 f π 6 sin π 6 ＜ f π 3 sin π 3 ，∴3f π 6 ＜f ...`

### f7e51247-2ac1-4d90-a6da-25a9b3747098

- Source: `0015_专题14_两个经典不等式的应用(教师版).pdf`
- Page: 8
- Quality: medium
- Score: 8
- Reasons: answer 为空; solution 为空; 只抽到 (1)，未抽到后续小问; 题干以未完成标点结尾; 题干偏短
- Question: `设函数 \( f(x) = \ln x - x + 1 \)。(1) 讨论 \( f(x) \) 的单调性；`
- Answer: ``
- Solution: ``
- Next page preview: ``

### e7e65a60-84b7-4b6b-9796-ff6deb592985

- Source: `0019_专题18_单变量不含参不等式证明方法之凹凸反转(教师版).pdf`
- Page: 4
- Quality: medium
- Score: 6
- Reasons: answer 为空; 下一页疑似从 (2)/解析/答案 继续
- Question: `已知\( f(x) = \ln x + \frac{2}{\mathrm{e}x} \)。 (1) 若函数\( g(x) = x f(x) \)，讨论\( g(x) \)的单调性与极值； (2) 证明：\( f(x) > \frac{1}{\mathrm{e}^x} \)。`
- Answer: ``
- Solution: `(1) 由题意，得\( g(x) = x f(x) = x \ln x + \frac{2}{\mathrm{e}} (x > 0) \)，则\( g'(x) = \ln x + 1 \)。 当\( ...`
- Next page preview: `### (2) 证明不等式 所证不等式等价于 $\ln x+1 > \frac{1}{e^x}-\frac{2}{ex} \iff x\ln x + x > \frac{x}{e^x}-\frac{2}{e}$。 设 $p(x)=x\ln x + x$，则 $p'(x)=1+\ln x + 1=\ln x+2$。 因此 $p(x)$ 在 $\left(0,\...`

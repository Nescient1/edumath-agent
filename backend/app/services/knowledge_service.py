from app.repositories.knowledge_repository import load_knowledge_points


def identify_knowledge_points(question_text: str) -> list[str]:
    text = question_text or ""
    scores: dict[str, int] = {}

    for point in load_knowledge_points():
        score = 0
        if point.name in text:
            score += 5
        for keyword in point.keywords:
            if keyword and keyword in text:
                score += 2
        if score > 0:
            scores[point.name] = score

    derivative_context = any(
        signal in text for signal in ["导数", "f'", "f’", "求导", "极值", "最值", "切线"]
    )

    heuristic_hits = [
        (derivative_context, "导数计算"),
        ("切线" in text or "斜率" in text, "导数几何意义"),
        ("单调" in text and derivative_context, "导数与函数单调性"),
        ("单调" in text and not derivative_context, "函数单调性"),
        ("极值" in text or "极大" in text or "极小" in text, "导数与极值"),
        ("最值" in text or "最大值" in text or "最小值" in text, "导数与最值"),
        (
            "参数" in text
            or "实数 a" in text
            or ("a" in text and ("讨论" in text or "取值范围" in text)),
            "含参函数讨论",
        ),
        ("定义域" in text or "ln" in text or "根号" in text or "√" in text, "函数定义域"),
        ("零点" in text or "根的个数" in text, "函数零点"),
        ("图像" in text or "对称" in text or "平移" in text, "函数图像与性质"),
        ("证明" in text and "不等式" in text, "导数证明不等式"),
    ]

    for hit, name in heuristic_hits:
        if hit:
            scores[name] = scores.get(name, 0) + 3

    if derivative_context and "导数与函数单调性" in scores:
        scores.pop("函数单调性", None)

    ranked = sorted(scores.items(), key=lambda item: item[1], reverse=True)
    points = [name for name, _ in ranked[:4]]

    if not points:
        points = ["函数单调性", "导数计算"]

    if "导数与函数单调性" in points and "导数计算" not in points:
        points.append("导数计算")

    return points[:4]


def infer_difficulty(question_text: str, knowledge_points: list[str]) -> str:
    hard_signals = ["参数", "恒成立", "证明", "综合", "零点个数", "根的个数", "取值范围"]
    medium_signals = ["极值", "最值", "单调区间", "切线"]

    if any(signal in question_text for signal in hard_signals):
        return "困难"
    if any(signal in question_text for signal in medium_signals) or len(knowledge_points) >= 2:
        return "中等"
    return "基础"

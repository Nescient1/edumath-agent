from pydantic import BaseModel


class KnowledgePoint(BaseModel):
    id: str
    name: str
    chapter: str
    description: str
    prerequisites: list[str] = []
    common_exam_methods: list[str] = []
    keywords: list[str] = []


class Question(BaseModel):
    id: str
    question_text: str
    answer: str
    solution: str
    knowledge_points: list[str]
    difficulty: str
    question_type: str
    quality_label: str = ""
    options: list[str] = []
    common_mistakes: list[str] = []
    image_paths: list[str] = []
    image_urls: list[str] = []
    image_descriptions: list[str] = []
    page_image_path: str | None = None
    page_image_url: str | None = None


class QuestionSummary(BaseModel):
    id: str
    question_text: str
    knowledge_points: list[str]
    difficulty: str
    question_type: str
    quality_label: str = ""
    options: list[str] = []
    image_paths: list[str] = []
    image_urls: list[str] = []
    image_descriptions: list[str] = []


class GeneratedQuestion(BaseModel):
    question_text: str
    answer: str
    solution: str
    difficulty: str
    knowledge_points: list[str]
    question_type: str = "解答题"
    source: str = "generated"

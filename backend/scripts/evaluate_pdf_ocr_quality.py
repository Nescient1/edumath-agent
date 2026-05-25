import argparse
import base64
import json
import sys
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parents[1]))

from app.core.config import settings
from app.services.llm_service import get_llm_client, is_llm_enabled
from app.services.pix2text_service import recognize_image_with_pix2text


BACKEND_DIR = Path(__file__).resolve().parents[1]
OUTPUT_ROOT = BACKEND_DIR / "data" / "ocr_trials" / "quality_eval"


def extract_page_text_with_pymupdf(pdf_path: Path, page_no: int) -> dict:
    try:
        import fitz
    except ImportError as exc:
        raise RuntimeError("Missing dependency: PyMuPDF") from exc

    with fitz.open(str(pdf_path)) as document:
        page = document[page_no - 1]
        text = page.get_text("text")
        blocks = page.get_text("blocks")

    return {
        "text": text.strip(),
        "char_count": len(text.strip()),
        "block_count": len(blocks),
    }


def render_pdf_page(pdf_path: Path, page_no: int, output_path: Path, dpi: int) -> dict:
    try:
        import fitz
    except ImportError as exc:
        raise RuntimeError("Missing dependency: PyMuPDF") from exc

    output_path.parent.mkdir(parents=True, exist_ok=True)
    with fitz.open(str(pdf_path)) as document:
        page = document[page_no - 1]
        pixmap = page.get_pixmap(dpi=dpi, alpha=False)
        pixmap.save(str(output_path))

    return {
        "image_path": str(output_path),
        "width": pixmap.width,
        "height": pixmap.height,
        "dpi": dpi,
    }


def write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def recognize_page_with_vision_llm(image_path: Path, *, model: str | None = None) -> dict:
    if not is_llm_enabled():
        return {"status": "skipped", "error": "LLM is not configured.", "text": ""}

    client = get_llm_client()
    if client is None:
        return {"status": "skipped", "error": "OpenAI-compatible client is unavailable.", "text": ""}

    try:
        image_b64 = base64.b64encode(image_path.read_bytes()).decode("ascii")
        response = client.chat.completions.create(
            model=model or settings.openai_model,
            messages=[
                {
                    "role": "system",
                    "content": (
                        "你是高中数学资料 OCR 与结构化助手。请严格根据图片内容输出 Markdown，"
                        "保留题号、题干、选项、解析、答案和数学公式。不要补充图片中不存在的内容。"
                        "无法确认的公式或字符请用 [UNCERTAIN: ...] 标记。"
                    ),
                },
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "text",
                            "text": "请识别这张高中数学试题页面，输出可用于知识库整理的 Markdown。",
                        },
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": f"data:image/png;base64,{image_b64}",
                            },
                        },
                    ],
                },
            ],
            max_tokens=settings.llm_max_tokens,
            temperature=0.0,
        )
        text = response.choices[0].message.content or ""
        return {"status": "success", "error": None, "text": text.strip()}
    except Exception as exc:
        return {"status": "failed", "error": str(exc), "text": ""}


def run_eval(
    pdf_path: Path,
    page_no: int,
    dpi: int,
    output_dir: Path,
    *,
    run_vision: bool = False,
    vision_model: str | None = None,
) -> dict:
    output_dir.mkdir(parents=True, exist_ok=True)

    pymupdf = extract_page_text_with_pymupdf(pdf_path, page_no)
    pymupdf_path = output_dir / "pymupdf_page_text.md"
    write_text(
        pymupdf_path,
        "# PyMuPDF Page Text\n\n"
        f"- source: `{pdf_path}`\n"
        f"- page: {page_no}\n"
        f"- char_count: {pymupdf['char_count']}\n"
        f"- block_count: {pymupdf['block_count']}\n\n"
        "```text\n"
        f"{pymupdf['text']}\n"
        "```\n",
    )

    image_path = output_dir / f"page_{page_no:03d}_{dpi}dpi.png"
    rendered = render_pdf_page(pdf_path, page_no, image_path, dpi)

    pix2text_result = recognize_image_with_pix2text(image_path)
    pix2text_path = output_dir / "pix2text_page_markdown.md"
    pix2text_markdown = pix2text_result.text.strip()
    write_text(
        pix2text_path,
        "# Pix2Text Page Markdown\n\n"
        f"- source_image: `{image_path}`\n"
        f"- page: {page_no}\n"
        f"- error: {pix2text_result.error or ''}\n"
        f"- char_count: {len(pix2text_markdown)}\n\n"
        f"{pix2text_markdown}\n",
    )

    vision_path = output_dir / "mimo_vision_page_markdown.md"
    vision_result = {"status": "skipped", "error": "vision disabled", "text": ""}
    if run_vision:
        vision_result = recognize_page_with_vision_llm(image_path, model=vision_model)
    vision_markdown = vision_result["text"].strip()
    write_text(
        vision_path,
        "# MiMoAI Vision Page Markdown\n\n"
        f"- source_image: `{image_path}`\n"
        f"- page: {page_no}\n"
        f"- model: {vision_model or settings.openai_model}\n"
        f"- status: {vision_result['status']}\n"
        f"- error: {vision_result['error'] or ''}\n"
        f"- char_count: {len(vision_markdown)}\n\n"
        f"{vision_markdown}\n",
    )

    report = {
        "pdf_path": str(pdf_path),
        "page_no": page_no,
        "output_dir": str(output_dir),
        "pymupdf_text_path": str(pymupdf_path),
        "pix2text_markdown_path": str(pix2text_path),
        "mimo_vision_markdown_path": str(vision_path),
        "rendered_image": rendered,
        "pymupdf": {
            "char_count": pymupdf["char_count"],
            "block_count": pymupdf["block_count"],
            "preview": pymupdf["text"][:500],
        },
        "pix2text": {
            "status": "failed" if pix2text_result.error else "success",
            "error": pix2text_result.error,
            "char_count": len(pix2text_markdown),
            "preview": pix2text_markdown[:500],
        },
        "mimo_vision": {
            "status": vision_result["status"],
            "error": vision_result["error"],
            "char_count": len(vision_markdown),
            "preview": vision_markdown[:500],
            "model": vision_model or settings.openai_model,
        },
    }
    comparison_path = output_dir / "comparison.md"
    write_text(
        comparison_path,
        "# PDF Extraction Quality Comparison\n\n"
        f"- PDF: `{pdf_path}`\n"
        f"- page: {page_no}\n"
        f"- rendered_image: `{image_path}`\n\n"
        "## Result Files\n\n"
        f"- PyMuPDF: `{pymupdf_path}`\n"
        f"- Pix2Text: `{pix2text_path}`\n"
        f"- MiMoAI Vision: `{vision_path}`\n\n"
        "## Metrics\n\n"
        "| method | status | chars | notes |\n"
        "| --- | --- | ---: | --- |\n"
        f"| PyMuPDF | success | {pymupdf['char_count']} | blocks={pymupdf['block_count']} |\n"
        f"| Pix2Text | {report['pix2text']['status']} | {len(pix2text_markdown)} | {pix2text_result.error or ''} |\n"
        f"| MiMoAI Vision | {vision_result['status']} | {len(vision_markdown)} | {vision_result['error'] or ''} |\n\n"
        "## PyMuPDF Preview\n\n"
        "```text\n"
        f"{pymupdf['text'][:1500]}\n"
        "```\n\n"
        "## Pix2Text Preview\n\n"
        "```markdown\n"
        f"{pix2text_markdown[:1500]}\n"
        "```\n\n"
        "## MiMoAI Vision Preview\n\n"
        "```markdown\n"
        f"{vision_markdown[:1500]}\n"
        "```\n",
    )
    report["comparison_path"] = str(comparison_path)
    report_path = output_dir / "report.json"
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description="Evaluate PDF text extraction and Pix2Text page OCR quality.")
    parser.add_argument("--pdf", required=True, help="PDF path.")
    parser.add_argument("--page", type=int, default=1, help="1-based page number.")
    parser.add_argument("--dpi", type=int, default=300, help="Render DPI.")
    parser.add_argument("--output-dir", default=None, help="Output directory.")
    parser.add_argument("--run-vision", action="store_true", help="Run OpenAI-compatible vision model on the page PNG.")
    parser.add_argument("--vision-model", default=None, help="Optional vision-capable model override.")
    args = parser.parse_args()

    pdf_path = Path(args.pdf).resolve()
    if not pdf_path.exists():
        raise FileNotFoundError(pdf_path)

    output_dir = Path(args.output_dir) if args.output_dir else OUTPUT_ROOT / f"{pdf_path.stem}_page_{args.page:03d}"
    report = run_eval(
        pdf_path,
        args.page,
        args.dpi,
        output_dir,
        run_vision=args.run_vision,
        vision_model=args.vision_model,
    )

    print(f"PDF: {report['pdf_path']}")
    print(f"Output: {report['output_dir']}")
    print(f"PyMuPDF: chars={report['pymupdf']['char_count']}, blocks={report['pymupdf']['block_count']}")
    print(f"Pix2Text: {report['pix2text']['status']}, chars={report['pix2text']['char_count']}")
    if report["pix2text"]["error"]:
        print(f"Pix2Text error: {report['pix2text']['error'][:500]}")
    print(
        "MiMoAI Vision: {status}, chars={chars}".format(
            status=report["mimo_vision"]["status"],
            chars=report["mimo_vision"]["char_count"],
        )
    )
    if report["mimo_vision"]["error"]:
        print(f"MiMoAI Vision error: {report['mimo_vision']['error'][:500]}")
    print(f"PyMuPDF text: {report['pymupdf_text_path']}")
    print(f"Pix2Text markdown: {report['pix2text_markdown_path']}")
    print(f"MiMoAI Vision markdown: {report['mimo_vision_markdown_path']}")
    print(f"Comparison: {report['comparison_path']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

from io import BytesIO

from reportlab.lib.styles import getSampleStyleSheet
from reportlab.platypus import PageBreak, Paragraph, SimpleDocTemplate


def make_pdf(pages: list[str]) -> bytes:
    buffer = BytesIO()
    document = SimpleDocTemplate(buffer)
    styles = getSampleStyleSheet()
    story = []

    for index, text in enumerate(pages):
        story.append(Paragraph(text, styles["BodyText"]))
        if index < len(pages) - 1:
            story.append(PageBreak())

    document.build(story)
    return buffer.getvalue()

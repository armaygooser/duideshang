from __future__ import annotations

import html
import re
import sys
from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import (
    BaseDocTemplate,
    Frame,
    HRFlowable,
    Image,
    KeepTogether,
    LongTable,
    PageBreak,
    PageTemplate,
    Paragraph,
    Spacer,
    Table,
    TableStyle,
)


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "docs" / "interview-report.md"
SCREENSHOT = ROOT / "docs" / "assets" / "demo-overview.png"

GREEN = colors.HexColor("#176B4D")
GREEN_DARK = colors.HexColor("#123D2E")
GREEN_PALE = colors.HexColor("#EEF6F2")
INK = colors.HexColor("#1D2A24")
MUTED = colors.HexColor("#647169")
LINE = colors.HexColor("#D9E3DD")
AMBER_PALE = colors.HexColor("#FFF7E8")


def register_fonts() -> None:
    pdfmetrics.registerFont(TTFont("Deng", r"C:\Windows\Fonts\Deng.ttf"))
    pdfmetrics.registerFont(TTFont("DengBold", r"C:\Windows\Fonts\Dengb.ttf"))
    pdfmetrics.registerFontFamily(
        "Deng", normal="Deng", bold="DengBold", italic="Deng", boldItalic="DengBold"
    )


def inline_markup(text: str) -> str:
    escaped = html.escape(text.strip())
    escaped = re.sub(
        r"\[([^\]]+)\]\((https?://[^)]+)\)",
        r'<link href="\2" color="#176B4D"><u>\1</u></link>',
        escaped,
    )
    escaped = re.sub(
        r"&lt;(https?://[^&]+)&gt;",
        r'<link href="\1" color="#176B4D"><u>\1</u></link>',
        escaped,
    )
    escaped = re.sub(r"\*\*([^*]+)\*\*", r"<b>\1</b>", escaped)
    escaped = re.sub(r"`([^`]+)`", r'<font name="DengBold">\1</font>', escaped)
    return escaped


def styles() -> dict[str, ParagraphStyle]:
    base = getSampleStyleSheet()
    return {
        "body": ParagraphStyle(
            "BodyCN",
            parent=base["BodyText"],
            fontName="Deng",
            fontSize=10.2,
            leading=16.2,
            textColor=INK,
            spaceAfter=7,
            wordWrap="CJK",
        ),
        "h2": ParagraphStyle(
            "H2CN",
            parent=base["Heading2"],
            fontName="DengBold",
            fontSize=16,
            leading=21,
            textColor=GREEN_DARK,
            spaceBefore=15,
            spaceAfter=8,
            keepWithNext=True,
            wordWrap="CJK",
        ),
        "h3": ParagraphStyle(
            "H3CN",
            parent=base["Heading3"],
            fontName="DengBold",
            fontSize=12.3,
            leading=17,
            textColor=GREEN,
            spaceBefore=10,
            spaceAfter=5,
            keepWithNext=True,
            wordWrap="CJK",
        ),
        "bullet": ParagraphStyle(
            "BulletCN",
            parent=base["BodyText"],
            fontName="Deng",
            fontSize=10,
            leading=15.5,
            textColor=INK,
            leftIndent=15,
            firstLineIndent=-9,
            bulletIndent=3,
            spaceAfter=4,
            wordWrap="CJK",
        ),
        "number": ParagraphStyle(
            "NumberCN",
            parent=base["BodyText"],
            fontName="Deng",
            fontSize=10,
            leading=15.5,
            textColor=INK,
            leftIndent=18,
            firstLineIndent=-13,
            spaceAfter=4,
            wordWrap="CJK",
        ),
        "quote": ParagraphStyle(
            "QuoteCN",
            parent=base["BodyText"],
            fontName="DengBold",
            fontSize=11,
            leading=17,
            textColor=GREEN_DARK,
            leftIndent=12,
            rightIndent=8,
            borderColor=GREEN,
            borderWidth=2,
            borderPadding=(8, 10, 8, 10),
            backColor=GREEN_PALE,
            spaceBefore=5,
            spaceAfter=10,
            wordWrap="CJK",
        ),
        "code": ParagraphStyle(
            "CodeCN",
            parent=base["Code"],
            fontName="Deng",
            fontSize=9.3,
            leading=14,
            textColor=GREEN_DARK,
            leftIndent=10,
            rightIndent=10,
            borderColor=LINE,
            borderWidth=0.6,
            borderPadding=8,
            backColor=colors.HexColor("#F7FAF8"),
            spaceBefore=5,
            spaceAfter=10,
            wordWrap="CJK",
        ),
        "small": ParagraphStyle(
            "SmallCN",
            parent=base["BodyText"],
            fontName="Deng",
            fontSize=8.6,
            leading=13,
            textColor=MUTED,
            wordWrap="CJK",
        ),
        "table": ParagraphStyle(
            "TableCN",
            parent=base["BodyText"],
            fontName="Deng",
            fontSize=8.4,
            leading=12.2,
            textColor=INK,
            wordWrap="CJK",
        ),
        "table_head": ParagraphStyle(
            "TableHeadCN",
            parent=base["BodyText"],
            fontName="DengBold",
            fontSize=8.7,
            leading=12.5,
            textColor=colors.white,
            wordWrap="CJK",
        ),
    }


class ReportDoc(BaseDocTemplate):
    def __init__(self, filename: str):
        super().__init__(
            filename,
            pagesize=A4,
            leftMargin=18 * mm,
            rightMargin=18 * mm,
            topMargin=19 * mm,
            bottomMargin=18 * mm,
            title="对得上 - FDE 面试项目报告",
            author="吴林斌",
            subject="AI 协作、问题定义与工程交付过程",
        )
        frame = Frame(
            self.leftMargin,
            self.bottomMargin,
            self.width,
            self.height,
            id="normal",
            leftPadding=0,
            rightPadding=0,
            topPadding=0,
            bottomPadding=0,
        )
        self.addPageTemplates(PageTemplate(id="main", frames=[frame], onPage=self._page))

    def _page(self, canvas, doc) -> None:
        if doc.page == 1:
            return
        canvas.saveState()
        canvas.setStrokeColor(LINE)
        canvas.setLineWidth(0.5)
        canvas.line(18 * mm, A4[1] - 12 * mm, A4[0] - 18 * mm, A4[1] - 12 * mm)
        canvas.setFont("Deng", 8)
        canvas.setFillColor(MUTED)
        canvas.drawString(18 * mm, A4[1] - 9.5 * mm, "对得上 | FDE 面试项目报告")
        canvas.drawRightString(A4[0] - 18 * mm, 10 * mm, f"{doc.page}")
        canvas.restoreState()


def cover(st: dict[str, ParagraphStyle]) -> list:
    flow = [Spacer(1, 9 * mm)]
    title = ParagraphStyle(
        "CoverTitle",
        fontName="DengBold",
        fontSize=30,
        leading=38,
        textColor=GREEN_DARK,
        alignment=TA_LEFT,
        wordWrap="CJK",
    )
    subtitle = ParagraphStyle(
        "CoverSubtitle",
        fontName="Deng",
        fontSize=14,
        leading=22,
        textColor=MUTED,
        wordWrap="CJK",
    )
    flow.append(Paragraph("对得上", title))
    flow.append(Paragraph("需求澄清、确认、透明报价与验收闭环", subtitle))
    flow.append(Spacer(1, 7 * mm))
    lead = Table(
        [[
            Paragraph("<b>FDE 面试项目报告</b><br/>吴林斌（armaygooser）", st["body"]),
            Paragraph("从 10 个候选问题到可运行产品<br/>记录人与 AI 的真实协作过程", st["body"]),
        ]],
        colWidths=[78 * mm, 90 * mm],
    )
    lead.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, -1), GREEN_PALE),
                ("BOX", (0, 0), (-1, -1), 0.8, LINE),
                ("INNERGRID", (0, 0), (-1, -1), 0.5, LINE),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("LEFTPADDING", (0, 0), (-1, -1), 12),
                ("RIGHTPADDING", (0, 0), (-1, -1), 12),
                ("TOPPADDING", (0, 0), (-1, -1), 10),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 10),
            ]
        )
    )
    flow.append(lead)
    flow.append(Spacer(1, 8 * mm))
    if SCREENSHOT.exists():
        image = Image(str(SCREENSHOT), width=174 * mm, height=105 * mm)
        flow.append(image)
    flow.append(Spacer(1, 5 * mm))
    link_style = ParagraphStyle(
        "CoverLinks",
        fontName="Deng",
        fontSize=9.5,
        leading=15,
        textColor=GREEN,
        alignment=TA_CENTER,
    )
    flow.append(
        Paragraph(
            '<link href="https://armaygooser.site"><u>armaygooser.site</u></link>　·　'
            '<link href="https://github.com/armaygooser/duideshang"><u>GitHub</u></link>',
            link_style,
        )
    )
    flow.append(PageBreak())
    return flow


def overview(st: dict[str, ParagraphStyle]) -> list:
    flow = [Paragraph("一页速览", st["h2"])]
    cards = [
        ("问题", "客户口语存在歧义，商家默认理解可能在交付时造成返工。"),
        ("方案", "引用原话、逐项澄清、确认后报价，并生成交付边界与验收标准。"),
        ("关键转折", "从“快速报价”转向“需求对齐”，不让 AI 替客户做决定。"),
        ("AI 协作", "AI 参与检索、反驳、规格、编码和验证；人负责目标、约束与验收。"),
        ("工程结果", "Next.js + FastAPI，可选 DeepSeek、本地降级、确定性报价与自动化测试。"),
        ("真实性边界", "演示价目未经过真实门店核价，不虚构访谈、转化率或节省时间。"),
    ]
    rows = []
    for i in range(0, len(cards), 2):
        row = []
        for label, body in cards[i : i + 2]:
            row.append(
                Paragraph(
                    f'<font name="DengBold" color="#176B4D">{label}</font><br/>{body}',
                    st["body"],
                )
            )
        rows.append(row)
    table = Table(rows, colWidths=[84 * mm, 84 * mm], hAlign="LEFT")
    table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, -1), colors.white),
                ("BOX", (0, 0), (-1, -1), 0.7, LINE),
                ("INNERGRID", (0, 0), (-1, -1), 0.5, LINE),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("LEFTPADDING", (0, 0), (-1, -1), 10),
                ("RIGHTPADDING", (0, 0), (-1, -1), 10),
                ("TOPPADDING", (0, 0), (-1, -1), 9),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 9),
            ]
        )
    )
    flow.extend([table, Spacer(1, 5 * mm)])
    flow.append(Paragraph("建议阅读路径", st["h3"]))
    flow.append(
        Paragraph(
            "如果时间有限，优先阅读第二至六节：候选方向筛选、问题重定义、人与 AI 的协作过程，以及双方职责边界。技术实现、结果与局限位于后半部分。",
            st["body"],
        )
    )
    flow.append(PageBreak())
    return flow


def make_table(lines: list[str], st: dict[str, ParagraphStyle]) -> LongTable:
    rows: list[list[Paragraph]] = []
    for row_index, line in enumerate(lines):
        cells = [cell.strip() for cell in line.strip().strip("|").split("|")]
        if row_index == 1 and all(re.fullmatch(r":?-{3,}:?", cell) for cell in cells):
            continue
        style = st["table_head"] if not rows else st["table"]
        rows.append([Paragraph(inline_markup(cell), style) for cell in cells])
    widths = [43 * mm, 57 * mm, 68 * mm] if len(rows[0]) == 3 else [84 * mm, 84 * mm]
    table = LongTable(rows, colWidths=widths, repeatRows=1, hAlign="LEFT")
    commands = [
        ("BACKGROUND", (0, 0), (-1, 0), GREEN_DARK),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("BOX", (0, 0), (-1, -1), 0.7, LINE),
        ("INNERGRID", (0, 0), (-1, -1), 0.4, LINE),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 6),
        ("RIGHTPADDING", (0, 0), (-1, -1), 6),
        ("TOPPADDING", (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
    ]
    for idx in range(1, len(rows)):
        if idx % 2 == 0:
            commands.append(("BACKGROUND", (0, idx), (-1, idx), colors.HexColor("#F7FAF8")))
    table.setStyle(TableStyle(commands))
    return table


def markdown_flow(st: dict[str, ParagraphStyle]) -> list:
    lines = SOURCE.read_text(encoding="utf-8").splitlines()
    flow: list = []
    paragraph: list[str] = []
    code: list[str] = []
    in_code = False
    index = 0

    def flush_paragraph() -> None:
        if paragraph:
            text = "".join(part.strip() for part in paragraph)
            if text:
                flow.append(Paragraph(inline_markup(text), st["body"]))
            paragraph.clear()

    while index < len(lines):
        line = lines[index]
        stripped = line.strip()
        if stripped.startswith("```"):
            flush_paragraph()
            if in_code:
                flow.append(Paragraph("<br/>".join(html.escape(x) for x in code), st["code"]))
                code.clear()
            in_code = not in_code
            index += 1
            continue
        if in_code:
            code.append(line)
            index += 1
            continue
        if stripped.startswith("# "):
            flush_paragraph()
            index += 1
            while index < len(lines) and (
                lines[index].startswith("**") or not lines[index].strip()
            ):
                index += 1
            continue
        if stripped.startswith("## "):
            flush_paragraph()
            flow.append(Paragraph(inline_markup(stripped[3:]), st["h2"]))
        elif stripped.startswith("### "):
            flush_paragraph()
            flow.append(Paragraph(inline_markup(stripped[4:]), st["h3"]))
        elif stripped.startswith("> "):
            flush_paragraph()
            quote_lines = [stripped[2:]]
            while index + 1 < len(lines) and lines[index + 1].strip().startswith("> "):
                index += 1
                quote_lines.append(lines[index].strip()[2:])
            flow.append(Paragraph(inline_markup(" ".join(quote_lines)), st["quote"]))
        elif stripped.startswith("| "):
            flush_paragraph()
            table_lines = [line]
            while index + 1 < len(lines) and lines[index + 1].strip().startswith("|"):
                index += 1
                table_lines.append(lines[index])
            flow.extend([make_table(table_lines, st), Spacer(1, 4 * mm)])
        elif re.match(r"^- ", stripped):
            flush_paragraph()
            flow.append(Paragraph("• " + inline_markup(stripped[2:]), st["bullet"]))
        elif re.match(r"^\d+\. ", stripped):
            flush_paragraph()
            match = re.match(r"^(\d+)\. (.*)", stripped)
            flow.append(
                Paragraph(f"{match.group(1)}. {inline_markup(match.group(2))}", st["number"])
            )
        elif not stripped:
            flush_paragraph()
        else:
            paragraph.append(line)
        index += 1
    flush_paragraph()
    return flow


def build(output: Path) -> None:
    register_fonts()
    st = styles()
    output.parent.mkdir(parents=True, exist_ok=True)
    doc = ReportDoc(str(output))
    story = cover(st) + overview(st) + markdown_flow(st)
    story.append(Spacer(1, 5 * mm))
    story.append(HRFlowable(width="100%", thickness=0.6, color=LINE))
    story.append(Spacer(1, 3 * mm))
    story.append(
        Paragraph(
            "本报告记录的是面试原型的真实探索与工程过程。市场判断仍需通过真实用户访谈和业务数据验证。",
            st["small"],
        )
    )
    doc.build(story)


if __name__ == "__main__":
    destination = Path(sys.argv[1]) if len(sys.argv) > 1 else ROOT / "output" / "pdf" / "对得上_项目报告_吴林斌.pdf"
    build(destination)
    print(destination)

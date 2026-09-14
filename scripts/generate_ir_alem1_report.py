"""Generate the IR ALÉM 1 report (generative AI clinical extraction).

Same visual system as ``generate_report.py``. The JSON example printed in the
document is produced by the real ``MockClinicalExtractor`` at build time, so
the report can never drift from the code. Run from the project root:

    python scripts/generate_ir_alem1_report.py
"""

from __future__ import annotations

import argparse
from collections import Counter
from io import BytesIO
import json
from pathlib import Path
import sys
import textwrap

from reportlab.graphics.shapes import Drawing, Line, Polygon, Rect, String
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import (
    KeepTogether,
    PageBreak,
    Paragraph,
    Preformatted,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.backend.clinical_extractor import (  # noqa: E402 - after sys.path setup
    COT_STEPS,
    DEFAULT_MODEL,
    FEW_SHOT_EXAMPLES,
    SYSTEM_PROMPT,
    MockClinicalExtractor,
)

DEFAULT_OUTPUT = ROOT / "output" / "pdf" / "ir-alem-1-extracao-clinica.pdf"
EVIDENCE_PATH = ROOT / "document" / "ir-alem-1-evidencia-llm.json"
REPORT_DATE = "14/09/2026"

INK = colors.HexColor("#173E3F")
MUTED = colors.HexColor("#5E7474")
TEAL = colors.HexColor("#0B706F")
TEAL_DARK = colors.HexColor("#074D4E")
TEAL_PALE = colors.HexColor("#E7F4F1")
CORAL = colors.HexColor("#E86D65")
CORAL_PALE = colors.HexColor("#FFF0EE")
LINE = colors.HexColor("#D7E5E1")
CODE_BG = colors.HexColor("#F3F7F6")
WHITE = colors.white

EXAMPLE_INPUT = (
    "Acordei ontem à noite com uma dor forte no peito, tipo um aperto. "
    "Suei muito frio. Durou uns 30 minutos e achei que ia morrer."
)


def register_fonts() -> tuple[str, str, str]:
    fonts_dir = Path(r"C:\Windows\Fonts")
    regular, bold, mono = fonts_dir / "arial.ttf", fonts_dir / "arialbd.ttf", fonts_dir / "consola.ttf"
    italic, bold_italic = fonts_dir / "ariali.ttf", fonts_dir / "arialbi.ttf"
    text_fonts = ("Helvetica", "Helvetica-Bold")
    mono_font = "Courier"
    if regular.is_file() and bold.is_file():
        pdfmetrics.registerFont(TTFont("CardioRegular", str(regular)))
        pdfmetrics.registerFont(TTFont("CardioBold", str(bold)))
        pdfmetrics.registerFont(TTFont("CardioItalic", str(italic if italic.is_file() else regular)))
        pdfmetrics.registerFont(TTFont("CardioBoldItalic", str(bold_italic if bold_italic.is_file() else bold)))
        # Lets <b> and <i> inside paragraphs switch to the real bold/italic faces.
        pdfmetrics.registerFontFamily(
            "CardioRegular",
            normal="CardioRegular",
            bold="CardioBold",
            italic="CardioItalic",
            boldItalic="CardioBoldItalic",
        )
        text_fonts = ("CardioRegular", "CardioBold")
    if mono.is_file():
        pdfmetrics.registerFont(TTFont("CardioMono", str(mono)))
        mono_font = "CardioMono"
    return text_fonts[0], text_fonts[1], mono_font


FONT, FONT_BOLD, FONT_MONO = register_fonts()


def styles():
    sheet = getSampleStyleSheet()
    add = sheet.add
    add(ParagraphStyle(name="ReportTitle", parent=sheet["Title"], fontName=FONT_BOLD, fontSize=22, leading=25, textColor=TEAL_DARK, alignment=TA_LEFT, spaceAfter=4))
    add(ParagraphStyle(name="ReportSubtitle", parent=sheet["Normal"], fontName=FONT, fontSize=9.3, leading=13, textColor=MUTED, spaceAfter=10))
    add(ParagraphStyle(name="Section", parent=sheet["Heading2"], fontName=FONT_BOLD, fontSize=12, leading=15, textColor=TEAL_DARK, spaceBefore=9, spaceAfter=5))
    add(ParagraphStyle(name="Body", parent=sheet["BodyText"], fontName=FONT, fontSize=8.6, leading=12, textColor=INK, spaceAfter=5))
    add(ParagraphStyle(name="Small", parent=sheet["BodyText"], fontName=FONT, fontSize=7.4, leading=9.8, textColor=INK))
    add(ParagraphStyle(name="SmallMuted", parent=sheet["BodyText"], fontName=FONT, fontSize=7.2, leading=9.6, textColor=MUTED))
    add(ParagraphStyle(name="SmallBold", parent=sheet["BodyText"], fontName=FONT_BOLD, fontSize=7.4, leading=9.8, textColor=INK))
    add(ParagraphStyle(name="HeaderCell", parent=sheet["BodyText"], fontName=FONT_BOLD, fontSize=7.4, leading=9.8, textColor=WHITE))
    add(ParagraphStyle(name="Callout", parent=sheet["BodyText"], fontName=FONT_BOLD, fontSize=8.3, leading=11.4, textColor=colors.HexColor("#7A3733")))
    add(ParagraphStyle(name="CenterSmall", parent=sheet["BodyText"], fontName=FONT_BOLD, fontSize=7.1, leading=9, textColor=INK, alignment=TA_CENTER))
    add(ParagraphStyle(name="CodeBlock", parent=sheet["Code"], fontName=FONT_MONO, fontSize=6.9, leading=8.9, textColor=INK, leftIndent=0))
    add(ParagraphStyle(name="CodeBlockSmall", parent=sheet["Code"], fontName=FONT_MONO, fontSize=6.4, leading=8.2, textColor=INK, leftIndent=0))
    add(ParagraphStyle(name="InlineCode", parent=sheet["BodyText"], fontName=FONT_MONO, fontSize=7.2, leading=9.6, textColor=INK))
    return sheet


def cell(text: str, style) -> Paragraph:
    return Paragraph(text, style)


def make_table(rows, widths, style, *, header=True, paddings=(5, 4), zebra=True) -> Table:
    """All cells become Paragraphs so text wraps and inline markup renders."""

    body_style, head_style = style["Small"], style["HeaderCell"]
    data = []
    for row_index, row in enumerate(rows):
        row_style = head_style if header and row_index == 0 else body_style
        data.append([item if isinstance(item, (Paragraph, Table, Preformatted)) else cell(str(item), row_style) for item in row])

    table = Table(data, colWidths=widths, repeatRows=1 if header else 0, hAlign="LEFT")
    commands = [
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), paddings[0]),
        ("RIGHTPADDING", (0, 0), (-1, -1), paddings[0]),
        ("TOPPADDING", (0, 0), (-1, -1), paddings[1]),
        ("BOTTOMPADDING", (0, 0), (-1, -1), paddings[1]),
        ("GRID", (0, 0), (-1, -1), 0.45, LINE),
    ]
    if zebra:
        commands.append(("ROWBACKGROUNDS", (0, 1 if header else 0), (-1, -1), [WHITE, colors.HexColor("#F6FAF8")]))
    if header:
        commands.append(("BACKGROUND", (0, 0), (-1, 0), TEAL_DARK))
    table.setStyle(TableStyle(commands))
    return table


def wrap_code(text: str, width: int = 118) -> str:
    """Preformatted never wraps; fold long lines with a hanging indent instead."""

    lines = []
    for line in text.splitlines():
        indent = len(line) - len(line.lstrip(" "))
        wrapped = textwrap.wrap(
            line,
            width=width,
            subsequent_indent=" " * (indent + 4),
            break_long_words=False,
            break_on_hyphens=False,
            drop_whitespace=False,
        )
        lines.extend(wrapped or [""])
    return "\n".join(lines)


def code_block(text: str, style, width: float, *, small: bool = False) -> Table:
    code_style = style["CodeBlockSmall"] if small else style["CodeBlock"]
    block = Table([[Preformatted(wrap_code(text, 126 if small else 118), code_style)]], colWidths=[width], hAlign="LEFT")
    block.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, -1), CODE_BG),
                ("BOX", (0, 0), (-1, -1), 0.6, LINE),
                ("LEFTPADDING", (0, 0), (-1, -1), 8),
                ("RIGHTPADDING", (0, 0), (-1, -1), 8),
                ("TOPPADDING", (0, 0), (-1, -1), 6),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
            ]
        )
    )
    return block


def callout(label: str, text: str, style) -> Table:
    table = Table(
        [[cell(label, style["SmallBold"]), cell(text, style["Callout"])]],
        colWidths=[37 * mm, 137 * mm],
        hAlign="LEFT",
    )
    table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, -1), CORAL_PALE),
                ("BOX", (0, 0), (-1, -1), 0.8, colors.HexColor("#F2C1BD")),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("LEFTPADDING", (0, 0), (-1, -1), 7),
                ("RIGHTPADDING", (0, 0), (-1, -1), 7),
                ("TOPPADDING", (0, 0), (-1, -1), 7),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 7),
            ]
        )
    )
    return table


def tag_row(style) -> Table:
    tags = ["FLASK", "CHAT COMPLETIONS (OPENAI-COMPATÍVEL)", "JSON MODE", "FEW-SHOT + CHAIN-OF-THOUGHT"]
    widths = [24 * mm, 64 * mm, 28 * mm, 58 * mm]
    table = Table([[cell(tag, style["CenterSmall"]) for tag in tags]], colWidths=widths, hAlign="LEFT")
    table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, -1), TEAL_PALE),
                ("BOX", (0, 0), (-1, -1), 0.6, LINE),
                ("INNERGRID", (0, 0), (-1, -1), 2, WHITE),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("TOPPADDING", (0, 0), (-1, -1), 4),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
            ]
        )
    )
    return table


def flow_drawing() -> Drawing:
    drawing = Drawing(492, 70)
    steps = [
        ("TEXTO LIVRE", "relato fictício"),
        ("PROMPT", "system + few-shot + CoT"),
        ("MODELO", "JSON mode, T = 0.2"),
        ("VALIDAÇÃO", "faixas, enum, defaults"),
        ("JSON", "severidade + entidades"),
    ]
    box_w, box_h, gap, y = 86, 46, 15.5, 12
    for index, (title, detail) in enumerate(steps):
        x = index * (box_w + gap)
        dark = index in (0, 4)
        drawing.add(Rect(x, y, box_w, box_h, rx=8, ry=8, fillColor=TEAL_DARK if dark else TEAL_PALE, strokeColor=TEAL if dark else LINE, strokeWidth=0.8))
        drawing.add(String(x + box_w / 2, y + 27, title, fontName=FONT_BOLD, fontSize=7.6, fillColor=WHITE if dark else TEAL_DARK, textAnchor="middle"))
        drawing.add(String(x + box_w / 2, y + 14, detail, fontName=FONT, fontSize=6.4, fillColor=colors.HexColor("#CBE7E2") if dark else MUTED, textAnchor="middle"))
        if index < len(steps) - 1:
            start, end, mid_y = x + box_w + 3, x + box_w + gap - 3, y + box_h / 2
            drawing.add(Line(start, mid_y, end, mid_y, strokeColor=CORAL, strokeWidth=1.4))
            drawing.add(Polygon([end, mid_y, end - 5, mid_y + 3, end - 5, mid_y - 3], fillColor=CORAL, strokeColor=CORAL))
    return drawing


def compact_json(payload: dict) -> str:
    """One top-level key per line; each entity on a single line to save height."""

    lines = ["{"]
    keys = list(payload)
    for index, key in enumerate(keys):
        comma = "," if index < len(keys) - 1 else ""
        value = payload[key]
        if key == "entities" and isinstance(value, list):
            if not value:
                lines.append(f'  "{key}": []{comma}')
                continue
            lines.append(f'  "{key}": [')
            for item_index, item in enumerate(value):
                item_comma = "," if item_index < len(value) - 1 else ""
                lines.append(f"    {json.dumps(item, ensure_ascii=False)}{item_comma}")
            lines.append(f"  ]{comma}")
        else:
            lines.append(f'  "{key}": {json.dumps(value, ensure_ascii=False)}{comma}')
    lines.append("}")
    return "\n".join(lines)


def load_evidence() -> dict | None:
    """Real OpenAI outputs saved by ``demo_clinical_extractor.py --real --save``."""

    if not EVIDENCE_PATH.is_file():
        return None
    data = json.loads(EVIDENCE_PATH.read_text(encoding="utf-8"))
    if data.get("mode") not in {"llm", "openai"} or not data.get("scenarios"):
        return None
    return data


def format_date(iso_date: str) -> str:
    try:
        year, month, day = iso_date.split("-")
        return f"{day}/{month}/{year}"
    except ValueError:
        return iso_date


def example_section(style, width: float) -> list:
    """Real model output when evidence exists; otherwise the deterministic mock."""

    evidence = load_evidence()
    if evidence:
        first = evidence["scenarios"][0]
        note = (
            "Saída real do modelo <b>%s</b> (provedor %s) em %s, gravada por <font face='%s'>python scripts/demo_clinical_extractor.py --real --save</font> "
            "em <font face='%s'>document/ir-alem-1-evidencia-llm.json</font>. Sem chave, o mesmo comando devolve o esquema idêntico no modo de simulação."
            % (evidence["model"], evidence.get("provider", "?"), format_date(evidence["date"]), FONT_MONO, FONT_MONO)
        )
        text, payload = first["input"], first["output"]
    else:
        note = (
            "Saída gerada no momento da compilação deste PDF pelo modo de simulação, reproduzível com "
            "<font face='%s'>python scripts/demo_clinical_extractor.py</font>. O modo com modelo real devolve exatamente o mesmo esquema." % FONT_MONO
        )
        text, payload = EXAMPLE_INPUT, MockClinicalExtractor().extract(EXAMPLE_INPUT).to_dict()

    return [
        Paragraph("Exemplo reproduzível", style["Section"]),
        Paragraph("Entrada fictícia: <i>\"%s\"</i>" % text, style["Body"]),
        code_block(compact_json(payload), style, width),
        Paragraph(note, style["SmallMuted"]),
    ]


def evidence_section(style) -> list:
    """Compact table with every real scenario; empty when there is no evidence."""

    evidence = load_evidence()
    if not evidence:
        return []
    rows = [["Cenário", "Nível", "Int.", "Conf.", "Sintoma extraído", "Entidades por tipo"]]
    for scenario in evidence["scenarios"]:
        output = scenario["output"]
        counts = Counter(entity["type"] for entity in output.get("entities", []))
        entities = ", ".join(f"{count} {kind}" for kind, count in counts.items()) or "-"
        rows.append(
            [
                scenario["title"],
                output["alert_severity"],
                str(output["intensity"]),
                f"{output['confidence']:.2f}",
                output["symptom"],
                entities,
            ]
        )
    return [
        KeepTogether(
            [
                Paragraph("Evidência de execução real", style["Section"]),
                Paragraph(
                    "Cenários da demo enviados ao modelo <b>%s</b> (provedor %s) em %s; JSON completo em "
                    "<font face='%s'>document/ir-alem-1-evidencia-llm.json</font>. O provedor foi usado só nesta verificação: qualquer API "
                    "compatível serve, trocando <font face='%s'>LLM_BASE_URL</font> e <font face='%s'>LLM_MODEL</font>."
                    % (evidence["model"], evidence.get("provider", "?"), format_date(evidence["date"]), FONT_MONO, FONT_MONO, FONT_MONO),
                    style["Body"],
                ),
                make_table(rows, [52 * mm, 16 * mm, 9 * mm, 11 * mm, 44 * mm, 42 * mm], style, paddings=(4, 3)),
            ]
        ),
    ]


def few_shot_block() -> str:
    example = FEW_SHOT_EXAMPLES[1]
    return f'Texto: "{example["input"]}"\nSaída JSON:\n{compact_json(example["output"])}'


def on_page_factory(total_pages: int):
    def on_page(canvas, doc):
        width, height = A4
        canvas.saveState()
        canvas.setFillColor(TEAL_DARK)
        canvas.rect(0, height - 13 * mm, width, 13 * mm, fill=1, stroke=0)
        canvas.setFillColor(WHITE)
        canvas.setFont(FONT_BOLD, 8)
        canvas.drawString(18 * mm, height - 8.2 * mm, "FIAP  |  CARDIOIA ACOLHE")
        canvas.setFont(FONT, 7)
        canvas.drawRightString(width - 18 * mm, height - 8.2 * mm, "IR ALÉM 1 · IA GENERATIVA E EXTRAÇÃO CLÍNICA")
        canvas.setStrokeColor(LINE)
        canvas.line(18 * mm, 13 * mm, width - 18 * mm, 13 * mm)
        canvas.setFillColor(MUTED)
        canvas.setFont(FONT, 6.7)
        canvas.drawString(18 * mm, 8.5 * mm, f"Grupo 7 · Fase 5 - Capítulo 1 · {REPORT_DATE}")
        canvas.drawRightString(width - 18 * mm, 8.5 * mm, f"{doc.page}/{total_pages}")
        canvas.restoreState()

    return on_page


def build_story(style) -> list:
    content_width = 174 * mm
    cot = "".join(f"<br/>{index}. {step}" for index, step in enumerate(COT_STEPS, start=1))

    return [
        Spacer(1, 4),
        Paragraph("CardioIA Acolhe - IR ALÉM 1", style["ReportTitle"]),
        Paragraph("IA generativa aplicada à extração de informações clínicas a partir de texto livre", style["ReportSubtitle"]),
        tag_row(style),
        Spacer(1, 8),
        Paragraph("Objetivo", style["Section"]),
        Paragraph(
            "O IR ALÉM 1 expande o assistente para <b>interpretar relatos clínicos não estruturados</b>: uma pessoa escreve "
            "livremente o que sente e um modelo de linguagem devolve a mesma informação <b>organizada em JSON</b> - sintoma, "
            "intensidade de 0 a 10, duração, contexto, entidades nomeadas, nível de alerta e confiança. O módulo é um serviço "
            "Python independente (<font face='%s'>src/backend/clinical_extractor.py</font>), exposto pela API Flask e "
            "integrado ao fluxo conversacional do Watson Assistant já entregue na Parte 1." % FONT_MONO,
            style["Body"],
        ),
        callout(
            "LIMITES CLÍNICOS",
            "O modelo apenas extrai e organiza o que foi relatado: não diagnostica, não prescreve e não recomenda medicamentos. "
            "A orientação de emergência (SAMU 192) é decidida pelo backend a partir do nível de alerta, nunca pelo modelo. "
            "Todos os textos usados no projeto são fictícios.",
            style,
        ),
        Paragraph("Fluxo de extração", style["Section"]),
        flow_drawing(),
        Paragraph(
            "<b>1.</b> O texto é validado (não vazio, até 2.000 caracteres na API) e normalizado. "
            "<b>2.</b> O backend monta duas mensagens: um <i>system prompt</i> com papel, regras e esquema de saída, e uma mensagem "
            "de usuário com os exemplos <i>few-shot</i>, os passos de raciocínio e o texto a analisar. "
            "<b>3.</b> A API Chat Completions (protocolo da OpenAI, aceito também por Google Gemini, Groq e outros) é chamada com "
            "<font face='%s'>response_format={\"type\": \"json_object\"}</font>, temperatura 0,2 e limite de 4.000 tokens (modelos com raciocínio interno, "
            "como o Gemini 3.x, gastam parte do orçamento antes de escrever o JSON), o que força uma resposta JSON estável. "
            "<b>4.</b> A resposta é convertida e validada: inteiros são limitados a 0-10, confianças a 0,0-1,0, a severidade é "
            "mapeada para um <i>enum</i> e valores ausentes recebem padrões seguros. "
            "<b>5.</b> O objeto <font face='%s'>ClinicalExtraction</font> é serializado e devolvido pela API."
            % (FONT_MONO, FONT_MONO),
            style["Body"],
        ),
        Paragraph("Técnicas de prompting aplicadas", style["Section"]),
        make_table(
            [
                ["Técnica", "Como foi aplicada", "Onde está"],
                [
                    "<b>System prompt com papel e regras</b>",
                    "Define o papel de assistente de PLN clínica, dez regras explícitas (não diagnosticar, escalas numéricas, critérios "
                    "de severidade, valores ausentes) e o esquema JSON esperado.",
                    "SYSTEM_PROMPT",
                ],
                [
                    "<b>Few-shot learning</b>",
                    "Quatro exemplos completos - <i>critical</i>, <i>high</i>, <i>moderate</i> e <i>info</i> - com entidades, "
                    "normalização e justificativa, cobrindo todos os caminhos do fluxo.",
                    "FEW_SHOT_EXAMPLES",
                ],
                [
                    "<b>Chain-of-thought</b>",
                    "Seis passos ordenados que o modelo segue antes de responder; a justificativa fica registrada no campo "
                    "<font face='%s'>reasoning</font>." % FONT_MONO + cot,
                    "COT_STEPS",
                ],
                [
                    "<b>Saída estruturada (JSON mode)</b>",
                    "Temperatura baixa, limite de tokens e <font face='%s'>json_object</font> garantem JSON sintaticamente válido "
                    "em todas as chamadas." % FONT_MONO,
                    "ClinicalExtractor.extract",
                ],
                [
                    "<b>Validação pós-modelo</b>",
                    "Normaliza tipos, faixas, enum de severidade e tipos de entidade; nunca confia cegamente no texto gerado.",
                    "parse_extraction",
                ],
            ],
            [38 * mm, 100 * mm, 36 * mm],
            style,
        ),
        PageBreak(),
        Spacer(1, 4),
        Paragraph("Estrutura da saída", style["ReportTitle"]),
        Paragraph("Um esquema único para o modelo, a validação, a API e os testes", style["ReportSubtitle"]),
        make_table(
            [
                ["Campo", "Tipo", "Descrição"],
                ["symptom", "string", "Sintoma principal relatado ou \"nenhum sintoma relatado\"."],
                ["intensity", "inteiro 0-10", "Intensidade estimada a partir das palavras usadas; 0 quando não há sintoma."],
                ["duration", "string", "Duração ou frequência descrita; \"não informado\" quando ausente."],
                ["context", "string", "Circunstâncias: momento, atividade, sinais associados."],
                ["alert_severity", "enum", "critical, high, moderate, low ou info - decide a ação do backend."],
                ["confidence", "número 0,0-1,0", "Confiança geral do modelo na extração."],
                ["entities", "lista", "Entidades nomeadas: value, type (symptom, medication, condition, duration, context, other), confidence, normalized."],
                ["reasoning", "string", "Justificativa curta produzida pelo passo de chain-of-thought."],
            ],
            [30 * mm, 28 * mm, 116 * mm],
            style,
        ),
        *example_section(style, content_width),
        Paragraph("Integração com o assistente conversacional", style["Section"]),
        make_table(
            [
                ["Método", "Rota", "Contrato essencial"],
                ["POST", "/api/extract", "text → extraction (JSON acima), model e mode. 400 para entrada inválida; 502 se o modelo falhar."],
                ["POST", "/api/chat/clinical", "message + conversationId → mesmo contrato de /api/chat (reply, intent, entities, urgent) mais clinical e source."],
                ["GET", "/api/health", "Inclui clinical.mode (mock ou llm), clinical.provider e clinical.model, sem expor segredos."],
            ],
            [18 * mm, 34 * mm, 122 * mm],
            style,
        ),
        Spacer(1, 4),
        make_table(
            [
                ["Nível de alerta", "Critério", "Comportamento de /api/chat/clinical"],
                ["critical", "Dor torácica com sinais de alerta, falta de ar em repouso, desmaio.", "Responde imediatamente com orientação de emergência (urgent: true) sem consultar o Watson."],
                ["high, moderate, low, info", "Demais relatos, perguntas e saudações.", "O Watson responde e a extração é anexada em clinical; se o Watson não estiver configurado ou falhar, o backend devolve uma resposta educativa local construída a partir da extração."],
            ],
            [34 * mm, 58 * mm, 82 * mm],
            style,
        ),
        PageBreak(),
        Spacer(1, 4),
        Paragraph("Anatomia do prompt", style["ReportTitle"]),
        Paragraph("O que o modelo recebe em cada chamada, exatamente como está no código", style["ReportSubtitle"]),
        Paragraph("Mensagem de sistema (papel, regras e esquema)", style["Section"]),
        code_block(SYSTEM_PROMPT, style, content_width, small=True),
        Paragraph("Mensagem de usuário (few-shot + chain-of-thought + texto)", style["Section"]),
        Paragraph(
            "Montada por <font face='%s'>build_extraction_prompt</font>: os quatro exemplos few-shot no formato abaixo, os seis passos de "
            "raciocínio da página 1 e o texto a analisar entre aspas, encerrando com \"Responda APENAS com o JSON\". Exemplo 2, como enviado:" % FONT_MONO,
            style["Body"],
        ),
        code_block(few_shot_block(), style, content_width, small=True),
        *evidence_section(style),
        PageBreak(),
        Spacer(1, 4),
        Paragraph("Confiabilidade e reprodução", style["ReportTitle"]),
        Paragraph("Falhas seguras, dois modos de execução, comandos de reprodução e testes automatizados", style["ReportSubtitle"]),
        Paragraph("Tratamento de erros e privacidade", style["Section"]),
        make_table(
            [
                ["Situação", "Comportamento"],
                ["Texto vazio ou acima do limite", "ValueError no módulo; 400 na API, antes de qualquer chamada ao modelo."],
                ["Falha de rede, chave inválida ou cota esgotada", "Erro do SDK encapsulado em ClinicalExtractionError com mensagem neutra; 502 em /api/extract; /api/chat/clinical segue com o Watson."],
                ["Resposta não JSON, vazia ou com estrutura errada", "Mesmo tratamento seguro; o conteúdo bruto nunca é devolvido ao cliente."],
                ["Campos ausentes ou fora da faixa", "Padrões seguros (intensidade 0, confiança 0,5, severidade moderate) e limites aplicados."],
                ["Privacidade", "Nenhum texto clínico, resposta do modelo ou credencial é registrado em log; o campo raw_model_output não sai da API; chave apenas em .env ignorado pelo git."],
            ],
            [58 * mm, 116 * mm],
            style,
        ),
        Paragraph("Modos de execução", style["Section"]),
        make_table(
            [
                ["Modo", "Quando é usado", "Características"],
                ["mock", "Sem LLM_API_KEY (padrão em testes e CI).", "Simulação determinística por palavras-chave com o mesmo esquema e as mesmas regras de severidade; sem rede e sem custo."],
                [
                    "llm",
                    "Com LLM_API_KEY no .env.",
                    "Chat Completions no provedor de LLM_BASE_URL e modelo de LLM_MODEL (padrão %s); JSON mode, temperatura 0,2, "
                    "timeout 20 s. Verificado com o Google Gemini (free tier) apenas por conveniência: OpenAI, Groq ou qualquer API "
                    "compatível funcionam sem alterar código." % DEFAULT_MODEL,
                ],
            ],
            [16 * mm, 44 * mm, 114 * mm],
            style,
        ),
        Paragraph("Como executar", style["Section"]),
        code_block(
            "\n".join(
                [
                    "python -m venv .venv; .\\.venv\\Scripts\\Activate.ps1",
                    "python -m pip install -r requirements.txt",
                    "Copy-Item .env.example .env        # opcional: LLM_API_KEY (+ LLM_BASE_URL / LLM_MODEL)",
                    "python scripts/demo_clinical_extractor.py            # 4 cenários no modo mock",
                    "python scripts/demo_clinical_extractor.py --real     # usa o provedor do .env (Gemini, OpenAI...)",
                    "python scripts/demo_clinical_extractor.py --real --save document/ir-alem-1-evidencia-llm.json",
                    "python -m src.backend                                # API em http://127.0.0.1:5000",
                    "curl -X POST http://127.0.0.1:5000/api/extract -H \"Content-Type: application/json\" `",
                    "     -d '{\"text\": \"Falta de ar ao subir escadas, uns 10 minutos\"}'",
                ]
            ),
            style,
            content_width,
        ),
        Paragraph("Testes automatizados", style["Section"]),
        make_table(
            [
                ["Arquivo", "Testes", "Cobertura"],
                ["tests/backend/test_clinical_extractor.py", "51", "Conteúdo do prompt, exemplos few-shot, parsing e limites, extrator real com cliente falso, provedores, mock e fábricas."],
                ["tests/backend/test_clinical_api.py", "23", "/api/extract e /api/chat/clinical: validação, severidade crítica, anexo ao Watson, degradação sem Watson, erros 502/503 sem vazamento."],
                ["Suíte original (API, gateway e export)", "42", "Inalterada; o health passou a informar o modo do extrator."],
                ["<b>Total</b>", "<b>116</b>", "<b>116/116 aprovados em %s com Python 3.11.9</b>" % REPORT_DATE],
            ],
            [62 * mm, 16 * mm, 96 * mm],
            style,
        ),
        Paragraph("Limites e próximos passos", style["Section"]),
        Paragraph(
            "O extrator trabalha apenas com texto; imagens simuladas não fazem parte desta entrega. A qualidade com modelo real depende do "
            "provedor escolhido e não foi medida com um conjunto anotado: o critério de aceitação foi o esquema válido e a coerência com as regras "
            "de severidade. Próximos passos: medir precisão em relatos fictícios rotulados, ligar a interface React a "
            "<font face='%s'>/api/chat/clinical</font> e persistir extrações para o IR ALÉM 2." % FONT_MONO,
            style["Body"],
        ),
        Spacer(1, 6),
        Paragraph(
            "<b>Referências.</b> "
            "OpenAI - <link href='https://platform.openai.com/docs/guides/structured-outputs' color='#0B706F'>Structured outputs / JSON mode</link>. "
            "Google - <link href='https://ai.google.dev/gemini-api/docs/openai' color='#0B706F'>Gemini API: OpenAI compatibility</link>. "
            "Brown et al. (2020) - <i>Language Models are Few-Shot Learners</i>. "
            "Wei et al. (2022) - <i>Chain-of-Thought Prompting Elicits Reasoning in Large Language Models</i>. "
            "Ministério da Saúde - <link href='https://www.gov.br/saude/pt-br/composicao/saes/samu-192' color='#0B706F'>SAMU 192</link>.",
            style["SmallMuted"],
        ),
    ]


def build_report(output: Path) -> Path:
    output.parent.mkdir(parents=True, exist_ok=True)
    style = styles()
    metadata = {
        "pagesize": A4,
        "rightMargin": 18 * mm,
        "leftMargin": 18 * mm,
        "topMargin": 19 * mm,
        "bottomMargin": 17 * mm,
        "title": "CardioIA Acolhe - IR ALÉM 1: IA generativa e extração clínica",
        "author": "Grupo 7 - FIAP",
        "subject": "Extração de informações clínicas de texto livre com modelos de linguagem",
    }

    # First pass only counts pages so the footer can show "n/total".
    probe = SimpleDocTemplate(BytesIO(), **metadata)
    probe.build(build_story(style), onFirstPage=on_page_factory(0), onLaterPages=on_page_factory(0))
    total_pages = probe.page

    doc = SimpleDocTemplate(str(output), **metadata)
    on_page = on_page_factory(total_pages)
    doc.build(build_story(style), onFirstPage=on_page, onLaterPages=on_page)
    return output


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    return parser.parse_args()


if __name__ == "__main__":
    print(build_report(parse_args().output.resolve()))

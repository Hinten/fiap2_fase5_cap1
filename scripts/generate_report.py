"""Generate the two-page CardioIA Acolhe technical report.

The PDF is intentionally generated from deterministic content so the academic
deliverable is reproducible without an office suite. Use only verified status
text in the command-line options.
"""

from __future__ import annotations

import argparse
from pathlib import Path

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
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT = ROOT / "output" / "pdf" / "relatorio-cardioia.pdf"

INK = colors.HexColor("#173E3F")
MUTED = colors.HexColor("#5E7474")
TEAL = colors.HexColor("#0B706F")
TEAL_DARK = colors.HexColor("#074D4E")
TEAL_PALE = colors.HexColor("#E7F4F1")
CORAL = colors.HexColor("#E86D65")
CORAL_PALE = colors.HexColor("#FFF0EE")
LINE = colors.HexColor("#D7E5E1")
PAPER = colors.HexColor("#FCFDFC")
WHITE = colors.white


def register_fonts() -> tuple[str, str]:
    regular = Path(r"C:\Windows\Fonts\arial.ttf")
    bold = Path(r"C:\Windows\Fonts\arialbd.ttf")
    if regular.is_file() and bold.is_file():
        pdfmetrics.registerFont(TTFont("CardioRegular", str(regular)))
        pdfmetrics.registerFont(TTFont("CardioBold", str(bold)))
        return "CardioRegular", "CardioBold"
    return "Helvetica", "Helvetica-Bold"


FONT, FONT_BOLD = register_fonts()


def styles():
    sheet = getSampleStyleSheet()
    sheet.add(
        ParagraphStyle(
            name="ReportTitle",
            parent=sheet["Title"],
            fontName=FONT_BOLD,
            fontSize=23,
            leading=26,
            textColor=TEAL_DARK,
            alignment=TA_LEFT,
            spaceAfter=4,
        )
    )
    sheet.add(
        ParagraphStyle(
            name="ReportSubtitle",
            parent=sheet["Normal"],
            fontName=FONT,
            fontSize=9.3,
            leading=13,
            textColor=MUTED,
            spaceAfter=10,
        )
    )
    sheet.add(
        ParagraphStyle(
            name="Section",
            parent=sheet["Heading2"],
            fontName=FONT_BOLD,
            fontSize=12.2,
            leading=15,
            textColor=TEAL_DARK,
            spaceBefore=8,
            spaceAfter=5,
        )
    )
    sheet.add(
        ParagraphStyle(
            name="BodyCompact",
            parent=sheet["BodyText"],
            fontName=FONT,
            fontSize=8.4,
            leading=11.6,
            textColor=INK,
            spaceAfter=4,
        )
    )
    sheet.add(
        ParagraphStyle(
            name="Small",
            parent=sheet["BodyText"],
            fontName=FONT,
            fontSize=7.3,
            leading=9.6,
            textColor=MUTED,
        )
    )
    sheet.add(
        ParagraphStyle(
            name="SmallBold",
            parent=sheet["BodyText"],
            fontName=FONT_BOLD,
            fontSize=7.4,
            leading=9.6,
            textColor=INK,
        )
    )
    sheet.add(
        ParagraphStyle(
            name="Callout",
            parent=sheet["BodyText"],
            fontName=FONT_BOLD,
            fontSize=8.4,
            leading=11.5,
            textColor=colors.HexColor("#7A3733"),
        )
    )
    sheet.add(
        ParagraphStyle(
            name="CenterSmall",
            parent=sheet["BodyText"],
            fontName=FONT_BOLD,
            fontSize=7.2,
            leading=9,
            textColor=INK,
            alignment=TA_CENTER,
        )
    )
    return sheet


def architecture_drawing() -> Drawing:
    drawing = Drawing(500, 72)
    labels = [
        ("PESSOA", "mensagem"),
        ("REACT + VITE", "interface segura"),
        ("FLASK", "validação + sessão"),
        ("WATSON", "Dialog Skill"),
    ]
    box_w, box_h, gap = 105, 48, 25
    y = 13
    for index, (title, detail) in enumerate(labels):
        x = index * (box_w + gap)
        drawing.add(
            Rect(
                x,
                y,
                box_w,
                box_h,
                rx=8,
                ry=8,
                fillColor=TEAL_DARK if index in (0, 3) else TEAL_PALE,
                strokeColor=TEAL if index in (0, 3) else LINE,
                strokeWidth=0.8,
            )
        )
        title_color = WHITE if index in (0, 3) else TEAL_DARK
        detail_color = colors.HexColor("#CBE7E2") if index in (0, 3) else MUTED
        drawing.add(String(x + box_w / 2, y + 29, title, fontName=FONT_BOLD, fontSize=8, fillColor=title_color, textAnchor="middle"))
        drawing.add(String(x + box_w / 2, y + 15, detail, fontName=FONT, fontSize=6.9, fillColor=detail_color, textAnchor="middle"))
        if index < len(labels) - 1:
            start = x + box_w + 4
            end = x + box_w + gap - 5
            mid_y = y + box_h / 2
            drawing.add(Line(start, mid_y, end, mid_y, strokeColor=CORAL, strokeWidth=1.4))
            drawing.add(Polygon([end, mid_y, end - 5, mid_y + 3, end - 5, mid_y - 3], fillColor=CORAL, strokeColor=CORAL))
    return drawing


def make_table(data, widths, *, header=True, font_size=7.2, paddings=(5, 4)) -> Table:
    table = Table(data, colWidths=widths, repeatRows=1 if header else 0, hAlign="LEFT")
    commands = [
        ("FONTNAME", (0, 0), (-1, -1), FONT),
        ("FONTSIZE", (0, 0), (-1, -1), font_size),
        ("LEADING", (0, 0), (-1, -1), font_size + 2.3),
        ("TEXTCOLOR", (0, 0), (-1, -1), INK),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), paddings[0]),
        ("RIGHTPADDING", (0, 0), (-1, -1), paddings[0]),
        ("TOPPADDING", (0, 0), (-1, -1), paddings[1]),
        ("BOTTOMPADDING", (0, 0), (-1, -1), paddings[1]),
        ("GRID", (0, 0), (-1, -1), 0.45, LINE),
        ("ROWBACKGROUNDS", (0, 1 if header else 0), (-1, -1), [WHITE, colors.HexColor("#F6FAF8")]),
    ]
    if header:
        commands.extend(
            [
                ("BACKGROUND", (0, 0), (-1, 0), TEAL_DARK),
                ("TEXTCOLOR", (0, 0), (-1, 0), WHITE),
                ("FONTNAME", (0, 0), (-1, 0), FONT_BOLD),
            ]
        )
    table.setStyle(TableStyle(commands))
    return table


def tag_row(style) -> Table:
    tags = ["FLASK", "REACT/VITE", "WATSON ASSISTANT", "SEM IA GENERATIVA"]
    cells = [Paragraph(tag, style["CenterSmall"]) for tag in tags]
    table = Table([cells], colWidths=[31 * mm, 34 * mm, 43 * mm, 47 * mm], hAlign="LEFT")
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


def on_page(canvas, doc):
    width, height = A4
    canvas.saveState()
    canvas.setFillColor(TEAL_DARK)
    canvas.rect(0, height - 13 * mm, width, 13 * mm, fill=1, stroke=0)
    canvas.setFillColor(WHITE)
    canvas.setFont(FONT_BOLD, 8)
    canvas.drawString(18 * mm, height - 8.2 * mm, "FIAP  |  CARDIOIA ACOLHE")
    canvas.setFont(FONT, 7)
    canvas.drawRightString(width - 18 * mm, height - 8.2 * mm, "RELATÓRIO TÉCNICO · v0.1.0")
    canvas.setStrokeColor(LINE)
    canvas.line(18 * mm, 13 * mm, width - 18 * mm, 13 * mm)
    canvas.setFillColor(MUTED)
    canvas.setFont(FONT, 6.7)
    canvas.drawString(18 * mm, 8.5 * mm, "Grupo 7 · Fase 5 — Capítulo 1 · 12/09/2026")
    canvas.drawRightString(width - 18 * mm, 8.5 * mm, f"{doc.page}/2")
    canvas.restoreState()


def build_report(output: Path, watson_status: str, video_status: str) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    style = styles()
    doc = SimpleDocTemplate(
        str(output),
        pagesize=A4,
        rightMargin=18 * mm,
        leftMargin=18 * mm,
        topMargin=19 * mm,
        bottomMargin=17 * mm,
        title="CardioIA Acolhe — Relatório técnico",
        author="Grupo 7 — FIAP",
        subject="Assistente cardiológico educativo com IBM Watson Assistant",
    )

    story = [
        Spacer(1, 4),
        Paragraph("CardioIA Acolhe", style["ReportTitle"]),
        Paragraph("Assistente conversacional para acolhimento cardiológico educativo", style["ReportSubtitle"]),
        tag_row(style),
        Spacer(1, 8),
        Paragraph("Objetivo", style["Section"]),
        Paragraph(
            "O CardioIA Acolhe organiza um relato fictício de sintomas antes de uma conversa com um profissional. "
            "Em poucos turnos, coleta <b>sintoma, intensidade de 0 a 10 e duração</b>, mantém essas informações no contexto "
            "e devolve um resumo estruturado. O protótipo é determinístico, acadêmico e não persiste conversas em banco de dados.",
            style["BodyCompact"],
        ),
        Table(
            [[Paragraph("SEGURANÇA CLÍNICA", style["SmallBold"]), Paragraph("Não diagnostica, não prescreve e não substitui atendimento. Diante de dor torácica intensa, falta de ar importante, suor frio ou desmaio, orienta emergência ou SAMU 192.", style["Callout"])]],
            colWidths=[37 * mm, 124 * mm],
            style=TableStyle(
                [
                    ("BACKGROUND", (0, 0), (-1, -1), CORAL_PALE),
                    ("BOX", (0, 0), (-1, -1), 0.8, colors.HexColor("#F2C1BD")),
                    ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                    ("LEFTPADDING", (0, 0), (-1, -1), 7),
                    ("RIGHTPADDING", (0, 0), (-1, -1), 7),
                    ("TOPPADDING", (0, 0), (-1, -1), 7),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 7),
                ]
            ),
        ),
        Paragraph("Arquitetura", style["Section"]),
        architecture_drawing(),
        Paragraph(
            "O React renderiza texto de forma segura e usa a API na mesma origem. O Flask valida entradas, oculta credenciais, "
            "normaliza a resposta e usa API V1 Classic/Lite ou V2 quando disponível. Na V1, o contexto é efêmero (TTL de 30 min e até 500 conversas). A Dialog Skill concentra as decisões; nenhum modelo generativo participa do fluxo.",
            style["BodyCompact"],
        ),
        make_table(
            [
                ["Camada", "Responsabilidade", "Evidência no repositório"],
                ["Interface", "Histórico, sugestões, Enter/botão, loading, erros, reset, alerta e painel NLP.", "src/frontend"],
                ["API", "Health, chat e reset; V1/V2; limites; códigos 400/502/503; contexto efêmero.", "src/backend"],
                ["NLU", "7 intents, 3 entidades com sinônimos, @sys-number, contexto e fallback.", "config/watson"],
            ],
            [25 * mm, 92 * mm, 44 * mm],
        ),
        Paragraph("Modelagem NLU e fluxo", style["Section"]),
        Paragraph(
            "Intents: <b>#saudacao, #relatar_sintoma, #sinal_alerta, #preparar_consulta, #limites_assistente, #agradecimento</b> e <b>#despedida</b> (7–8 exemplos cada). "
            "Entidades: <b>@sintoma, @intensidade, @confirmacao</b> e <b>@sys-number</b>. Contexto: <b>$sintoma, $intensidade, $duracao</b>. Dor no peito ou falta de ar com valor a partir de 7/10 aciona o alerta prioritário.",
            style["BodyCompact"],
        ),
        make_table(
            [[
                Paragraph("<b>1</b><br/>Emergência", style["CenterSmall"]),
                Paragraph("<b>2</b><br/>Sintoma", style["CenterSmall"]),
                Paragraph("<b>3</b><br/>Intensidade", style["CenterSmall"]),
                Paragraph("<b>4</b><br/>Duração", style["CenterSmall"]),
                Paragraph("<b>5</b><br/>Resumo", style["CenterSmall"]),
                Paragraph("<b>6</b><br/>Apoio", style["CenterSmall"]),
                Paragraph("<b>7</b><br/>Fallback", style["CenterSmall"]),
            ]],
            [23 * mm] * 7,
            header=False,
            font_size=6.7,
            paddings=(3, 5),
        ),
        PageBreak(),
        Spacer(1, 4),
        Paragraph("Implementação verificável", style["ReportTitle"]),
        Paragraph("Contratos pequenos, respostas rastreáveis e limites explícitos", style["ReportSubtitle"]),
        Paragraph("Contrato da API", style["Section"]),
        make_table(
            [
                ["Método", "Rota", "Contrato essencial"],
                ["GET", "/api/health", "Estado do app e presença da configuração, sem revelar segredos."],
                ["POST", "/api/chat", "message + conversationId → reply, intent, confiança, entidades e urgent."],
                ["POST", "/api/reset", "Encerra/descarta a sessão e devolve conversationId nulo."],
            ],
            [18 * mm, 31 * mm, 112 * mm],
        ),
        Spacer(1, 5),
        Paragraph(
            "Entradas vazias ou acima de 500 caracteres retornam <b>400</b>; configuração ausente, <b>503</b>; falha do Watson, <b>502</b>. "
            "Uma sessão 404/410 é recriada uma única vez. Mensagens clínicas e credenciais não são registradas.",
            style["BodyCompact"],
        ),
        Paragraph("Privacidade, acessibilidade e experiência", style["Section"]),
        make_table(
            [
                [Paragraph("Privacidade por desenho", style["SmallBold"]), Paragraph("Sem banco; .env ignorado; opt-out IBM; uso exclusivo de frases fictícias.", style["Small"])],
                [Paragraph("Interface acessível", style["SmallBold"]), Paragraph("aria-live, rótulos, foco por teclado, contraste, movimento reduzido e layout responsivo.", style["Small"])],
                [Paragraph("Resposta segura", style["SmallBold"]), Paragraph("Renderização de texto pelo React; urgência em destaque; fallback oferece caminhos de retomada.", style["Small"])],
            ],
            [43 * mm, 118 * mm],
            header=False,
        ),
        Paragraph("Testes e resultados", style["Section"]),
        make_table(
            [
                ["Verificação", "Resultado"],
                ["Backend + export Watson", "42/42 testes pytest aprovados em Python 3.14"],
                ["Frontend", "ESLint aprovado; build de produção Vite 8.3 aprovado"],
                ["React → Flask (sem credencial)", "Health, build servido e falha 503 segura conferidos no Chrome"],
                ["React → Flask → Watson", watson_status],
                ["Roteiro e vídeo", video_status],
            ],
            [67 * mm, 94 * mm],
        ),
        Paragraph("Entregáveis e reprodutibilidade", style["Section"]),
        Paragraph(
            "O repositório contém export importável da Dialog Skill, API Flask testável por injeção, interface React/Vite, lockfile pnpm, CI, suíte automatizada, relatório-fonte e roteiro de 2min32s. "
            "As instruções do README reproduzem desenvolvimento, build integrado e smoke test. O repositório permanece privado por decisão do grupo, com o avaliador previamente convidado.",
            style["BodyCompact"],
        ),
        Paragraph("Grupo 7", style["Section"]),
        Paragraph(
            "Alice C. M. Assis — RM 566233  ·  Leonardo S. Souza — RM 563928  ·  Lucas B. Francelino — RM 561409  ·  "
            "Pedro L. T. Silva — RM 561644  ·  Vitor A. Bezerra — RM 563001<br/>"
            "Coordenação: André Godoi Chiovato. Grupo com cinco integrantes; ponto adicional registrado separadamente.",
            style["Small"],
        ),
        Paragraph("Referências", style["Section"]),
        Paragraph(
            "IBM — <link href='https://cloud.ibm.com/docs/watson-assistant?topic=watson-assistant-skill-dialog-add' color='#0B706F'>Dialog Skills</link> e "
            "<link href='https://cloud.ibm.com/docs/watson-assistant?topic=watson-assistant-api-overview' color='#0B706F'>APIs</link> e "
            "<link href='https://cloud.ibm.com/docs/watson-assistant?topic=watson-assistant-admin-securing' color='#0B706F'>segurança</link>. "
            "Ministério da Saúde — <link href='https://www.gov.br/saude/pt-br/assuntos/saude-de-a-a-z/i/infarto' color='#0B706F'>Infarto</link> e "
            "<link href='https://www.gov.br/saude/pt-br/composicao/saes/samu-192' color='#0B706F'>SAMU 192</link>. "
            "Código e documentação: README do projeto.",
            style["Small"],
        ),
    ]

    doc.build(story, onFirstPage=on_page, onLaterPages=on_page)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument(
        "--watson-status",
        default="Pendente: configuração acompanhada no plano Lite e smoke test real",
    )
    parser.add_argument(
        "--video-status",
        default="Roteiro de 2min32s pronto; gravação e link pendentes do usuário",
    )
    return parser.parse_args()


if __name__ == "__main__":
    arguments = parse_args()
    build_report(arguments.output.resolve(), arguments.watson_status, arguments.video_status)
    print(arguments.output.resolve())

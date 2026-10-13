from pathlib import Path
from PIL import Image
from pptx import Presentation
from pptx.util import Inches, Pt
from pptx.dml.color import RGBColor
from pptx.enum.shapes import MSO_SHAPE, MSO_CONNECTOR
from pptx.enum.text import PP_ALIGN, MSO_ANCHOR
from pptx.oxml.xmlchemy import OxmlElement
from pptx.oxml.ns import qn

ROOT = Path(__file__).resolve().parent
OUT = ROOT / "deck-草稿.pptx"
FONT = "Microsoft YaHei UI"
TITLE_FONT = "Noto Serif SC"
W, H = 13.3333, 7.5

C = {
    "bg": "F6F3EC", "paper": "FCFAF5", "green": "2D4E45", "ink": "344640",
    "muted": "6E7D73", "sage": "839E8A", "pale": "E2E9DC", "line": "D5D8CB",
    "terracotta": "C77B5B", "peach": "ECD3C0", "teal": "6C958A", "white": "FFFDF8"
}

def rgb(value):
    return RGBColor.from_string(value)

def set_font(run, size, color, bold=False, family=FONT):
    run.font.name = family
    run.font.size = Pt(size)
    run.font.bold = bold
    run.font.color.rgb = rgb(color)
    rpr = run._r.get_or_add_rPr()
    for tag in ("a:latin", "a:ea"):
        node = rpr.find(qn(tag))
        if node is None:
            node = OxmlElement(tag)
            rpr.append(node)
        node.set("typeface", family)

def no_shadow(shape):
    sp_pr = getattr(shape._element, "spPr", None)
    if sp_pr is not None and sp_pr.find(qn("a:effectLst")) is None:
        sp_pr.append(OxmlElement("a:effectLst"))


def add_text(slide, x, y, w, h, text, size=20, color=None, bold=False,
             align=PP_ALIGN.LEFT, valign=MSO_ANCHOR.TOP, font=FONT):
    box = slide.shapes.add_textbox(Inches(x), Inches(y), Inches(w), Inches(h))
    no_shadow(box)
    tf = box.text_frame
    tf.clear()
    tf.word_wrap = True
    tf.margin_left = Inches(0.015)
    tf.margin_right = Inches(0.015)
    tf.margin_top = Inches(0.01)
    tf.margin_bottom = Inches(0.01)
    tf.vertical_anchor = valign
    p = tf.paragraphs[0]
    p.alignment = align
    p.space_before = Pt(0)
    p.space_after = Pt(0)
    p.line_spacing = 1.08
    run = p.add_run()
    run.text = text
    set_font(run, size, color or C["ink"], bold, font)
    return box

def rect(slide, x, y, w, h, fill=None, border=None, radius=False, transparency=0):
    kind = MSO_SHAPE.ROUNDED_RECTANGLE if radius else MSO_SHAPE.RECTANGLE
    sh = slide.shapes.add_shape(kind, Inches(x), Inches(y), Inches(w), Inches(h))
    if fill:
        sh.fill.solid()
        sh.fill.fore_color.rgb = rgb(fill)
        sh.fill.transparency = transparency
    else:
        sh.fill.background()
    if border:
        sh.line.color.rgb = rgb(border)
        sh.line.width = Pt(1)
    else:
        sh.line.fill.background()
    no_shadow(sh)
    return sh

def oval(slide, x, y, w, h, fill=None, border=None, width=1.2, transparency=0):
    sh = slide.shapes.add_shape(MSO_SHAPE.OVAL, Inches(x), Inches(y), Inches(w), Inches(h))
    if fill:
        sh.fill.solid()
        sh.fill.fore_color.rgb = rgb(fill)
        sh.fill.transparency = transparency
    else:
        sh.fill.background()
    if border:
        sh.line.color.rgb = rgb(border)
        sh.line.width = Pt(width)
    else:
        sh.line.fill.background()
    no_shadow(sh)
    return sh

def line(slide, x1, y1, x2, y2, color=None, width=1):
    sh = slide.shapes.add_connector(
        MSO_CONNECTOR.STRAIGHT, Inches(x1), Inches(y1), Inches(x2), Inches(y2)
    )
    sh.line.color.rgb = rgb(color or C["line"])
    sh.line.width = Pt(width)
    no_shadow(sh)
    return sh

def bg(slide):
    slide.background.fill.solid()
    slide.background.fill.fore_color.rgb = rgb(C["bg"])

def add_image(slide, name, x, y, w, h):
    path = ROOT / "assets" / name
    with Image.open(path) as im:
        iw, ih = im.size
    scale = min(w / iw, h / ih)
    fit_w, fit_h = iw * scale, ih * scale
    left, top = x + (w - fit_w) / 2, y + (h - fit_h) / 2
    pic = slide.shapes.add_picture(str(path), Inches(left), Inches(top), Inches(fit_w), Inches(fit_h))
    no_shadow(pic)
    return pic

def footer(slide, index, note):
    line(slide, .75, 6.91, 12.58, 6.91, C["line"], .75)
    add_text(slide, .78, 7.00, 11.0, .38, note, 16, C["muted"])
    add_text(slide, 12.1, 7.00, .48, .33, f"{index:02d}", 16, C["terracotta"], align=PP_ALIGN.RIGHT)

def header(slide, title, section, sub=None):
    add_text(slide, .78, .42, 5.8, .29, section.upper(), 16, C["terracotta"], True)
    add_text(slide, .78, .81, 11.8, .62, title, 32, C["green"], True, font=TITLE_FONT)
    if sub:
        add_text(slide, .81, 1.53, 11.2, .45, sub, 18, C["muted"])

def notes(slide, text):
    slide.notes_slide.notes_text_frame.text = text

prs = Presentation()
prs.slide_width = Inches(W)
prs.slide_height = Inches(H)
blank = prs.slide_layouts[6]

# 01 — calm editorial cover
s = prs.slides.add_slide(blank); bg(s)
oval(s, 8.12, .55, 4.6, 4.6, C["pale"])
oval(s, 8.75, 1.1, 3.45, 3.45, None, "D3D8C9", .9)
add_text(s, .84, .66, 5.1, .34, "健康信息素养   /   01", 18, C["terracotta"], True)
add_text(s, .84, 1.62, 5.8, .88, "认识健康信息", 32, C["green"], True, font=TITLE_FONT)
add_text(s, .84, 2.65, 5.55, 1.12, "先看证据，再问来源，\n也别忘了沟通", 25, C["ink"], True)
rect(s, .88, 4.15, .72, .06, C["terracotta"])
add_text(s, .86, 4.55, 5.6, .8, "练习判断信息，不追求一眼定真伪。", 20, C["muted"])
add_image(s, "source-pages.png", 7.7, .88, 4.65, 4.65)
footer(s, 1, "健康信息素养科普｜帮助理解与沟通，不提供诊断或治疗建议")
notes(s, "开场说明：这份展示稿讨论的是如何阅读和沟通健康信息，不给出具体疾病的诊断、治疗或用药建议。遇到个人健康决定，应结合自己的情况向合适的医疗专业人员咨询。")

# 02 — four questions, open editorial rows
s = prs.slides.add_slide(blank); bg(s)
header(s, "先把一条信息拆成四个问题", "01 / FIRST LOOK",
       "看到醒目的结论时，先慢下来检查它的来处。")
# left cue column and four broad rows
add_text(s, .88, 2.23, 2.25, .52, "先问", 22, C["green"], True)
add_text(s, .88, 2.88, 2.35, 1.65, "四个\n小问题", 32, C["terracotta"], True, font=TITLE_FONT)
line(s, 3.3, 2.12, 3.3, 6.12, C["line"], 1.0)
rows = [
    ("01", "说的是什么？", "把标题还原成可核对的具体主张。"),
    ("02", "谁在发布？", "查运营、目的、审核与资助。"),
    ("03", "依据在哪里？", "能否找到研究、原始资料或明确出处？"),
    ("04", "何时更新？", "发布日期、更新时间与适用对象是什么？")
]
for i, (num, question, detail) in enumerate(rows):
    yy = 2.16 + i * 1.0
    add_text(s, 3.74, yy, .62, .34, num, 16, C["terracotta"], True)
    add_text(s, 4.56, yy-.05, 2.55, .48, question, 20, C["green"], True)
    add_text(s, 7.45, yy-.04, 4.65, .58, detail, 18, C["muted"])
    if i < 3:
        line(s, 3.72, yy+.73, 12.2, yy+.73, C["line"], .65)
footer(s, 2, "参考：MedlinePlus（美国国家医学图书馆），Evaluating Health Information")
notes(s, "可引导观众选一条日常看到的健康信息，依次检查内容主张、发布者、依据与更新时间。MedlinePlus的健康信息评估页面也建议关注网站运营方、目的、编辑审核、研究依据、资助、隐私与更新等线索。此处为中文概述，不是逐字翻译。")

# 03 — boundaries and four lenses, shown as a radial composition
s = prs.slides.add_slide(blank); bg(s)
header(s, "证据能支持什么，也要看它的边界", "02 / EVIDENCE & LIMITS",
       "一项结论是否适用，取决于材料、对象与具体情境。")
# four questions orbit a central "范围" anchor
oval(s, 5.15, 2.35, 2.82, 2.82, C["pale"], "B6C6B5", 1.2)
oval(s, 5.64, 2.84, 1.84, 1.84, C["green"])
add_text(s, 5.77, 3.2, 1.58, .5, "结论\n边界", 22, C["white"], True, PP_ALIGN.CENTER, MSO_ANCHOR.MIDDLE)
# four distinct callouts with rule connectors
line(s, 4.25, 2.82, 5.38, 3.2, C["sage"], 1.0)
line(s, 7.78, 3.03, 9.0, 2.62, C["sage"], 1.0)
line(s, 4.2, 4.82, 5.37, 4.42, C["sage"], 1.0)
line(s, 7.77, 4.42, 9.0, 4.9, C["sage"], 1.0)
add_text(s, .92, 2.25, 3.3, .42, "研究怎么做？", 20, C["green"], True)
add_text(s, .94, 2.82, 3.2, .63, "方法与证据来源，\n是否说得清楚？", 18, C["muted"])
add_text(s, 9.08, 2.18, 3.15, .42, "参与者是谁？", 20, C["green"], True)
add_text(s, 9.08, 2.76, 3.0, .62, "对象与条件，\n和所讨论的问题吻合吗？", 18, C["muted"])
add_text(s, .92, 4.66, 3.2, .42, "有哪些局限？", 20, C["green"], True)
add_text(s, .94, 5.23, 3.15, .62, "单个结果不能自动\n代表所有情境。", 18, C["muted"])
add_text(s, 9.08, 4.72, 3.2, .42, "是否适合个人？", 20, C["green"], True)
add_text(s, 9.08, 5.29, 3.15, .62, "通用信息不等于\n个人建议。", 18, C["muted"])
add_text(s, 4.12, 5.65, 5.4, .42, "结论的适用范围，需要回到原资料确认。", 18, C["terracotta"], True, PP_ALIGN.CENTER)
footer(s, 3, "参考：MedlinePlus，Evaluating Health Information；内容为信息素养概述")
notes(s, "本页不把证据简化成固定排名，而是提示观众查看研究如何开展、参与者情况、资料的局限以及结论适用范围。MedlinePlus建议核对健康信息的证据依据和来源，并与医疗人员讨论其是否适合自己的情况。")

# 04 — source trail as a typographic chain
s = prs.slides.add_slide(blank); bg(s)
header(s, "别只看转述：顺着引用找到原文", "03 / TRACE THE SOURCE",
       "从一句结论往回走，核对是谁说的、依据是什么、何时更新。")
# left excerpt; central source bridge; right original source checkpoints
rect(s, .88, 2.35, 2.5, 2.72, C["paper"], "D9DCCF", True)
add_text(s, 1.12, 2.63, 1.95, .32, "你看到的", 18, C["terracotta"], True)
add_text(s, 1.1, 3.18, 2.02, 1.12, "“研究证实，\n人人都应该……”", 22, C["green"], True, font=TITLE_FONT)
add_text(s, 1.12, 4.6, 2.06, .35, "标题 / 摘要 / 转述", 16, C["muted"])
# connector route with checkpoints
line(s, 3.6, 3.72, 9.55, 3.72, C["sage"], 1.8)
for x, label in [(4.18, "作者"), (5.78, "引用"), (7.38, "日期")]:
    oval(s, x, 3.48, .48, .48, C["bg"], C["terracotta"], 1.2)
    add_text(s, x-.2, 4.12, .92, .35, label, 18, C["green"], True, PP_ALIGN.CENTER)
# right hand source endpoint
oval(s, 9.25, 3.42, .62, .62, C["green"])
add_text(s, 9.12, 2.65, 2.5, .4, "回到原始发布页", 20, C["green"], True)
add_text(s, 10.05, 3.42, 2.2, .9, "找依据\n看限制与更新时间", 18, C["muted"])
add_text(s, .92, 5.62, 11.2, .56, "如果找不到原文、作者或研究背景，先保留疑问，再继续核对。", 20, C["ink"], True)
footer(s, 4, "参考：MedlinePlus（NLM），Evaluating Health Information")
notes(s, "左侧引文是虚构的夸张标题，用来练习追溯，不是实际健康主张。沿着作者、引用和日期找到原始页面后，应查看证据描述、适用条件与更新时间；无法找到出处时，可把它作为尚未核实的信息。")

# 05 — a respectful conversation route
s = prs.slides.add_slide(blank); bg(s)
header(s, "把疑问带进一次好沟通", "04 / TALK IT THROUGH",
       "带着来源、原文和自己的问题，与合适的专业人员讨论。")
add_text(s, .9, 2.1, 5.6, .38, "可以这样开口", 18, C["terracotta"], True)
prompts = [
    ("我看到……", "把具体信息或出处带来"),
    ("它依据什么？", "一起确认原始材料"),
    ("还有哪些未知？", "说清楚自己仍不确定的地方"),
    ("这和我有关吗？", "讨论是否适合个人情境")
]
for i, (q, small) in enumerate(prompts):
    yy = 2.62 + i * .83
    oval(s, .93, yy+.08, .34, .34, C["terracotta"] if i == 0 else C["pale"], None)
    add_text(s, 1.48, yy, 2.55, .43, q, 20, C["green"], True)
    add_text(s, 4.0, yy+.01, 3.75, .42, small, 18, C["muted"])
    if i < 3:
        line(s, 1.1, yy+.43, 1.1, yy+.78, C["line"], .9)
# generated listening illustration balances the composition
oval(s, 8.3, 2.1, 3.52, 3.52, C["pale"])
add_image(s, "listening-ear.png", 8.45, 2.22, 3.3, 3.3)
add_text(s, .95, 6.12, 11.3, .4, "重要的个人健康决定，请结合具体情况向医疗专业人员咨询。", 18, C["green"], True)
footer(s, 5, "科普用途｜不替代诊断、治疗或个体化医疗建议")
notes(s, "收束：健康信息素养不是独自判断每条信息，而是知道如何找来源、描述疑问，并与合适的医疗专业人员沟通。不要让通用信息替代针对个人情况的专业建议。")

prs.save(OUT)
print(f"Created {OUT}")
print(f"Slides: {len(prs.slides)}")


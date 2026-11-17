"""Edit only identified fields of the supplied immutable template."""
from copy import deepcopy
from dataclasses import dataclass
from datetime import datetime
from io import BytesIO
from pathlib import Path
import re
import subprocess
import tempfile
import fitz
from docx import Document
from docx.enum.text import WD_ALIGN_PARAGRAPH, WD_LINE_SPACING
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Cm, Pt
from config import TEMPLATE, SOFFICE

MONTHS = 'yanvar fevral mart aprel may iyun iyul avgust sentabr oktabr noyabr dekabr'.split()
OLD_NAME = 'Anvarov Anvar Anvar o‘g‘li'
OLD_ROLE = 'O‘zbekiston Respublikasi Oliy sudi jinoyat ishlari bo‘yicha sudlov hay’atining katta konsultanti'
SHORT_ROLE = 'jinoyat ishlari bo‘yicha sudlov hay’atining katta konsultanti'
OLD_OFFICER = 'Komplayens nazorat xizmati bosh inspektori'

def parse_date(value):
    if not re.fullmatch(r'\d{2}\.\d{2}\.\d{4}', value):
        raise ValueError('Sanani KK.OO.YYYY shaklida kiriting. Masalan: 17.11.2026')
    try:
        return datetime.strptime(value, '%d.%m.%Y').date()
    except ValueError as exc:
        raise ValueError('Bunday sana mavjud emas. Sanani qayta kiriting.') from exc

def uz_date(value):
    d = parse_date(value)
    return f'{d.year}-yil {d.day}-{MONTHS[d.month-1]}'

def validate_text(value, kind):
    if not isinstance(value, str) or any(ord(c) < 32 for c in value):
        raise ValueError('Ma’lumotni bitta qatorda matn shaklida kiriting.')
    value = ' '.join(value.split())
    limit = 120 if kind in {'employee','officer'} else 260 if 'role' in kind else 80
    if not 3 <= len(value) <= limit:
        raise ValueError(f'Matn uzunligi 3–{limit} belgi bo‘lsin.')
    if kind in {'employee','officer'} and (len(value.split()) < 2 or not all(any(c.isalpha() for c in w) for w in value.split())):
        raise ValueError('Kamida familiya va ismni kiriting.')
    return value

def initials(name):
    surname, given, *_ = name.split()
    return f'{given[0].upper()}.{surname}'

@dataclass(frozen=True)
class Record:
    employee: str
    employee_role: str
    date: str
    place: str
    officer_role: str
    officer: str

    def validate(self):
        parse_date(self.date)
        for key in ('employee','employee_role','place','officer_role','officer'):
            if validate_text(getattr(self,key),key) != getattr(self,key):
                raise ValueError('Matn chetlaridagi va ortiqcha bo‘shliqlarni olib tashlang.')

def replace_span(p, old, new):
    """Replace across runs while retaining unaffected run properties and text."""
    text = p.text
    if text.count(old) != 1:
        raise ValueError('Shablon maydoni o‘zgargan: '+old)
    start = text.index(old); end = start + len(old); offset = 0
    for r in p.runs:
        original = r.text; stop = offset + len(original)
        if offset < end and stop > start:
            left = max(0,start-offset); right = min(len(original),end-offset)
            r.text = original[:left] + (new if offset <= start < stop else '') + original[right:]
        offset = stop

def set_text(p, text):
    props = deepcopy(p.runs[0]._r.rPr) if p.runs and p.runs[0]._r.rPr is not None else None
    p.clear()
    r = p.add_run(text)
    if props is not None: r._r.insert(0,props)
    return r

def pair_table(doc, anchor, left, right, date=False):
    """Fixed borderless columns prevent long fields from overlapping."""
    sec=doc.sections[0]; width=sec.page_width-sec.left_margin-sec.right_margin
    table=doc.add_table(rows=1, cols=2); table.autofit=False
    table.columns[0].width=int(width*(0.40 if date else 0.63))
    table.columns[1].width=width-table.columns[0].width
    pr=table._tbl.tblPr
    borders=OxmlElement('w:tblBorders')
    for side in ('top','left','bottom','right','insideH','insideV'):
        el=OxmlElement('w:'+side); el.set(qn('w:val'),'nil'); borders.append(el)
    pr.append(borders)
    margins=OxmlElement('w:tblCellMar')
    for side in ('top','left','bottom','right'):
        el=OxmlElement('w:'+side); el.set(qn('w:w'),'0'); el.set(qn('w:type'),'dxa'); margins.append(el)
    pr.append(margins)
    cant=OxmlElement('w:cantSplit'); table.rows[0]._tr.get_or_add_trPr().append(cant)
    for i,text in enumerate((left,right)):
        cell=table.cell(0,i); cell.width=table.columns[i].width
        p=cell.paragraphs[0]
        p._p.insert(0,deepcopy(anchor._p.get_or_add_pPr()))
        set_text(p,text)
        p.paragraph_format.first_line_indent=Pt(0)
        p.paragraph_format.left_indent=Pt(0)
        p.paragraph_format.right_indent=Pt(0)
        p.paragraph_format.space_after=Pt(0)
        p.alignment=WD_ALIGN_PARAGRAPH.LEFT if i==0 else WD_ALIGN_PARAGRAPH.RIGHT
        for r in p.runs:
            r.font.name='Times New Roman';r.font.size=Pt(14);r.bold=not date
    anchor._p.addprevious(table._tbl)
    anchor._p.getparent().remove(anchor._p)
    return table

def generate_docx(record: Record, destination: Path, image: bytes | None=None):
    record.validate();doc=Document(TEMPLATE);p=list(doc.paragraphs)
    if len(p)!=30 or 'B A Y O N N O M A S I'!=p[2].text or len(doc.inline_shapes)!=1:
        raise ValueError('Asl shablon tuzilmasi mos kelmadi.')
    replace_span(p[0],OLD_ROLE,record.employee_role)
    replace_span(p[0],OLD_NAME,record.employee)
    replace_span(p[16],OLD_OFFICER,record.officer_role)
    replace_span(p[16],SHORT_ROLE,record.employee_role)
    replace_span(p[16],OLD_NAME,record.employee)
    replace_span(p[17],'A.Anvarov',initials(record.employee))
    # Extra title/place lines must not push the picture off page one.
    # Reclaim only existing empty spacer paragraphs when input is lengthy.
    if len(record.employee_role + record.employee) > 165 or len(record.place) > 42:
        for idx in (1,3,5,12):
            p[idx].paragraph_format.line_spacing_rule=WD_LINE_SPACING.EXACTLY
            p[idx].paragraph_format.line_spacing=Pt(0.5)
            p[idx].paragraph_format.space_before=Pt(0)
            p[idx].paragraph_format.space_after=Pt(0)
    pair_table(doc,p[4],uz_date(record.date),record.place,date=True)
    p[19].paragraph_format.keep_with_next=True
    p[20].paragraph_format.keep_with_next=True
    pair_table(doc,p[21],record.officer_role,initials(record.officer))
    p[22]._p.getparent().remove(p[22]._p)
    pair_table(doc,p[28],record.employee_role,initials(record.employee))
    p[29]._p.getparent().remove(p[29]._p)
    shape=doc.inline_shapes[0]
    shape.width=Cm(17);shape.height=Cm(9)
    p[13].alignment=WD_ALIGN_PARAGRAPH.CENTER
    p[13].paragraph_format.line_spacing=1.0
    p[13].paragraph_format.first_line_indent=Pt(0)
    if image is not None:
        # Change only the existing DrawingML relationship, never append a picture.
        old_rid=shape._inline.graphic.graphicData.pic.blipFill.blip.embed
        rid,_=doc.part.get_or_add_image(BytesIO(image))
        shape._inline.graphic.graphicData.pic.blipFill.blip.embed=rid
        if old_rid != rid and not doc.part.element.xpath('.//*[@r:embed="%s"]' % old_rid):
            doc.part.drop_rel(old_rid)
    destination=Path(destination);destination.parent.mkdir(parents=True,exist_ok=True)
    doc.save(destination)
    return destination

def to_pdf(docx: Path):
    docx=Path(docx).resolve()
    with tempfile.TemporaryDirectory(prefix='lo-profile-') as profile:
        try:
            result=subprocess.run([SOFFICE,'-env:UserInstallation='+Path(profile).as_uri(),'--headless','--convert-to','pdf:writer_pdf_Export','--outdir',str(docx.parent),str(docx)],capture_output=True,timeout=120)
        except FileNotFoundError as exc:
            raise RuntimeError('LibreOffice o‘rnatilmagan.') from exc
        pdf=docx.with_suffix('.pdf')
        if result.returncode or not pdf.exists() or pdf.stat().st_size<100:
            raise RuntimeError('PDF yaratilmadi. LibreOffice sozlamalarini tekshiring.')
        with fitz.open(pdf) as rendered:
            first=rendered[0]
            rectangles=[rect for item in first.get_images() for rect in first.get_image_rects(item[0])]
            if not rectangles:
                raise ValueError('Lavozim yoki joy matni juda uzun: rasm birinchi sahifaga sig‘madi. Tahrirlash orqali matnni qisqartiring.')
        return pdf

def filename(record):
    surname=re.sub(r'[^\w‘’\-]', '_',record.employee.split()[0])[:60]
    return f'Bayonnoma_{surname}_{parse_date(record.date):%d-%m-%Y}'

import hashlib
from io import BytesIO
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import pytest
from PIL import Image
from docx import Document
from docx.oxml.ns import qn
from config import TEMPLATE
from transliteration import convert
from document_generator import Record, generate_docx, initials, parse_date, uz_date, replace_span
from image_processor import prepare_image

@pytest.fixture
def record():
    return Record('Karimov Sardor Olim o‘g‘li','Samarqand viloyat sudi katta konsultanti','17.11.2026','Samarqand shahri','Komplayens nazorat xizmati bosh inspektori','Rasulova Malika Olim qizi')

def raw_image(size=(500,900)):
    b=BytesIO();Image.new('RGB',size,'red').save(b,'PNG');return b.getvalue()

def test_dates():
    for month in range(1,13): assert uz_date(f'01.{month:02}.2026').startswith('2026-yil 1-')
    assert uz_date('17.11.2026')=='2026-yil 17-noyabr'
    assert parse_date('29.02.2024').day==29
    for bad in ['29.02.2026','31.04.2026','1.2.2026','<date>']:
        with pytest.raises(ValueError): parse_date(bad)

def test_initials():
    assert initials('Karimov Sardor Olim o‘g‘li')=='S.Karimov'
    assert initials('Rasulova Malika Olim qizi')=='M.Rasulova'

def test_cross_runs():
    d=Document();p=d.add_paragraph();p.add_run('left Anv').bold=True;p.add_run('arov right').italic=True
    replace_span(p,'Anvarov','Karimov')
    assert p.text=='left Karimov right' and p.runs[0].bold and p.runs[1].italic

def test_photo_proportions():
    im=Image.open(BytesIO(prepare_image(raw_image())))
    assert im.size==(2040,1080)
    # Entire portrait retained: its 500:900 rectangle remains proportional.
    pix=im.load();xs=[];ys=[]
    for x in range(im.width):
        if pix[x,540][0]>250 and pix[x,540][1]<10: xs.append(x)
    for y in range(im.height):
        if pix[1020,y][0]>250 and pix[1020,y][1]<10: ys.append(y)
    assert abs(len(xs)/len(ys)-500/900)<0.005
    with pytest.raises(ValueError):prepare_image(b'fake image')
    with pytest.raises(ValueError):prepare_image(raw_image((20,20)))

def test_immutable_legal_text_and_fields(tmp_path,record):
    before=hashlib.sha256(TEMPLATE.read_bytes()).hexdigest()
    source=Document(TEMPLATE)
    out=generate_docx(record,tmp_path/'output.docx',prepare_image(raw_image()))
    result=Document(out)
    texts=[p.text for p in result.paragraphs]
    for idx in [1,2,3,5,6,7,8,9,10,11,12,14,15,18,19,20,23,24,25,26,27]:
        assert convert(source.paragraphs[idx].text) in texts
    assert record.employee in texts[0] and record.employee_role in texts[0]
    combined='\n'.join(texts)
    assert 'Anvarov' not in combined and 'A.Anvarov' not in combined
    assert 'S.Karimov' in combined and record.officer_role in combined
    assert len(result.tables)==3
    date=result.tables[0]
    assert date.cell(0,0).text=='2026-yil 17-noyabr'
    assert date.cell(0,1).text==record.place
    assert int(date.cell(0,0).paragraphs[0].alignment)==0
    assert int(date.cell(0,1).paragraphs[0].alignment)==2
    assert result.tables[1].cell(0,1).text=='M.Rasulova'
    assert result.tables[2].cell(0,1).text=='S.Karimov'
    assert len(result.inline_shapes)==1
    assert result.inline_shapes[0].width==6120000
    assert result.inline_shapes[0].height==3240000
    assert result.sections[0]._sectPr.xml==source.sections[0]._sectPr.xml
    assert before==hashlib.sha256(TEMPLATE.read_bytes()).hexdigest()

def test_keep_image(tmp_path,record):
    source=Document(TEMPLATE);out=Document(generate_docx(record,tmp_path/'keep.docx'))
    def blob(d):return d.part.related_parts[d.inline_shapes[0]._inline.graphic.graphicData.pic.blipFill.blip.embed].blob
    assert blob(source)==blob(out)

def test_concurrent_users(tmp_path,record):
    records=[Record(f'User{i} Sardor Olim o‘g‘li',record.employee_role,record.date,record.place,record.officer_role,record.officer) for i in range(6)]
    with ThreadPoolExecutor(max_workers=3) as pool:
        outputs=list(pool.map(lambda pair:generate_docx(pair[1],tmp_path/f'{pair[0]}.docx'),enumerate(records)))
    for i,path in enumerate(outputs):
        text=Document(path).paragraphs[0].text
        assert f'User{i} ' in text
        for j in range(6):
            if i!=j:assert f'User{j} ' not in text

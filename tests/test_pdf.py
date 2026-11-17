import os
import shutil
from pathlib import Path
from dataclasses import replace
from transliteration import convert
import pytest
import fitz
from document_generator import generate_docx, to_pdf, filename
from tests.create_examples import records

@pytest.mark.skipif(not shutil.which(os.environ.get('SOFFICE','libreoffice')),reason='LibreOffice required')
@pytest.mark.parametrize('record',records)
@pytest.mark.parametrize('script',['latin','cyrillic','new_latin'])
def test_pdf_first_page_and_date_alignment(record,tmp_path,script):
    record=replace(record,script=script)
    pdf=to_pdf(generate_docx(record,tmp_path/(filename(record)+'.docx')))
    doc=fitz.open(pdf);page=doc[0]
    rects=[r for im in page.get_images() for r in page.get_image_rects(im[0])]
    assert len(rects)==1
    assert abs(rects[0].width-17/2.54*72)<0.2
    assert abs(rects[0].height-9/2.54*72)<0.2
    assert rects[0].y1<page.rect.height-40
    words=page.get_text('words')
    date=next(w for w in words if w[4]==convert(record.date[-4:]+'-yil',script))
    place=next(w for w in words if w[4]==convert(record.place.split()[0],script))
    assert abs(date[1]-place[1])<0.5
    assert abs(date[0]-71)<0.5
    assert place[0]>date[2]+30
    assert len(doc)==2

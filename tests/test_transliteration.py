from dataclasses import replace
from io import BytesIO
import asyncio
from pathlib import Path
from docx import Document
from PIL import Image
import pytest
import bot
from document_generator import Record, generate_docx, convert_paragraph, to_pdf
from transliteration import convert,normalize_apostrophes
from tests.test_bot import message

@pytest.mark.parametrize('input',["O'zbekiston G'afur ma'no",'O`zbekiston G`afur ma’no','O-zbekiston G-afur maʼno','Oʻzbekiston Gʻafur maʼno'])
def test_apostrophe_variants(input):
    assert convert(input)=='O‘zbekiston G‘afur maʼno'
    assert convert('2026-yil 17-noyabr')=='2026-yil 17-noyabr'

def test_signs_and_new_latin():
    assert convert('Ўзбекистон Ғафур маъно объект субъект компьютер')=='O‘zbekiston G‘afur maʼno obyekt subyekt kompyuter'
    assert convert('O‘zbekiston G‘afur Toshkent Chirchiq','new_latin')=='Ŏzbekiston Ğafur Toşkent Çirçiq'
    assert convert('Ŏzbekiston Ğafur Toşkent Çirçiq')=='O‘zbekiston G‘afur Toshkent Chirchiq'
    assert convert('O‘zbekiston maʼno obyekt subyekt','cyrillic')=='Ўзбекистон маъно объект субъект'
    assert convert('Объект, субъект, компьютер','cyrillic')=='Объект, субъект, компьютер'

def test_split_runs_preserve_styles_and_drawing():
    doc=Document();p=doc.add_paragraph();p.add_run('To').bold=True;p.add_run('shkent G').italic=True;p.add_run("'afur")
    # Retain the exact drawing node while converting split text nodes.
    image=BytesIO();Image.new('RGB',(100,100),'white').save(image,'PNG');image.seek(0)
    p.add_run().add_picture(image)
    drawing=p._p.xpath('.//w:drawing')[0]
    convert_paragraph(p,'new_latin')
    assert p.text=='Toşkent Ğafur' and p.runs[0].bold and p.runs[1].italic
    assert p._p.xpath('.//w:drawing')[0] is drawing

@pytest.mark.parametrize('script,expected',[('latin','O‘zbekiston'),('cyrillic','Ўзбекистон'),('new_latin','Ŏzbekiston')])
def test_whole_document_and_signatures(tmp_path,script,expected):
    record=Record('Ғафуров Шерзод Али ўғли','O‘zbekiston Respublikasi sud konsultanti','17.11.2026','Toshkent shahri','Komplayens bosh inspektori','Каримова Малика Али қизи',script)
    d=Document(generate_docx(record,tmp_path/f'{script}.docx'))
    assert expected in d.paragraphs[0].text
    assert d.tables[0].cell(0,0).text==convert('2026-yil 17-noyabr',script)
    assert d.tables[0].cell(0,1).text==convert('Toshkent shahri',script)
    assert d.tables[1].cell(0,1).text==convert('М.Каримова',script)
    assert d.tables[2].cell(0,1).text==convert('Ш.Ғафуров',script)
    source=Document('templates/BAYONNOMA_NAMUNA.docx')
    legal=source.paragraphs[25].text
    assert convert(legal,script) in [p.text for p in d.paragraphs]
    assert len(d.inline_shapes)==1

def test_language_selection_and_editing():
    async def run():
        bot.sessions.clear();await bot.handle(message(bot.NEW))
        assert bot.sessions[1].mode=='script'
        await bot.handle(message('✨ Yangi lotin yozuvi'))
        s=bot.sessions[1];assert s.script=='new_latin' and s.mode=='input'
        s.values=dict(employee='Ғафуров Шерзод Али ўғли',employee_role='Sud konsultanti',date='17.11.2026',place='Toshkent shahri',officer_role='Bosh inspektor',officer='Каримова Малика Али қизи')
        m=message('');await bot.summary(m,s)
        assert 'Ş.Ğafurov'==convert('Ш.Ғафуров',s.script)
        assert 'Toşkent' in m.answer.call_args.args[0] and s.mode=='review'
        await bot.handle(message(bot.MAKE));assert s.mode=='review'
        await bot.handle(message(bot.EDIT));await bot.handle(message(bot.SCRIPT_EDIT));await bot.handle(message('🔤 Kirill yozuvi'))
        assert s.script=='cyrillic' and s.mode=='review'
        await bot.handle(message(bot.TEXT_OK));assert s.mode=='confirm'
        bot.sessions.clear()
    asyncio.run(run())


def test_cyrillic_soft_sign_and_months():
    assert convert('sudyalar obyektlar subyektlar','cyrillic')=='судьялар объектлар субъектлар'
    assert convert('2026-yil 17-noyabr','cyrillic')=='2026-йил 17-ноябрь'
    assert convert('yanvar fevral aprel iyun iyul sentabr oktabr dekabr','cyrillic')=='январь февраль апрель июнь июль сентябрь октябрь декабрь'


def test_initials_follow_selected_alphabet():
    from document_generator import initials
    assert initials('G‘afurov Sherzod Ali o‘g‘li','cyrillic')=='Ш.Ғафуров'
    assert initials('G‘afurov Sherzod Ali o‘g‘li','new_latin')=='Ş.Ğafurov'
    assert initials('Ғафуров Шерзод Али ўғли','latin')=='Sh.G‘afurov'

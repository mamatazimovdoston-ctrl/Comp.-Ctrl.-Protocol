"""Run from the project root. Creates three real DOCX/PDF pairs."""
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from io import BytesIO
from PIL import Image, ImageDraw
from document_generator import Record, generate_docx, to_pdf, filename
from image_processor import prepare_image

records=[
Record('Karimov Sardor Olim o‘g‘li','O‘zbekiston Respublikasi Oliy sudi jinoyat ishlari bo‘yicha sudlov hay’atining katta konsultanti','17.11.2026','Samarqand shahri','Komplayens nazorat xizmati bosh inspektori','Rasulova Malika Olim qizi'),
Record('Rasulova Malika Olim qizi','Samarqand viloyat sudi katta konsultanti','29.02.2024','Urgut tumani','Komplayens nazorat xizmati yetakchi inspektori','Karimov Sardor Olim o‘g‘li'),
Record('Usmonov Jasur Akmal o‘g‘li','O‘zbekiston Respublikasi Oliy sudi jinoyat ishlari bo‘yicha sudlov hay’atining tashkiliy masalalar va murojaatlar bilan ishlash bo‘yicha katta konsultanti','01.12.2026','Qoraqalpog‘iston Respublikasi Amudaryo tumani Mang‘it shahri','Korrupsiyaga qarshi ichki nazorat va komplayens nazorat xizmati hududiy boshqarmasining bosh inspektori','Tursunov Bekzod Ali o‘g‘li')]

def main():
    out=Path('examples');out.mkdir(exist_ok=True)
    for i,r in enumerate(records):
        image=None
        if i:
            im=Image.new('RGB',(800,1400) if i==1 else (1800,700),'#dce8f0');d=ImageDraw.Draw(im)
            d.rectangle((80,80,im.width-80,im.height-80),outline='#296080',width=10)
            d.text((100,110),'SINOV RASMI - '+str(i+1),fill='black',font_size=38)
            b=BytesIO();im.save(b,'PNG');image=prepare_image(b.getvalue())
        docx=generate_docx(r,out/(filename(r)+'.docx'),image)
        print(to_pdf(docx))
if __name__=='__main__':main()

"""Create a DOCX/PDF pair for each supported writing system."""
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from dataclasses import replace
from document_generator import generate_docx,to_pdf
from tests.create_examples import records

def main():
    for script in ('latin','cyrillic','new_latin'):
        record=replace(records[0],script=script)
        path=Path('examples')/f'Yozuv_{script}.docx'
        generate_docx(record,path)
        print(to_pdf(path))
if __name__=='__main__':main()

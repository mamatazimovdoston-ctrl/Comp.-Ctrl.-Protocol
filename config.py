import os
from pathlib import Path
from dotenv import load_dotenv
load_dotenv()
BASE = Path(__file__).resolve().parent
TEMPLATE = BASE / 'templates/BAYONNOMA_NAMUNA.docx'
BOT_TOKEN = os.getenv('BOT_TOKEN', '')
MAX_IMAGE_BYTES = 10 * 1024 * 1024
SESSION_SECONDS = 1800
SOFFICE = os.getenv('SOFFICE', 'libreoffice')
ALLOWED_USER_IDS = {int(x) for x in os.getenv('ALLOWED_USER_IDS', '').split(',') if x.strip()}

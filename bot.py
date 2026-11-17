import asyncio
import logging
import time
from dataclasses import dataclass, field
from io import BytesIO
from pathlib import Path
from tempfile import TemporaryDirectory
from aiogram import Bot, Dispatcher, F
from aiogram.enums import ChatType
from aiogram.filters import Command, CommandStart
from aiogram.types import Message, KeyboardButton, ReplyKeyboardMarkup, FSInputFile
from config import BOT_TOKEN, TEMPLATE, MAX_IMAGE_BYTES, SESSION_SECONDS, ALLOWED_USER_IDS
from document_generator import Record, validate_text, parse_date, uz_date, filename, generate_docx, to_pdf
from image_processor import prepare_image

NEW='📝 Yangi bayonnoma yaratish'; SAMPLE='📄 Bayonnoma namunasini ko‘rish'; HELP='ℹ️ Yordam'
KEEP='🖼 Namunadagi rasmni qoldirish'; MAKE='✅ Bayonnomani tayyorlash'; EDIT='✏️ Tahrirlash'; CANCEL='❌ Bekor qilish'
KEYS=['employee','employee_role','date','place','officer_role','officer','image']
LABELS=['Xodim F.I.Sh.','Xodim lavozimi','Bayonnoma sanasi','Suhbat joyi','Mas’ul lavozimi','Mas’ul F.I.Sh.','Rasm']
QUESTIONS=[
'Suhbat o‘tkazilgan xodimning familiyasi, ismi va otasining ismini kiriting.\n\nMasalan: Anvarov Anvar Anvar o‘g‘li',
'Xodimning to‘liq lavozimini kiriting.\n\nMasalan: O‘zbekiston Respublikasi Oliy sudi jinoyat ishlari bo‘yicha sudlov hay’atining katta konsultanti',
'Bayonnoma sanasini kiriting.\n\nMasalan: 17.11.2026',
'Suhbat o‘tkazilgan joyni kiriting.\n\nMasalan:\n- Toshkent shahri\n- Samarqand shahri\n- Samarqand viloyati\n- Urgut tumani',
'Suhbat o‘tkazgan mas’ul xodimning to‘liq lavozimini kiriting.\n\nMasalan: Komplayens nazorat xizmati bosh inspektori',
'Suhbat o‘tkazgan mas’ul xodimning familiyasi, ismi va otasining ismini kiriting.',
'Bayonnomaga joylashtiriladigan rasmni yuboring.\n\nRasm Word namunasidagi mavjud rasm o‘rniga joylashtiriladi.\n\nTavsiya etilgan o‘lcham: eni 17 sm, balandligi 9 sm.']

def keyboard(*rows):
    return ReplyKeyboardMarkup(keyboard=[[KeyboardButton(text=x) for x in row] for row in rows],resize_keyboard=True)
MENU=keyboard([NEW],[SAMPLE,HELP])
CONFIRM=keyboard([MAKE],[EDIT,CANCEL])

@dataclass
class Session:
    values: dict=field(default_factory=dict)
    step: int=0
    mode: str='input'
    editing: bool=False
    touched: float=field(default_factory=time.monotonic)
    image: bytes | None=None
    busy: bool=False

sessions: dict[int,Session]={}
locks: dict[int,asyncio.Lock]={}
workers=asyncio.Semaphore(2)
dp=Dispatcher()

async def ask(m,s):
    await m.answer(QUESTIONS[s.step],reply_markup=keyboard([KEEP],[CANCEL]) if s.step==6 else keyboard([CANCEL]))

async def summary(m,s):
    v=s.values;s.mode='confirm'
    await m.answer(f'📋 Bayonnoma ma’lumotlari:\n\nSuhbat o‘tkazilgan xodim: {v["employee"]}\n\nLavozimi: {v["employee_role"]}\n\nBayonnoma sanasi: {uz_date(v["date"])}\n\nSuhbat o‘tkazilgan joy: {v["place"]}\n\nSuhbat o‘tkazgan xodim: {v["officer"]}\n\nLavozimi: {v["officer_role"]}\n\nRasm: {"yuborilgan" if s.image else "namunadagi rasm"}\n\nMa’lumotlarni tasdiqlaysizmi?',reply_markup=CONFIRM)

async def generate_and_send(m,s):
    s.busy=True
    try:
        await m.answer('⏳ Word va PDF hujjatlar tayyorlanmoqda…')
        async with workers:
            record=Record(**s.values)
            with TemporaryDirectory(prefix='bayonnoma-') as temp:
                target=Path(temp)/(filename(record)+'.docx')
                await asyncio.to_thread(generate_docx,record,target,s.image)
                try:
                    pdf=await asyncio.to_thread(to_pdf,target)
                except ValueError:
                    raise
                except Exception:
                    await m.answer_document(FSInputFile(target),caption='Word tayyor. PDF yaratishda xato yuz berdi; qayta urinish mumkin.')
                    raise
                await m.answer_document(FSInputFile(target),caption='Tahrirlash va chop etish uchun Word')
                await m.answer_document(FSInputFile(pdf),caption='Chop etish uchun PDF')
        sessions.pop(m.from_user.id,None)
        s.image=None;s.values.clear()
        await m.answer('✅ Bayonnoma muvaffaqiyatli tayyorlandi!\n\nWord va PDF shaklidagi hujjatlar quyida yuborildi.',reply_markup=MENU)
    except ValueError as exc:
        await m.answer(str(exc),reply_markup=CONFIRM)
    except Exception as exc:
        # Do not log tokens, document contents, names or Telegram response bodies.
        logging.error('Generation/send failure: %s',type(exc).__name__)
        await m.answer('Hujjatlarni tayyorlash yoki yuborishda xato yuz berdi. Qayta urinib ko‘ring yoki ma’lumotlarni tahrirlang.',reply_markup=CONFIRM)
    finally:
        s.busy=False

async def handle(m):
    uid=m.from_user.id
    if m.chat.type!=ChatType.PRIVATE:
        await m.answer('Botdan shaxsiy chatda foydalaning.');return
    if ALLOWED_USER_IDS and uid not in ALLOWED_USER_IDS:
        await m.answer('Bu botdan foydalanishga ruxsat berilmagan.');return
    text=m.text or ''
    s=sessions.get(uid)
    if s and s.busy:
        await m.answer('Hujjatlar tayyorlanmoqda. Iltimos, kuting.');return
    if text in {'/start',CANCEL,'/cancel'}:
        sessions.pop(uid,None)
        await m.answer('Assalomu alaykum!\n\nSud xodimlari bilan o‘tkazilgan suhbat bayonnomalarini avtomatik tayyorlash tizimiga xush kelibsiz.\n\nBayonnoma tayyorlash uchun quyidagi tugmani bosing.',reply_markup=MENU);return
    if text==HELP or text=='/help':
        await m.answer('Yangi bayonnoma tugmasini bosing va 7 bosqichni bajaring. Sana: KK.OO.YYYY. Rasm: JPG/PNG, 10 MB gacha. Tasdiqlashdan oldin har bir maydonni tahrirlash mumkin. /cancel — bekor qilish. Ma’lumotlar 30 daqiqa faollik bo‘lmasa o‘chadi. Bot qayta ishga tushsa, so‘rovni boshidan kiriting. Maxfiylik uchun shaxsiy chatdan foydalaning.',reply_markup=MENU);return
    if text==SAMPLE:
        await m.answer_document(FSInputFile(TEMPLATE),caption='Asl, o‘zgartirilmagan bayonnoma namunasi.');return
    if text==NEW:
        s=Session();sessions[uid]=s;await ask(m,s);return
    if not s:
        await m.answer('Bayonnoma yaratishni boshlang.',reply_markup=MENU);return
    s.touched=time.monotonic()
    if s.mode=='confirm':
        if text==MAKE: await generate_and_send(m,s)
        elif text==EDIT:
            s.mode='choose';await m.answer('Qaysi maydonni o‘zgartirasiz?',reply_markup=keyboard(*[[x] for x in LABELS],[CANCEL]))
        else: await m.answer('Tasdiqlash yoki tahrirlash tugmasini bosing.',reply_markup=CONFIRM)
        return
    if s.mode=='choose':
        if text not in LABELS:
            await m.answer('Maydonni tugma orqali tanlang.');return
        s.step=LABELS.index(text);s.editing=True;s.mode='input';await ask(m,s);return
    try:
        if s.step==6:
            if text==KEEP: s.image=None
            else:
                attachment=m.photo[-1] if m.photo else m.document
                if not attachment:
                    raise ValueError('JPG/PNG rasm yuboring yoki namunadagi rasmni qoldirish tugmasini bosing.')
                if attachment.file_size is None or attachment.file_size>MAX_IMAGE_BYTES:
                    raise ValueError('Rasm hajmi 10 MB dan oshmasin.')
                buf=BytesIO();await m.bot.download(attachment,destination=buf)
                s.image=await asyncio.to_thread(prepare_image,buf.getvalue())
        else:
            if not text: raise ValueError('Matn yuboring.')
            key=KEYS[s.step]
            value=text.strip()
            if key=='date': parse_date(value)
            else: value=validate_text(value,key)
            s.values[key]=value
    except ValueError as exc:
        await m.answer(str(exc));return
    except Exception as exc:
        logging.error('Input failure: %s',type(exc).__name__)
        await m.answer('Rasmni yuklab bo‘lmadi. Qayta yuboring.');return
    if s.editing or s.step==6:
        s.editing=False;await summary(m,s)
    else:
        s.step+=1;await ask(m,s)

@dp.message()
async def route(m: Message):
    if not m.from_user:return
    uid=m.from_user.id
    lock=locks.setdefault(uid,asyncio.Lock())
    if lock.locked():
        await m.answer('Oldingi so‘rov bajarilmoqda. Iltimos, kuting.');return
    async with lock:
        await handle(m)

async def expire_sessions():
    while True:
        await asyncio.sleep(30)
        now=time.monotonic()
        for uid,s in list(sessions.items()):
            if not s.busy and now-s.touched>SESSION_SECONDS and not locks.get(uid,asyncio.Lock()).locked():
                sessions.pop(uid,None)
        for uid,lock in list(locks.items()):
            if uid not in sessions and not lock.locked(): locks.pop(uid,None)

async def main():
    if not BOT_TOKEN: raise SystemExit('BOT_TOKEN topilmadi. .env yoki Railway Variables orqali kiriting.')
    if not TEMPLATE.is_file(): raise SystemExit('Word shabloni topilmadi.')
    cleanup=asyncio.create_task(expire_sessions())
    try:
        async with Bot(BOT_TOKEN) as bot:
            await bot.delete_webhook(drop_pending_updates=True)
            await dp.start_polling(bot)
    finally:
        cleanup.cancel();sessions.clear()
        try: await cleanup
        except asyncio.CancelledError: pass

if __name__=='__main__':
    logging.basicConfig(level=logging.WARNING)
    asyncio.run(main())

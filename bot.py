import asyncio
import logging
import time
import secrets
from dataclasses import dataclass, field, replace
from io import BytesIO
from pathlib import Path
from tempfile import TemporaryDirectory
from aiogram import Bot, Dispatcher, F
from aiogram.enums import ChatType
from aiogram.filters import Command, CommandStart
from aiogram.types import Message, KeyboardButton, ReplyKeyboardMarkup, FSInputFile, BufferedInputFile, InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery
from config import BOT_TOKEN, TEMPLATE, MAX_IMAGE_BYTES, SESSION_SECONDS, ALLOWED_USER_IDS, SOFFICE
from document_generator import Record, validate_text, parse_date, uz_date, filename, generate_docx, to_pdf
from image_processor import prepare_options
from transliteration import convert, SCRIPTS
from pdf_tools import BACK, ENTRY, MIB, PdfTools, positive_env

NEW='📝 Yangi bayonnoma yaratish'; SAMPLE='📄 Bayonnoma namunasini ko‘rish'; HELP='ℹ️ Yordam'
KEEP='🖼 Namunadagi rasmni qoldirish'; MAKE='✅ Bayonnomani tayyorlash'; EDIT='✏️ Tahrirlash'; CANCEL='❌ Bekor qilish'
ACCEPT_IMAGE='✅ Rasmni tasdiqlash'; ORIGINAL_IMAGE='🖼 Asl rasmni saqlash'; REPLACE_IMAGE='🔄 Boshqa rasm yuborish'
SCRIPT_BUTTONS={'🇺🇿 Lotin yozuvi':'latin','🔤 Kirill yozuvi':'cyrillic','✨ Yangi lotin yozuvi':'new_latin'}
SCRIPT_EDIT='🔤 Yozuv turi'
TEXT_OK='✅ Matnni tasdiqlash'
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
MENU=keyboard([NEW],[ENTRY],[SAMPLE,HELP])
CONFIRM=keyboard([MAKE],[EDIT,CANCEL])
IMAGE_MENU=keyboard([ACCEPT_IMAGE],[ORIGINAL_IMAGE],[REPLACE_IMAGE,CANCEL])
SCRIPT_MENU=keyboard(*[[x] for x in SCRIPT_BUTTONS],[CANCEL])
TEXT_MENU=keyboard([TEXT_OK],[EDIT,CANCEL])

@dataclass
class Session:
    values: dict=field(default_factory=dict)
    step: int=0
    mode: str='input'
    script: str='latin'
    text_confirmed: bool=False
    editing: bool=False
    touched: float=field(default_factory=time.monotonic)
    image: bytes | None=None
    busy: bool=False
    pending_original: bytes | None=None
    pending_crop: bytes | None=None

@dataclass
class SavedDocument:
    owner: int
    chat_id: int
    record: Record
    image: bytes | None
    expires: float
    busy: bool=False

saved_documents: dict[str,SavedDocument]={}
SCRIPT_SUFFIX={'latin':'Lotin','cyrillic':'Kirill','new_latin':'Yangi_lotin'}

def document_buttons(token):
    labels=[('🔤 Kirillga o‘girish','cyrillic'),('🇺🇿 Lotinga o‘girish','latin'),('✨ Yangi lotinga o‘girish','new_latin'),('🗑 Saqlangan ma’lumotni o‘chirish','delete')]
    return InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text=label,callback_data=f'doc:{token}:{action}')] for label,action in labels])

def purge_documents(now=None):
    now=time.monotonic() if now is None else now
    for token,item in list(saved_documents.items()):
        if not item.busy and item.expires<=now:saved_documents.pop(token,None)

def save_document(owner,chat_id,record,image):
    purge_documents()
    owned=[key for key,item in saved_documents.items() if item.owner==owner and not item.busy]
    while len(owned)>=5:saved_documents.pop(owned.pop(0),None)
    token=secrets.token_hex(6)
    saved_documents[token]=SavedDocument(owner,chat_id,record,image,time.monotonic()+SESSION_SECONDS)
    return token

async def send_document_pair(m,record,image,with_suffix=False):
    async with workers:
        with TemporaryDirectory(prefix='bayonnoma-') as temp:
            stem=filename(record)+(('_'+SCRIPT_SUFFIX[record.script]) if with_suffix else '')
            target=Path(temp)/(stem+'.docx')
            await asyncio.to_thread(generate_docx,record,target,image)
            try:
                pdf=await asyncio.to_thread(to_pdf,target)
            except ValueError:raise
            except Exception:
                await m.answer_document(FSInputFile(target),caption='Word tayyor. PDF yaratishda xato yuz berdi; qayta urinish mumkin.')
                raise
            await m.answer_document(FSInputFile(target),caption='Tahrirlash va chop etish uchun Word')
            await m.answer_document(FSInputFile(pdf),caption='Chop etish uchun PDF')

sessions: dict[int,Session]={}
locks: dict[int,asyncio.Lock]={}
workers=asyncio.Semaphore(2)
dp=Dispatcher()
pdf_tools: PdfTools | None = None

async def ask(m,s):
    await m.answer(QUESTIONS[s.step],reply_markup=keyboard([KEEP],[CANCEL]) if s.step==6 else keyboard([CANCEL]))

async def summary(m,s):
    v={k:convert(value,s.script) if k!='date' else value for k,value in s.values.items()};s.mode='review'
    s.text_confirmed=False
    await m.answer(f'📋 Bayonnoma ma’lumotlari:\n\nYozuv: {SCRIPTS[s.script]}\n\nSuhbat o‘tkazilgan xodim: {v["employee"]}\n\nLavozimi: {v["employee_role"]}\n\nBayonnoma sanasi: {convert(uz_date(v["date"]),s.script)}\n\nSuhbat o‘tkazilgan joy: {v["place"]}\n\nSuhbat o‘tkazgan xodim: {v["officer"]}\n\nLavozimi: {v["officer_role"]}\n\nRasm: {"yuborilgan" if s.image else "namunadagi rasm"}\n\nIsm va lavozimlarni tekshiring. Harflar va apostroflar mahalliy transliteratsiya bilan to‘g‘rilandi. Matnni tasdiqlaysizmi?',reply_markup=TEXT_MENU)

async def generate_and_send(m,s):
    s.busy=True
    try:
        await m.answer('⏳ Word va PDF hujjatlar tayyorlanmoqda…')
        record=Record(**s.values,script=s.script)
        await send_document_pair(m,record,s.image)
        token=save_document(m.from_user.id,m.chat.id,record,s.image)
        sessions.pop(m.from_user.id,None)
        s.image=None;s.values.clear()
        await m.answer(f'✅ Bayonnoma tayyor!\nJoriy yozuv: {SCRIPTS[record.script]}\n\nShu bayonnomani boshqa yozuvda olish uchun tanlang. Ma’lumot va rasm 30 daqiqa saqlanadi (oxirgi 5 ta bayonnoma).',reply_markup=document_buttons(token))
        await m.answer('Yangi bayonnoma yaratishingiz yoki yuqoridagi tugmalardan foydalanishingiz mumkin.',reply_markup=MENU)
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
    pdf_session = pdf_tools.sessions.get(uid) if pdf_tools else None
    if text == ENTRY and pdf_tools:
        pdf_session = pdf_tools.session_for(uid)
        pdf_session.expire()
        await pdf_tools.start(m, pdf_session)
        return
    if pdf_session and pdf_session.active:
        if text in {'/start', BACK, NEW, SAMPLE, HELP, '/help', CANCEL, '/cancel'}:
            pdf_session.active = False
            if text == BACK:
                await m.answer('Kerakli amalni tanlang.', reply_markup=MENU)
                return
        else:
            pdf_session.expire()
            try:
                await pdf_tools.handle(m, pdf_session)
            except Exception as exc:
                logging.warning('PDF amali bajarilmadi (%s).', type(exc).__name__)
                await m.answer('Amalni yakunlab bo‘lmadi. Qayta urinib ko‘ring.')
            return
    if text in {'/start',CANCEL,'/cancel'}:
        sessions.pop(uid,None)
        await m.answer('Assalomu alaykum!\n\nSud xodimlari bilan o‘tkazilgan suhbat bayonnomalarini avtomatik tayyorlash tizimiga xush kelibsiz.\n\nBayonnoma tayyorlash uchun quyidagi tugmani bosing.',reply_markup=MENU);return
    if text==HELP or text=='/help':
        await m.answer('Yangi bayonnoma tugmasini bosing va 7 bosqichni bajaring. Sana: KK.OO.YYYY. Rasm: JPG/PNG, 10 MB gacha. Tasdiqlashdan oldin har bir maydonni tahrirlash mumkin. /cancel — bekor qilish. Ma’lumotlar 30 daqiqa faollik bo‘lmasa o‘chadi. Bot qayta ishga tushsa, so‘rovni boshidan kiriting. Maxfiylik uchun shaxsiy chatdan foydalaning.',reply_markup=MENU);return
    if text==SAMPLE:
        await m.answer_document(FSInputFile(TEMPLATE),caption='Asl, o‘zgartirilmagan bayonnoma namunasi.');return
    if text==NEW:
        s=Session(mode='script');sessions[uid]=s
        await m.answer('Bayonnoma qaysi yozuvda tayyorlansin?',reply_markup=SCRIPT_MENU);return
    if not s:
        await m.answer('Bayonnoma yaratishni boshlang.',reply_markup=MENU);return
    s.touched=time.monotonic()
    if s.mode=='script':
        if text not in SCRIPT_BUTTONS:
            await m.answer('Yozuv turini tugma orqali tanlang.',reply_markup=SCRIPT_MENU);return
        s.script=SCRIPT_BUTTONS[text]
        if s.editing:
            s.editing=False;await summary(m,s)
        else:
            s.mode='input';await ask(m,s)
        return
    if s.mode=='review':
        if text==TEXT_OK:
            s.text_confirmed=True;s.mode='confirm'
            await m.answer('✅ Matn tasdiqlandi. Word va PDF bayonnomani tayyorlash uchun tugmani bosing.',reply_markup=CONFIRM)
        elif text==EDIT:
            s.mode='choose';await m.answer('Qaysi maydonni o‘zgartirasiz?',reply_markup=keyboard(*[[x] for x in LABELS],[SCRIPT_EDIT],[CANCEL]))
        else:await m.answer('Matnni tasdiqlang yoki tahrirlang.',reply_markup=TEXT_MENU)
        return
    if s.mode=='image_preview':
        if text==REPLACE_IMAGE:
            s.pending_original=None;s.pending_crop=None;s.mode='input'
            await ask(m,s);return
        if text not in {ACCEPT_IMAGE,ORIGINAL_IMAGE}:
            await m.answer('Rasmni tasdiqlang, aslini saqlang yoki boshqa rasm yuboring.',reply_markup=IMAGE_MENU);return
        s.image=s.pending_crop if text==ACCEPT_IMAGE else s.pending_original
        s.pending_original=None;s.pending_crop=None;s.editing=False
        await summary(m,s);return
    if s.mode=='confirm':
        if text==MAKE: await generate_and_send(m,s)
        elif text==EDIT:
            s.mode='choose';await m.answer('Qaysi maydonni o‘zgartirasiz?',reply_markup=keyboard(*[[x] for x in LABELS],[SCRIPT_EDIT],[CANCEL]))
        else: await m.answer('Tasdiqlash yoki tahrirlash tugmasini bosing.',reply_markup=CONFIRM)
        return
    if s.mode=='choose':
        if text==SCRIPT_EDIT:
            s.editing=True;s.mode='script';await m.answer('Yozuv turini tanlang.',reply_markup=SCRIPT_MENU);return
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
                async with workers:
                    options=await asyncio.to_thread(prepare_options,buf.getvalue())
                caption=('🤖 Yuzlar aniqlanib, 17:9 ko‘rinishga qirqildi. Yuzlar, qo‘llar va hujjat to‘liq ko‘rinayotganini tekshiring.'
                         if options.cropped else
                         '🖼 Xavfsiz qirqish aniqlanmadi. Asl rasm kesilmasdan 17:9 maydonga sig‘dirildi.')
                await m.answer_photo(BufferedInputFile(options.suggested,filename='Rasm_17x9.png'),
                                     caption=caption+'\n\nTasdiqlasangiz, shu ko‘rinish bayonnomaga qo‘yiladi. Aslini saqlash — suratni kesmasdan joylashtirish.',
                                     reply_markup=IMAGE_MENU)
                s.pending_original=options.original;s.pending_crop=options.suggested
                s.mode='image_preview'
                return
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
    file_session = pdf_tools.sessions.get(uid) if pdf_tools else None
    queued_upload = bool(file_session and file_session.active and m.document)
    if lock.locked() and not queued_upload:
        await m.answer('Oldingi so‘rov bajarilmoqda. Iltimos, kuting.');return
    upload_target = (file_session.mode, file_session.selected_group) if queued_upload else None
    async with lock:
        if queued_upload and (not file_session.active or (file_session.mode, file_session.selected_group) != upload_target):
            await m.answer('Faylni qabul qilish bo‘limi o‘zgardi. Amalni tanlab, faylni qayta yuboring.')
            return
        await handle(m)

@dp.callback_query(F.data.startswith('doc:'))
async def document_action(q: CallbackQuery):
    parts=(q.data or '').split(':')
    if len(parts)!=3 or parts[2] not in {*SCRIPTS,'delete'}:
        await q.answer('Tugma noto‘g‘ri.',show_alert=True);return
    _,token,action=parts
    item=saved_documents.get(token)
    if not item or item.expires<=time.monotonic():
        if item and not item.busy:saved_documents.pop(token,None)
        await q.answer('Saqlash muddati tugagan yoki ma’lumot o‘chirilgan. Yangi bayonnoma yarating.',show_alert=True);return
    if not q.message or q.message.chat.type!=ChatType.PRIVATE or item.owner!=q.from_user.id or item.chat_id!=q.message.chat.id:
        await q.answer('Bu bayonnomadan foydalanishga ruxsat yo‘q.',show_alert=True);return
    if ALLOWED_USER_IDS and q.from_user.id not in ALLOWED_USER_IDS:
        await q.answer('Ruxsat berilmagan.',show_alert=True);return
    lock=locks.setdefault(q.from_user.id,asyncio.Lock())
    if lock.locked() or item.busy:
        await q.answer('Oldingi so‘rov bajarilmoqda. Iltimos, kuting.',show_alert=True);return
    async with lock:
        if action=='delete':
            saved_documents.pop(token,None)
            await q.answer('Saqlangan ma’lumot o‘chirildi.')
            await q.message.edit_reply_markup(reply_markup=None)
            await q.message.answer('🗑 Shu bayonnomaning serverdagi ma’lumoti va rasmi o‘chirildi. Telegramga yuborilgan fayllar chatda qoladi.')
            return
        item.busy=True
        try:
            await q.answer('Bayonnoma qayta tayyorlanmoqda…')
            record=replace(item.record,script=action)
            await send_document_pair(q.message,record,item.image,with_suffix=True)
            if item.expires>time.monotonic():
                await q.message.answer(f'✅ Bayonnoma qayta tayyorlandi.\nJoriy yozuv: {SCRIPTS[action]}',reply_markup=document_buttons(token))
            else:
                saved_documents.pop(token,None)
                await q.message.answer('✅ Bayonnoma qayta tayyorlandi. Saqlash muddati tugagani uchun serverdagi ma’lumot tozalandi.')
        except ValueError as exc:
            await q.message.answer(str(exc))
        except Exception as exc:
            logging.error('Script conversion/send failure: %s',type(exc).__name__)
            await q.message.answer('Qayta tayyorlash yoki yuborishda xato yuz berdi. Tugmani qayta bosib urinib ko‘ring.')
        finally:
            item.busy=False
            purge_documents()

@dp.callback_query(F.data.startswith(('add:', 'pg:')))
async def pdf_result_action(q: CallbackQuery):
    uid = q.from_user.id
    if not pdf_tools or not isinstance(q.message, Message) or q.message.chat.type != ChatType.PRIVATE:
        await q.answer('Botdan shaxsiy chatda foydalaning.', show_alert=True)
        return
    if ALLOWED_USER_IDS and uid not in ALLOWED_USER_IDS:
        await q.answer('Ruxsat berilmagan.', show_alert=True)
        return
    lock = locks.setdefault(uid, asyncio.Lock())
    if lock.locked():
        await q.answer('Oldingi so‘rov bajarilmoqda. Iltimos, kuting.')
        return
    async with lock:
        session = pdf_tools.session_for(uid)
        session.expire()
        try:
            if q.data.startswith('add:'):
                await pdf_tools.add_to_result(q, session)
            else:
                await pdf_tools.group_action(q, session)
        except Exception as exc:
            logging.warning('Tayyor PDFni tanlab bo‘lmadi (%s).', type(exc).__name__)
            await q.message.answer('Tayyor PDFni tanlab bo‘lmadi. Qayta urinib ko‘ring.')

async def expire_sessions():
    while True:
        await asyncio.sleep(30)
        now=time.monotonic()
        purge_documents(now)
        if pdf_tools:
            pdf_tools.purge(locks)
        for uid,s in list(sessions.items()):
            if not s.busy and now-s.touched>SESSION_SECONDS and not locks.get(uid,asyncio.Lock()).locked():
                sessions.pop(uid,None)
        for uid,lock in list(locks.items()):
            has_pdf_session = pdf_tools is not None and uid in pdf_tools.sessions
            if uid not in sessions and not has_pdf_session and not lock.locked():
                locks.pop(uid, None)

async def main():
    if not BOT_TOKEN: raise SystemExit('BOT_TOKEN topilmadi. .env yoki Railway Variables orqali kiriting.')
    if not TEMPLATE.is_file(): raise SystemExit('Word shabloni topilmadi.')
    global pdf_tools
    with TemporaryDirectory(prefix='word-pdf-') as directory:
        pdf_tools = PdfTools(
            Path(directory), positive_env('MAX_FILE_MIB', 19, 19) * MIB,
            positive_env('FILE_TTL_SECONDS', 3600),
            positive_env('CONVERSION_TIMEOUT_SECONDS', 90), workers, SOFFICE,
        )
        cleanup = asyncio.create_task(expire_sessions())
        try:
            async with Bot(BOT_TOKEN) as bot:
                await bot.delete_webhook(drop_pending_updates=True)
                print('Bayonnoma va Word/PDF bo‘limlari ishga tayyor.', flush=True)
                await dp.start_polling(bot)
        finally:
            cleanup.cancel()
            sessions.clear()
            saved_documents.clear()
            try:
                await cleanup
            except asyncio.CancelledError:
                pass
            pdf_tools = None

if __name__=='__main__':
    logging.basicConfig(level=logging.WARNING)
    asyncio.run(main())

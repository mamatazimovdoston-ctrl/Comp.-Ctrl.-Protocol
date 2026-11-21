import asyncio
import logging
import os
import re
from contextlib import suppress
from dataclasses import dataclass, field
from pathlib import Path
from time import monotonic
from uuid import uuid4

from aiogram import BaseMiddleware, Bot, Dispatcher, F, Router
from aiogram.exceptions import TelegramAPIError
from aiogram.types import (
    FSInputFile, InlineKeyboardButton, InlineKeyboardMarkup, KeyboardButton, ReplyKeyboardMarkup,
)

from pdf_documents import (
    DocumentError, convert_word, merge_pdfs, parse_selection, pdf_count,
    select_pdf,
)

ENTRY = "📎 Word va PDF"
BACK = "Asosiy menyu"
WORD = "Word → PDF"
PDF = "PDF birlashtirish"
HELP = "Yordam"
ALL_BUTTON = "Barchasini"
CLEAR = "Navbatni tozalash"
MERGE = "Birlashtirish"
CANCEL = "Bekor qilish"
ADD = "Shu PDFga fayl qo‘shish"
BUSY = "Ishlanmoqda…"
CONTINUE = "Sahifalarni yozing yoki «Barchasini» tugmasini bosing."
HELP_TEXT = """Word → PDF
.doc va .docx fayllarini hujjat sifatida yuboring. Fayllarni yuborib bo‘lgach, «Barchasini» tugmasini bosing yoki sahifalarni yozing.

• 2, 4-6, 9 — har bir hujjatdan 2, 4, 5, 6 va 9-betlar.
• Har bir hujjat uchun raqam va sahifalarni alohida qatorlarda yozing:
1: 2-4, 7
2: barchasini
Ro‘yxatda ko‘rsatilmagan hujjatlar navbatda qoladi. Sahifa raqamlari PDFdagi birinchi jismoniy sahifadan boshlanadi.

PDF birlashtirish
Kamida ikkita PDFni kerakli tartibda yuboring va «Birlashtirish»ni bosing.

Tayyor PDFga qo‘shish
Natija ostida «Shu PDFga fayl qo‘shish»ni bosing. Masalan, Wordning 1-betidan olingan PDFga bir betli Ilova.pdf faylini yuborsangiz, «Birlashtirish» 2 betli PDF beradi. Avval Worddan olingan bet, keyin ilova keladi.

Faol navbatdan chiqish uchun «Bekor qilish»ni bosing yoki /bekor yozing."""
LOG = logging.getLogger(__name__)
MIB = 1024 * 1024
UPLOAD_LIMIT = 50_000_000


def keyboard(*rows):
    return ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text=label) for label in row] for row in rows],
        resize_keyboard=True,
    )


MAIN_KEYS = keyboard((WORD, PDF), (HELP, BACK))
WORD_KEYS = keyboard((ALL_BUTTON, CLEAR), (WORD, PDF), (HELP, CANCEL), (BACK,))
PDF_KEYS = keyboard((MERGE, CANCEL), (WORD, PDF), (HELP, BACK))


def positive_env(name, default, maximum=None):
    value = int(os.environ.get(name, default))
    if value < 1 or (maximum is not None and value > maximum):
        raise ValueError(name)
    return value


@dataclass
class StoredFile:
    name: str
    path: Path
    expires: float
    pages: int = 0

    def remove(self):
        self.path.unlink(missing_ok=True)


@dataclass
class Session:
    directory: Path
    mode: str = ""
    active: bool = False
    words: dict[int, StoredFile] = field(default_factory=dict)
    next_word: int = 1
    pdfs: list[StoredFile] = field(default_factory=list)
    additions: list[StoredFile] = field(default_factory=list)
    results: dict[str, StoredFile] = field(default_factory=dict)
    base: StoredFile | None = None
    waiting_for_base: bool = False
    base_unique_id: str | None = None
    base_result_id: str | None = None

    def clear_word(self):
        for item in self.words.values():
            item.remove()
        self.words.clear()
        self.next_word = 1

    def clear_merge(self, mode):
        items = self.additions if mode == "add" else self.pdfs
        for item in items:
            item.remove()
        items.clear()
        if mode == "add":
            if self.base:
                self.base.remove()
            self.base = None
            self.waiting_for_base = False
            self.base_unique_id = None
            self.base_result_id = None

    def expire(self):
        now = monotonic()
        for queue in (self.words, self.results):
            for key, item in list(queue.items()):
                if item.expires <= now:
                    item.remove()
                    del queue[key]
        for queue in (self.pdfs, self.additions):
            for item in queue[:]:
                if item.expires <= now:
                    item.remove()
                    queue.remove(item)
        if self.base and self.base.expires <= now:
            self.base.remove()
            self.base = None
            self.waiting_for_base = True
        with suppress(OSError):
            self.directory.rmdir()


class PdfTools:
    def __init__(self, root, max_bytes, ttl, timeout, workers, office):
        self.root = root
        self.max_bytes = max_bytes
        self.ttl = ttl
        self.timeout = timeout
        self.workers = workers
        self.office = office
        self.sessions = {}

    def session_for(self, uid):
        if uid not in self.sessions:
            self.sessions[uid] = Session(self.root / str(uid))
        return self.sessions[uid]

    async def handle(self, message, session):
        text = message.text or ""
        command = text.split(maxsplit=1)[0].split("@", 1)[0] if text.startswith("/") else ""
        if text == WORD:
            await self.menu_word(message, session)
        elif text == PDF:
            await self.menu_pdf(message, session)
        elif text == HELP or command == "/yordam":
            await self.help(message)
        elif text == CLEAR:
            await self.clear_word(message, session)
        elif text == MERGE:
            await self.merge(message, session)
        elif text == CANCEL or command == "/bekor":
            await self.cancel(message, session)
        elif message.document:
            await self.upload(message, session, message.bot)
        elif session.mode and text:
            await self.text(message, session)
        else:
            await message.answer("Menyudan amalni tanlang.", reply_markup=MAIN_KEYS)

    def stored(self, session, name, suffix):
        session.directory.mkdir(mode=0o700, exist_ok=True)
        return StoredFile(name, session.directory / (uuid4().hex + suffix), monotonic() + self.ttl)

    def purge(self, locks):
        for uid, session in list(self.sessions.items()):
            lock = locks.get(uid)
            if lock is not None and lock.locked():
                continue
            session.expire()
            if not session.directory.exists() and not session.active:
                del self.sessions[uid]

    @staticmethod
    async def start(message, session):
        session.active = True
        session.mode = ""
        await message.answer("Kerakli amalni tanlang.", reply_markup=MAIN_KEYS)

    @staticmethod
    async def help(message):
        await message.answer(HELP_TEXT)

    @staticmethod
    async def show_queue(message, heading, lines, tail, keys):
        text = heading
        for line in lines:
            if len(text) + len(line) > 1500:
                await message.answer(text)
                text = ""
            text += "\n" + line
        await message.answer(f"{text}\n\n{tail}", reply_markup=keys)

    async def word_queue(self, message, session, heading="Word navbati"):
        lines = [f"{number}. {item.name}" for number, item in session.words.items()]
        await self.show_queue(message, heading, lines or ["Navbat bo‘sh."],
                              CONTINUE if lines else ".doc yoki .docx yuboring.", WORD_KEYS)

    async def pdf_queue(self, message, session):
        if session.mode == "add":
            items = ([session.base] if session.base else []) + session.additions
            tail = ("Avval tayyor PDFni Telegramdan qayta jo‘nating." if session.waiting_for_base
                    else "Qo‘shmoqchi bo‘lgan PDF fayllaringizni yuboring yoki «Birlashtirish»ni bosing.")
        else:
            items = session.pdfs
            tail = "Kamida ikkita PDF yuboring va «Birlashtirish»ni bosing."
        lines = [f"{index}. {item.name} ({item.pages} sahifa)" for index, item in enumerate(items, 1)]
        await self.show_queue(message, "PDF navbati", lines or ["Navbat bo‘sh."], tail, PDF_KEYS)

    async def menu_word(self, message, session):
        session.mode = "word"
        await self.word_queue(message, session)

    async def menu_pdf(self, message, session):
        session.mode = "pdf"
        await self.pdf_queue(message, session)

    async def clear_word(self, message, session):
        session.clear_word()
        session.mode = "word"
        await message.answer("Word navbati tozalandi. .doc yoki .docx yuboring.", reply_markup=WORD_KEYS)

    @staticmethod
    async def cancel(message, session):
        if session.mode == "word":
            session.clear_word()
        elif session.mode in ("pdf", "add"):
            session.clear_merge(session.mode)
        session.mode = ""
        await message.answer("Amal bekor qilindi.", reply_markup=MAIN_KEYS)

    async def upload(self, message, session, bot):
        mode = session.mode
        if not mode:
            await message.answer("Faylni yuborishdan oldin menyudan amalni tanlang.", reply_markup=MAIN_KEYS)
            return
        document = message.document
        raw_name = (document.file_name or "Hujjat").replace("\\", "/").split("/")[-1]
        suffix = Path(raw_name).suffix.lower()
        name = "".join(char if char.isprintable() else "_" for char in raw_name)
        if len(name) > 120:
            name = name[:110] + "…" + suffix[:8]
        allowed = (".doc", ".docx") if mode == "word" else (".pdf",)
        if suffix not in allowed:
            await message.answer(f"«{name}» formati qo‘llab-quvvatlanmaydi. Qabul qilinadigan formatlar: {', '.join(allowed)}.")
            return
        if mode == "add" and session.waiting_for_base and session.base_unique_id:
            if document.file_unique_id != session.base_unique_id:
                await message.answer("Avval tugmasini bosgan tayyor PDFni Telegramdan qayta jo‘nating.")
                return
        if document.file_size is not None and document.file_size > self.max_bytes:
            await message.answer(f"«{name}» fayli juda katta. Chegara: {self.max_bytes / MIB:g} MiB.")
            return
        item = self.stored(session, name, suffix)
        accepted = False
        try:
            with item.path.open("wb") as stream:
                size = 0
                async for chunk in self.download_chunks(bot, document.file_id):
                    size += len(chunk)
                    if size > self.max_bytes:
                        raise DocumentError(f"Fayl juda katta. Chegara: {self.max_bytes / MIB:g} MiB.")
                    stream.write(chunk)
            if mode != "word":
                async with self.workers:
                    item.pages = await asyncio.to_thread(pdf_count, item.path)
            item.expires = monotonic() + self.ttl
            if mode == "word":
                session.words[session.next_word] = item
                session.next_word += 1
            elif mode == "add" and session.waiting_for_base:
                session.base = item
                session.waiting_for_base = False
            else:
                (session.additions if mode == "add" else session.pdfs).append(item)
            accepted = True
        except DocumentError as error:
            await message.answer(f"«{name}». {error}")
            return
        except (TelegramAPIError, OSError, TimeoutError):
            await message.answer(f"«{name}» faylini yuklab bo‘lmadi. Qayta yuboring.")
            return
        finally:
            if not accepted:
                item.remove()
        if mode == "word":
            await self.word_queue(message, session)
        else:
            await self.pdf_queue(message, session)

    @staticmethod
    async def download_chunks(bot, file_id):
        descriptor = await bot.get_file(file_id)
        if not descriptor.file_path:
            raise DocumentError("Telegram faylni yuklash manzilini bermadi.")
        url = bot.session.api.file_url(bot.token, descriptor.file_path)
        async for chunk in bot.session.stream_content(url=url, timeout=30, chunk_size=65536):
            yield chunk

    async def text(self, message, session):
        if session.mode != "word":
            keys = PDF_KEYS if session.mode in ("pdf", "add") else MAIN_KEYS
            await message.answer("Menyudan amalni tanlang yoki fayl yuboring.", reply_markup=keys)
            return
        if not session.words:
            await self.word_queue(message, session)
            return
        try:
            selections = parse_selection(message.text, session.words)
        except DocumentError as error:
            await message.answer(str(error))
            return
        await message.answer(BUSY)
        completed = 0
        for number, item in list(session.words.items()):
            if number in selections and await self.word_result(message, session, item, selections[number]):
                del session.words[number]
                completed += 1
        if not session.words:
            session.next_word = 1
        await self.word_queue(message, session, f"Tayyor PDFlar soni: {completed}. Qolgan Word navbati")

    async def word_result(self, message, session, item, selection):
        result_id = uuid4().hex
        result = self.stored(session, Path(item.name).stem + ".pdf", ".pdf")
        full = self.stored(session, "", ".pdf")
        sent = False
        try:
            async with self.workers:
                await convert_word(item.path, full.path, self.timeout, self.office)
                result.pages = await asyncio.to_thread(select_pdf, full.path, result.path, selection)
            await self.send_pdf(message, result, result_id)
            result.expires = monotonic() + self.ttl
            session.results[result_id] = result
            sent = True
            item.remove()
        except DocumentError as error:
            await message.answer(f"«{item.name}». {error}")
        except TelegramAPIError:
            await message.answer(f"«{item.name}» natijasini Telegramga yuborib bo‘lmadi. Hujjat navbatda.")
        except Exception as error:
            LOG.warning("Word amali bajarilmadi (%s).", type(error).__name__)
            await message.answer(f"«{item.name}» hujjatini aylantirib bo‘lmadi. Hujjat navbatda.")
        finally:
            full.remove()
            if not sent:
                result.remove()
        return sent

    @staticmethod
    async def send_pdf(message, result, result_id=None):
        if result.path.stat().st_size > UPLOAD_LIMIT:
            raise DocumentError("Natija Telegram yuklash chegarasidan katta (50 MB).")
        markup = None
        if result_id:
            markup = InlineKeyboardMarkup(inline_keyboard=[[
                InlineKeyboardButton(text=ADD, callback_data="add:" + result_id),
            ]])
        await message.answer_document(FSInputFile(result.path, filename=result.name),
                                      caption=f"Jami {result.pages} sahifa.", reply_markup=markup)

    async def add_to_result(self, callback, session):
        message = callback.message
        if not re.fullmatch(r"add:[a-f0-9]{32}", callback.data) or not message.document:
            await callback.answer("Tayyor PDF topilmadi.")
            return
        result = session.results.get(callback.data[4:])
        unique_id = message.document.file_unique_id
        if session.base_result_id != callback.data:
            session.clear_merge("add")
        session.active = True
        session.mode = "add"
        session.base_unique_id = unique_id
        session.base_result_id = callback.data
        if session.base is None and result:
            session.base = self.stored(session, result.name, ".pdf")
            try:
                os.link(result.path, session.base.path)
            except OSError:
                session.base = None
            else:
                session.base.pages = result.pages
                session.base.expires = result.expires
        session.waiting_for_base = session.base is None
        await callback.answer()
        await self.pdf_queue(message, session)

    async def merge(self, message, session):
        mode = session.mode
        if mode not in ("add", "pdf"):
            await message.answer("Menyudan «PDF birlashtirish» amalini tanlang.")
            return
        if mode == "add" and not session.base:
            await self.pdf_queue(message, session)
            return
        items = [session.base, *session.additions] if mode == "add" else session.pdfs
        if len(items) < 2:
            await message.answer("Birlashtirish uchun yana PDF fayl yuboring.", reply_markup=PDF_KEYS)
            return
        result = self.stored(session, "Birlashtirilgan.pdf", ".pdf")
        try:
            await message.answer(BUSY)
            async with self.workers:
                result.pages = await asyncio.to_thread(merge_pdfs, [item.path for item in items], result.path)
            await self.send_pdf(message, result)
        except DocumentError as error:
            await message.answer(str(error), reply_markup=PDF_KEYS)
        except TelegramAPIError:
            await message.answer("PDFni Telegramga yuborib bo‘lmadi. Fayllar navbatda.", reply_markup=PDF_KEYS)
        except Exception as error:
            LOG.warning("PDF amali bajarilmadi (%s).", type(error).__name__)
            await message.answer("PDFlarni birlashtirib bo‘lmadi. Fayllar navbatda.", reply_markup=PDF_KEYS)
        else:
            session.clear_merge(mode)
            session.mode = ""
            await message.answer("Birlashtirish tugadi.", reply_markup=MAIN_KEYS)
        finally:
            result.remove()

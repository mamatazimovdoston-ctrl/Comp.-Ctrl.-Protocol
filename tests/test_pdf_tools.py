"""Haqiqiy Word va PDF namunalari bilan Telegram yangilanishlarini sinash."""

import asyncio
import subprocess
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from time import monotonic

from aiogram import Bot
from aiogram.client.session.base import BaseSession
from aiogram.types import Update
from pypdf import PdfReader, PdfWriter

import bot as protocol
from pdf_tools import ADD, ALL_BUTTON, BACK, CANCEL, CLEAR, ENTRY, HELP, MERGE, PDF, WORD, PdfTools


def make_word(root, name, count, suffix):
    source = root / f"{name}.fodt"
    paragraphs = "".join(
        f'<text:p text:style-name="{"Next" if page > 1 else "Standard"}">{name.upper()} PAGE {page}</text:p>'
        for page in range(1, count + 1)
    )
    source.write_text(f'''<?xml version="1.0" encoding="UTF-8"?>
<office:document xmlns:office="urn:oasis:names:tc:opendocument:xmlns:office:1.0"
 xmlns:style="urn:oasis:names:tc:opendocument:xmlns:style:1.0"
 xmlns:text="urn:oasis:names:tc:opendocument:xmlns:text:1.0"
 xmlns:fo="urn:oasis:names:tc:opendocument:xmlns:xsl-fo-compatible:1.0"
 office:version="1.2" office:mimetype="application/vnd.oasis.opendocument.text">
 <office:automatic-styles><style:style style:name="Next" style:family="paragraph">
 <style:paragraph-properties fo:break-before="page"/>
 </style:style></office:automatic-styles>
 <office:body><office:text>{paragraphs}</office:text></office:body>
</office:document>
''', encoding="utf-8")
    filter_name = {"doc": "MS Word 97", "docx": "Office Open XML Text", "pdf": "writer_pdf_Export"}[suffix]
    subprocess.run(
        ["libreoffice", f"-env:UserInstallation={(root / 'fixtures-profile').as_uri()}", "--headless",
         "--infilter=OpenDocument Text Flat XML", "--convert-to", f"{suffix}:{filter_name}", "--outdir", str(root), str(source)],
        check=True, capture_output=True, timeout=30,
    )
    output = source.with_suffix("." + suffix)
    if not output.exists():
        raise RuntimeError(f"Namuna tayyorlanmadi: {output.name}")
    return output


class TelegramStub(BaseSession):
    def __init__(self):
        super().__init__()
        self.files = {}
        self.sent = []
        self.messages = []
        self.callbacks = []
        self.delay = 0

    async def close(self):
        pass

    async def make_request(self, bot, method, timeout=None):
        name = method.__api_method__
        if name == "getFile":
            from aiogram.types import File
            return File(file_id=method.file_id, file_unique_id=method.file_id,
                        file_path=method.file_id)
        if name == "sendMessage":
            self.messages.append(method)
        elif name == "sendDocument":
            self.sent.append((method, Path(method.document.path).read_bytes()))
            await asyncio.sleep(self.delay)
        elif name == "answerCallbackQuery":
            self.callbacks.append(method.text)
        else:
            raise AssertionError(name)
        return True

    async def stream_content(self, url, **kwargs):
        yield self.files[url.rsplit("/", 1)[-1]]


class BotIntegration(unittest.IsolatedAsyncioTestCase):
    @classmethod
    def setUpClass(cls):
        cls.fixtures = TemporaryDirectory()
        cls.addClassCleanup(cls.fixtures.cleanup)
        root = Path(cls.fixtures.name)
        cls.a = make_word(root, "bayonnoma", 4, "docx")
        cls.b = make_word(root, "hisobot", 2, "doc")
        cls.x = make_word(root, "ilova", 1, "pdf")
        cls.y = make_word(root, "izoh", 2, "pdf")
        reader = PdfReader(cls.y)
        writer = PdfWriter()
        for page in reader.pages:
            page.rotate(90)
            page.mediabox.upper_right = (720, 905)
            writer.add_page(page)
        writer.write(cls.y)
        cls.broken = root / "buzilgan.pdf"
        cls.broken.write_bytes(b"%PDF-1.7\nBuzilgan fayl")
        cls.encrypted = root / "parol.pdf"
        writer.encrypt("test")
        writer.write(cls.encrypted)

    async def asyncSetUp(self):
        self.runtime = TemporaryDirectory()
        self.addCleanup(self.runtime.cleanup)
        self.api = TelegramStub()
        self.bot = Bot("100:testing", session=self.api)
        self.app = PdfTools(Path(self.runtime.name), 19 * 1024**2, 3600, 30,
                            asyncio.Semaphore(2), "libreoffice")
        self.addCleanup(setattr, protocol, "pdf_tools", protocol.pdf_tools)
        self.addCleanup(protocol.sessions.clear)
        self.addCleanup(protocol.locks.clear)
        protocol.pdf_tools = self.app
        self.seq = 0

    async def update(self, text=None, path=None, user=7, callback=None, identity=None, filename=None):
        self.seq += 1
        person = {"id": user, "is_bot": False, "first_name": "Sinov"}
        message = {"date": 1, "message_id": self.seq,
                   "chat": {"id": user, "type": "private"}, "from": person}
        if text is not None:
            message["text"] = text
        if path is not None:
            file_id = f"file{self.seq}"
            data = path.read_bytes()
            self.api.files[file_id] = data
            message["document"] = {"file_id": file_id, "file_unique_id": identity or file_id,
                                   "file_name": filename or path.name, "file_size": len(data)}
        if callback:
            method, data = self.api.sent[callback - 1]
            button = method.reply_markup.inline_keyboard[0][0]
            self.assertEqual(button.text, ADD)
            message["from"] = {"id": 100, "is_bot": True, "first_name": "Bot"}
            message["document"] = {"file_id": f"result{callback}", "file_unique_id": f"output{callback}",
                                   "file_name": method.document.filename, "file_size": len(data)}
            payload = {"callback_query": {"id": str(self.seq), "chat_instance": "test",
                                          "from": person, "message": message, "data": button.callback_data}}
        else:
            payload = {"message": message}
        update = Update.model_validate({"update_id": self.seq, **payload})
        await protocol.dp.feed_update(self.bot, update)

    def verify(self, labels, index=-1):
        from io import BytesIO
        method, content = self.api.sent[index]
        pages = PdfReader(BytesIO(content)).pages
        self.assertEqual(
            ["".join(page.extract_text().split()) for page in pages],
            ["".join(label.split()) for label in labels],
        )
        self.assertEqual(method.caption, f"Jami {len(labels)} sahifa.")
        return list(pages)

    async def queue_word(self, *paths):
        await self.update(ENTRY)
        await self.update(WORD)
        for path in paths:
            await self.update(path=path)

    async def test_single_and_multiple_all(self):
        await self.update("/start")
        labels = [button.text for row in self.api.messages[-1].reply_markup.keyboard for button in row]
        self.assertIn(protocol.NEW, labels)
        self.assertIn(ENTRY, labels)
        await self.update(ENTRY)
        labels = [button.text for row in self.api.messages[-1].reply_markup.keyboard for button in row]
        self.assertEqual(labels, [WORD, PDF, HELP, BACK])
        await self.queue_word(self.a)
        await self.update(ALL_BUTTON)
        self.verify([f"BAYONNOMA PAGE {i}" for i in range(1, 5)])
        await self.queue_word(self.a, self.b)
        await self.update("  BARCHASINI  ")
        self.verify([f"BAYONNOMA PAGE {i}" for i in range(1, 5)], -2)
        self.verify(["HISOBOT PAGE 1", "HISOBOT PAGE 2"])
        self.assertIn("Tayyor PDFlar soni: 2", self.api.messages[-1].text)
        self.assertFalse(self.app.sessions[7].words)

    async def test_shared_selection_and_validation(self):
        await self.queue_word(self.a, self.b)
        for invalid in ("0", "7-3", "9: barchasini", "bema’ni"):
            await self.update(invalid)
            self.assertIn("Masalan", self.api.messages[-1].text)
        await self.update("2, 1 - 2, 1")
        self.verify(["BAYONNOMA PAGE 1", "BAYONNOMA PAGE 2"], -2)
        self.verify(["HISOBOT PAGE 1", "HISOBOT PAGE 2"])

    async def test_individual_selection_and_retry(self):
        await self.queue_word(self.a, self.b, self.a)
        await self.update("1: 4, 2-3\n2: barchasini")
        self.verify(["BAYONNOMA PAGE 2", "BAYONNOMA PAGE 3", "BAYONNOMA PAGE 4"], -2)
        self.verify(["HISOBOT PAGE 1", "HISOBOT PAGE 2"])
        self.assertEqual(list(self.app.sessions[7].words), [3])
        await self.update(path=self.b)
        await self.update("4")
        self.verify(["BAYONNOMA PAGE 4"])
        self.assertIn("«hisobot.doc». 4-sahifa mavjud emas. Jami 2 sahifa.", self.api.messages[-2].text)
        self.assertEqual(list(self.app.sessions[7].words), [4])
        await self.update("4: 1")
        self.verify(["HISOBOT PAGE 1"])

    async def test_append_one_then_many_and_choose_correct_result(self):
        await self.queue_word(self.a, self.b)
        await self.update("1")
        await self.update(callback=1)
        await self.update(path=self.x)
        await self.update(MERGE)
        self.verify(["BAYONNOMA PAGE 1", "ILOVA PAGE 1"])
        await self.update(callback=2)
        await self.update(path=self.y)
        await self.update(path=self.x)
        await self.update(MERGE)
        pages = self.verify(["HISOBOT PAGE 1", "IZOH PAGE 1", "IZOH PAGE 2", "ILOVA PAGE 1"])
        self.assertEqual(pages[1].rotation, 90)
        self.assertEqual(tuple(pages[1].mediabox.upper_right), (720, 905))

    async def test_standalone_invalid_file_and_isolation(self):
        await self.queue_word(self.a)
        await self.update(PDF)
        await self.update(path=self.y, filename="bir xil.pdf")
        await self.update(path=self.broken)
        self.assertIn("buzilgan.pdf", self.api.messages[-1].text)
        self.assertIn("buzilgan yoki", self.api.messages[-1].text)
        await self.update(path=self.encrypted)
        self.assertIn("parol bilan", self.api.messages[-1].text)
        await self.update(ENTRY, user=9)
        await self.update(PDF, user=9)
        await self.update(path=self.x, user=9)
        await self.update(path=self.x, filename="bir xil.pdf")
        await self.update(path=self.x)
        self.api.delay = 0.2
        first = asyncio.create_task(self.update(MERGE))
        async with asyncio.timeout(5):
            while not self.api.sent:
                await asyncio.sleep(0.01)
        await self.update(MERGE)
        await first
        self.assertEqual(len(self.api.sent), 1)
        self.verify(["IZOH PAGE 1", "IZOH PAGE 2", "ILOVA PAGE 1", "ILOVA PAGE 1"])
        self.assertEqual(len(self.app.sessions[9].pdfs), 1)
        await self.update(WORD)
        await self.update("1")
        self.verify(["BAYONNOMA PAGE 1"])

    async def test_back_preserves_protocol_draft(self):
        await self.update(protocol.NEW)
        await self.update("🇺🇿 Lotin yozuvi")
        await self.update("Anvarov Anvar Anvar o‘g‘li")
        await self.queue_word(self.a)
        await self.update(BACK)
        await self.update("Sud bosh mutaxassisi")
        self.assertEqual(protocol.sessions[7].step, 2)
        self.assertEqual(protocol.sessions[7].values["employee_role"], "Sud bosh mutaxassisi")
        self.assertEqual(len(self.app.sessions[7].words), 1)

    async def test_expire_forward_cancel_and_clear(self):
        await self.queue_word(self.a)
        await self.update("1")
        session = self.app.sessions[7]
        result = next(iter(session.results.values()))
        result.expires = monotonic() - 1
        saved = Path(self.runtime.name).parent / ("forward-" + Path(self.runtime.name).name + ".pdf")
        self.addCleanup(saved.unlink, missing_ok=True)
        saved.write_bytes(self.api.sent[0][1])
        await self.update(callback=1)
        self.assertFalse(result.path.exists())
        self.assertIn("qayta jo‘nating", self.api.messages[-1].text)
        await self.update(path=self.x)
        self.assertIsNone(session.base)
        await self.update(path=saved, identity="output1")
        await self.update(path=self.x)
        await self.update(MERGE)
        self.verify(["BAYONNOMA PAGE 1", "ILOVA PAGE 1"])
        await self.queue_word(self.a)
        await self.update(CLEAR)
        self.assertFalse(session.words)
        await self.queue_word(self.b)
        await self.update("/bekor")
        self.assertFalse(session.words)
        await self.update(PDF)
        await self.update(path=self.x)
        await self.update(CANCEL)
        self.assertFalse(session.pdfs)
        self.assertEqual(list(Path(self.runtime.name).rglob('*.pdf')), [])


if __name__ == "__main__":
    unittest.main()

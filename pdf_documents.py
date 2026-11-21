import asyncio
import os
import re
import signal
from pathlib import Path
from tempfile import TemporaryDirectory
from zipfile import BadZipFile, ZipFile

import olefile
from pypdf import PdfReader, PdfWriter


class DocumentError(ValueError):
    pass


PAGE_EXAMPLE = "Masalan: 2, 4-6, 9 yoki barchasini. Alohida tanlov: 1: 2-4 va keyingi qatorda 2: barchasini."
ALL = "barchasini"


def parse_pages(text):
    if text.strip().casefold() == ALL:
        return None
    ranges = []
    for part in text.split(","):
        match = re.fullmatch(r"\s*([0-9]{1,9})(?:\s*-\s*([0-9]{1,9}))?\s*", part)
        if not match:
            raise DocumentError(f"Sahifa tanlovi noto‘g‘ri. {PAGE_EXAMPLE}")
        first = int(match[1])
        last = int(match[2] or match[1])
        if first < 1 or last < first:
            raise DocumentError(f"Sahifalar 1 dan boshlanadi. Oraliq o‘sish tartibida yoziladi. {PAGE_EXAMPLE}")
        ranges.append((first, last))
    return ranges


def parse_selection(text, ids):
    if ":" not in text:
        pages = parse_pages(text)
        return dict.fromkeys(ids, pages)
    selection = {}
    for line in filter(str.strip, text.splitlines()):
        number, _, pages = line.partition(":")
        if not re.fullmatch(r"[0-9]{1,9}", number.strip()):
            raise DocumentError(f"Har qatorda hujjat raqami va sahifalarni yozing. {PAGE_EXAMPLE}")
        number = int(number)
        if number not in ids:
            raise DocumentError(f"Navbatda {number}-raqamli hujjat yo‘q. {PAGE_EXAMPLE}")
        if number in selection:
            raise DocumentError(f"{number}-raqamli hujjat ikki marta ko‘rsatilgan. {PAGE_EXAMPLE}")
        selection[number] = parse_pages(pages)
    return selection


def open_pdf(stream):
    try:
        reader = PdfReader(stream)
        if reader.is_encrypted:
            raise DocumentError("PDF parol bilan himoyalangan.")
        if not len(reader.pages):
            raise DocumentError("PDFda sahifa yo‘q.")
        return reader
    except DocumentError:
        raise
    except Exception:
        raise DocumentError("PDF buzilgan yoki uni o‘qib bo‘lmadi.") from None


def pdf_count(path):
    with path.open("rb") as stream:
        reader = open_pdf(stream)
        try:
            for page in reader.pages:
                contents = page.get_contents()
                if contents is not None:
                    contents.get_data()
            return len(reader.pages)
        except Exception:
            raise DocumentError("PDF buzilgan yoki uni o‘qib bo‘lmadi.") from None


def select_pdf(source, destination, ranges):
    with source.open("rb") as stream:
        reader = open_pdf(stream)
        total = len(reader.pages)
        if ranges is None:
            destination.write_bytes(source.read_bytes())
            return total
        for first, last in ranges:
            if last > total:
                invalid = max(first, total + 1)
                raise DocumentError(f"{invalid}-sahifa mavjud emas. Jami {total} sahifa. {PAGE_EXAMPLE}")
        indexes = sorted({index for first, last in ranges for index in range(first - 1, last)})
        writer = PdfWriter()
        for index in indexes:
            writer.add_page(reader.pages[index])
        writer.write(destination)
        return len(indexes)


def merge_pdfs(paths, destination):
    writer = PdfWriter()
    for path in paths:
        with path.open("rb") as stream:
            reader = open_pdf(stream)
            for page in reader.pages:
                writer.add_page(page)
    writer.write(destination)
    return len(writer.pages)


def validate_word(path):
    try:
        if olefile.isOleFile(path):
            with olefile.OleFileIO(path) as ole:
                if ole.exists("EncryptedPackage"):
                    raise DocumentError("Word hujjati parol bilan himoyalangan.")
                if path.suffix == ".doc" and ole.exists("WordDocument"):
                    with ole.openstream("WordDocument") as stream:
                        header = stream.read(12)
                    if len(header) != 12:
                        raise DocumentError("Word hujjati buzilgan.")
                    if int.from_bytes(header[10:12], "little") & 0x8100:
                        raise DocumentError("Word hujjati parol bilan himoyalangan.")
                    return
        elif path.suffix == ".docx":
            with ZipFile(path) as archive:
                entries = archive.infolist()
                if any(entry.flag_bits & 1 for entry in entries):
                    raise DocumentError("Word hujjati parol bilan himoyalangan.")
                if {"[Content_Types].xml", "word/document.xml"} <= set(archive.namelist()):
                    return
    except (OSError, BadZipFile):
        pass
    raise DocumentError("Word hujjati buzilgan yoki fayl formati kengaytmasiga mos emas.")


async def convert_word(source: Path, destination: Path, timeout: int, office: str):
    await asyncio.to_thread(validate_word, source)
    with TemporaryDirectory(dir=destination.parent) as directory:
        work = Path(directory)
        profile = work / "profile"
        config = profile / "user"
        config.mkdir(parents=True)
        (config / "registrymodifications.xcu").write_text(
            '<?xml version="1.0" encoding="UTF-8"?>'
            '<oor:items xmlns:oor="http://openoffice.org/2001/registry">'
            '<item oor:path="/org.openoffice.Office.Common/Security/Scripting">'
            '<prop oor:name="MacroSecurityLevel" oor:op="fuse"><value>3</value></prop>'
            '</item></oor:items>',
            encoding="utf-8",
        )
        process = await asyncio.create_subprocess_exec(
            office, f"-env:UserInstallation={profile.as_uri()}", "--headless",
            "--convert-to", "pdf:writer_pdf_Export", "--outdir", str(work), str(source),
            stdin=asyncio.subprocess.DEVNULL, stdout=asyncio.subprocess.DEVNULL,
            stderr=asyncio.subprocess.DEVNULL, start_new_session=True,
            env={key: value for key, value in os.environ.items() if key != "BOT_TOKEN"},
        )
        try:
            await asyncio.wait_for(process.wait(), timeout)
        except (TimeoutError, asyncio.CancelledError) as error:
            if process.returncode is None:
                try:
                    os.killpg(process.pid, signal.SIGKILL)
                except ProcessLookupError:
                    pass
            await process.wait()
            if isinstance(error, asyncio.CancelledError):
                raise
            raise DocumentError("Word hujjatini aylantirish vaqti tugadi.") from None
        output = work / f"{source.stem}.pdf"
        if process.returncode or not output.is_file():
            raise DocumentError("Word hujjatini ochib yoki PDFga aylantirib bo‘lmadi.")
        output.replace(destination)

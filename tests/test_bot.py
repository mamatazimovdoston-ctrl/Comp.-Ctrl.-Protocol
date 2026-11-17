import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock
import bot

def message(text,uid=1):
    return SimpleNamespace(text=text,from_user=SimpleNamespace(id=uid),chat=SimpleNamespace(type='private'),answer=AsyncMock(),answer_document=AsyncMock(),photo=None,document=None)

def test_full_conversation_edit_cancel():
    async def run():
        bot.sessions.clear()
        uid=1
        for text in [bot.NEW,'🇺🇿 Lotin yozuvi','Karimov Sardor Olim o‘g‘li','Sud katta konsultanti','31.02.2026']:
            await bot.handle(message(text,uid))
        assert bot.sessions[uid].step==2
        for text in ['17.11.2026','Samarqand shahri','Komplayens bosh inspektori','Rasulova Malika Olim qizi',bot.KEEP]:
            await bot.handle(message(text,uid))
        s=bot.sessions[uid];assert s.mode=='review' and s.image is None
        await bot.handle(message(bot.EDIT,uid));await bot.handle(message('Suhbat joyi',uid));await bot.handle(message('Urgut tumani',uid))
        assert s.mode=='review' and s.values['place']=='Urgut tumani'
        await bot.handle(message(bot.TEXT_OK,uid))
        assert s.mode=='confirm' and s.text_confirmed
        await bot.handle(message(bot.NEW,2))
        assert bot.sessions[2].values=={} and bot.sessions[1].values['place']=='Urgut tumani'
        await bot.handle(message(bot.CANCEL,uid));assert uid not in bot.sessions
        bot.sessions.clear()
    asyncio.run(run())

def test_private_and_allowlist():
    async def run():
        m=message(bot.NEW);m.chat.type='group'
        await bot.handle(m);assert 1 not in bot.sessions
        previous=bot.ALLOWED_USER_IDS
        try:
            bot.ALLOWED_USER_IDS={999}
            m=message(bot.NEW);await bot.handle(m)
            assert 1 not in bot.sessions
        finally:bot.ALLOWED_USER_IDS=previous
    asyncio.run(run())

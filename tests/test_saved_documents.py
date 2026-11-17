import asyncio
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock,patch
import bot
from document_generator import Record


def record(name='Karimov Sardor Olim o‘g‘li'):
    return Record(name,'Sud katta konsultanti','17.11.2026','Samarqand shahri','Komplayens bosh inspektori','Rasulova Malika Olim qizi')

def message(uid=1):
    return SimpleNamespace(from_user=SimpleNamespace(id=uid),chat=SimpleNamespace(id=uid,type='private'),answer=AsyncMock(),answer_document=AsyncMock(),edit_reply_markup=AsyncMock())

def callback(token,action='cyrillic',uid=1):
    return SimpleNamespace(data=f'doc:{token}:{action}',from_user=SimpleNamespace(id=uid),message=message(uid),answer=AsyncMock())

def reset():
    bot.saved_documents.clear();bot.sessions.clear();bot.locks.clear()

def test_completed_document_is_saved_after_delivery():
    async def run():
        reset();m=message();r=record();values={k:getattr(r,k) for k in ('employee','employee_role','date','place','officer_role','officer')}
        s=bot.Session(values=values.copy(),image=b'image',mode='confirm');bot.sessions[1]=s
        with patch('bot.send_document_pair',new=AsyncMock()) as send:
            await bot.generate_and_send(m,s)
        send.assert_awaited_once()
        assert 1 not in bot.sessions and not s.values and s.image is None
        assert len(bot.saved_documents)==1
        token,item=next(iter(bot.saved_documents.items()))
        assert item.record==r and item.image==b'image'
        keys=m.answer.call_args_list[1].kwargs['reply_markup'].inline_keyboard
        assert all(token in row[0].callback_data for row in keys)
        reset()
    asyncio.run(run())

def test_callbacks_use_exact_document_and_keep_active_draft():
    async def run():
        reset();a=bot.save_document(1,1,record(),b'photo-a')
        b=bot.save_document(1,1,record('Hasanov Anvar Olim o‘g‘li'),b'photo-b')
        draft=bot.Session(values={'employee':'New Draft'});bot.sessions[1]=draft
        for script in ('cyrillic','latin','new_latin'):
            with patch('bot.send_document_pair',new=AsyncMock()) as send:
                await bot.document_action(callback(a,script))
            args=send.call_args.args
            assert args[1].employee==record().employee and args[1].script==script
            assert args[2]==b'photo-a' and send.call_args.kwargs['with_suffix']
            assert bot.saved_documents[a].record.script=='latin'
            assert bot.saved_documents[b].image==b'photo-b'
            assert bot.sessions[1] is draft
        reset()
    asyncio.run(run())

def test_owner_expiry_delete_and_busy():
    async def run():
        reset();token=bot.save_document(1,1,record(),b'photo')
        with patch('bot.send_document_pair',new=AsyncMock()) as send:
            q=callback(token,uid=2);await bot.document_action(q)
            send.assert_not_awaited();assert token in bot.saved_documents
            bot.saved_documents[token].busy=True
            await bot.document_action(callback(token));send.assert_not_awaited()
            bot.saved_documents[token].busy=False
            q=callback(token,'delete');await bot.document_action(q)
            assert token not in bot.saved_documents
            q.message.edit_reply_markup.assert_awaited_once_with(reply_markup=None)
            await bot.document_action(callback(token));send.assert_not_awaited()
            token=bot.save_document(1,1,record(),None)
            bot.saved_documents[token].expires=0
            await bot.document_action(callback(token));send.assert_not_awaited()
            assert token not in bot.saved_documents
        reset()
    asyncio.run(run())

def test_expiry_and_cache_limit():
    reset()
    tokens=[bot.save_document(1,1,record(),b'photo') for _ in range(6)]
    assert tokens[0] not in bot.saved_documents and len(bot.saved_documents)==5
    other=bot.save_document(2,2,record(),None)
    item=bot.saved_documents[tokens[-1]];item.expires=1;item.busy=True
    bot.purge_documents(now=2);assert tokens[-1] in bot.saved_documents
    item.busy=False;bot.purge_documents(now=2)
    assert tokens[-1] not in bot.saved_documents and other in bot.saved_documents
    reset()

def test_failed_conversion_can_retry():
    async def run():
        reset();token=bot.save_document(1,1,record(),b'photo')
        with patch('bot.send_document_pair',new=AsyncMock(side_effect=RuntimeError)):
            await bot.document_action(callback(token))
        assert token in bot.saved_documents and not bot.saved_documents[token].busy
        with patch('bot.send_document_pair',new=AsyncMock()) as send:
            await bot.document_action(callback(token));send.assert_awaited_once()
        reset()
    asyncio.run(run())

def test_pair_filenames_and_temporary_cleanup():
    async def run():
        reset();m=message();r=record();r=bot.replace(r,script='new_latin');seen=[]
        def generate(r,target,image):Path(target).write_bytes(b'docx')
        def pdf(target):p=Path(target).with_suffix('.pdf');p.write_bytes(b'pdf');return p
        async def sent(file,**kwargs):
            p=Path(file.path);assert p.exists();seen.append(p)
        m.answer_document.side_effect=sent
        with patch('bot.generate_docx',side_effect=generate),patch('bot.to_pdf',side_effect=pdf):
            await bot.send_document_pair(m,r,b'photo',with_suffix=True)
        assert len(seen)==2 and seen[0].name.endswith('_Yangi_lotin.docx') and seen[1].name.endswith('_Yangi_lotin.pdf')
        assert all(not p.exists() for p in seen)
        reset()
    asyncio.run(run())

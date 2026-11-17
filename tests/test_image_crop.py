from io import BytesIO
from unittest.mock import patch, AsyncMock
import asyncio
from PIL import Image
from image_processor import prepare_options, crop_box, detect_faces
import bot
from tests.test_bot import message

def picture():
    image=Image.new('RGB',(1000,1600),'white')
    buf=BytesIO();image.save(buf,'PNG');return buf.getvalue()

def test_crop_preserves_all_detected_heads():
    faces=[(150,500,100,100),(700,490,110,110)]
    box=crop_box((1000,1600),faces)
    assert box is not None
    assert abs((box[2]-box[0])/(box[3]-box[1])-17/9)<.01
    for x,y,w,h in faces:
        assert box[0]<=x and box[1]<=y and box[2]>=x+w and box[3]>=y+h
    assert box[3]>=max(y+2.8*h for x,y,w,h in faces)

def test_no_faces_or_spread_faces_keeps_original():
    assert crop_box((1000,1600),[]) is None
    assert crop_box((1000,1600),[(20,10,100,100),(700,1200,100,100)]) is None
    with patch('image_processor.detect_faces',return_value=[]):
        options=prepare_options(picture())
    assert not options.cropped and options.original==options.suggested

def test_suggested_and_original_options():
    with patch('image_processor.detect_faces',return_value=[(180,500,100,100),(700,510,100,100)]):
        options=prepare_options(picture())
    assert options.cropped and options.face_count==2
    assert options.original!=options.suggested
    assert Image.open(BytesIO(options.suggested)).size==(2040,1080)

def test_detector_loads_and_blank_image_is_not_a_face():
    assert detect_faces(Image.new('RGB',(400,600),'white'))==[]

def test_detector_failure_falls_back():
    with patch('image_processor.detect_faces',side_effect=RuntimeError):
        options=prepare_options(picture())
    assert not options.cropped and options.original==options.suggested

def test_preview_choices_and_replacement():
    async def run():
        values=dict(employee='Karimov Sardor Olim o‘g‘li',employee_role='Sud katta konsultanti',date='17.11.2026',place='Toshkent shahri',officer_role='Komplayens bosh inspektori',officer='Rasulova Malika Olim qizi')
        for choice,expected in [(bot.ACCEPT_IMAGE,b'crop'),(bot.ORIGINAL_IMAGE,b'original')]:
            s=bot.Session(values=values.copy(),step=6,mode='image_preview',pending_original=b'original',pending_crop=b'crop')
            bot.sessions[1]=s
            await bot.handle(message(choice))
            assert s.image==expected and s.mode=='review'
            assert s.pending_original is None and s.pending_crop is None
        s=bot.Session(step=6,mode='image_preview',pending_original=b'original',pending_crop=b'crop')
        bot.sessions[1]=s
        await bot.handle(message(bot.REPLACE_IMAGE))
        assert s.mode=='input' and s.step==6 and s.pending_original is None
        bot.sessions.clear()
    asyncio.run(run())

def test_upload_requires_preview_confirmation():
    from types import SimpleNamespace
    async def run():
        s=bot.Session(step=6);bot.sessions[1]=s
        m=message('');m.photo=[SimpleNamespace(file_size=len(picture()))]
        async def download(attachment,destination):destination.write(picture())
        m.bot=SimpleNamespace(download=download);m.answer_photo=AsyncMock()
        with patch('image_processor.detect_faces',return_value=[(180,500,100,100)]):
            await bot.handle(m)
        assert s.mode=='image_preview' and s.image is None
        assert s.pending_original and s.pending_crop
        m.answer_photo.assert_awaited_once()
        await bot.handle(message(bot.CANCEL))
        assert 1 not in bot.sessions
    asyncio.run(run())

from io import BytesIO
import warnings
from PIL import Image, ImageOps, UnidentifiedImageError
from config import MAX_IMAGE_BYTES
Image.MAX_IMAGE_PIXELS = 25_000_000

def prepare_image(raw: bytes) -> bytes:
    if not raw or len(raw) > MAX_IMAGE_BYTES:
        raise ValueError('Rasm hajmi 10 MB dan oshmasin.')
    try:
        with warnings.catch_warnings():
            warnings.simplefilter('error', Image.DecompressionBombWarning)
            with Image.open(BytesIO(raw)) as source:
                if source.format not in {'JPEG', 'PNG'}:
                    raise ValueError('Faqat JPG, JPEG yoki PNG rasm yuboring.')
                source.load()
                image = ImageOps.exif_transpose(source).convert('RGBA')
                if min(image.size) < 100:
                    raise ValueError('Rasmning har bir tomoni kamida 100 piksel bo‘lsin.')
                image.thumbnail((2040, 1080), Image.Resampling.LANCZOS)
                canvas = Image.new('RGB', (2040, 1080), '#f3f3f3')
                canvas.paste(image, ((2040-image.width)//2, (1080-image.height)//2), image)
                out = BytesIO()
                canvas.save(out, 'PNG', optimize=True)
                return out.getvalue()
    except (UnidentifiedImageError, OSError, Image.DecompressionBombError, Image.DecompressionBombWarning) as exc:
        raise ValueError('Rasm ochilmadi yoki o‘lchami juda katta. Boshqa JPG/PNG yuboring.') from exc

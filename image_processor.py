"""Local trained face detectors suggest a crop; users always approve the preview."""
from dataclasses import dataclass
from functools import lru_cache
from io import BytesIO
import warnings
from PIL import Image, ImageOps, UnidentifiedImageError
from config import MAX_IMAGE_BYTES
Image.MAX_IMAGE_PIXELS = 25_000_000
SIZE = (2040, 1080)
RATIO = 17 / 9

@dataclass(frozen=True)
class ImageOptions:
    original: bytes
    suggested: bytes
    cropped: bool
    face_count: int

def read_image(raw):
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
                return image
    except (UnidentifiedImageError, OSError, Image.DecompressionBombError, Image.DecompressionBombWarning) as exc:
        raise ValueError('Rasm ochilmadi yoki o‘lchami juda katta. Boshqa JPG/PNG yuboring.') from exc

def encode(image):
    image=image.copy()
    image.thumbnail(SIZE, Image.Resampling.LANCZOS)
    canvas=Image.new('RGB', SIZE, '#f3f3f3')
    canvas.paste(image, ((SIZE[0]-image.width)//2, (SIZE[1]-image.height)//2), image if image.mode=='RGBA' else None)
    out=BytesIO();canvas.save(out,'PNG',optimize=True)
    return out.getvalue()

def prepare_image(raw: bytes) -> bytes:
    """Original photo fitted without cropping or distortion."""
    return encode(read_image(raw))

@lru_cache(maxsize=1)
def detector_paths():
    import cv2
    from pathlib import Path
    paths=[str(Path(__file__).resolve().parent/'models'/name) for name in
           ('haarcascade_frontalface_default.xml','haarcascade_profileface.xml')]
    if not all(Path(p).is_file() for p in paths):
        raise RuntimeError('Face detector model files missing')
    return paths

def detect_faces(image):
    """OpenCV trained Haar models, frontal and both profile directions; no network."""
    import cv2
    import numpy as np
    sample=image.convert('RGB');sample.thumbnail((1024,1024),Image.Resampling.LANCZOS)
    gray=cv2.cvtColor(np.array(sample),cv2.COLOR_RGB2GRAY)
    gray=cv2.equalizeHist(gray)
    scale_x=image.width/sample.width;scale_y=image.height/sample.height
    boxes=[]
    for path in detector_paths():
        # Classifiers are per-call: simultaneous users never share mutable detector state.
        model=cv2.CascadeClassifier(path)
        if model.empty():raise RuntimeError('Face detector could not load')
        for flipped in (False,True):
            view=cv2.flip(gray,1) if flipped else gray
            found=model.detectMultiScale(view,scaleFactor=1.1,minNeighbors=6,minSize=(32,32))
            for x,y,w,h in found:
                if flipped:x=sample.width-x-w
                box=(int(x*scale_x),int(y*scale_y),int(w*scale_x),int(h*scale_y))
                # Merge repeated detections of the same face conservatively.
                if any(abs(box[0]+box[2]/2-a-c/2)<min(box[2],c)*.45 and
                       abs(box[1]+box[3]/2-b-d/2)<min(box[3],d)*.45 for a,b,c,d in boxes):continue
                boxes.append(box)
    return boxes

def crop_box(size, faces):
    """Largest 17:9 crop that keeps all detected heads and room below for the desk.

    This is a face-aware suggestion, not a guarantee that every hand/object is detected.
    If the safety region cannot fit, preserve the whole photograph with padding.
    """
    width,height=size
    if not faces:return None
    crop_w=min(float(width),height*RATIO);crop_h=crop_w/RATIO
    left=min(max(0,x-.4*w) for x,y,w,h in faces)
    right=max(min(width,x+1.4*w) for x,y,w,h in faces)
    top=min(max(0,y-.4*h) for x,y,w,h in faces)
    bottom=max(min(height,y+2.8*h) for x,y,w,h in faces)
    if right-left>crop_w or bottom-top>crop_h:return None
    # Aim below face centers to retain shoulders, hands and interview documents.
    target_x=(left+right)/2-crop_w/2
    target_y=(top+bottom)/2-crop_h/2
    x0=max(0,right-crop_w,min(left,width-crop_w,target_x))
    y0=max(0,bottom-crop_h,min(top,height-crop_h,target_y))
    return (round(x0),round(y0),round(x0+crop_w),round(y0+crop_h))

def prepare_options(raw: bytes) -> ImageOptions:
    image=read_image(raw)
    original=encode(image)
    try:
        faces=detect_faces(image)
    except Exception:
        # Detection failure must never destroy a user's image or block their workflow.
        faces=[]
    box=crop_box(image.size,faces)
    cropped=box is not None and (box[0]>0 or box[1]>0 or box[2]<image.width or box[3]<image.height)
    return ImageOptions(original,encode(image.crop(box)) if cropped else original,cropped,len(faces))

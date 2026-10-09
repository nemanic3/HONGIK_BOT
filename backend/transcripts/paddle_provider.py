"""CPU-only local OCR with bounded tiles; no transcript text is logged."""
from io import BytesIO
import os
import threading
from PIL import Image

_model = None
_lock = threading.Lock()


def model():
    global _model
    if _model is None:
        from paddleocr import PaddleOCR
        _model = PaddleOCR(text_detection_model_name='PP-OCRv5_mobile_det',
            text_recognition_model_name='korean_PP-OCRv5_mobile_rec',
            use_doc_orientation_classify=False, use_doc_unwarping=False,
            use_textline_orientation=False, enable_mkldnn=False,
            cpu_threads=int(os.environ.get('OCR_CPU_THREADS', '4')))
    return _model


def observation_boxes(result, width, height, offset=0):
    if isinstance(result, str):
        import json
        result=json.loads(result)
    result=result.get('res',result)
    boxes=[]
    for text,score,poly in zip(result['rec_texts'],result['rec_scores'],result['rec_polys']):
        xs=[float(p[0]) for p in poly];ys=[float(p[1]) for p in poly]
        boxes.append({'text':text,'confidence':float(score),'x':min(xs)/width,'y':(min(ys)+offset)/height,
                      'width':(max(xs)-min(xs))/width,'height':(max(ys)-min(ys))/height})
    return boxes


def recognize_png(data):
    import numpy as np
    with Image.open(BytesIO(data)) as source:
        im=source.convert('RGB')
        if im.width*im.height > 20_000_000:
            raise ValueError('Image dimensions exceed OCR limit')
        # Preserve readable character size on long scrolling captures.
        if im.width>2400:
            im=im.resize((2400,round(im.height*2400/im.width)),Image.Resampling.LANCZOS)
        width,height=im.size
        starts=list(range(0,max(1,height-160),1840))
        boxes=[]
        with _lock:
            engine=model()
            for top in starts:
                tile=im.crop((0,top,width,min(height,top+2000)))
                pixels=np.asarray(tile)[:,:,::-1].copy()
                found=observation_boxes(list(engine.predict(pixels))[0].json,width,height,top)
                for b in found:
                    same=next((old for old in boxes if old['text']==b['text'] and abs(old['x']-b['x'])*width<12 and abs(old['y']-b['y'])*height<12),None)
                    if same is None:boxes.append(b)
                    elif b['confidence']>same['confidence']:same.update(b)
    return {'provider':'paddleocr-korean-mobile','text':'\n'.join(b['text'] for b in boxes),
            'observations':boxes,'width':width,'height':height,'tile_count':len(starts),
            'orientation':'exif-normalized','warnings':[]}

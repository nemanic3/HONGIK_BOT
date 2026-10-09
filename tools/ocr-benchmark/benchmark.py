import json,time,resource,os
from pathlib import Path
from paddleocr import PaddleOCR
started=time.perf_counter()
ocr=PaddleOCR(text_detection_model_name='PP-OCRv5_mobile_det',text_recognition_model_name='korean_PP-OCRv5_mobile_rec',use_doc_orientation_classify=False,use_doc_unwarping=False,use_textline_orientation=False,enable_mkldnn=False,cpu_threads=4)
print(json.dumps({'model_load_seconds':round(time.perf_counter()-started,3)}),flush=True)
if os.environ.get('DOWNLOAD_ONLY')=='1':
    raise SystemExit(0)
for file in sorted(Path('/inputs').glob('*.png')):
    for iteration in range(2):
        started=time.perf_counter()
        result=list(ocr.predict(str(file)))[0].json
        if isinstance(result,str): result=json.loads(result)
        result=result.get('res',result)
        elapsed=time.perf_counter()-started
        out=Path('/output')/(file.stem+f'-{iteration}.json')
        out.write_text(json.dumps(result,ensure_ascii=False,default=lambda x:x.tolist()))
        out.chmod(0o600)
        print(json.dumps({'file':file.name,'run':iteration,'seconds':round(elapsed,3),'lines':len(result.get('rec_texts',[])),'peak_rss_kib':resource.getrusage(resource.RUSAGE_SELF).ru_maxrss}),flush=True)

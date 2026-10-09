"""Position-based Hongik table extraction. Never repair uncertain OCR characters."""
import re
from copy import deepcopy
from .parser import LABELS

TERM = re.compile(r'(\d{4})\s*학년도\s*\d\s*학년\s*([12]학기|동계계절학기|하계계절학기)')
GRADE = re.compile(r'(?:[ABCD][+0]?|F|P|NP|PASS)\Z')


def label(text):
    return LABELS.get(re.sub(r'\s+', '', text).lower())


def grouped(boxes):
    rows = []
    for b in sorted(boxes, key=lambda b: b['y'] + b['height']/2):
        cy = b['y'] + b['height']/2
        if rows and abs(cy-rows[-1][0]) < max(b['height'], rows[-1][1])*.55:
            rows[-1][2].append(b)
        else:
            rows.append([cy,b['height'],[b]])
    return [sorted(r[2],key=lambda b:b['x']) for r in rows]


def restore_headers(page, previous):
    """Reuse column positions only; never infer a missing semester across captures."""
    if not previous or not page.get('observations'):
        return page
    # Different resolutions/layouts cannot safely share absolute column positions.
    if page.get('width') and previous.get('width') and abs(page['width']/previous['width']-1) > .03:
        return page
    result=deepcopy(page)
    current=result['observations'];added=[]
    for row in grouped(previous.get('observations', [])):
        fields=[label(b['text']) for b in row]
        if not {'code','name','credit','grade'}.issubset(fields) or not all(fields) or len(set(fields))!=len(fields):
            continue
        x=row[fields.index('code')]['x']
        if any(abs(x-old)<.04 for old in added):continue
        starts=[b['y'] for b in current if label(b['text'])=='code' and abs(b['x']-x)<.04]
        early=[b for b in current if re.fullmatch(r'\d{6}',b['text'].strip()) and abs(b['x']-x)<.04 and b['y']<min(starts or [1])]
        if not early:continue
        first=min(b['y'] for b in early)
        for b in row:
            current.append({**b,'y':first-.024,'height':.008,'inherited_header':True})
        added.append(x)
    return result


def extract(page):
    boxes = deepcopy(page.get('observations', []))
    if not boxes:
        return None
    # Some engines combine adjacent short headers. Split only exact known labels.
    expanded=[]
    for b in boxes:
        if re.sub(r'\s+', '', b['text']) == '학점성적':
            for i,t in enumerate(['학점','성적']):
                expanded.append({**b,'text':t,'x':b['x']+i*b['width']/2,'width':b['width']/2})
        else:
            expanded.append(b)
    boxes=expanded
    starts=sorted(b['x'] for b in boxes if label(b['text'])=='code')
    lanes=[]
    for x in starts:
        if not lanes or x-lanes[-1]>.2:
            lanes.append(x)
    if not lanes:
        return None
    bounds=[0]+[x-.012 for x in lanes[1:]]+[1.01]
    courses,issues=[],[]
    for lane,(left,right) in enumerate(zip(bounds,bounds[1:]),1):
        local=[b for b in boxes if left <= b['x'] < right]
        rows=grouped(local)
        headers=[]
        for row in rows:
            fields=[label(b['text']) for b in row]
            if {'code','name','credit','grade'}.issubset(fields) and all(fields) and len(fields)==len(set(fields)):
                headers.append(row)
        for hi,header in enumerate(headers):
            y=max(b['y']+b['height'] for b in header)
            next_y=min(b['y'] for b in headers[hi+1]) if hi+1<len(headers) else 1.01
            titles=[(b,TERM.search(b['text'])) for b in local if b['y']<y and TERM.search(b['text'])]
            title,match=max(titles,key=lambda pair:pair[0]['y']) if titles else (None,None)
            semester=f"{match[1]}-{ {'1학기':'1','2학기':'2','동계계절학기':'winter','하계계절학기':'summer'}[match[2]]}" if match else None
            # End at next semester title or summary block, not merely the next header.
            endings=[b['y'] for b in local if b['y']>y and (TERM.search(b['text']) or re.search('이수구분별|필수 교과목',b['text']))]
            end=min([next_y]+endings)
            region=[b for b in local if y<b['y']<end]
            codes=sorted([b for b in region if re.fullmatch(r'\d{6}',b['text'].strip()) and abs(b['x']-header[0]['x'])<.045],key=lambda b:b['y'])
            fields=[label(b['text']) for b in header]
            centers=[b['x']+b['width']/2 for b in header]
            boundaries=[(a+b)/2 for a,b in zip(centers,centers[1:])]
            semester_retake=any('학기재수강' in b['text'].replace(' ','') for b in region)
            for line in grouped(region):
                # A row with numeric credit and a grade but unreadable/missing code
                # must remain a visible review issue, not disappear silently.
                texts=[b['text'].strip() for b in line]
                if any(GRADE.fullmatch(t) for t in texts) and any(re.fullmatch(r'\d+(?:\.\d+)?',t) for t in texts) and not any(re.fullmatch(r'\d{6}',t) for t in texts):
                    issues.append({'code':'unassigned_row','file_number':page.get('file_number',1),'column':lane,'message':'학수번호를 읽지 못한 행이 있습니다. 원본에서 추가해주세요.'})
            for ri,code in enumerate(codes):
                cy=code['y']+code['height']/2
                previous=codes[ri-1] if ri else None
                following=codes[ri+1] if ri+1<len(codes) else None
                low=(previous['y']+previous['height']/2+cy)/2 if previous else y
                high=(following['y']+following['height']/2+cy)/2 if following else min(end,cy+code['height']*1.8)
                cells={f:[] for f in fields}
                used=[]
                for b in region:
                    if not low<=b['y']+b['height']/2<high or re.search('취득학점|평점|학기재수강',b['text']):
                        continue
                    center=b['x']+b['width']/2
                    index=sum(center>v for v in boundaries)
                    if b is code:
                        index=fields.index('code')
                    elif index==0:
                        index=fields.index('name')
                    cells[fields[index]].append(b);used.append(b)
                values={f:' '.join(b['text'].strip() for b in sorted(bs,key=lambda b:(b['y'],b['x']))) for f,bs in cells.items()}
                values['code']=code['text'].strip()
                raw_credit=values.get('credit','')
                values['credit']=float(raw_credit) if re.fullmatch(r'\d+(?:\.\d+)?',raw_credit) else None
                raw_retake=values.get('retake','')
                values['retake']='재수강' in raw_retake
                values['semester_retake']=semester_retake
                values['semester']=semester
                values.setdefault('type','')
                values.setdefault('grade','')
                confidence=min([float(b.get('confidence',1)) for b in used] or [0])
                flags=[]
                if any(b.get('inherited_header') for b in header): flags.append('이전 캡처의 열 위치 사용: 학기와 행 확인 필요')
                for f in ['name','credit','grade','type','semester']:
                    if values.get(f) in ('',None): flags.append(f+' 누락')
                if values['grade'] and not GRADE.fullmatch(values['grade']): flags.append('성적 확인')
                if confidence<.9: flags.append('낮은 OCR 신뢰도')
                if code['y']+code['height']>.975: flags.append('하단 잘림 가능')
                source={'file_number':page.get('file_number',1),'page_number':page.get('page_number',1),'column':lane,
                        'bbox':[left,max(0,low),right-left,min(1,high)-max(0,low)]}
                values.update(sources=[source],ocr_confidence=confidence,review_reasons=flags,
                              raw_fields={'credit':raw_credit,'retake':raw_retake},source_page=source['page_number'])
                if values['retake'] or semester_retake: values['review_reasons'].append('재수강 인정 기록 선택 필요')
                courses.append(values)
            # Non-course text at cropped boundaries is not silently discarded.
            if not codes: issues.append({'code':'empty_table','file_number':page.get('file_number',1),'column':lane,'message':'표의 과목 행을 복원하지 못했습니다.'})
        if not headers and local:
            issues.append({'code':'missing_header','file_number':page.get('file_number',1),'column':lane,'message':'잘린 표의 머리글/학기를 확인해주세요.'})
        if local and any(b['y']+b['height']>.98 for b in local):
            issues.append({'code':'cropped_edge','file_number':page.get('file_number',1),'column':lane,'message':'이미지 하단의 잘린 표를 다음 캡처와 대조해주세요.'})
    return courses,issues


def merge_captures(courses):
    """Only identical code+semester+values across different captures are merged."""
    result=[];seen={}
    for course in courses:
        key=tuple(course.get(k) for k in ('code','semester','name','credit','type','grade','retake','semester_retake'))
        source=course.get('sources',[])
        existing=seen.get(key)
        if key[0] and key[1] and existing is not None and source and existing.get('sources') and all((s['file_number'],s['page_number'])!=(source[0]['file_number'],source[0]['page_number']) for s in existing['sources']):
            existing['sources'].extend(source)
            existing['capture_overlap']=True
            existing['review_reasons']=list(dict.fromkeys(existing.get('review_reasons',[])+course.get('review_reasons',[])))
        else:
            result.append(course);seen[key]=course
    groups={}
    for i,c in enumerate(result): groups.setdefault(c.get('code') or c.get('name'),[]).append(i)
    for indexes in groups.values():
        if len(indexes)>1:
            semesters={result[i].get('semester') for i in indexes}
            kind='retake_candidate' if len(semesters)>1 else 'capture_conflict'
            for i in indexes:
                result[i][kind]=True
                result[i].setdefault('review_reasons',[]).append('다른 학기 동일 과목: 인정 기록 선택 필요' if kind=='retake_candidate' else '같은 학기 중복/충돌: 원본 비교 필요')
    names={}
    for c in result:
        names.setdefault(re.sub(r'\s+', '', c.get('name','')).casefold(),[]).append(c)
    for rows in names.values():
        if len({c.get('code') for c in rows})>1:
            for c in rows:
                c['identity_candidate']=True
                c.setdefault('review_reasons',[]).append('다른 코드·같은 이름: 동일/대체과목 확인 필요')
    return result

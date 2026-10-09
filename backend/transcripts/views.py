# transcripts/views.py
from rest_framework.views import APIView
from rest_framework.parsers import MultiPartParser, FormParser
from rest_framework.response import Response
from rest_framework import status, permissions
from django.shortcuts import get_object_or_404

from .models import Transcript
from .serializers import (
    TranscriptUploadSerializer,
    TranscriptStatusSerializer,
    TranscriptParsedSerializer
)



def _source(transcript):
    if transcript.confirmed_data is not None:
        return 'confirmed'
    if transcript.ocr_data is not None:
        return 'ocr'
    if transcript.ocr_raw_data is not None:
        return 'raw'
    if transcript.parsed_data is not None:
        return 'legacy'
    return 'none'


def _resource(transcript, *, detail=False):
    data = {'id': transcript.id, 'transcript_id': transcript.id, 'status': transcript.status,
            'error_message': transcript.error_message, 'source': _source(transcript),
            'needs_review': transcript.confirmed_data is None}
    if detail:
        raw = transcript.ocr_raw_data if isinstance(transcript.ocr_raw_data, dict) else {}
        raw_pages = raw.get('pages', []) if isinstance(raw.get('pages', []), list) else []
        from analysis.course_identity import identify_for_user
        data.update(ocr_raw_data=transcript.ocr_raw_data, document=identify_for_user(transcript.get_course_document(), transcript.user),
                    confirmed_at=transcript.confirmed_at,
                    sources=[{'file_number': p.page_number, 'page_number': n}
                             for p in transcript.pages.order_by('page_number')
                             for n in (sorted({r.get('page_number',1) for r in raw_pages if isinstance(r,dict) and r.get('file_number')==p.page_number}) or [1])])
    return data


class TranscriptDetailView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request, transcript_id):
        transcript = get_object_or_404(Transcript, pk=transcript_id, user=request.user)
        return Response(_resource(transcript, detail=True))


class TranscriptConfirmView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, transcript_id):
        from django.core.exceptions import ValidationError
        transcript = get_object_or_404(Transcript, pk=transcript_id, user=request.user)
        if (not isinstance(request.data, dict) or type(request.data.get('schema_version')) is not int
                or request.data.get('schema_version') != 1 or 'courses' not in request.data):
            return Response({'error': 'A schema_version: 1 document with courses is required.'}, status=400)
        try:
            transcript.confirm_courses(request.data, confirmed_by=request.user)
        except ValidationError as exc:
            return Response({'error': exc.messages}, status=400)
        return Response(_resource(transcript, detail=True))


def _rows_to_tsv(rows: list[list[str]]) -> str:
    return "\n".join("\t".join(map(str, r)) for r in rows)


class TranscriptUploadView(APIView):
    permission_classes = [permissions.IsAuthenticated]
    parser_classes = [MultiPartParser, FormParser]

    def post(self, request, user_id):
        if request.user.id != user_id:
            return Response(status=status.HTTP_403_FORBIDDEN)

        # ✅ 여기서만 import (지연 임포트)
        try:
            from .tasks import process_transcript
        except Exception:
            return Response({"error": "OCR 모듈을 불러오지 못했습니다."}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

        if 'files' not in request.data:
            return Response({"error": "파일이 전송되지 않았습니다."}, status=status.HTTP_400_BAD_REQUEST)

        serializer = TranscriptUploadSerializer(
            data={"files": request.data.getlist('files')},
            context={'request': request}
        )
        if serializer.is_valid():
            transcript = serializer.save()
            from django.conf import settings
            if getattr(settings, 'TRANSCRIPT_PROCESSING', 'celery') == 'inline':
                process_transcript.run(transcript.id)
            else:
                try:
                    process_transcript.delay(transcript.id)
                except Exception:
                    Transcript.objects.filter(pk=transcript.id, confirmed_data__isnull=True,
                                              status='pending').update(
                        status=Transcript.STATUS.error,
                        error_message='Processing queue unavailable. Start the queue/worker or set TRANSCRIPT_PROCESSING=inline locally; original files preserved and manual confirmation is available.')
                    transcript.refresh_from_db()
                    return Response(_resource(transcript), status=status.HTTP_503_SERVICE_UNAVAILABLE)
            transcript.refresh_from_db()
            return Response(_resource(transcript), status=status.HTTP_201_CREATED)

        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

class TranscriptStatusView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request, user_id):
        # 1) 인증 체크
        if request.user.id != user_id:
            return Response(
                {"error": "인증이 필요합니다."},
                status=status.HTTP_403_FORBIDDEN
            )

        # 2) 최신 업로드 한 건만 조회
        transcript = (
            Transcript.objects
            .filter(user_id=user_id)
            .order_by('-created_at')
            .first()
        )
        if not transcript:
            return Response(
                {"error": "해당 성적표가 존재하지 않습니다."},
                status=status.HTTP_404_NOT_FOUND
            )

        # 3) 상태 반환 (소문자)
        return Response(
            _resource(transcript),
            status=status.HTTP_200_OK
        )


class TranscriptParsedView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request, user_id):
        if request.user.id != user_id:
            return Response(
                {"error": "인증이 필요합니다."},
                status=status.HTTP_403_FORBIDDEN
            )

        transcript = Transcript.objects.filter(user_id=user_id).order_by('-created_at').first()

        if not transcript:
            return Response(
                {"error": "해당 성적표가 존재하지 않습니다."},
                status=status.HTTP_404_NOT_FOUND
            )

        # 상태가 'done'이 아니거나, 'done'인데 데이터가 없는 경우
        if transcript.confirmed_data is None and (transcript.status.lower() != 'done' or (
            transcript.get_course_document() is None
            and transcript.ocr_raw_data is None and transcript.parsed_data is None
        )):
            return Response(
                {"error": "아직 파싱이 완료되지 않았거나 결과가 없습니다."},
                status=status.HTTP_404_NOT_FOUND  # 명세에 따라 404 유지
            )

        # Preserve legacy JSON keys while preferring the user's confirmed document.
        data = transcript.get_course_document()
        if data is None:
            # Raw text/table cells remain JSON values; they are never analysis inputs.
            data = transcript.ocr_raw_data if transcript.ocr_raw_data is not None else transcript.parsed_data
        return Response(data, status=status.HTTP_200_OK)


class TranscriptSourceView(APIView):
    """Owner-only, bounded preview. Never expose storage URLs or file names."""
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request, transcript_id, file_number):
        from io import BytesIO
        import base64
        import pymupdf
        from PIL import Image, ImageOps
        transcript = get_object_or_404(Transcript, pk=transcript_id, user=request.user)
        source = get_object_or_404(transcript.pages, page_number=file_number)
        try:
            page_number=int(request.query_params.get('page','1'))
            with source.file.open('rb') as f:
                data=f.read()
            if data.startswith(b'%PDF-'):
                with pymupdf.open(stream=data,filetype='pdf') as pdf:
                    if not 1 <= page_number <= len(pdf):
                        return Response({'error':'Invalid page'},status=400)
                    image=Image.open(BytesIO(pdf[page_number-1].get_pixmap(dpi=100).tobytes('png')))
            else:
                if page_number != 1: return Response({'error':'Invalid page'},status=400)
                image=ImageOps.exif_transpose(Image.open(BytesIO(data)))
            image.thumbnail((1600,1600))
            output=BytesIO();image.convert('RGB').save(output,format='JPEG',quality=85)
            response=Response({'image':'data:image/jpeg;base64,'+base64.b64encode(output.getvalue()).decode(),
                               'file_number':file_number,'page_number':page_number})
            response['Cache-Control']='private, no-store'
            return response
        except (ValueError,OSError,RuntimeError):
            return Response({'error':'원본 미리보기를 생성하지 못했습니다.'},status=400)


class TranscriptRetryView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, transcript_id):
        from datetime import timedelta
        from django.utils import timezone
        from django.db import transaction
        from django.conf import settings
        from .models import TranscriptPage
        from .tasks import process_transcript
        with transaction.atomic():
            old=get_object_or_404(Transcript.objects.select_for_update(),pk=transcript_id,user=request.user)
            stale=old.status in ('pending','processing') and old.updated_at < timezone.now()-timedelta(minutes=15)
            if old.confirmed_data is not None or (old.status!='error' and not stale):
                return Response({'error':'실패했거나 15분 이상 멈춘 작업만 재시도할 수 있습니다.'},status=409)
            sources=list(old.pages.order_by('page_number'))
            if not sources: return Response({'error':'원본 파일이 없습니다.'},status=409)
            related=Transcript.objects.filter(user=request.user,pages__file=sources[0].file.name,created_at__gte=timezone.now()-timedelta(hours=1)).distinct()
            if related.count()>=3:
                return Response({'error':'같은 파일은 한 시간에 최대 3회 처리할 수 있습니다.'},status=429)
            active=related.filter(status__in=['pending','processing']).exclude(pk=old.pk).first()
            if active: return Response(_resource(active),status=200)
            new=Transcript.objects.create(user=request.user)
            for s in sources:
                TranscriptPage.objects.create(transcript=new,page_number=s.page_number,file=s.file.name)
        # Preserve the failed resource and its raw extraction for comparison.
        try:
            if settings.TRANSCRIPT_PROCESSING=='inline': process_transcript.run(new.pk)
            else: process_transcript.delay(new.pk)
        except Exception:
            Transcript.objects.filter(pk=new.pk,status='pending').update(status='error',error_message='작업 대기열에 연결하지 못했습니다.')
        new.refresh_from_db()
        return Response(_resource(new),status=201)

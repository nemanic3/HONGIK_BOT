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
        data.update(ocr_raw_data=transcript.ocr_raw_data, document=transcript.get_course_document(),
                    confirmed_at=transcript.confirmed_at)
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
        except Exception as e:
            return Response({"error": f"OCR 모듈 로드 실패: {e}"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

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

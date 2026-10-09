"""Unified report for the authenticated student's explicitly selected transcript."""
from django.shortcuts import get_object_or_404
from django.core.exceptions import ValidationError
from rest_framework import permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView
from common.course_schema import CourseSchemaError
from transcripts.models import Transcript
from .engine import evaluate_rules
from .policy import policy_for_user, SUPPORTED_TRACKS


class GraduationReportView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        base={'criteria':[], 'courses':[], 'by_semester':{}, 'warnings':[]}
        user=request.user
        if not user.admission_year or user.accreditation_track not in SUPPORTED_TRACKS or not user.major:
            return Response({**base,'status':'profile_required','warnings':['학과·입학연도·인증과정을 직접 확인해 입력하세요.']})
        raw_id=request.query_params.get('transcript_id')
        if raw_id is not None:
            if not raw_id.isdecimal() or len(raw_id)>18:
                return Response({'error':'유효한 transcript_id가 필요합니다.'},status=status.HTTP_400_BAD_REQUEST)
            transcript=get_object_or_404(Transcript,pk=int(raw_id),user=user)
        else:
            transcript=Transcript.objects.filter(user=user).order_by('-created_at','-pk').first()
            if not transcript:
                return Response({'error':'성적표가 없습니다.'},status=status.HTTP_404_NOT_FOUND)
        base['transcript_id']=transcript.pk
        if transcript.confirmed_data is None:
            return Response({**base,'status':'needs_confirmation','warnings':['OCR 결과를 확인·수정한 뒤 확정하세요.']})
        policy=policy_for_user(user)
        if policy is None:
            return Response({**base,'status':'policy_unavailable','warnings':['이 학과·입학연도·인증과정의 기준이 없거나 중복 버전이 있습니다. 검증 필요.']})
        try:
            result=evaluate_rules(policy,transcript.confirmed_data)
        except ValidationError:
            return Response({**base,'status':'policy_unavailable','warnings':['졸업 기준 문서 검증에 실패했습니다. 새 버전의 기준을 확인하세요.']})
        except CourseSchemaError:
            return Response({**base,'status':'needs_confirmation','warnings':['확정 문서 형식 검증에 실패했습니다. 다시 확인하세요.']})
        meta={key:value for key,value in policy.items() if key!='data'}
        meta['admission_year']=user.admission_year
        result.update(policy=meta,transcript_id=transcript.pk,confirmed_at=transcript.confirmed_at,source='confirmed')
        return Response(result)

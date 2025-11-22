from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
import logging

from .models import CommunicationLog
from .apps import CommunicationConfig


# 로거 설정
logger = logging.getLogger(__name__)


class ClassifyAPI(APIView):
    """
    피싱 탐지 API 엔드포인트
    POST /api/classify/
    Body: {"text": "사용자가 입력한 문자 원문"}
    """
    
    def post(self, request):
        # 1. 입력 데이터 검증
        input_text = request.data.get('text', None)
        
        if not input_text:
            logger.warning(f"[CLASSIFY] 빈 텍스트 요청")
            return Response(
                {"error": "텍스트가 필요합니다."}, 
                status=status.HTTP_400_BAD_REQUEST
            )
        
        
        # 텍스트 길이 제한
        if len(input_text) > 1000:
            logger.warning(f"[CLASSIFY] 너무 긴 텍스트 ({len(input_text)}자)")
            return Response(
                {"error": "텍스트는 1000자 이하로 입력해주세요."}, 
                status=status.HTTP_400_BAD_REQUEST
            )


        # 2. 모델 로드 여부 확인
        if not CommunicationConfig.model_loaded:
            logger.error("[CLASSIFY] 모델이 로드되지 않음")
            return Response(
                {"error": "모델이 아직 준비되지 않았습니다. 잠시 후 다시 시도해주세요."}, 
                status=status.HTTP_503_SERVICE_UNAVAILABLE
            )
        
        # 3. 피싱 탐지 수행
        try:
            from .ml_loader import analyze_intent
            
            # 핵심 분석 함수 호출
            result = analyze_intent(input_text)

            # 응답 데이터 구성
            response_data = {
                "level": result["type"],
                "percent": round(result["probability"] * 100, 2),
                "message": result["message"],
                "is_dangerous": result["label"] == 1,
            }
            
            # 4. DB 로그 저장
            try:
                CommunicationLog.objects.create(
                    input_text=input_text,
                    result_label=result["type"],  # "피싱 위험", "정상" 등
                    result_percent=round(result["probability"] * 100, 2)
                )
            except Exception as db_error:
                logger.error(f"[CLASSIFY] DB 저장 실패: {db_error}")

            # 로깅
            logger.info(
                f"[CLASSIFY] 성공 - Label: {result['type']}, "
                f"Prob: {response_data['percent']}%, "
            )
        
            
            # 5. 프론트엔드에 응답 전송
            return Response(response_data, status=status.HTTP_200_OK)
        
        except Exception as e:
            # 에러 로깅 (실제 운영에서는 로그 파일에 기록)
            logger.error(f"[CLASSIFY] 모델 추론 오류: {e}", exc_info=True)
            
            return Response(
                {"error": "서버 내부 오류가 발생했습니다."}, 
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

class HealthCheckAPI(APIView):
    """
    서버 상태 확인용 엔드포인트 (옵션)
    GET /api/health/
    """
    def get(self, request):
        return Response({
            "status": "ok",
            "model_loaded": CommunicationConfig.model_loaded
        })

from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
import logging

from .models import CommunicationLog
from .apps import CommunicationConfig


# 로거 설정
logger = logging.getLogger(__name__)


# ============================================
# 헬퍼 함수들
# ============================================

def get_simple_type(level):
    """7단계 → 3단계로 단순화 (안전/주의/피싱)"""
    if level == "정상":
        return "안전"
    elif "피싱" in level:
        return "피싱"
    else:
        return "주의"

def get_danger_list(level, text):
    """위험 요소 리스트 생성"""
    dangers = []

    # 가족 사칭
    if "가족 사칭" in level:
        dangers.append("가족을 사칭한 금전 요구")
        if "입금" in text or "송금" in text:
            dangers.append("즉시 송금 요구")
    
    # 링크 피싱
    if "링크" in level or "http" in text.lower() or "[url]" in text.lower():
        dangers.append("의심스러운 링크 포함")
    
    # 결제 관련
    if "결제" in level or "결제" in text or "승인" in text:
        dangers.append("결제/승인 관련 내용")
    
    # 계정 관련
    if "계정" in text or "로그인" in text:
        dangers.append("계정 정보 요구")
    
    # 해외 관련
    if "해외" in text:
        dangers.append("해외 결제/접속 의심")
    
    # 개인정보
    if "본인" in text or "개인정보" in text:
        dangers.append("개인정보 요구")
    
    # 위험 요소가 없으면 기본 메시지
    if not dangers:
        if "피싱" in level or "주의" in level:
            dangers.append("의심스러운 내용 포함")
        else:
            dangers.append("특별한 위험 요소 없음")
    
    return dangers


def get_solve_list(level):
    """해결 방법 리스트 생성"""
    solves = []
    
    if "피싱" in level:
        solves.append("절대 송금하거나 개인정보를 입력하지 마세요")
        solves.append("발신자 번호를 공식 홈페이지와 대조하세요")
        solves.append("의심되면 해당 기관에 직접 전화로 확인하세요")
        solves.append("링크를 클릭하지 말고 공식 앱을 이용하세요")
    elif "주의" in level:
        solves.append("발신자 번호를 확인하세요")
        solves.append("공식 채널로 재확인하세요")
        solves.append("개인정보 입력 전 신중히 판단하세요")
    else:  # 정상
        solves.append("정상적인 메시지로 판단됩니다")
        solves.append("그래도 의심되면 발신자에게 직접 확인하세요")
    
    return solves



# ============================================
# API Views
# ============================================

class ClassifyAPI(APIView):
    """
    피싱 탐지 API 엔드포인트
    POST /api/classify/
    Body: {"text": "사용자가 입력한 문자 원문"}
    """
    
    def post(self, request):
        # 디버깅: 받은 데이터 출력
        print("=" * 50)
        print("받은 데이터:", request.data)
        print("=" * 50)
        
        # 1. 입력 데이터 검증
        input_text = request.data.get('text') or request.data.get('spamM')

        print(f"추출한 텍스트: '{input_text}'")
        print(f"텍스트 길이: {len(input_text) if input_text else 0}")
        
        if not input_text or len(input_text.strip()) == 0:
            logger.warning(f"[CLASSIFY] 빈 텍스트 요청")
            return Response(
                {"error": "텍스트를 입력해주세요."}, 
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

            # 응답 데이터 구성 (프론트 형식에 맞춰 변경하였습니다.)
            response_data = {
                "type": get_simple_type(result["type"]),      # "안전", "주의", "피싱"
                "message": result["message"],                 # AI 생성 메시지
                "danger": get_danger_list(result["type"], input_text),  # 위험 요소 리스트
                "solve": get_solve_list(result["type"]),      # 해결 방법 리스트
                "percent": round(result["probability"] * 100, 2),  # 확신도
                "is_dangerous": result["label"] == 1          # 위험 여부
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

            # 로깅 (콘솔에 출력)
            logger.info(
                f"[CLASSIFY] 성공 - Type: {response_data['type']}, "
                f"Label: {result['type']}, "
                f"Prob: {response_data['percent']}%"
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

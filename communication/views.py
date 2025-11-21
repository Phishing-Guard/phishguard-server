from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.pagination import PageNumberPagination
from django.core.cache import cache
from django.db.models import Count, Q, Avg
from django.utils.decorators import method_decorator
from django.views.decorators.cache import cache_page
from django.utils import timezone
from datetime import timedelta
import hashlib
import logging

from .models import CommunicationLog
from .apps import CommunicationConfig
from .throttling import UserRateThrottle

# 로거 설정
logger = logging.getLogger(__name__)


class ClassifyAPI(APIView):
    """
    피싱 탐지 API 엔드포인트
    POST /api/classify/
    Body: {"text": "사용자가 입력한 문자 원문"}
    """
    
    # Rate Limiting 적용 (IP당 분당 60회)
    throttle_classes = [UserRateThrottle]
    
    def post(self, request):
        start_time = timezone.now()
        
        # 1. 입력 데이터 검증
        input_text = request.data.get('text', None)
        
        if not input_text:
            logger.warning(f"[CLASSIFY] 빈 텍스트 요청 - IP: {self.get_client_ip(request)}")
            return Response(
                {"error": "텍스트가 필요합니다."}, 
                status=status.HTTP_400_BAD_REQUEST
            )
        
        if not isinstance(input_text, str):
            return Response(
                {"error": "텍스트는 문자열이어야 합니다."}, 
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # 텍스트 길이 제한 (너무 긴 요청 차단)
        if len(input_text) > 1000:
            logger.warning(f"[CLASSIFY] 너무 긴 텍스트 ({len(input_text)}자)")
            return Response(
                {"error": "텍스트는 1000자 이하로 입력해주세요."}, 
                status=status.HTTP_400_BAD_REQUEST
            )
        
        if len(input_text.strip()) == 0:
            return Response(
                {"error": "유효한 텍스트를 입력해주세요."}, 
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # 2. 모델 로드 여부 확인
        if not CommunicationConfig.model_loaded:
            logger.error("[CLASSIFY] 모델이 로드되지 않음")
            return Response(
                {"error": "모델이 아직 준비되지 않았습니다. 잠시 후 다시 시도해주세요."}, 
                status=status.HTTP_503_SERVICE_UNAVAILABLE
            )
        
        # 3. 캐시 확인 (같은 텍스트는 캐시에서 빠르게 반환)
        cache_key = self._get_cache_key(input_text)
        cached_result = cache.get(cache_key)
        
        if cached_result:
            logger.info(f"[CLASSIFY] 캐시 히트 - {cache_key[:16]}...")
            # 캐시된 결과도 DB에는 저장
            self._save_log(input_text, cached_result)
            return Response(cached_result, status=status.HTTP_200_OK)
        
        # 4. 피싱 탐지 수행
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
                "processing_time_ms": int((timezone.now() - start_time).total_seconds() * 1000)
            }
            
            # 5. DB 로그 저장
            self._save_log(input_text, response_data)
            
            # 6. 캐시에 저장 (10분간 유지)
            cache.set(cache_key, response_data, timeout=600)
            
            # 로깅
            logger.info(
                f"[CLASSIFY] 성공 - Label: {result['type']}, "
                f"Prob: {response_data['percent']}%, "
                f"Time: {response_data['processing_time_ms']}ms"
            )
            
            return Response(response_data, status=status.HTTP_200_OK)
        
        except Exception as e:
            logger.error(f"[CLASSIFY] 모델 추론 오류: {e}", exc_info=True)
            
            return Response(
                {"error": "서버 내부 오류가 발생했습니다. 잠시 후 다시 시도해주세요."}, 
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    def _get_cache_key(self, text: str) -> str:
        """텍스트의 해시값을 캐시 키로 사용"""
        text_hash = hashlib.md5(text.encode('utf-8')).hexdigest()
        return f"phishing_result:{text_hash}"
    
    def _save_log(self, input_text: str, response_data: dict):
        """DB에 로그 저장 (비동기 처리 가능)"""
        try:
            CommunicationLog.objects.create(
                input_text=input_text,
                result_label=response_data["level"],
                result_percent=response_data["percent"]
            )
        except Exception as e:
            logger.error(f"[CLASSIFY] DB 저장 실패: {e}")
    
    def get_client_ip(self, request):
        """클라이언트 IP 추출"""
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            ip = x_forwarded_for.split(',')[0]
        else:
            ip = request.META.get('REMOTE_ADDR')
        return ip


class LogListAPI(APIView):
    """
    로그 조회 API
    GET /api/logs/?page=1&size=20&filter=dangerous
    """
    
    def get(self, request):
        # 쿼리 파라미터
        page = int(request.GET.get('page', 1))
        size = int(request.GET.get('size', 20))
        filter_type = request.GET.get('filter', 'all')  # all, dangerous, safe
        
        # 기본 쿼리셋
        queryset = CommunicationLog.objects.all().order_by('-created_at')
        
        # 필터링
        if filter_type == 'dangerous':
            queryset = queryset.filter(
                Q(result_label__contains='피싱') | 
                Q(result_label__contains='주의')
            )
        elif filter_type == 'safe':
            queryset = queryset.filter(result_label='정상')
        
        # 페이지네이션
        paginator = PageNumberPagination()
        paginator.page_size = size
        paginated_logs = paginator.paginate_queryset(queryset, request)
        
        # 데이터 직렬화
        data = [{
            "id": log.id,
            "text": log.input_text[:100] + "..." if len(log.input_text) > 100 else log.input_text,
            "label": log.result_label,
            "percent": log.result_percent,
            "created_at": log.created_at.isoformat()
        } for log in paginated_logs]
        
        return paginator.get_paginated_response(data)


class StatisticsAPI(APIView):
    """
    통계 API
    GET /api/statistics/?period=today
    """
    
    @method_decorator(cache_page(60 * 5))  # 5분 캐싱
    def get(self, request):
        period = request.GET.get('period', 'today')  # today, week, month, all
        
        # 기간 필터
        queryset = CommunicationLog.objects.all()
        now = timezone.now()
        
        if period == 'today':
            queryset = queryset.filter(created_at__date=now.date())
        elif period == 'week':
            queryset = queryset.filter(created_at__gte=now - timedelta(days=7))
        elif period == 'month':
            queryset = queryset.filter(created_at__gte=now - timedelta(days=30))
        
        # 통계 계산
        total_count = queryset.count()
        
        dangerous_count = queryset.filter(
            Q(result_label__contains='피싱') | 
            Q(result_label__contains='주의')
        ).count()
        
        safe_count = queryset.filter(result_label='정상').count()
        
        # 평균 확률
        avg_percent = queryset.aggregate(Avg('result_percent'))['result_percent__avg'] or 0
        
        # 레이블별 분포
        label_distribution = queryset.values('result_label').annotate(
            count=Count('result_label')
        ).order_by('-count')
        
        return Response({
            "period": period,
            "total_requests": total_count,
            "dangerous_count": dangerous_count,
            "safe_count": safe_count,
            "average_confidence": round(avg_percent, 2),
            "label_distribution": list(label_distribution),
            "danger_rate": round(dangerous_count / total_count * 100, 2) if total_count > 0 else 0
        })


class HealthCheckAPI(APIView):
    """
    서버 상태 확인
    GET /api/health/
    """
    
    def get(self, request):
        # 모델 상태
        model_status = CommunicationConfig.model_loaded
        
        # DB 연결 확인
        try:
            CommunicationLog.objects.count()
            db_status = True
        except Exception:
            db_status = False
        
        # 캐시 상태 확인
        try:
            cache.set('health_check', 'ok', 1)
            cache_status = cache.get('health_check') == 'ok'
        except Exception:
            cache_status = False
        
        # 최근 요청 수 (최근 1분)
        recent_requests = CommunicationLog.objects.filter(
            created_at__gte=timezone.now() - timedelta(minutes=1)
        ).count()
        
        overall_status = model_status and db_status and cache_status
        
        return Response({
            "status": "healthy" if overall_status else "unhealthy",
            "model_loaded": model_status,
            "database_connected": db_status,
            "cache_available": cache_status,
            "recent_requests_per_minute": recent_requests,
            "timestamp": timezone.now().isoformat()
        }, status=status.HTTP_200_OK if overall_status else status.HTTP_503_SERVICE_UNAVAILABLE)


class ClearCacheAPI(APIView):
    """
    캐시 초기화 (관리자용)
    POST /api/cache/clear/
    """
    
    def post(self, request):
        try:
            cache.clear()
            logger.info("[CACHE] 캐시 전체 초기화")
            return Response({"message": "캐시가 초기화되었습니다."})
        except Exception as e:
            logger.error(f"[CACHE] 초기화 실패: {e}")
            return Response(
                {"error": "캐시 초기화 실패"}, 
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
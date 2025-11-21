"""
Rate Limiting (속도 제한) 설정
과도한 요청으로부터 서버를 보호
"""
from rest_framework.throttling import SimpleRateThrottle


class UserRateThrottle(SimpleRateThrottle):
    """
    사용자별 요청 제한
    - 인증된 사용자: user ID 기준
    - 비인증 사용자: IP 주소 기준
    """
    scope = 'user'
    
    def get_cache_key(self, request, view):
        """
        캐시 키 생성
        인증된 사용자는 user.id, 아니면 IP 주소 사용
        """
        if request.user and request.user.is_authenticated:
            ident = request.user.pk
        else:
            ident = self.get_ident(request)
        
        return self.cache_format % {
            'scope': self.scope,
            'ident': ident
        }


class BurstRateThrottle(SimpleRateThrottle):
    """
    짧은 시간 동안의 급격한 요청 차단
    예: 1초에 5회 이상 요청 시 차단
    """
    scope = 'burst'
    
    def get_cache_key(self, request, view):
        if request.user and request.user.is_authenticated:
            ident = request.user.pk
        else:
            ident = self.get_ident(request)
        
        return self.cache_format % {
            'scope': self.scope,
            'ident': ident
        }
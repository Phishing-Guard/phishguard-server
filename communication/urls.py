# 앱 세부 주소록
from django.urls import path
from .views import (
    ClassifyAPI,
    LogListAPI,
    StatisticsAPI,
    HealthCheckAPI,
    ClearCacheAPI
)

urlpatterns = [
    # 핵심 API
    path('classify/', ClassifyAPI.as_view(), name='classify'),
    
    # 데이터 조회 API
    path('logs/', LogListAPI.as_view(), name='logs'),
    path('statistics/', StatisticsAPI.as_view(), name='statistics'),
    
    # 시스템 관리 API
    path('health/', HealthCheckAPI.as_view(), name='health'),
    path('cache/clear/', ClearCacheAPI.as_view(), name='clear_cache'),
]
# 앱 세부 주소록
from django.urls import path
from .views import (
    ClassifyAPI,
    HealthCheckAPI,
)

urlpatterns = [
    # 피싱 탐지 API
    path('classify/', ClassifyAPI.as_view(), name='classify'),
    
    # 서버 상태 확인
    path('health/', HealthCheckAPI.as_view(), name='health'),

]
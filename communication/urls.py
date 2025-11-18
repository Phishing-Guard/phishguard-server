# 앱 세부 주소록
from django.urls import path
from . import views

urlpatterns = [
    # 'api/classify/' 주소로 요청이 오면 'views.ClassifyAPI'가 처리
    path('classify/', views.ClassifyAPI.as_view(), name='classify')
]

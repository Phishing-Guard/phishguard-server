from django.contrib import admin
from django.urls import path, include

urlpatterns = [
    path('admin/', admin.site.urls),
    # 프론트엔드가 'api/'로 요청 시 communication 앱으로 연결합니다.
    path('api/', include('communication.urls')), 
    
]

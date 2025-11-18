from django.db import models

# CommunicationLog 모델 설계 : 
# 피싱 감지 API 의 로그를 저장할 DB 테이블을 ORM으로 설계합니다.

class CommunicationLog(models.Model):
    input_text = models.TextField(help_text="사용자가 입력한 문자 원문")
    result_label = models.CharField(max_length=10, help_text="모델이 판별한 결과 (예: 위험, 안전)")
    result_percent = models.FloatField(help_text="모델이 계산한 확률 (예: 98.5)")
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"[{self.result_label}] {self.input_text[:30]}..."
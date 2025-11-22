from django.db import models

class CommunicationLog(models.Model):
    """피싱 감지 API 로그 저장 모델"""
    input_text = models.TextField(
        help_text="사용자가 입력한 문자 원문"
    )

    result_label = models.CharField(
        max_length=50, # ✅ 10 → 50 (긴 레이블 저장)
        help_text="모델이 판별한 결과 (예: 위험, 안전)",
        db_index=True  # ✅ 검색 성능 향상
    )

    result_percent = models.FloatField(
        help_text="모델이 계산한 확률 (0~100)"
    )

    created_at = models.DateTimeField(
        auto_now_add=True,
        db_index=True  # ✅ 날짜 기반 쿼리 최적화
    )

    class Meta:
        db_table = 'communication_logs'  # ✅ 테이블 이름 명시
        ordering = ['-created_at']  # ✅ 최신순 정렬
        verbose_name = '피싱 탐지 로그'
        verbose_name_plural = '피싱 탐지 로그'

    def __str__(self):
        return f"[{self.result_label}] {self.input_text[:30]}..."
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status

# DB 모델 임포트
from .models import CommunicationLog
# 모델 로더 임포트
from .apps import CommunicationConfig

class ClassifyAPI(APIView):
    def post(self, request):
        input_text = request.data.get('text', None) # 프론트엔드가 보낸 JSON 데이터를 받음
        if not input_text:
            return Response({"error": "텍스트가 필요합니다."}, status=400)
        
        # apps.py 의 미리 로드된 모델 가져오기 
        model = CommunicationConfig.phishing_model
        vectorizer = CommunicationConfig.tfidf_vectorizer

        # 모델 로드 실패 시 수행
        if not model or not vectorizer:
            return Response({"error": "모델이 준비되지 않았습니다."}, status=500)
        
        # 백엔드 1과 약속된 로직 수행 예시
        try:
            text_vector = vectorizer.transform([input_text]) # 입력 텍스트를 번역 (TF_IDF)
            prediction = model.predict(text_vector) # 예: [0] (안전) or [1] (위험) -> 모델이 예측한 결과?
            probability = model.predict_proba(text_vector) # 예: [[0.98, 0.02]] -> 정확도? 

            label = "위험" if prediction[0] == 1 else "안전"
            percent = round(probability[0][prediction[0]] * 100, 2)

            # DB에 로그를 생성 (models.py)
            CommunicationLog.objects.create(
                input_text=input_text,
                result_label = label,
                result_percent = percent
            )

            # 프론트엔드에 최종 응답 전송
            return Response({
                "level" : label,
                "percent" : percent
            }, status=status.HTTP_200_OK)
        
        except Exception as e:
            return Response({"error": f"모델 추론 중 오류: {e}"}, status=500)

        
        
        

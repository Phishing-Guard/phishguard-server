# 앱 처음 실행 시 모델을 한 번만 로드
# 모델을 로드할 코드를 ready() 함수 안에 작성합니다.

from django.apps import AppConfig
import joblib   # pkl 파일 관련
import os

# 테스트 모델
from .ml_models import PhishingModelMock, TfidfVectorizerMock

class CommunicationConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'communication'

    # 로드된 모델을 담을 변수
    phishing_model = None
    tfidf_vectorizer = None # (TF-IDF도 같이 로드해야 함)

    def ready(self): # 이 함수는 서버가 켜질 때 한 번만 실행됩니다.
        print("피싱 감지 모델을 로드합니다...")

        #백엔드 1이 전달한 모델 파일의 경로
        model_path = "communication/ml_models/phishing_model.pkl"
        vectorizer_path = "communication/ml_models/tfidf_vectorizer.pkl"

        # 모델 파일의 경로로부터 모델을 로드해 클래스 변수에 저장 
        try:
            # 1. TF-IDF 벡터라이저 로드
            CommunicationConfig.tfidf_vectorizer = joblib.load(vectorizer_path) 
            # 2. 피싱 감지 모델 로드
            CommunicationConfig.phishing_model = joblib.load(model_path)
            print("모델 로드 완료.")
        except FileNotFoundError:
            print("⚠️ [백엔드 2] 모델 파일을 찾을 수 없습니다. (테스트 모드)")
        return super().ready()

# communication/ml_models.py (새 파일 생성 - '백엔드 2'가 테스트용으로)

import time
import random

class PhishingModelMock:
    """
    '백엔드 1'이 완성할 실제 모델의 '가짜' 버전 (Mock)
    - load()는 오래 걸리는 척
    - predict()는 0.1초 안에 가짜 결과를 반환
    """
    def __init__(self):
        # 1. Colab에서 만든 무거운 모델을 로드하는 척 (5초)
        # (apps.py에서 서버 켤 때 딱 한 번 실행될 부분)
        print("    [Mock Model] 가짜 딥러닝 모델 로드 시작... (5초)")
        time.sleep(5)
        print("    [Mock Model] 가짜 딥러닝 모델 로드 완료.")
        
    def predict(self, text_vector):
        # 2. 'views.py'에서 호출할 가짜 예측 함수
        # (API 호출 시마다 실행될 부분)
        
        # '위험'이 30% 확률로, '안전'이 70% 확률로 나오도록 함
        if random.random() < 0.3:
            return [1] # [위험]
        else:
            return [0] # [안전]
            
    def predict_proba(self, text_vector):
        # 3. 'views.py'에서 호출할 가짜 확률 함수
        prediction = self.predict(text_vector)
        percent = round(random.uniform(90.0, 99.9), 2)
        
        if prediction[0] == 1: # 위험
            return [[(100.0 - percent) / 100, percent / 100]]
        else: # 안전
            return [[percent / 100, (100.0 - percent) / 100]]

class TfidfVectorizerMock:
    """
    '백엔드 1'이 완성할 TF-IDF의 '가짜' 버전 (Mock)
    """
    def __init__(self):
        print("    [Mock TF-IDF] 가짜 벡터라이저 로드 완료.")
        
    def transform(self, text_list):
        # 1. 'views.py'에서 호출할 가짜 변환 함수
        # (어떤 텍스트가 들어와도 그냥 [1]이라는 가짜 벡터 반환)
        print(f"    [Mock TF-IDF] '{text_list[0][:10]}...' 텍스트 변환 완료.")
        return [1]
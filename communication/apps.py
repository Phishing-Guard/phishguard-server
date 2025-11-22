from django.apps import AppConfig

class CommunicationConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'communication'

    # 모델 로드 상태 플래그
    model_loaded = False

    def ready(self):
        """서버 시작 시 한 번만 실행"""
        # Django의 ready()는 여러 번 호출될 수 있으므로 중복 방지
        if not CommunicationConfig.model_loaded:
            print("\n" + "="*60)
            print("🚀 피싱 탐지 모델 초기화 시작")
            print("="*60)
            
            try:
                from .ml_loader import load_models
                # 모델 로드 
                success = load_models(model_dir="communication/ml_models")
                
                if success:
                    CommunicationConfig.model_loaded = True
                    print("="*60)
                    print("✅ 피싱 탐지 시스템 준비 완료!")
                    print("="*60 + "\n")
                else:
                    print("⚠️ 모델 로드에 실패했습니다.")
                    print("⚠️ API 호출 시 503 에러가 반환됩니다.")
                    
            except Exception as e:
                print(f"❌ 모델 초기화 중 오류: {e}")
                print("⚠️ 서버는 실행되지만 AI 기능이 작동하지 않습니다.")
        
        return super().ready()
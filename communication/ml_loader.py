# ----------------------------------------------------
# Jupyter Notebook 코드를 Django용으로 변환한 모델 로더

import os
import re
import random
import numpy as np
import torch
from transformers import AutoTokenizer, AutoModelForSequenceClassification
from sentence_transformers import SentenceTransformer, util
from torch.serialization import add_safe_globals

# numpy scalar 허용 (threshold .pt 로드 에러 방지)
add_safe_globals([np._core.multiarray.scalar])


# ----------------------------------------------------
# 0. 기본 설정 (Device & Seed)
# ----------------------------------------------------

# 전역 변수로 모델들을 저장
_tokenizer = None
_service_model = None
_service_threshold = None
_sbert_model = None
_fn_texts = None
_fn_embs = None
_device = None

# 설정값 (모델 상수)
MODEL_NAME = "skt/kobert-base-v1"
SBERT_MODEL_NAME = "jhgan/ko-sroberta-multitask"
SIM_THRESHOLD = 0.80


def set_seed(seed: int = 42):
    """재현성을 위한 시드 고정"""
    random.seed(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)
    torch.cuda.manual_seed_all(seed)
    torch.backends.cudnn.deterministic = True
    torch.backends.cudnn.benchmark = False


# ----------------------------------------------------
# 1. 전처리 함수 (학습 때 쓰던 그대로)
# ----------------------------------------------------
def preprocess_text(text: str) -> str:
    """학습 때 사용한 전처리 함수"""
    if not isinstance(text, str):
        text = str(text)
    text = text.replace("\n", " ")
    text = re.sub(r"(https?://\S+|www\.\S+)", "[URL]", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


# ----------------------------------------------------
# ** Google Drive에서 모델 파일 다운로드
# ----------------------------------------------------
def download_models_from_gdrive(model_dir="communication/ml_models"): 
    import gdown 

    # 폴더 생성
    os.makedirs(model_dir, exist_ok=True)

    # Google Drive 링크
    MODEL_LINK = "https://drive.google.com/uc?id=1BHXCSzY1zA5lh_7UMPGNyckczLwQ6Fmm"
    TH_LINK = "https://drive.google.com/uc?id=1krNqo9Q5q0FPGE_BqTWwGTZ8JhBRIOL-"
    BANK_LINK = "https://drive.google.com/uc?id=197kaEJ2YNXQHNo7AqW2DvtZcxpth5pSA"

    model_path = os.path.join(model_dir, "best_model_v1.pt")
    threshold_path = os.path.join(model_dir, "best_threshold_recall_prior.pt")
    bank_path = os.path.join(model_dir, "semantic_bank_fn.pt")

    # 파일이 이미 있으면 스킵
    if os.path.exists(model_path) and os.path.exists(threshold_path) and os.path.exists(bank_path):
        print("   ✅ 모델 파일이 이미 존재합니다. 다운로드 스킵.")
        return True
    
    print("   🔽 Google Drive에서 모델 다운로드 중...")
    
    try:
        if not os.path.exists(model_path):
            print("   🔽 best_model_v1.pt 다운로드 중...")
            gdown.download(MODEL_LINK, model_path, quiet=False)
        
        if not os.path.exists(threshold_path):
            print("   🔽 best_threshold_recall_prior.pt 다운로드 중...")
            gdown.download(TH_LINK, threshold_path, quiet=False)
        
        if not os.path.exists(bank_path):
            print("   🔽 semantic_bank_fn.pt 다운로드 중...")
            gdown.download(BANK_LINK, bank_path, quiet=False)
        
        print("   ✅ 모델 다운로드 완료!")
        return True
        
    except Exception as e:
        print(f"   ❌ 모델 다운로드 실패: {e}")
        return False


# ----------------------------------------------------
# 2. 토크나이저 & 최종 서비스용 모델 & Threshold & SBERT 뱅크 로드

    # 서버 시작 시 한 번만 실행되는 모델 로드 함수
    # apps.py의 ready()에서 호출됨
    
# ----------------------------------------------------
def load_models(model_dir="communication/ml_models"):

    global _tokenizer, _service_model, _service_threshold
    global _sbert_model, _fn_texts, _fn_embs, _device
    
    print("🔄 피싱 탐지 모델 로딩 시작...")

    # 모델 파일 다운로드
    if not download_models_from_gdrive(model_dir):
        print("   ⚠️ 모델 파일 다운로드 실패. 수동으로 다운로드 필요.")
        return False        

    # Device 설정
    _device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    print(f"   Device: {_device}")
    
    # Seed 고정
    set_seed(42)

    # 파일 경로
    model_path = os.path.join(model_dir, "best_model_v1.pt")
    threshold_path = os.path.join(model_dir, "best_threshold_recall_prior.pt")
    bank_path = os.path.join(model_dir, "semantic_bank_fn.pt")

    try:
        # 1. 토크나이저 로드
        print("   🔄 토크나이저 로드 중...")
        _tokenizer = AutoTokenizer.from_pretrained(MODEL_NAME)
        
        # 2. KoBERT 모델 로드
        print("   🔄 KoBERT 모델 로드 중...")
        _service_model = AutoModelForSequenceClassification.from_pretrained(
            MODEL_NAME,
            num_labels=2,
        )
        state_dict = torch.load(model_path, map_location=_device)
        _service_model.load_state_dict(state_dict)
        _service_model.to(_device)
        _service_model.eval()

         # 3. Threshold 로드
        print("   🔄 Threshold 로드 중...")
        _service_threshold = torch.load(
            threshold_path,
            map_location="cpu",
            weights_only=False,
        )["threshold"]
        
        # 4. SBERT 모델 로드
        print("   🔄 SBERT 모델 로드 중...")
        _sbert_model = SentenceTransformer(SBERT_MODEL_NAME, device=_device)
        
        # 5. FN 임베딩 뱅크 로드
        print("   🔄 FN 임베딩 뱅크 로드 중...")
        bank = torch.load(bank_path, map_location="cpu")
        _fn_texts = bank["fn_texts"]
        _fn_embs = bank["fn_embs"].to(_device)
        
        print("✅ 모델 로드 완료!")
        print(f"   - Threshold: {_service_threshold:.4f}")
        print(f"   - SIM_THRESHOLD: {SIM_THRESHOLD:.2f}")
        print(f"   - FN Count: {_fn_embs.shape[0]}")

        return True
    
    except Exception as e:
        print(f"❌ 모델 로드 실패: {e}")
        return False


# ----------------------------------------------------
# 3. 예측 함수 (AI 모델 추론) - 1단계 KoBERT
# ----------------------------------------------------
def predict_smishing(text_input: str):
    """1단계: KoBERT 기반 피싱 예측"""
    text = preprocess_text(text_input)
    
    encoding = _tokenizer.encode_plus(
        text,
        add_special_tokens=True,
        max_length=128,
        padding="max_length",
        truncation=True,
        return_attention_mask=True,
        return_tensors="pt",
    )
    
    with torch.no_grad():
        outputs = _service_model(
            input_ids=encoding["input_ids"].to(_device),
            attention_mask=encoding["attention_mask"].to(_device),
        )
        prob = torch.softmax(outputs.logits, dim=-1)[0][1].item()
        label = 1 if prob >= _service_threshold else 0
    
    return label, prob

# ----------------------------------------------------
# 3-1. SBERT 기반 FN-유사도 계산 함수 - 2단계용
# ----------------------------------------------------
def sbert_max_similarity_fn(text_input: str) -> float:
    """2단계: SBERT 기반 FN 유사도 계산"""
    text = preprocess_text(text_input)
    with torch.no_grad():
        query_emb = _sbert_model.encode(text, convert_to_tensor=True).to(_device)
        cos_sim = util.cos_sim(query_emb, _fn_embs)
        max_sim = float(torch.max(cos_sim).item())
    return max_sim


# ----------------------------------------------------
# 4. 의도 분석 함수 (✨ 하이브리드 로직)
# view에서 호출하는 최종 함수
# ----------------------------------------------------

def analyze_intent(text_input: str) -> dict:
    """
    하이브리드 피싱 탐지 로직
    Django View에서 호출할 메인 함수
    """
    # 1단계: KoBERT 분류
    label, prob = predict_smishing(text_input)
    
    # 텍스트 분석 준비
    text = preprocess_text(text_input)
    t = text.lower()
    
    # CASE A: KoBERT가 '피싱(1)'이라고 판단
    if label == 1:
        # 링크 없는 결제/승인 알림
        if ("결제" in text or "승인" in text) and ("http" not in t and "[url]" not in t):
            return {
                "label": 1,
                "probability": prob,
                "type": "주의 요망(결제 알림)",
                "message": "⚠️ 결제/승인 알림으로 보이지만, 발신자 번호와 카드사 공식번호를 반드시 확인하세요."
            }
        
        # 가족 사칭
        if ("엄마" in text or "아빠" in text or "부모" in text) and \
           ("입금" in text or "송금" in text or "액정" in text or "수리" in text):
            return {
                "label": 1,
                "probability": prob,
                "type": "가족 사칭 피싱",
                "message": "🚨 가족을 사칭하여 금전이나 개인정보를 요구하고 있습니다. 절대 송금하지 마세요."
            }
        
        # 결제/링크 피싱
        if ("결제" in text or "승인" in text or "로그인" in text or "계정" in text) and \
           ("http" in t or "[url]" in t):
            return {
                "label": 1,
                "probability": prob,
                "type": "결제/링크 피싱",
                "message": "🚨 결제/로그인 관련 내용을 미끼로 링크 클릭을 유도하고 있습니다. 링크를 절대 누르지 마세요."
            }
        
        # 기타 피싱
        return {
            "label": 1,
            "probability": prob,
            "type": "피싱 위험",
            "message": "🚨 피싱 위험이 감지되었습니다. 포함된 링크나 번호를 절대 누르지 마세요."
        }
    
    # CASE B: KoBERT는 정상이지만 SBERT 2단계 검증
    max_sim_p = sbert_max_similarity_fn(text_input)
    
    if max_sim_p >= SIM_THRESHOLD:
        return {
            "label": 1,
            "probability": prob,
            "type": "의심 피싱(의미 유사)",
            "message": (
                f"🚨 과거 피싱(FN) 사례들과 의미적으로 매우 유사합니다 "
                f"(유사도 {max_sim_p:.2f}). 발신자 및 링크를 반드시 확인하세요."
            ),
        }
    
    # CASE C: 민감 키워드 포함
    risk_keywords = ["해외", "결제", "승인", "본인", "개인정보", "계좌", "출금", "지급", "로그인", "계정"]
    
    if any(keyword in text for keyword in risk_keywords):
        return {
            "label": 0,
            "probability": prob,
            "type": "주의 요망",
            "message": "⚠️ 피싱 확률은 낮으나, 결제/개인정보 등 민감한 내용이 포함되어 있습니다. 발신자를 꼭 확인하세요."
        }
    
    # CASE D: 정상 메시지
    return {
        "label": 0,
        "probability": prob,
        "type": "정상",
        "message": "✅ 정상적인 메시지로 판단됩니다."
    }
import streamlit as st
import pandas as pd
import google.generativeai as genai
from PIL import Image
from thefuzz import process, fuzz
import io
import json

# ==========================================
# 1. 설정 및 데이터 로드
# ==========================================

# [수정됨] API 키를 Streamlit의 비밀 보관소(Secrets)에서 가져옵니다.
# 만약 로컬에서 테스트 중이라면 st.secrets가 없으므로 예외처리를 합니다.
try:
    api_key = st.secrets["GEMINI_API_KEY"]
    genai.configure(api_key=api_key)
except Exception:
    st.error("API 키가 설정되지 않았습니다. Streamlit 설정에서 Secrets를 등록해주세요.")

@st.cache_data
def load_data():
    # 이제 csv 문자열이 아니라, 방금 올린 파일을 읽어옵니다.
    return pd.read_csv("gim_data.csv")

df = load_data()

# ==========================================
# 2. AI 분석 및 매칭 로직
# ==========================================

def analyze_image_with_gemini(image):
    # 모델 설정을 2.5 Flash로 지정
    model = genai.GenerativeModel('gemini-2.5-flash')
    
    prompt = """
    이 김 포장지 사진을 분석해서 다음 정보를 JSON 형식으로 출력해줘.
    응답 형식:
    {
        "brand": "브랜드명",
        "product_name": "제품명",
        "keywords": "주요 특징 키워드 3개"
    }
    JSON 외에 다른 말은 하지 마.
    """
    
    try:
        # 에러 확인을 위해 stream=False로 호출
        response = model.generate_content([prompt, image])
        
        # 응답이 비어있는지 확인
        if not response.text:
            st.error("AI 응답이 비어있습니다. (Safety Filter 등 원인)")
            return None

        text = response.text.replace("```json", "").replace("```", "").strip()
        return json.loads(text)

    except Exception as e:
        # [중요] 에러가 나면 화면에 빨간 글씨로 띄워줍니다.
        st.error(f"🚨 AI 분석 중 오류 발생: {e}")
        return None

def find_best_match(ai_result, database):
    """AI가 찾은 텍스트와 DB를 비교하여 가장 비슷한 제품 찾기 (오류 수정판)"""
    
    # 검색을 위해 DB에 '검색용_텍스트' 컬럼 생성 (브랜드 + 제품명)
    database['검색용_텍스트'] = database['브랜드'].astype(str) + " " + database['제품명'].astype(str)
    
    # AI가 찾은 브랜드 + 제품명
    query = f"{ai_result.get('brand', '')} {ai_result.get('product_name', '')}"
    
    # 가장 유사한 제품 찾기 (TheFuzz 라이브러리 사용)
    # extractOne은 보통 (매칭된문자열, 점수) 튜플을 반환합니다.
    choices = database['검색용_텍스트'].tolist()
    best_match = process.extractOne(query, choices, scorer=fuzz.token_set_ratio)
    
    if best_match:
        # 반환값이 (문자열, 점수) 2개인 경우와 (문자열, 점수, 인덱스) 3개인 경우를 모두 대비
        matched_str = best_match[0]
        score = best_match[1]
        
        # 유사도 점수가 50점 미만이면 매칭 실패로 간주
        if score < 50:
            return None, score
            
        # 찾은 문자열(matched_str)을 이용해 DB에서 해당 행(Row)을 다시 가져옵니다
        matched_row = database[database['검색용_텍스트'] == matched_str].iloc[0]
        return matched_row, score
        
    return None, 0

# ==========================================
# 3. UI 구성
# ==========================================

st.set_page_config(page_title="Gim Sommelier", page_icon="🍙")
st.title("🍙 김 소믈리에 (Gim Sommelier)")
st.caption("사진을 찍으면 어떤 김인지 분석해드립니다. (Gemini 2.5 Flash)")

uploaded_file = st.file_uploader("김 포장지 사진을 올려주세요", type=["jpg", "png", "jpeg"])

if uploaded_file is not None:
    image = Image.open(uploaded_file)
    st.image(image, caption='업로드된 사진', width=300)
    
    if st.button("🔍 분석 시작"):
        with st.spinner('Gemini가 포장지를 읽는 중...'):
            ai_result = analyze_image_with_gemini(image)
            if ai_result:
                matched_product, score = find_best_match(ai_result, df)
                st.divider()
                if matched_product is not None:
                    st.subheader(f"🎯 {matched_product['브랜드']} {matched_product['제품명']}")
                    st.write(f"**평점:** ⭐ {matched_product['평점']}")
                    st.write(f"**특징:** {matched_product['핵심요약']}")
                    search_query = f"{matched_product['브랜드']} {matched_product['제품명']}"
                    st.link_button("🛍️ 네이버 최저가 보기", f"https://search.shopping.naver.com/search/all?query={search_query}")
                else:

                    st.warning("비슷한 제품을 찾지 못했습니다.")







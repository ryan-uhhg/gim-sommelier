import streamlit as st
import pandas as pd
import google.generativeai as genai
from PIL import Image
from thefuzz import process, fuzz
import io
import json

# ==========================================
# 1. 페이지 설정 (가장 먼저 실행되어야 함)
# ==========================================
st.set_page_config(page_title="Gim Sommelier", page_icon="🍙")

# ==========================================
# 2. 설정 및 데이터 로드
# ==========================================

# API 키 설정
try:
    api_key = st.secrets["GEMINI_API_KEY"]
    genai.configure(api_key=api_key)
except Exception:
    st.error("API 키가 설정되지 않았습니다. Streamlit 설정에서 Secrets를 등록해주세요.")

# CSV 데이터 파일 로드
@st.cache_data
def load_data():
    # GitHub에 올린 gim_data.csv 파일을 읽어옵니다.
    try:
        return pd.read_csv("gim_data.csv")
    except Exception as e:
        st.error(f"데이터 파일을 찾을 수 없습니다: {e}")
        return pd.DataFrame()

df = load_data()

# ==========================================
# 3. AI 및 매칭 로직
# ==========================================

def analyze_image_with_gemini(image):
    """Gemini 1.5 Flash를 사용하여 이미지 분석"""
    model = genai.GenerativeModel('gemini-2.5-flash') # 모델명 확인 필요
    
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
        response = model.generate_content([prompt, image])
        text = response.text.replace("```json", "").replace("```", "").strip()
        return json.loads(text)
    except Exception as e:
        st.error(f"AI 분석 중 오류가 발생했습니다: {e}")
        return None

def find_best_match(ai_result, database):
    """Fuzzy Matching 로직 (오류 수정됨)"""
    if database.empty:
        return None, 0

    # 검색을 위해 DB에 '검색용_텍스트' 컬럼 생성
    database['검색용_텍스트'] = database['브랜드'].astype(str) + " " + database['제품명'].astype(str)
    
    # AI가 찾은 텍스트
    query = f"{ai_result.get('brand', '')} {ai_result.get('product_name', '')}"
    
    # 가장 유사한 제품 찾기
    choices = database['검색용_텍스트'].tolist()
    best_match = process.extractOne(query, choices, scorer=fuzz.token_set_ratio)
    
    if best_match:
        # 반환값이 (문자열, 점수) 또는 (문자열, 점수, 인덱스) 일 수 있음
        matched_str = best_match[0]
        score = best_match[1]
        
        if score < 40: # 유사도가 너무 낮으면 실패 처리
            return None, score
            
        matched_row = database[database['검색용_텍스트'] == matched_str].iloc[0]
        return matched_row, score
        
    return None, 0

# ==========================================
# 4. UI 구성 (상세 대시보드 버전)
# ==========================================

st.title("🍙 김 소믈리에 (Gim Sommelier)")
st.caption("사진을 찍으면 어떤 김인지 분석해드립니다. (Powered by Gemini)")

# 파일 업로더 (이 코드는 전체 파일 중 딱 한 번만 나와야 함!)
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
                    # [결과 화면]
                    st.success("제품을 찾았습니다!")
                    st.markdown(f"## 🎯 {matched_product['브랜드']} {matched_product['제품명']}")
                    
                    # 핵심 지표
                    col1, col2, col3 = st.columns(3)
                    with col1:
                        st.metric("⭐ 평점", f"{matched_product['평점']}점")
                    with col2:
                        st.metric("💬 리뷰 수", f"{matched_product['리뷰수']}개")
                    with col3:
                        st.metric("💰 가격", f"{matched_product['가격']}")
                    
                    st.markdown("---")
                    
                    # 상세 스펙
                    st.markdown("### 📋 상세 정보")
                    detail_col1, detail_col2 = st.columns(2)
                    
                    with detail_col1:
                        st.markdown(f"**🏷️ 종류:** {matched_product['종류']}")
                        st.markdown(f"**🛒 주요 판매처:** {matched_product['쇼핑몰']}")
                    
                    with detail_col2:
                        st.markdown(f"**🔑 제품 ID:** {matched_product['제품_ID']}")
                        
                    # 핵심 요약
                    st.info(f"**💡 핵심 요약:**\n\n{matched_product['핵심요약']}")
                    
                    # 쇼핑몰 링크
                    search_query = f"{matched_product['브랜드']} {matched_product['제품명']}"
                    st.link_button(
                        "🛍️ 네이버 최저가 검색하러 가기", 
                        f"https://search.shopping.naver.com/search/all?query={search_query}",
                        use_container_width=True
                    )
                    
                    # 디버깅
                    with st.expander("AI 분석 상세 보기"):
                        st.write(f"AI 인식: {ai_result}")
                        st.write(f"일치율: {score}점")
                        
                else:
                    st.warning("비슷한 제품을 찾지 못했습니다.")
                    st.write(f"AI가 읽은 내용: {ai_result}")

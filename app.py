import streamlit as st
import pandas as pd
import google.generativeai as genai
from PIL import Image
from thefuzz import process, fuzz
import io
import json

# ==========================================
# 1. 다국어 설정 (Language Dictionary)
# ==========================================
ui_text = {
    "ko": {
        "title": "🍙 김 소믈리에",
        "caption": "사진을 찍으면 어떤 김인지 분석해드립니다.",
        "sidebar_title": "언어 설정 (Language)",
        "upload_label": "김 포장지 사진을 올려주세요",
        "btn_analyze": "🔍 분석 시작",
        "analyzing": "AI가 포장지를 읽고 있습니다...",
        "success_match": "제품을 찾았습니다!",
        "fail_match": "비슷한 제품을 찾지 못했습니다.",
        "score": "평점",
        "reviews": "리뷰 수",
        "price": "가격",
        "type": "종류",
        "shop": "판매처",
        "id": "제품 ID",
        "summary_title": "💡 핵심 요약",
        "link_btn": "🛍️ 최저가 검색하러 가기",
        "translating": "설명을 번역 중입니다...",
        "currency_unit": "원"
    },
    "en": {
        "title": "🍙 Gim Sommelier",
        "caption": "Upload a photo of Seaweed(Gim). AI will analyze it.",
        "sidebar_title": "Language",
        "upload_label": "Upload a photo of the package",
        "btn_analyze": "🔍 Analyze",
        "analyzing": "AI is analyzing the image...",
        "success_match": "Product Found!",
        "fail_match": "No matching product found.",
        "score": "Rating",
        "reviews": "Reviews",
        "price": "Price",
        "type": "Type",
        "shop": "Shop",
        "id": "ID",
        "summary_title": "💡 Summary",
        "link_btn": "🛍️ Search Online",
        "translating": "Translating description...",
        "currency_unit": " KRW"
    },
    "ja": {
        "title": "🍙 海苔ソムリエ",
        "caption": "写真を撮ると、どの海苔かAIが分析します。",
        "sidebar_title": "言語設定",
        "upload_label": "海苔のパッケージ写真をアップロード",
        "btn_analyze": "🔍 分析開始",
        "analyzing": "AIが画像を分析しています...",
        "success_match": "製品が見つかりました！",
        "fail_match": "一致する製品が見つかりませんでした。",
        "score": "評価",
        "reviews": "レビュー数",
        "price": "価格",
        "type": "種類",
        "shop": "販売店",
        "id": "ID",
        "summary_title": "💡 特徴まとめ",
        "link_btn": "🛍️ オンラインで検索",
        "translating": "説明を翻訳中...",
        "currency_unit": " ウォン"
    }
}

# ==========================================
# 2. 기본 설정 및 데이터 로드
# ==========================================
st.set_page_config(page_title="Gim Sommelier", page_icon="🍙")

# 언어 선택 사이드바
with st.sidebar:
    lang_choice = st.selectbox(
        "Language / 言語", 
        ["한국어", "English", "日本語"]
    )

# 선택된 언어 코드 결정
if lang_choice == "English":
    lang_code = "en"
elif lang_choice == "日本語":
    lang_code = "ja"
else:
    lang_code = "ko"

# 현재 언어의 텍스트 팩 가져오기
t = ui_text[lang_code]

# API 키 설정
try:
    api_key = st.secrets["GEMINI_API_KEY"]
    genai.configure(api_key=api_key)
except Exception:
    st.error("API Key Error. Please check Streamlit Secrets.")

# 데이터 로드
@st.cache_data
def load_data():
    try:
        return pd.read_csv("gim_data.csv")
    except:
        return pd.DataFrame()

df = load_data()

# ==========================================
# 3. AI 로직 (분석 + 번역)
# ==========================================

def analyze_image_with_gemini(image):
    model = genai.GenerativeModel('gemini-2.5-flash')
    # 분석은 정확도를 위해 한국어로 진행하고, 매칭 후에 번역합니다.
    prompt = """
    이 김 포장지 사진을 분석해서 다음 정보를 JSON 형식으로 출력해줘.
    텍스트를 있는 그대로 정확하게 읽어줘.
    응답 형식:
    {
        "brand": "브랜드명",
        "product_name": "제품명",
        "keywords": "특징 키워드"
    }
    JSON 외에 다른 말은 하지 마.
    """
    try:
        response = model.generate_content([prompt, image])
        text = response.text.replace("```json", "").replace("```", "").strip()
        return json.loads(text)
    except:
        return None

def translate_content(text, target_lang):
    """한국어 설명을 타겟 언어로 번역"""
    if target_lang == "ko": return text
    
    model = genai.GenerativeModel('gemini-1.5-flash')
    prompt = f"Translate the following Korean sentence to {target_lang} naturally:\n\n'{text}'"
    try:
        response = model.generate_content(prompt)
        return response.text.strip()
    except:
        return text # 실패하면 원문 반환

def find_best_match(ai_result, database):
    if database.empty: return None, 0
    database['검색용_텍스트'] = database['브랜드'].astype(str) + " " + database['제품명'].astype(str)
    query = f"{ai_result.get('brand', '')} {ai_result.get('product_name', '')}"
    choices = database['검색용_텍스트'].tolist()
    best_match = process.extractOne(query, choices, scorer=fuzz.token_set_ratio)
    
    if best_match:
        matched_str, score = best_match[0], best_match[1]
        if score < 40: return None, score
        matched_row = database[database['검색용_텍스트'] == matched_str].iloc[0]
        return matched_row, score
    return None, 0

# ==========================================
# 4. UI 렌더링
# ==========================================

st.title(t["title"])
st.caption(t["caption"])

uploaded_file = st.file_uploader(t["upload_label"], type=["jpg", "png", "jpeg"])

if uploaded_file is not None:
    image = Image.open(uploaded_file)
    st.image(image, caption='Uploaded Image', width=300)
    
    if st.button(t["btn_analyze"]):
        with st.spinner(t["analyzing"]):
            # 1. 이미지 분석
            ai_result = analyze_image_with_gemini(image)
            
            if ai_result:
                matched_product, score = find_best_match(ai_result, df)
                st.divider()
                
                if matched_product is not None:
                    st.success(t["success_match"])
                    
                    # 2. 즉석 번역 (핵심 요약)
                    final_summary = matched_product['핵심요약']
                    if lang_code != "ko":
                        with st.spinner(t["translating"]):
                            final_summary = translate_content(final_summary, lang_choice)
                    
                    # 결과 표시
                    st.markdown(f"## 🎯 {matched_product['브랜드']} {matched_product['제품명']}")
                    
                    col1, col2, col3 = st.columns(3)
                    with col1: st.metric(f"⭐ {t['score']}", f"{matched_product['평점']}")
                    with col2: st.metric(f"💬 {t['reviews']}", f"{matched_product['리뷰수']}")
                    with col3: st.metric(f"💰 {t['price']}", f"{matched_product['가격']}")
                    
                    st.markdown("---")
                    st.markdown(f"### 📋 Info")
                    d_col1, d_col2 = st.columns(2)
                    with d_col1:
                        st.markdown(f"**🏷️ {t['type']}:** {matched_product['종류']}")
                        st.markdown(f"**🛒 {t['shop']}:** {matched_product['쇼핑몰']}")
                    with d_col2:
                        st.markdown(f"**🔑 {t['id']}:** {matched_product['제품_ID']}")
                        
                    st.info(f"**{t['summary_title']}:**\n\n{final_summary}")
                    
                    search_query = f"{matched_product['브랜드']} {matched_product['제품명']}"
                    st.link_button(
                        t["link_btn"], 
                        f"https://search.shopping.naver.com/search/all?query={search_query}",
                        use_container_width=True
                    )
                else:
                    st.warning(t["fail_match"])


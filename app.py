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

# CSV 데이터 (코드 내장형)
csv_data = """제품_ID,브랜드,제품명,종류,평점,리뷰수,쇼핑몰,가격,핵심요약
1,정담김,구운 김밥김 100매,김밥용,4.6,3600,쿠팡,"17,900원",터짐 없고 대용량(100매)으로 경제적 + 품질우수
2,청정원,올리브유 재래김,도시락김,4.5,1200,다중몰,"3,500~4,000",이탈리아산 올리브유 + 고소하면서 적절한 간
3,만전김,햇살과 바람이 길러낸 유기김,도시락김,4.7,1800,컬리,"10,900",유기농 인증 + 건강한 재료 + 가족용 추천
4,성경식품,지도표 성경 녹차식탁김,도시락김,4.8,950,다중몰,"4,000~4,500",최고평점(4.8) + 녹차향기 + 뉴질랜드염
5,광천해저김,짜지 않은 김,도시락김,4.6,620,컬리,"3,500~4,500",저염식(건강고민가족용) + 고소함 유지
6,동원,양반 들기름 식탁김,도시락김,4.3,2100,다중몰,"2,000~3,000",국민 조미김 + 들기름 고소함 + 가성비
7,풀무원,재래김 (들기름),도시락김,4.2,1650,다중몰,"2,500~3,500",대기업신뢰도 + 안정적 맛 + 무난한 선택
8,CJ제일제당,비비고 직화구이김,도시락김,4.5,1400,편의점,"2,500~3,500",직화구이로 고소함 극대화 + 편의점 구매용
9,소문난삼부자,한가족김,도시락김,4.3,2800,다중몰,"2,000~2,500",저가격 국민 조미김 + 가성비 최우선
10,해표,더 고소한 김 재래김,도시락김,4.6,1100,다중몰,"3,500~4,500",들기름+참기름 압착유 + 고소함 극대화
13,대천김,곱창 도시락김 5g,도시락김,4.7,2250,컬리,"12,500원",곱창처럼 두텁고 오독오독한 식감 + 은은한 단맛
14,대천김,곱창 캔김 30g (8캔),고급캔김,4.7,350,컬리,"36,000~41,000원",프리미엄 선물용 + 곱창 품질 + 대용량
15,해우촌,파래 곱창 도시락김,도시락김,4.6,1850,이마트,"3,500~4,500",파래 특유의 향기 + 곱창 식감 + 화학조미료 무
17,CJ제일제당,비비고 들기름 직화,도시락김,4.5,1520,편의점/마트,"9,980원",직화구이 + 프리미엄 들기름 + 편의점용
18,동원,양반 참기름김 식탁,도시락김,4.4,1980,편의점/마트,"4,780~5,480원",참기름 고소함 + 시장 1위 신뢰도
21,성경식품,지도표 재래 전장김,대형김,4.8,520,다중몰,"8,500~12,000",프리미엄 전장김 + 최고평점
23,광천김,달인 파래 광천김,도시락김,4.6,1520,다중몰,"3,500~4,500",광천의 대표 파래 + 달인의 기술
32,곰곰,광천 도시락김 256개,대량김,4.5,4200,쿠팡,"54,050~80,000",곰곰 가성비 + 광천 품질 + 최대대량
33,진도,곱창 조미김 도시락,도시락김,4.7,940,온라인,"5,000~6,500",진도 최고 원초 + 곱창식감 + 적조 무
37,대천김,재래 도시락김 5g,도시락김,4.8,2180,쿠팡,"12,500~14,900",곱창 다음 프리미엄 라인 + 높은평점
51,사조씨푸드,김 프리미엄 세트,고급세트,4.7,280,온라인,"45,000~55,000",김 대장주 + 수출 명성 + 프리미엄 구성
60,삼양식품,불닭 시즈닝 김,특수맛,4.4,420,편의점,"4,500~5,500",불닭 인기 + 신제품 인기
"""

@st.cache_data
def load_data():
    return pd.read_csv(io.StringIO(csv_data))

df = load_data()

# ==========================================
# 2. AI 분석 및 매칭 로직
# ==========================================

def analyze_image_with_gemini(image):
    # 모델 설정을 1.5 Flash로 지정
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
st.caption("사진을 찍으면 어떤 김인지 분석해드립니다. (Gemini 1.5 Flash)")

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





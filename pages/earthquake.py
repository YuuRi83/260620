import streamlit as st
import pandas as pd
import requests
import folium
from streamlit_folium import st_folium
from datetime import datetime, timedelta

# --- 페이지 설정 ---
st.set_page_config(page_title="내 위치 기반 지진 탐색기", page_icon="🌍", layout="wide")
st.title("🌍 반경 탐색기: 내 주변은 안전할까?")
st.markdown("선택한 도시를 중심으로 지정한 반경 내에서 발생한 최근 지진 데이터를 탐색합니다.")

# --- 사이드바 설정 (퀘스트 조건 입력) ---
st.sidebar.header("🔍 탐색 조건 설정")

# 관심 도시 목록 (위도, 경도)
cities = {
    "서울 (대한민국)": [37.5665, 126.9780],
    "상하이 (중국)": [31.2304, 121.4737],
    "도쿄 (일본)": [35.6895, 139.6917],
    "타이베이 (대만)": [25.0329, 121.5654],
    "로스앤젤레스 (미국)": [34.0522, -118.2437]
}

selected_city = st.sidebar.selectbox("📍 탐색할 도시를 선택하세요", list(cities.keys()))
lat, lon = cities[selected_city]

radius_km = st.sidebar.slider("📏 탐색 반경 (km)", min_value=100, max_value=1000, value=500, step=100)
min_mag = st.sidebar.slider("⚠️ 최소 지진 규모", min_value=1.0, max_value=9.0, value=3.0, step=0.5)

# 날짜 설정 (최근 1년 기본값)
today = datetime.today()
last_year = today - timedelta(days=365)
start_date = st.sidebar.date_input("🗓️ 시작일", last_year)
end_date = st.sidebar.date_input("🗓️ 종료일", today)

# --- USGS API 데이터 호출 함수 ---
@st.cache_data(show_spinner="지진 데이터를 분석 중입니다...")
def fetch_earthquake_data(lat, lon, radius, min_magnitude, start, end):
    url = "https://earthquake.usgs.gov/fdsnws/event/1/query"
    params = {
        "format": "geojson",
        "latitude": lat,
        "longitude": lon,
        "maxradiuskm": radius,
        "minmagnitude": min_magnitude,
        "starttime": start.strftime("%Y-%m-%d"),
        "endtime": end.strftime("%Y-%m-%d"),
    }
    
    response = requests.get(url, params=params)
    if response.status_code == 200:
        data = response.json()
        features = data.get("features", [])
        
        # JSON 데이터를 Pandas DataFrame으로 변환
        eq_list = []
        for f in features:
            props = f["properties"]
            coords = f["geometry"]["coordinates"]
            eq_list.append({
                "place": props["place"],
                "magnitude": props["mag"],
                "time": datetime.fromtimestamp(props["time"]/1000).strftime("%Y-%m-%d %H:%M"),
                "longitude": coords[0],
                "latitude": coords[1],
                "depth": coords[2]
            })
        return pd.DataFrame(eq_list)
    else:
        st.error("API 호출에 실패했습니다.")
        return pd.DataFrame()

# --- 데이터 가져오기 ---
df = fetch_earthquake_data(lat, lon, radius_km, min_mag, start_date, end_date)

# --- 대시보드 요약 통계 ---
st.subheader(f"📊 {selected_city} 반경 {radius_km}km 지진 분석 결과")

col1, col2, col3 = st.columns(3)
if not df.empty:
    col1.metric("총 발생 건수", f"{len(df)} 건")
    col2.metric("최대 지진 규모", f"{df['magnitude'].max():.1f}")
    col3.metric("평균 지진 깊이", f"{df['depth'].mean():.1f} km")
else:
    col1.metric("총 발생 건수", "0 건")
    col2.metric("최대 지진 규모", "-")
    col3.metric("평균 지진 깊이", "-")

st.markdown("---")

# --- 지도 시각화 (Folium) ---
# 중심 좌표로 지도 생성
m = folium.Map(location=[lat, lon], zoom_start=5, tiles="CartoDB positron")

# 탐색 반경 원 그리기
folium.Circle(
    location=[lat, lon],
    radius=radius_km * 1000, # meters로 변환
    color="blue",
    fill=True,
    fill_color="blue",
    fill_opacity=0.1,
    tooltip=f"탐색 반경 {radius_km}km"
).add_to(m)

# 지진 데이터 마커 추가
if not df.empty:
    for _, row in df.iterrows():
        # 규모에 따라 마커 색상 변경
        mag = row['magnitude']
        if mag >= 6.0:
            color = "red"
        elif mag >= 4.5:
            color = "orange"
        else:
            color = "green"
            
        popup_info = f"<b>장소:</b> {row['place']}<br><b>규모:</b> {mag}<br><b>깊이:</b> {row['depth']}km<br><b>시간:</b> {row['time']}"
        
        folium.CircleMarker(
            location=[row['latitude'], row['longitude']],
            radius=mag * 2, # 규모에 비례하는 크기
            color=color,
            fill=True,
            fill_color=color,
            fill_opacity=0.6,
            popup=folium.Popup(popup_info, max_width=300)
        ).add_to(m)

# 스트림릿에 지도 출력
st_folium(m, width=1000, height=600)

# --- 원본 데이터 표 출력 ---
with st.expander("📝 상세 데이터 기록 보기"):
    if not df.empty:
        st.dataframe(df, use_container_width=True)
    else:
        st.info("해당 조건에 맞는 지진 데이터가 없습니다.")

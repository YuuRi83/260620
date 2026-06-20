import streamlit as st
import pandas as pd
import requests
import folium
from streamlit_folium import st_folium
from datetime import datetime, timedelta

# --- 페이지 설정 ---
st.set_page_config(page_title="내 위치 기반 지진 탐색기", page_icon="🌍", layout="wide")
st.title("🌍 지진 반경 탐색기 & 대피소 안내")
st.markdown("선택한 도시 주변의 지진 발생 기록을 확인하고, 유사시 대피할 수 있는 안전지대(대피소)를 탐색하세요.")

# --- 지진 규모별 상황 및 대피 요령 함수 ---
def get_magnitude_info(mag):
    if mag < 3.0:
        return "진동을 거의 느끼지 못합니다.", "특별한 대피가 필요하지 않으며 일상생활을 유지합니다."
    elif mag < 4.0:
        return "실내의 일부 사람만 진동을 느끼고 전등이 흔들립니다.", "떨어질 물건이 없는지 주변을 살피고 주의를 기울입니다."
    elif mag < 5.0:
        return "대부분의 사람이 진동을 느끼고 물건이 떨어질 수 있습니다.", "즉시 튼튼한 탁자 아래로 들어가 몸을 보호하고 진동이 멈출 때까지 기다립니다."
    elif mag < 6.0:
        return "무거운 가구가 움직이고, 부실한 건물이 손상될 수 있습니다.", "탁자 밑으로 피한 후, 흔들림이 멈추면 가스 밸브와 전기를 차단하고 계단을 통해 밖으로 나갑니다."
    elif mag < 7.0:
        return "일부 건물이 붕괴될 수 있고, 땅에 균열이 생깁니다.", "머리를 보호하며 신속하게 학교 운동장이나 넓은 공원 등 건물과 떨어진 공터로 대피합니다."
    else:
        return "광범위한 파괴가 발생하고 대규모 건물이 붕괴됩니다.", "최대한 빨리 넓은 야외로 대피하고, 해안가인 경우 즉시 높은 곳으로 이동해 쓰나미에 대비합니다."

# --- 오픈스트리트맵(OSM) 대피소(학교/공원) 데이터 호출 함수 ---
@st.cache_data(show_spinner="주변 대피소 정보를 불러오는 중...")
def fetch_shelters(lat, lon, radius_m=5000):
    # 도시 중심 반경 5km 이내의 학교(school)와 공원(park)을 최대 30개 검색
    overpass_url = "http://overpass-api.de/api/interpreter"
    overpass_query = f"""
    [out:json];
    (
      node["amenity"="school"](around:{radius_m},{lat},{lon});
      node["leisure"="park"](around:{radius_m},{lat},{lon});
    );
    out center limit 30;
    """
    try:
        response = requests.get(overpass_url, params={'data': overpass_query})
        shelters = []
        if response.status_code == 200:
            data = response.json()
            for el in data.get('elements', []):
                # 이름이 없는 경우 기본값 지정
                name = el.get('tags', {}).get('name', '지정 대피 구역 (학교/공원)')
                shelters.append({
                    "name": name,
                    "lat": el.get('lat'),
                    "lon": el.get('lon')
                })
        return shelters
    except:
        return []

# --- 사이드바 설정 ---
st.sidebar.header("🔍 탐색 조건 설정")

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

today = datetime.today()
last_year = today - timedelta(days=365)
start_date = st.sidebar.date_input("🗓️ 시작일", last_year)
end_date = st.sidebar.date_input("🗓️ 종료일", today)

show_shelter = st.sidebar.checkbox("🏥 도시 중심 주변 대피소 보기 (반경 5km)", value=True)

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
    return pd.DataFrame()

# 데이터 불러오기
df = fetch_earthquake_data(lat, lon, radius_km, min_mag, start_date, end_date)

# --- 대시보드 요약 통계 ---
st.subheader(f"📊 {selected_city} 반경 {radius_km}km 분석 및 대처 방안")

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
m = folium.Map(location=[lat, lon], zoom_start=6, tiles="CartoDB positron")

# 탐색 반경 원 그리기
folium.Circle(
    location=[lat, lon],
    radius=radius_km * 1000,
    color="blue",
    fill=True,
    fill_color="blue",
    fill_opacity=0.05,
).add_to(m)

# 1. 지진 데이터 마커 추가
if not df.empty:
    for _, row in df.iterrows():
        mag = row['magnitude']
        situation, action = get_magnitude_info(mag) # 규모별 정보 가져오기
        
        if mag >= 6.0:
            color = "red"
        elif mag >= 4.5:
            color = "orange"
        else:
            color = "green"
            
        # HTML을 사용하여 팝업(클릭 시 나오는 창) 내용 풍성하게 구성
        popup_html = f"""
        <div style='width: 300px'>
            <h4 style='margin-bottom:5px; color:{color};'>규모 {mag} 지진 발생</h4>
            <b>📍 장소:</b> {row['place']}<br>
            <b>🕒 시간:</b> {row['time']}<br>
            <b>📏 깊이:</b> {row['depth']}km<br>
            <hr style='margin: 10px 0;'>
            <b>⚠️ 예상 상황:</b> {situation}<br>
            <b>🏃‍♂️ 대피 요령:</b> <span style='color: blue;'>{action}</span>
        </div>
        """
        
        folium.CircleMarker(
            location=[row['latitude'], row['longitude']],
            radius=mag * 2.5,
            color=color,
            fill=True,
            fill_color=color,
            fill_opacity=0.6,
            popup=folium.Popup(popup_html, max_width=350)
        ).add_to(m)

# 2. 대피소 마커 추가
if show_shelter:
    shelters = fetch_shelters(lat, lon)
    for s in shelters:
        # tooltip 옵션이 마우스를 '가져다 댈 때' 텍스트를 보여줍니다.
        folium.Marker(
            location=[s['lat'], s['lon']],
            tooltip=f"🟢 대피소: {s['name']}",
            icon=folium.Icon(color="green", icon="info-sign")
        ).add_to(m)

st_folium(m, width=1000, height=600)

st.info("💡 **이용 방법:** 빨간/주황/초록색 **원을 클릭**하면 지진 발생 상황과 행동 요령을 볼 수 있습니다. 초록색 **마커에 마우스를 올리면** 주변 대피소 이름을 확인할 수 있습니다.")

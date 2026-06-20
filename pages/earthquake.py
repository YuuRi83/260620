import streamlit as st
import pandas as pd
import requests
import folium
from streamlit_folium import st_folium
from datetime import datetime, timedelta

# --- 페이지 설정 ---
st.set_page_config(page_title="내 위치 기반 지진 탐색기", page_icon="🌍", layout="wide")
st.title("🌍 지진 반경 탐색기 & 실시간 대피 정보")
st.markdown("지도의 지진 아이콘을 클릭하면 지도 아래에 **상세 상황 및 대피소 정보**가 나타납니다.")

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
    overpass_url = "http://overpass-api.de/api/interpreter"
    overpass_query = f"""
    [out:json];
    (
      node["amenity"="school"](around:{radius_m},{lat},{lon});
      node["leisure"="park"](around:{radius_m},{lat},{lon});
    );
    out center limit 15;
    """
    try:
        response = requests.get(overpass_url, params={'data': overpass_query})
        shelters = []
        if response.status_code == 200:
            data = response.json()
            for el in data.get('elements', []):
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
                "id": f["id"], # 클릭 감지를 위한 고유 ID 추가
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

# --- 상단 대시보드 요약 통계 ---
st.subheader(f"📊 {selected_city} 반경 {radius_km}km 요약 통계")
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
    fill_opacity=0.03,
).add_to(m)

# 지진 데이터 마커 추가
if not df.empty:
    for _, row in df.iterrows():
        mag = row['magnitude']
        if mag >= 6.0:
            color = "red"
        elif mag >= 4.5:
            color = "orange"
        else:
            color = "green"
            
        # 팝업 대신 지도 하단 출력을 위해 팝업 제거 및 layer_id 설정
        folium.CircleMarker(
            location=[row['latitude'], row['longitude']],
            radius=mag * 2.5,
            color=color,
            fill=True,
            fill_color=color,
            fill_opacity=0.6,
            # 마우스를 올렸을 때 간단한 힌트만 제공
            tooltip=f"규모 {mag} - 클릭하여 상세 정보 보기"
        ).add_to(m)

# 스트림릿에 지도 출력 및 사용자 클릭 이벤트 캡처
map_data = st_folium(m, width=1000, height=500, key="earthquake_map")

st.markdown("---")

# --- 지도 하단 상세 정보 대시보드 ---
st.subheader("📋 선택한 지역의 상세 정보 및 대피 안내")

# 사용자가 지도의 마커를 클릭했는지 확인하는 로직
clicked_marker = None
if map_data and map_data.get("last_object_clicked"):
    click_lat = map_data["last_object_clicked"]["lat"]
    click_lon = map_data["last_object_clicked"]["lng"]
    
    # 클릭한 좌표와 일치하는 지진 데이터 필터링 (미세한 소수점 오차 방지를 위해 round 적용)
    if not df.empty:
        matched = df[
            (df['latitude'].round(3) == round(click_lat, 3)) & 
            (df['longitude'].round(3) == round(click_lon, 3))
        ]
        if not matched.empty:
            clicked_marker = matched.iloc[0]

# 마커가 클릭되었다면 상세 대시보드 출력
if clicked_marker is not None:
    mag = clicked_marker['magnitude']
    situation, action = get_magnitude_info(mag)
    
    # 레이아웃 분할 (상황/대피요령 vs 주변 대피소 리스트)
    detail_col1, detail_col2 = st.columns([2, 1])
    
    with detail_col1:
        st.markdown(f"### 🚨 규모 {mag} 지진 상세 정보")
        st.write(f"**📍 발생 위치:** {clicked_marker['place']}")
        st.write(f"**🕒 발생 시각:** {clicked_marker['time']}")
        st.write(f"**📏 진원 깊이:** {clicked_marker['depth']} km")
        
        # 시각적 구분을 위한 안내 박스
        st.error(f"**⚠️ 예상되는 상황:**\n\n{situation}")
        st.success(f"**🏃‍♂️ 권장 대피 요령:**\n\n{action}")
        
    with detail_col2:
        st.markdown("### 🏥 인근 대피 구역 (학교/공원)")
        st.caption("발생지 기준 반경 5km 이내의 안전 지역 목록입니다.")
        
        # 지진 발생지 주변 대피소 검색
        local_shelters = fetch_shelters(clicked_marker['latitude'], clicked_marker['longitude'])
        
        if local_shelters:
            for idx, shelter in enumerate(local_shelters, 1):
                st.markdown(f"**{idx}. {shelter['name']}**")
        else:
            st.info("반경 5km 내에 등록된 대피 구역 정보가 없습니다. 넓은 공터로 대피하세요.")
            
else:
    # 아무것도 클릭하지 않았을 때의 초기 상태 안내
    st.info("🗺️ 위의 지도에서 지진 마커(초록/주황/빨간 원)를 클릭하시면 해당 지역의 실시간 재난 상황과 대피소 목록이 이곳에 표시됩니다.")

import streamlit as st
import pydeck as pdk
import pandas as pd
import numpy as np
import math

# --- App Config ---
st.set_page_config(layout="wide", page_title="Gemini Strategic Arsenal", page_icon="☢️")

# --- CSS Styling ---
st.markdown("""
<style>
.metric-box {
    background-color: #1e1e1e;
    border-radius: 10px;
    padding: 15px;
    border: 1px solid #444;
    text-align: center;
    margin-bottom: 10px;
}
.metric-title { color: #aaa; font-size: 14px; font-weight: bold; }
.metric-value-red { color: #ff4b4b; font-size: 32px; font-weight: bold; }
.metric-value-orange { color: #ffa500; font-size: 32px; font-weight: bold; }
</style>
""", unsafe_allow_html=True)

st.title("☢️ Gemini Strategic Arsenal Pro")
st.markdown("단순 반경 계산을 넘어서는 궁극의 전술 시뮬레이터입니다. **실제 전략 무기 데이터베이스, 풍향/풍속 기반 방사능 낙진(Fallout) 모델링, 인구밀도 기반 사상자 추산 엔진**을 탑재하여 타 툴(Claude 등) 대비 압도적인 디테일을 제공합니다.")

# =====================================
# 1. 사이드바 UI
# =====================================
st.sidebar.header("🎯 1. 타격 목표 설정")
targets = {
    "서울 청계광장": (37.5693, 126.9774),
    "평양 김일성광장": (39.0194, 125.7533),
    "도쿄 신주쿠": (35.6909, 139.7002),
    "베이징 톈안먼": (39.9042, 116.3975),
    "워싱턴 D.C.": (38.8951, -77.0364),
    "모스크바 크렘린": (55.7520, 37.6175),
    "직접 입력 (사용자 좌표)": (0.0, 0.0)
}
target_name = st.sidebar.selectbox("목표 랜드마크", list(targets.keys()))
if target_name == "직접 입력 (사용자 좌표)":
    t_lat = st.sidebar.number_input("위도 (Lat)", value=37.5693, format="%.4f")
    t_lon = st.sidebar.number_input("경도 (Lon)", value=126.9774, format="%.4f")
else:
    t_lat, t_lon = targets[target_name]

st.sidebar.header("💣 2. 무기 체계 (Arsenal DB)")
arsenal = {
    "W76 (미국 트라이던트 II SLBM)": 100.0,
    "B61-12 (미국 최신 전술핵)": 50.0,
    "W87 (미국 미니트맨 III ICBM)": 300.0,
    "화성-17형 (북한 ICBM 추정치)": 1500.0,
    "DF-41 (중국 ICBM)": 3000.0,
    "RS-28 사르맛 (러시아 차세대 ICBM)": 5000.0,
    "Tsar Bomba (소련 역대 최대 실험핵)": 50000.0,
    "수동 위력 설정 (Custom)": 15.0
}
weapon = st.sidebar.selectbox("탄두 선택", list(arsenal.keys()))
if weapon == "수동 위력 설정 (Custom)":
    yield_kt = st.sidebar.slider("폭발 위력 (Kilotons)", 1.0, 100000.0, 15.0, 1.0, format="%f")
else:
    yield_kt = arsenal[weapon]
    st.sidebar.info(f"폭발 위력: **{yield_kt:,.1f} kt**")

burst = st.sidebar.radio("폭발 고도", ["지표면 폭발 (Ground Burst)", "공중 폭발 (Air Burst)"])
opt_factor = 1.3 if burst == "공중 폭발 (Air Burst)" else 1.0

st.sidebar.header("🌪️ 3. 기상 조건 (낙진 연산용)")
st.sidebar.caption("※ 지표면 폭발 시 방사성 낙진이 바람을 타고 퍼집니다.")
wind_deg = st.sidebar.slider("풍향 (도, 0=북풍)", 0, 360, 90, help="바람이 불어가는 방향입니다. (예: 90 = 서에서 동으로 붊)")
wind_speed = st.sidebar.slider("풍속 (km/h)", 0, 100, 25)

# =====================================
# 2. 엔진 연산 (물리 / 사상자 / 낙진)
# =====================================
# 반경 계산 (미터)
r_fireball = 150 * (yield_kt ** 0.32)
r_20psi = 280 * (yield_kt ** 0.33) * opt_factor
r_5psi = 700 * (yield_kt ** 0.33) * opt_factor
r_thermal = 1200 * (yield_kt ** 0.40)

# 사상자 추산 (도심지 인구밀도 기반 Heuristic)
density = 16000 # 도심 평균 인구밀도 (명/km^2)
area_20psi = math.pi * ((r_20psi/1000)**2)
area_5psi = math.pi * ((r_5psi/1000)**2) - area_20psi
area_thermal = math.pi * ((r_thermal/1000)**2) - (area_20psi + area_5psi)
if area_thermal < 0: area_thermal = 0

dead = int((area_20psi * density * 0.95) + (area_5psi * density * 0.40) + (area_thermal * density * 0.05))
injured = int((area_20psi * density * 0.05) + (area_5psi * density * 0.45) + (area_thermal * density * 0.50))

# 방사능 낙진 (Fallout) 폴리곤 계산 엔진
def get_fallout_polygon(lat, lon, y_kt, w_deg, w_speed):
    if w_speed == 0 or burst == "공중 폭발 (Air Burst)":
        return []
    
    # 낙진 플룸 길이 및 너비 (경험적 모델 변형)
    length_m = (y_kt ** 0.45) * (w_speed ** 0.5) * 800
    width_m = length_m * 0.25
    
    R = 6378137.0
    rad_dir = math.radians(w_deg)
    
    points = []
    # Teardrop(눈물방울) 형태의 폴리곤 생성
    for angle in range(0, 360, 5):
        a = math.radians(angle)
        r = length_m * (math.cos(a/2)**4)
        if r < 100: continue
        
        x = r * math.sin(a)
        y = r * math.cos(a)
        
        # 풍향에 따른 회전 행렬 적용
        rx = x * math.cos(rad_dir) - y * math.sin(rad_dir)
        ry = x * math.sin(rad_dir) + y * math.cos(rad_dir)
        
        d_lat = (ry / R) * (180 / math.pi)
        d_lon = (rx / (R * math.cos(math.pi * lat / 180))) * (180 / math.pi)
        points.append([lon + d_lon, lat + d_lat])
    
    if len(points) > 0:
        points.append(points[0])
    return [points]

fallout_poly = get_fallout_polygon(t_lat, t_lon, yield_kt, wind_deg, wind_speed)


# =====================================
# 3. 3D 렌더링 레이어 구축
# =====================================
df_blast = pd.DataFrame([
    {"name": "열복사 (3도 화상)", "radius": r_thermal, "color": [255, 140, 0, 70], "h": 50},
    {"name": "중압 폭풍 (5 psi)", "radius": r_5psi, "color": [150, 150, 150, 100], "h": 200},
    {"name": "고압 폭풍 (20 psi)", "radius": r_20psi, "color": [80, 80, 80, 150], "h": 600},
    {"name": "화구 (기화 구역)", "radius": r_fireball, "color": [255, 0, 0, 220], "h": 1200}
])
df_blast['lat'] = t_lat
df_blast['lon'] = t_lon

layers = [
    pdk.Layer(
        "ColumnLayer",
        data=df_blast,
        get_position="[lon, lat]",
        get_elevation="h",
        get_fill_color="color",
        get_radius="radius",
        elevation_scale=1,
        radius="radius",
        pickable=True,
        extruded=True
    )
]

if fallout_poly and len(fallout_poly[0]) > 0:
    df_fallout = pd.DataFrame([{"polygon": fallout_poly[0], "name": "방사성 낙진 구역 (Fallout Plume)"}])
    layers.append(
        pdk.Layer(
            "PolygonLayer",
            data=df_fallout,
            get_polygon="polygon",
            get_fill_color=[160, 32, 240, 90],
            get_line_color=[160, 32, 240, 200],
            lineWidthMinPixels=2,
            pickable=True,
            extruded=False
        )
    )

zoom_lvl = 12
if yield_kt > 5000: zoom_lvl = 7
elif yield_kt > 500: zoom_lvl = 9

view_state = pdk.ViewState(
    latitude=t_lat,
    longitude=t_lon,
    zoom=zoom_lvl,
    pitch=50,
    bearing=wind_deg - 180 # 뷰어 앵글을 풍향에 맞게 조정
)

# =====================================
# 4. 레이아웃 분할 및 화면 출력
# =====================================
col1, col2 = st.columns([7, 3])

with col1:
    st.pydeck_chart(pdk.Deck(
        map_style="mapbox://styles/mapbox/dark-v10",
        initial_view_state=view_state,
        layers=layers,
        tooltip={"html": "<b>{name}</b>"}
    ), use_container_width=True)

with col2:
    st.markdown("### 📊 실시간 피해 연산 결과")
    st.markdown(f"<div class='metric-box'><div class='metric-title'>추정 사망자 (도심 기준)</div><div class='metric-value-red'>{dead:,} 명</div></div>", unsafe_allow_html=True)
    st.markdown(f"<div class='metric-box'><div class='metric-title'>추정 부상자</div><div class='metric-value-orange'>{injured:,} 명</div></div>", unsafe_allow_html=True)
    
    st.markdown("### 📐 구역별 피해 반경")
    df_table = pd.DataFrame({
        "구역 (Zone)": ["🔥 화구 (Fireball)", "💥 완파 (20psi)", "🏚️ 반파 (5psi)", "☀️ 3도 화상"],
        "반경 (km)": [f"{r_fireball/1000:.2f}", f"{r_20psi/1000:.2f}", f"{r_5psi/1000:.2f}", f"{r_thermal/1000:.2f}"]
    })
    st.dataframe(df_table, hide_index=True, use_container_width=True)
    
    st.markdown("---")
    if burst == "지표면 폭발 (Ground Burst)":
        st.warning("⚠️ **낙진 발생 경고:** 지표면 폭발로 대량의 흙과 파편이 방사능화되어 대기 중으로 솟구쳤습니다. **보라색 영역**은 현재 기상(풍속/풍향) 데이터 기반의 치명적 방사능 낙진 예상 확산 경로입니다.")
    else:
        st.success("✅ **공중 폭발 감지:** 지면 파편화가 적어 광범위한 낙진 플룸은 형성되지 않으나, 마하 스템(Mach Stem) 효과로 충격파 피해 반경이 지표면 폭발 대비 확대되었습니다.")

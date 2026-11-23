import streamlit as st
import pydeck as pdk
import pandas as pd
import math

# --- 페이지 기본 설정 ---
st.set_page_config(layout="wide", page_title="Gemini Strategic Arsenal Pro", page_icon="☢️")

# --- 커스텀 다크 전술 UI 스타일 ---
st.markdown("""
<style>
.metric-box {
    background-color: #161b22;
    border-radius: 10px;
    padding: 14px;
    border: 1px solid #30363d;
    text-align: center;
    margin-bottom: 10px;
}
.metric-title { color: #8b949e; font-size: 13px; font-weight: 600; margin-bottom: 4px; }
.metric-value-red { color: #ff4b4b; font-size: 28px; font-weight: 800; }
.metric-value-orange { color: #ffa657; font-size: 28px; font-weight: 800; }
</style>
""", unsafe_allow_html=True)

st.title("☢️ Gemini Strategic Arsenal Pro")
st.markdown("실제 위성/전술 지도 위에 **탄도미사일 3D 비행 궤적, 다층 입체 폭발 돔, 풍향 기반 방사능 낙진(Fallout), 실시간 사상자 추산**을 통합한 전술 시뮬레이터입니다.")

# =====================================
# 1. 사이드바 UI 설정
# =====================================
st.sidebar.header("🗺️ 0. 지도 배경 스타일")
map_theme = st.sidebar.radio(
    "지도 모드 선택 (무료 고해상도)",
    ["다크 전술 지도 (야간 작전)", "실제 위성 사진 지도 (주간 정밀)"],
    index=0
)

st.sidebar.header("🎯 1. 타격 목표 및 발사 원점")
targets = {
    "서울 청계광장": {"target": (37.5693, 126.9774), "launch": (39.1500, 127.4500), "density": 16000},
    "평양 김일성광장": {"target": (39.0194, 125.7533), "launch": (37.2000, 124.8000), "density": 9500},
    "도쿄 신주쿠": {"target": (35.6909, 139.7002), "launch": (37.5000, 136.5000), "density": 15000},
    "베이징 톈안먼": {"target": (39.9042, 116.3975), "launch": (38.5000, 119.5000), "density": 11500},
    "워싱턴 D.C.": {"target": (38.8951, -77.0364), "launch": (37.5000, -74.0000), "density": 4500},
    "직접 입력 (사용자 좌표)": {"target": (37.5693, 126.9774), "launch": (38.5000, 126.5000), "density": 12000}
}

target_name = st.sidebar.selectbox("목표 랜드마크", list(targets.keys()))
if target_name == "직접 입력 (사용자 좌표)":
    t_lat = st.sidebar.number_input("목표 위도 (Lat)", value=37.5693, format="%.4f")
    t_lon = st.sidebar.number_input("목표 경도 (Lon)", value=126.9774, format="%.4f")
    l_lat = t_lat + 0.8
    l_lon = t_lon - 0.6
    density = st.sidebar.number_input("인구밀도 (명/km²)", value=12000, step=1000)
else:
    t_lat, t_lon = targets[target_name]["target"]
    l_lat, l_lon = targets[target_name]["launch"]
    density = targets[target_name]["density"]

show_trajectory = st.sidebar.checkbox("🚀 미사일 탄도 궤적(3D Arc) 표시", value=True)

st.sidebar.header("💣 2. 무기 체계 (Arsenal DB)")
arsenal = {
    "B61-12 (미국 최신 전술핵 - 50kt)": 50.0,
    "Little Boy (히로시마 원폭 - 15kt)": 15.0,
    "W76 (트라이던트 II SLBM - 100kt)": 100.0,
    "W87 (미니트맨 III ICBM - 300kt)": 300.0,
    "화성-17형 (북한 ICBM 추정 - 1,500kt)": 1500.0,
    "RS-28 사르맛 (러시아 ICBM - 5,000kt)": 5000.0,
    "Tsar Bomba (역대 최대 실험핵 - 50,000kt)": 50000.0,
    "수동 위력 설정 (Custom)": 15.0
}
weapon = st.sidebar.selectbox("탄두 선택", list(arsenal.keys()))
if weapon == "수동 위력 설정 (Custom)":
    yield_kt = st.sidebar.slider("폭발 위력 (Kilotons)", 1.0, 50000.0, 50.0, 1.0)
else:
    yield_kt = arsenal[weapon]
    st.sidebar.info(f"선택 탄두 위력: **{yield_kt:,.1f} kt**")

burst = st.sidebar.radio("폭발 고도", ["지표면 폭발 (Ground Burst)", "공중 폭발 (Air Burst)"])
opt_factor = 1.3 if burst == "공중 폭발 (Air Burst)" else 1.0

st.sidebar.header("🌪️ 3. 기상 조건 (낙진 연산용)")
wind_deg = st.sidebar.slider("풍향 (도, 0=북→남, 90=서→동)", 0, 360, 90)
wind_speed = st.sidebar.slider("풍속 (km/h)", 0, 100, 25)

# =====================================
# 2. 물리 반경 & 기하학 좌표 생성 함수
# =====================================
r_fireball = 150 * (yield_kt ** 0.32)
r_20psi = 280 * (yield_kt ** 0.33) * opt_factor
r_5psi = 700 * (yield_kt ** 0.33) * opt_factor
r_thermal = 1200 * (yield_kt ** 0.40)

def create_circle_polygon(lat, lon, radius_m, num_points=72):
    R = 6378137.0
    coords = []
    for i in range(num_points):
        angle = 2 * math.pi * i / num_points
        dx = radius_m * math.cos(angle)
        dy = radius_m * math.sin(angle)
        d_lat = (dy / R) * (180.0 / math.pi)
        d_lon = (dx / (R * math.cos(math.pi * lat / 180.0))) * (180.0 / math.pi)
        coords.append([lon + d_lon, lat + d_lat])
    coords.append(coords[0])
    return coords

def get_fallout_polygon(lat, lon, y_kt, w_deg, w_speed):
    if w_speed == 0 or burst == "공중 폭발 (Air Burst)":
        return []
    length_m = (y_kt ** 0.45) * (w_speed ** 0.5) * 950
    R = 6378137.0
    rad_dir = math.radians(w_deg)
    points = []
    for angle in range(0, 360, 5):
        a = math.radians(angle)
        r = length_m * (math.cos(a / 2) ** 4)
        if r < 100:
            continue
        x = r * math.sin(a)
        y = r * math.cos(a)
        rx = x * math.cos(rad_dir) - y * math.sin(rad_dir)
        ry = x * math.sin(rad_dir) + y * math.cos(rad_dir)
        d_lat = (ry / R) * (180.0 / math.pi)
        d_lon = (rx / (R * math.cos(math.pi * lat / 180.0))) * (180.0 / math.pi)
        points.append([lon + d_lon, lat + d_lat])
    if points:
        points.append(points[0])
    return points

# 사상자 추산
area_20psi = math.pi * ((r_20psi / 1000) ** 2)
area_5psi = max(0.0, math.pi * ((r_5psi / 1000) ** 2) - area_20psi)
area_thermal = max(0.0, math.pi * ((r_thermal / 1000) ** 2) - (area_20psi + area_5psi))

dead = int((area_20psi * density * 0.95) + (area_5psi * density * 0.40) + (area_thermal * density * 0.05))
injured = int((area_20psi * density * 0.05) + (area_5psi * density * 0.45) + (area_thermal * density * 0.50))

# =====================================
# 3. Pydeck 무료 고해상도 타일 & 3D 레이어 구성
# =====================================
tile_url = (
    "https://basemaps.cartocdn.com/dark_all/{z}/{x}/{y}@2x.png"
    if "다크" in map_theme
    else "https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}"
)

base_map_layer = pdk.Layer(
    "TileLayer",
    data=tile_url,
    min_zoom=0,
    max_zoom=19,
    tile_size=256,
)

# 4단계 3D 폭발 반경 폴리곤 (실제 미터 반경 + 고도 입체화)
blast_zones = [
    {
        "name": "☀️ 열복사 구역 (3도 화상)",
        "radius_km": f"{r_thermal/1000:.2f} km",
        "polygon": create_circle_polygon(t_lat, t_lon, r_thermal),
        "h": 60,
        "fill_color": [255, 140, 0, 75],
        "line_color": [255, 165, 0, 220],
    },
    {
        "name": "🏚️ 중압 폭풍 (5 psi - 일반건물 붕괴)",
        "radius_km": f"{r_5psi/1000:.2f} km",
        "polygon": create_circle_polygon(t_lat, t_lon, r_5psi),
        "h": 220,
        "fill_color": [255, 215, 0, 95],
        "line_color": [255, 230, 80, 230],
    },
    {
        "name": "💥 고압 폭풍 (20 psi - 콘크리트 완파)",
        "radius_km": f"{r_20psi/1000:.2f} km",
        "polygon": create_circle_polygon(t_lat, t_lon, r_20psi),
        "h": 550,
        "fill_color": [255, 69, 0, 145],
        "line_color": [255, 90, 30, 255],
    },
    {
        "name": "🔥 화구 중심부 (Fireball - 즉각 기화)",
        "radius_km": f"{r_fireball/1000:.2f} km",
        "polygon": create_circle_polygon(t_lat, t_lon, r_fireball),
        "h": 1100,
        "fill_color": [255, 20, 20, 220],
        "line_color": [255, 255, 255, 255],
    },
]
df_blast = pd.DataFrame(blast_zones)

blast_layer = pdk.Layer(
    "PolygonLayer",
    data=df_blast,
    get_polygon="polygon",
    get_elevation="h",
    get_fill_color="fill_color",
    get_line_color="line_color",
    line_width_min_pixels=2,
    extruded=True,
    wireframe=True,
    pickable=True,
)

# 버섯구름 상승 기둥(Stem) 연출
stem_layer = pdk.Layer(
    "ColumnLayer",
    data=pd.DataFrame([{"lat": t_lat, "lon": t_lon, "h": r_fireball * 4.2, "name": "☢️ 버섯구름 상승 기둥", "radius_km": f"고도 약 {r_fireball*4.2/1000:.1f} km"}]),
    get_position="[lon, lat]",
    get_elevation="h",
    radius=float(max(80.0, r_fireball * 0.42)),
    get_fill_color=[255, 110, 40, 190],
    extruded=True,
    pickable=True,
)

layers = [base_map_layer]

# 방사능 낙진 레이어 (지표면 폭발 시 바닥에 반투명 표시)
fallout_coords = get_fallout_polygon(t_lat, t_lon, yield_kt, wind_deg, wind_speed)
if fallout_coords:
    df_fallout = pd.DataFrame([{
        "polygon": fallout_coords,
        "name": "☢️ 방사능 낙진 확산 구역 (Fallout Plume)",
        "radius_km": f"풍속 {wind_speed}km/h 확산"
    }])
    layers.append(
        pdk.Layer(
            "PolygonLayer",
            data=df_fallout,
            get_polygon="polygon",
            get_fill_color=[170, 60, 255, 55],
            get_line_color=[190, 90, 255, 210],
            line_width_min_pixels=2,
            extruded=False,
            pickable=True,
        )
    )

layers.extend([blast_layer, stem_layer])

# 탄도미사일 3D 궤적 레이어
if show_trajectory:
    df_arc = pd.DataFrame([{
        "src_lon": l_lon,
        "src_lat": l_lat,
        "dst_lon": t_lon,
        "dst_lat": t_lat,
        "name": f"🚀 탄도미사일 궤적 ({weapon})",
        "radius_km": "탄착 지점 직격"
    }])
    layers.append(
        pdk.Layer(
            "ArcLayer",
            data=df_arc,
            get_source_position="[src_lon, src_lat]",
            get_target_position="[dst_lon, dst_lat]",
            get_source_color=[0, 220, 255, 160],
            get_target_color=[255, 40, 40, 255],
            get_width=4,
            get_height=0.45,
            pickable=True,
        )
    )

zoom_lvl = 12.2
if yield_kt >= 10000:
    zoom_lvl = 7.8
elif yield_kt >= 1000:
    zoom_lvl = 9.5
elif yield_kt >= 200:
    zoom_lvl = 11.0

view_state = pdk.ViewState(
    latitude=t_lat,
    longitude=t_lon,
    zoom=zoom_lvl,
    pitch=52,
    bearing=15
)

# =====================================
# 4. 메인 화면 분할 렌더링
# =====================================
col1, col2 = st.columns([7, 3])

with col1:
    st.pydeck_chart(
        pdk.Deck(
            map_style=None,
            initial_view_state=view_state,
            layers=layers,
            tooltip={"html": "<b>{name}</b><br/>규모/범위: {radius_km}"}
        ),
        use_container_width=True
    )
    st.caption("💡 마우스 좌클릭 드래그로 지도 이동, **우클릭(또는 Ctrl+클릭) 드래그로 3D 회전 및 기울기 조절**, 휠 스크롤로 확대/축소가 가능합니다.")

with col2:
    st.markdown("### 📊 실시간 피해 연산 결과")
    st.markdown(f"<div class='metric-box'><div class='metric-title'>추정 사망자 (인구밀도 {density:,}명/km²)</div><div class='metric-value-red'>{dead:,} 명</div></div>", unsafe_allow_html=True)
    st.markdown(f"<div class='metric-box'><div class='metric-title'>추정 부상자</div><div class='metric-value-orange'>{injured:,} 명</div></div>", unsafe_allow_html=True)

    st.markdown("### 📐 구역별 피해 반경")
    df_table = pd.DataFrame({
        "구역 (Zone)": ["🔥 화구 (Fireball)", "💥 완파 (20 psi)", "🏚️ 반파 (5 psi)", "☀️ 3도 화상"],
        "반경 (km)": [f"{r_fireball/1000:.2f}", f"{r_20psi/1000:.2f}", f"{r_5psi/1000:.2f}", f"{r_thermal/1000:.2f}"]
    })
    st.dataframe(df_table, hide_index=True, use_container_width=True)

    st.markdown("---")
    if burst == "지표면 폭발 (Ground Burst)":
        st.warning("⚠️ **낙진 경보:** 지표면 폭발로 방사성 낙진 플룸(보라색 구역)이 풍향에 따라 확산 중입니다.")
    else:
        st.success("✅ **공중 폭발:** 마하 스템(Mach Stem) 효과로 폭풍 파괴 반경이 30% 확대되었으며, 지표 낙진은 최소화되었습니다.")

import streamlit as st
import pydeck as pdk
import pandas as pd

st.set_page_config(layout="wide", page_title="청계천 3D 전술 뷰어")

st.title("핵무기 지표면 폭발 3D 시뮬레이터 (청계천 일대)")
st.markdown("왼쪽 사이드바에서 폭발 위력을 조절하면 3D 지도에 피해 반경이 표시됩니다. 지도를 드래그하거나 우클릭(또는 Ctrl+클릭)으로 3D 회전/기울기를 조절해 보세요.")

# 사이드바: 폭발 위력 설정
st.sidebar.header("시뮬레이션 설정")
yield_kt = st.sidebar.slider("폭발 위력 (Kilotons)", min_value=1.0, max_value=1000.0, value=15.0, step=1.0, help="15kt는 히로시마 원폭 수준입니다.")

# 청계광장 타격 좌표 (위도, 경도)
target_lat, target_lon = 37.5693, 126.9774

# 위력에 따른 피해 반경 계산 (단위: 미터)
radius_fireball = 150 * (yield_kt ** 0.32)
radius_20psi = 280 * (yield_kt ** 0.33)
radius_5psi = 700 * (yield_kt ** 0.33)
radius_thermal = 1200 * (yield_kt ** 0.40)

# Pydeck 레이어 구성 (겹침 방지를 위해 가장 넓은 범위부터 렌더링)
layers = [
    pdk.Layer(
        "ScatterplotLayer",
        data=pd.DataFrame([{"lat": target_lat, "lon": target_lon, "radius": radius_thermal, "name": "열복사 (3도 화상)"}]),
        get_position="[lon, lat]",
        get_radius="radius",
        get_fill_color=[255, 140, 0, 80], # 반투명 주황색
        pickable=True,
    ),
    pdk.Layer(
        "ScatterplotLayer",
        data=pd.DataFrame([{"lat": target_lat, "lon": target_lon, "radius": radius_5psi, "name": "5 psi 폭풍 (일반건물 파괴)"}]),
        get_position="[lon, lat]",
        get_radius="radius",
        get_fill_color=[150, 150, 150, 120], # 반투명 연회색
        pickable=True,
    ),
    pdk.Layer(
        "ScatterplotLayer",
        data=pd.DataFrame([{"lat": target_lat, "lon": target_lon, "radius": radius_20psi, "name": "20 psi 폭풍 (콘크리트 완파)"}]),
        get_position="[lon, lat]",
        get_radius="radius",
        get_fill_color=[50, 50, 50, 150], # 진한 회색
        pickable=True,
    ),
    pdk.Layer(
        "ScatterplotLayer",
        data=pd.DataFrame([{"lat": target_lat, "lon": target_lon, "radius": radius_fireball, "name": "화구 (모든 물질 기화)"}]),
        get_position="[lon, lat]",
        get_radius="radius",
        get_fill_color=[255, 0, 0, 200], # 불투명 빨간색
        pickable=True,
    )
]

# 3D 뷰포트 초기 설정 (청계광장 상공에서 비스듬히 내려다보는 앵글)
view_state = pdk.ViewState(
    latitude=target_lat,
    longitude=target_lon,
    zoom=13.5,
    pitch=45, # 3D 틸트 각도
    bearing=0
)

# 맵 렌더링
st.pydeck_chart(pdk.Deck(
    map_style="mapbox://styles/mapbox/dark-v10",
    initial_view_state=view_state,
    layers=layers,
    tooltip={"text": "{name}\n피해 반경: {radius}m"}
))

import streamlit as st
import requests
import pandas as pd
from io import BytesIO
import re

# 🔹 Função auxiliar: conversão segura de texto para float
def safe_val_dbl(s: str) -> float:
    """Converte texto numérico para float de forma robusta."""
    if pd.isna(s):
        return None
    s = str(s).replace('\xa0', ' ').strip().replace(',', '.')
    try:
        match = re.findall(r"[-+]?\d*\.\d+|\d+", s)
        return float(match[0]) if match else None
    except ValueError:
        return None

def normalise_cp_key(cp) -> str:
    """Normaliza CP para chave de cache (evita '1234.0', espaços, etc.)."""
    if cp is None or (isinstance(cp, float) and pd.isna(cp)):
        return None
    if isinstance(cp, float) and cp.is_integer():
        return str(int(cp)).strip()
    return str(cp).strip()

# =====================================================
# 🔹 Função principal: obter coordenadas de um CP4-CP3
# =====================================================
def get_coordinates(rua: str):
    """
    Obtém as coordenadas (lat, lon) de um código postal.
    Caso haja várias, devolve a média.
    """
    url = f"https://www.codigo-postal.pt/?rua={rua}"
    headers = {"User-Agent": "Mozilla/5.0"}

    try:
        r = requests.get(url, headers=headers, timeout=10)
        if r.status_code != 200:
            return None, None

        html = r.text

        pattern = re.compile(
            r'pull-right\s+gps[\s\S]*?([+-]?\d+\.\d+)[\s,]+([+-]?\d+\.\d+)',
            re.MULTILINE
        )
        matches = pattern.findall(html)
        if not matches:
            return None, None

        latitudes = [safe_val_dbl(lat) for lat, _ in matches if safe_val_dbl(lat) is not None]
        longitudes = [safe_val_dbl(lon) for _, lon in matches if safe_val_dbl(lon) is not None]

        if not latitudes or not longitudes:
            return None, None

        lat_media = sum(latitudes) / len(latitudes)
        lon_media = sum(longitudes) / len(longitudes)
        return lat_media, lon_media

    except Exception:
        return None, None

def calculate_distance(lat_orig, lon_orig, lat_dest, lon_dest, api_key, travel_mode: str):
    """
    Calcula a distância e tempo entre dois pontos usando a API TomTom
    Retorna: (distância em km, tempo em minutos)
    """
    if None in (lat_orig, lon_orig, lat_dest, lon_dest):
        return None, None

    api_url = (
        f'https://api.tomtom.com/routing/1/calculateRoute/'
        f'{lat_orig},{lon_orig}:{lat_dest},{lon_dest}/json'
        f'?key={api_key}&travelMode={travel_mode}'
    )

    try:
        response = requests.get(api_url, timeout=20)
        if response.status_code == 200:
            data = response.json()
            if "routes" in data and len(data["routes"]) > 0:
                summary = data["routes"][0]["summary"]
                distance_km = summary["lengthInMeters"] / 1000
                time_minutes = summary["travelTimeInSeconds"] / 60
                return round(distance_km, 2), round(time_minutes, 2)
        return None, None
    except Exception:
        return None, None

# =====================================================
# 🔹 NOVO: Cache de coordenadas e cache de rotas
# =====================================================
def get_coordinates_cached(cp_key: str, coord_cache: dict):
    """Devolve coordenadas via cache para evitar repetir scraping."""
    if not cp_key:
        return None, None
    if cp_key in coord_cache:
        return coord_cache[cp_key]
    lat, lon = get_coordinates(cp_key)
    coord_cache[cp_key] = (lat, lon)
    return lat, lon

def get_route_cached(cpp_key: str, cpc_key: str, travel_mode: str, api_key: str,
                     coord_cache: dict, route_cache: dict):
    """
    Se (cpp,cpc,modo) já existir, reutiliza Distância/Tempo.
    Caso contrário, calcula 1x e guarda em cache.
    """
    if not cpp_key or not cpc_key:
        return (None, None, None, None, None, None)

    route_key = (cpp_key, cpc_key, travel_mode)

    # ✅ Se já calculado, devolve logo (sem TomTom)
    if route_key in route_cache:
        distance, time = route_cache[route_key]
        lat_p, lon_p = get_coordinates_cached(cpp_key, coord_cache)
        lat_c, lon_c = get_coordinates_cached(cpc_key, coord_cache)
        return (lat_p, lon_p, lat_c, lon_c, distance, time)

    # Caso novo: obter coords (com cache) e chamar TomTom 1x
    lat_p, lon_p = get_coordinates_cached(cpp_key, coord_cache)
    lat_c, lon_c = get_coordinates_cached(cpc_key, coord_cache)

    distance, time = calculate_distance(lat_p, lon_p, lat_c, lon_c, api_key, travel_mode)
    route_cache[route_key] = (distance, time)

    return (lat_p, lon_p, lat_c, lon_c, distance, time)

# =====================================================
# 🔹 Interface Streamlit
# =====================================================
st.title('Cálculo entre Distâncias')

option = st.selectbox(
    "Escolha o método de transporte:",
    ("carro", "camião", "carrinha"),
    index=None,
    placeholder="Selecione uma das opções seguintes",
)

if option == "carro":
    travel_mode = "car"
elif option == "camião":
    travel_mode = "truck"
elif option == "carrinha":
    travel_mode = "van"
else:
    travel_mode = "truck"  # default

files = st.file_uploader("Upload do arquivo Excel", type=["xlsx"])
button = st.button("Cálcular as distâncias")

if files and button:
    try:
        if option is None:
            st.warning('Não selecionou o tipo de transporte. Será utilizado "truck" como padrão.', icon="⚠️")

        df = pd.read_excel(files, engine="openpyxl")

        if df.empty:
            st.error("O ficheiro Excel está vazio. Por favor, verifique se existem dados no ficheiro.")
            st.stop()

        required_cols = ["CP_Partida", "CP_Chegada"]
        if not set(required_cols).issubset(df.columns):
            st.error(f"O ficheiro deve conter as colunas: {', '.join(required_cols)}")
            st.stop()

        if df["CP_Partida"].isna().any() or df["CP_Chegada"].isna().any():
            st.error("Existem códigos postais vazios no ficheiro. Por favor, verifique os dados.")
            st.stop()

        st.info("A processar coordenadas/distâncias... isto pode demorar alguns minutos ⏳")

        results = []
        logs = []
        progress = st.progress(0.0)
        total = len(df)

        api_key = 'c3XHbxJPleK7qYyIzs9moDgxxu5sjRRW'

        # ✅ Caches para reduzir chamadas (scraping + TomTom)
        coord_cache = {}  # CP -> (lat, lon)
        route_cache = {}  # (CP_Partida, CP_Chegada, travel_mode) -> (distance, time)

        for idx, row in df.iterrows():
            cpp = row.get("CP_Partida")
            cpc = row.get("CP_Chegada")

            cpp_key = normalise_cp_key(cpp)
            cpc_key = normalise_cp_key(cpc)

            lat_p, lon_p, lat_c, lon_c, distance, time = get_route_cached(
                cpp_key, cpc_key, travel_mode, api_key,
                coord_cache=coord_cache,
                route_cache=route_cache
            )

            results.append({
                "CP Partida": f"{str(cpp_key).zfill(8)}" if cpp_key else None,
                "Latitude_Partida": lat_p,
                "Longitude_Partida": lon_p,
                "CP Chegada": f"{str(cpc_key).zfill(8)}" if cpc_key else None,
                "Latitude_Chegada": lat_c,
                "Longitude_Chegada": lon_c,
                "Distância": distance,
                "Tempo entre distâncias": time
            })

            if lat_p is None or lon_p is None:
                logs.append(f"Sem coordenadas para CP_Partida={cpp_key}")
            if lat_c is None or lon_c is None:
                logs.append(f"Sem coordenadas para CP_Chegada={cpc_key}")

            if total > 0:
                progress.progress((idx + 1) / total)

            if cpp_key is None or cpc_key is None:
                st.warning("Códigos postais inválidos encontrados. Por favor, verifique os dados.")

        result_df = pd.DataFrame(results)
        st.dataframe(result_df)

        if logs:
            st.warning("Alguns códigos não tiveram coordenadas encontradas:")
            for log in logs:
                st.write(f"• {log}")

        # ✅ Exportar Excel (resultados + logs)
        buffer = BytesIO()
        with pd.ExcelWriter(buffer, engine="openpyxl") as writer:
            result_df.to_excel(writer, index=False, sheet_name="Coordenadas")

            logs_df = pd.DataFrame({"Log": logs}) if logs else pd.DataFrame({"Log": ["Sem erros registados"]})
            logs_df.to_excel(writer, index=False, sheet_name="Logs")

        buffer.seek(0)

        st.download_button(
            label="📥 Descarregar resultados em Excel",
            data=buffer.getvalue(),
            file_name="coordenadas_cp.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            key="excel_download"
        )

        # Informação útil de controlo
        st.info(
            f"Rotas únicas calculadas (TomTom): {len(route_cache)} | "
            f"Linhas no ficheiro: {len(df)} | "
            f"Coordenadas únicas obtidas: {len(coord_cache)}"
        )

    except Exception as e:
        st.error(f"Ocorreu um erro ao ler o ficheiro: {e}")

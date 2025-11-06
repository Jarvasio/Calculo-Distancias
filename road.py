import streamlit as st
import requests
from urllib import response
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

        # Expressão regular para capturar múltiplas coordenadas
        pattern = re.compile(
            r'pull-right\s+gps[\s\S]*?([+-]?\d+\.\d+)[\s,]+([+-]?\d+\.\d+)',
            re.MULTILINE
        )
        matches = pattern.findall(html)

        if not matches:
            return None, None

        # Extrair todas as coordenadas e calcular a média
        latitudes = [safe_val_dbl(lat) for lat, _ in matches if safe_val_dbl(lat) is not None]
        longitudes = [safe_val_dbl(lon) for _, lon in matches if safe_val_dbl(lon) is not None]

        if not latitudes or not longitudes:
            return None, None

        lat_media = sum(latitudes) / len(latitudes)
        lon_media = sum(longitudes) / len(longitudes)
        return lat_media, lon_media

    except Exception as e:
        return None, None

def calculate_distance(lat_orig, lon_orig, lat_dest, lon_dest, api_key):
    """
    Calcula a distância e tempo entre dois pontos usando a API TomTom
    Retorna: (distância em km, tempo em minutos)
    """
    if None in (lat_orig, lon_orig, lat_dest, lon_dest):
        return None, None
    
    # Define o modo de transporte (car como padrão se nenhuma opção for selecionada)
    travel_mode = "car" if option is None else option
    api_url = f'https://api.tomtom.com/routing/1/calculateRoute/{lat_orig},{lon_orig}:{lat_dest},{lon_dest}/json?key={api_key}&travelMode={travel_mode}'
    
    try:
        response = requests.get(api_url)
        if response.status_code == 200:
            data = response.json()
            if "routes" in data and len(data["routes"]) > 0:
                summary = data["routes"][0]["summary"]
                # Converter metros para quilômetros
                distance_km = summary["lengthInMeters"] / 1000
                # Converter segundos para minutos
                time_minutes = summary["travelTimeInSeconds"] / 60
                return round(distance_km, 2), round(time_minutes, 2)
        return None, None
    except Exception:
        return None, None
# =====================================================
# 🔹 Interface Streamlit
# =====================================================
st.title('Cálculo entre Distâncias')

option = st.selectbox(
    "Escolha o método de transporte:",
    ("carro", "camião","carrinha"),
    index=None,
    placeholder= "Selecione uma das opções seguintes",
)


if option == "carro":
    option = "car"
elif option == "camião":
    option = "truck"
elif option =="carrinha":
    option = "van"

# Carregar o ficheiro excel
files = st.file_uploader("Upload do arquivo Excel", 
    type=["xlsx"],
)

button = st.button("Cálcular as distâncias")

# leitura das folhas do excel
if files and button:
    try:
        # Aviso sobre o tipo de transporte não selecionado
        if option is None:
            st.warning('Não selecionou o tipo de transporte. Será utilizado "carro" como padrão.', icon="⚠️")
            
        # Ler para um DataFrame
        df = pd.read_excel(files, engine="openpyxl")
        
        can_proceed = True
        
        # Verificar se o DataFrame está vazio
        if df.empty:
            st.error("O ficheiro Excel está vazio. Por favor, verifique se existem dados no ficheiro.")
            can_proceed = False
        
        # Verificação de colunas obrigatórias
        required_cols = ["CP_Partida", "CP_Chegada"]
        if can_proceed and not set(required_cols).issubset(df.columns):
            st.error(f"O ficheiro deve conter as colunas: {', '.join(required_cols)}")
            can_proceed = False
        
        # Verificar se existem valores nulos nos códigos postais
        if can_proceed and (df["CP_Partida"].isna().any() or df["CP_Chegada"].isna().any()):
            st.error("Existem códigos postais vazios no ficheiro. Por favor, verifique os dados.")
            can_proceed = False
        
        if can_proceed:
            st.info("A processar coordenadas... isto pode demorar alguns minutos ⏳")
            results = []
            logs = []
            progress = st.progress(0.0)
            total = len(df)

            api_key = 'c3XHbxJPleK7qYyIzs9moDgxxu5sjRRW'
        
            for idx, row in df.iterrows():
                 
                cpp = row.get("CP_Partida")
                cpc = row.get("CP_Chegada")

                lat_p, lon_p = get_coordinates(cpp)
                lat_c, lon_c = get_coordinates(cpc)
                
                # Calcular distância e tempo usando TomTom API
                distance, time = calculate_distance(lat_p, lon_p, lat_c, lon_c, api_key)

                results.append({
                    "CP Partida": f"{str(cpp).zfill(8)}",
                    "Latitude_Partida": lat_p,
                    "Longitude_Partida": lon_p,
                    "CP Chegada": f"{str(cpc).zfill(8)}",
                    "Latitude_Chegada": lat_c,
                    "Longitude_Chegada": lon_c,
                    "Distância": distance,  
                    "Tempo entre distâncias": time      
                })

                if lat_p is None or lon_p is None:
                    logs.append(f"Sem coordenadas para {cpp}")
                if lat_c is None or lon_c is None:
                    logs.append(f"Sem coordenadas para {cpc}")

                if total > 0:
                    progress.progress((idx + 1) / total)
                
                if cpp is None or cpc is None:
                    st.warning("Códigos postais inválidos encontrados. Por favor, verifique os dados.")
                   
                
            # Criar DataFrame de resultados
            
            result_df = pd.DataFrame(results)
            st.dataframe(result_df)
            #valid_distances = result_df["Distância"].dropna()
            #if not valid_distances.empty:
             #   st.write("📊 Estatísticas das distâncias (km):")
             #   st.write(f"Média: {valid_distances.mean():.2f} km")
                          
            #valid_time = result_df["Tempo entre distâncias"].dropna()
            #if not valid_time.empty:
             #   st.write("⏱️ Estatísticas do tempo de viagem (minutos):")
              #  st.write(f"Média: {valid_time.mean():.2f} min")
            
            # Mostrar logs se existirem
            if logs:
                st.warning("Alguns códigos não tiveram coordenadas encontradas:")
                for log in logs:
                    buffer = BytesIO()
                with pd.ExcelWriter(buffer, engine="openpyxl") as writer:
                    # folha de resultados
                    result_df.to_excel(writer, index=False, sheet_name="Coordenadas")

                    # folha de logs (converter lista -> DataFrame)
                    if logs:
                        logs_df = pd.DataFrame({"Log": logs})
                    else:
                        logs_df = pd.DataFrame({"Log": ["Sem erros registados"]})
                    logs_df.to_excel(writer, index=False, sheet_name="Logs")

                buffer.seek(0)

                st.download_button(
                    label="📥 Descarregar resultados em Excel",
                    data=buffer.getvalue(),
                    file_name="coordenadas_cp.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    key="excel_download"
                )

    except Exception as e:
        st.error(f"Ocorreu um erro ao ler o ficheiro: {e}")

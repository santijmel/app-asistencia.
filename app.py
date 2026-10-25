import streamlit as st
import pandas as pd
import requests
import unicodedata
import time
from datetime import datetime, timedelta, timezone

# --- CONFIGURACIÓN ---
st.set_page_config(page_title="Asistencia", page_icon="🏫", layout="wide")

URL_APPS_SCRIPT = "https://script.google.com/macros/s/AKfycbxfCpyXfNVSrDyNaH8xLz2Y4V3lcpq6tPvnQXKrBTnYIFerLY-4JhqWDJyyMymec3tr6g/exec"

def licuadora(texto):
    if pd.isna(texto): return ""
    texto = str(texto).strip().upper()
    return ''.join(c for c in unicodedata.normalize('NFD', texto) if unicodedata.category(c) != 'Mn')

# Guardamos los datos en el servidor por 30 minutos (1800 segundos)
@st.cache_data(ttl=1800)
def cargar_datos_seguros():
    # Sistema Anti-Tropiezos: Intenta hasta 3 veces si Google falla
    for intento in range(3):
        try:
            # timeout=15 evita que la app se quede colgada infinitamente esperando a Google
            respuesta = requests.get(URL_APPS_SCRIPT, timeout=15)
            
            # Verificamos que Google haya respondido bien antes de procesar
            if respuesta.status_code == 200:
                datos = respuesta.json()
                
                df_alumnos = pd.DataFrame(datos["alumnos"][1:], columns=datos["alumnos"][0])
                df_alumnos.rename(columns={df_alumnos.columns[0]: 'Alumno'}, inplace=True)
                df_alumnos['Alumno_Licuado'] = df_alumnos['Alumno'].apply(licuadora)
                
                columnas_historico = ["Fecha", "Fecha_Duplicada", "Alumno", "Materia", "Bloque", "Codigo", "Extra1", "Extra2"]
                df_historico = pd.DataFrame(datos["historico"], columns=columnas_historico)
                df_historico['Alumno_Licuado'] = df_historico['Alumno'].apply(licuadora)
                df_historico['Materia_Licuada'] = df_historico['Materia'].apply(licuadora)
                df_historico['Codigo'] = df_historico['Codigo'].fillna("")
                df_historico['Fecha'] = pd.to_datetime(df_historico['Fecha'], errors='coerce').dt.strftime('%Y-%m-%d')
                
                df_traductor = pd.DataFrame(datos["traductor"][1:], columns=["Original", "Agrupada"])
                df_traductor['Original_Licuada'] = df_traductor['Original'].apply(licuadora)
                df_traductor['Agrupada_Licuada'] = df_traductor['Agrupada'].apply(licuadora)
                
                tz_ba = timezone(timedelta(hours=-3))
                hora_actual = datetime.now(tz_ba).strftime("%H:%M:%S")
                
                return df_alumnos, df_historico, df_traductor, hora_actual
                
        except Exception:
            if intento == 2: # Si ya falló 3 veces, nos rendimos
                raise Exception("Google no responde después de 3 intentos.")
            time.sleep(1.5) # Espera 1.5 segundos antes de volver a intentar

# --- CARGA DE DATOS ---
try:
    with st.spinner('Conectando de forma segura al colegio...'):
        df_alumnos, df_historico, df_traductor, ultima_act = cargar_datos_seguros()
except Exception as e:
    st.error("Los servidores de Google están saturados en este momento. Por favor, recargá la página en un minuto.")
    st.stop()

# --- BOTÓN DE SINCRONIZACIÓN MANUAL ---
st.sidebar.title("Opciones ⚙️")
st.sidebar.info(f"⏱️ **Última lectura:** {ultima_act}")
st.sidebar.write("La base se actualiza sola cada 30 min. Para forzar una lectura inmediata desde el Drive, tocá abajo:")
if st.sidebar.button("🔄 Sincronizar con Drive", type="primary"):
    st.cache_data.clear()
    st.rerun()

# --- INTERFAZ PRINCIPAL ---
st.title("Control asistencia 1er año")
st.caption(f"Última sincronización con Google Sheets: {ultima_act}")

col_filtro1, col_filtro2, col_filtro3 = st.columns(3)

with col_filtro1:
    fecha_seleccionada = st.date_input("Día", format="DD/MM/YYYY")
    fecha_str = fecha_seleccionada.strftime("%Y-%m-%d") 
    fecha_visual = fecha_seleccionada.strftime("%d/%m/%Y") 

with col_filtro2:
    lista_materias = [col for col in df_alumnos.columns if col not in ['Alumno', 'Alumno_Licuado']]
    materia_seleccionada = st.selectbox("Materia", lista_materias)

with col_filtro3:
    grupos_disponibles = df_alumnos[materia_seleccionada].dropna().unique()
    grupo_seleccionado = st.selectbox("Grupo/Comisión", grupos_disponibles)

st.divider() 

# --- LÓGICA DE NEGOCIO ---
padron_ideal = df_alumnos[df_alumnos[materia_seleccionada] == grupo_seleccionado][['Alumno', 'Alumno_Licuado']]

materia_licuada = licuadora(materia_seleccionada)
traduccion = df_traductor[df_traductor['Original_Licuada'] == materia_licuada]
materia_a_buscar = traduccion.iloc[0]['Agrupada_Licuada'] if not traduccion.empty else materia_licuada

historico_dia = df_historico[
    (df_historico['Fecha'] == fecha_str) & 
    (df_historico['Materia_Licuada'] == materia_a_buscar) &
    (df_historico['Codigo'].str.upper().isin(['A', 'S', 'RE'])) 
]
alumnos_con_falta = historico_dia['Alumno_Licuado'].tolist()

padron_ideal['Estado'] = padron_ideal['Alumno_Licuado'].apply(
    lambda x: "Ausente" if x in alumnos_con_falta else "Presente"
)

df_presentes = padron_ideal[padron_ideal['Estado'] == "Presente"].copy()
df_ausentes = padron_ideal[padron_ideal['Estado'] == "Ausente"].copy()

df_presentes.rename(columns={'Alumno': 'Estudiantes presentes'}, inplace=True)
df_ausentes.rename(columns={'Alumno': 'Estudiantes ausentes'}, inplace=True)

st.subheader(f"{materia_seleccionada} - {grupo_seleccionado} ({fecha_visual})")

# --- MARCADORES CON TOTALES ---
col_tot1, col_tot2 = st.columns(2)
with col_tot1:
    st.success(f"### Total de presentes: {len(df_presentes)}")
with col_tot2:
    st.error(f"### Total de ausentes: {len(df_ausentes)}")

st.write("") 

# --- LISTAS ---
col_list1, col_list2 = st.columns(2)
with col_list1:
    st.dataframe(df_presentes[['Estudiantes presentes']], use_container_width=True, hide_index=True)
with col_list2:
    st.dataframe(df_ausentes[['Estudiantes ausentes']], use_container_width=True, hide_index=True)

import streamlit as st
import pandas as pd
import requests
import unicodedata

# --- CONFIGURACIÓN ---
st.set_page_config(page_title="Asistencia Diaria", layout="wide")
st.title("Control de Asistencia 🏫")

# --- CONEXIÓN A GOOGLE SHEETS ---
# REEMPLAZA EL TEXTO DE ABAJO POR TU URL DE APPS SCRIPT
URL_APPS_SCRIPT = "https://script.google.com/macros/s/AKfycbxfCpyXfNVSrDyNaH8xLz2Y4V3lcpq6tPvnQXKrBTnYIFerLY-4JhqWDJyyMymec3tr6g/exec"

def licuadora(texto):
    """Elimina tildes, pasa a mayúsculas y borra espacios."""
    if pd.isna(texto):
        return ""
    texto = str(texto).strip().upper()
    texto = ''.join(c for c in unicodedata.normalize('NFD', texto) if unicodedata.category(c) != 'Mn')
    return texto

@st.cache_data(ttl=60) # Refresca los datos cada 60 segundos
def cargar_datos_en_vivo():
    respuesta = requests.get(URL_APPS_SCRIPT)
    datos = respuesta.json()
    
    # 1. Base Alumnos (La fila 0 tiene los nombres de las columnas)
    df_alumnos = pd.DataFrame(datos["alumnos"][1:], columns=datos["alumnos"][0])
    df_alumnos.rename(columns={df_alumnos.columns[0]: 'Alumno'}, inplace=True)
    df_alumnos['Alumno_Licuado'] = df_alumnos['Alumno'].apply(licuadora)
    
    # 2. Histórico (Asignamos columnas manualmente)
    columnas_historico = ["Fecha", "Fecha_Duplicada", "Alumno", "Materia", "Bloque", "Codigo", "Extra1", "Extra2"]
    df_historico = pd.DataFrame(datos["historico"], columns=columnas_historico)
    df_historico['Alumno_Licuado'] = df_historico['Alumno'].apply(licuadora)
    df_historico['Materia_Licuada'] = df_historico['Materia'].apply(licuadora)
    df_historico['Codigo'] = df_historico['Codigo'].fillna("")
    
    # Normalizamos el formato de fecha para que coincida siempre
    df_historico['Fecha'] = pd.to_datetime(df_historico['Fecha'], errors='coerce').dt.strftime('%Y-%m-%d')
    
    # 3. Traductor
    df_traductor = pd.DataFrame(datos["traductor"][1:], columns=["Original", "Agrupada"])
    df_traductor['Original_Licuada'] = df_traductor['Original'].apply(licuadora)
    df_traductor['Agrupada_Licuada'] = df_traductor['Agrupada'].apply(licuadora)
    
    return df_alumnos, df_historico, df_traductor

try:
    df_alumnos, df_historico, df_traductor = cargar_datos_en_vivo()
except Exception as e:
    st.error("Error al cargar los datos. Revisá que la URL de Apps Script esté pegada correctamente en el código de GitHub.")
    st.stop()

# --- INTERFAZ (FILTROS LADO IZQUIERDO) ---
st.sidebar.header("🔍 Filtros")

fecha_seleccionada = st.sidebar.date_input("Seleccionar Día")
fecha_str = fecha_seleccionada.strftime("%Y-%m-%d")

# Excluimos columnas técnicas para dejar solo las materias
lista_materias = [col for col in df_alumnos.columns if col not in ['Alumno', 'Alumno_Licuado']]
materia_seleccionada = st.sidebar.selectbox("Materia", lista_materias)

# Filtra solo los grupos que cursan esa materia
grupos_disponibles = df_alumnos[materia_seleccionada].dropna().unique()
grupo_seleccionado = st.sidebar.selectbox("Grupo/Comisión", grupos_disponibles)

# --- LÓGICA DE NEGOCIO ---
# 1. Armar el padrón ideal
padron_ideal = df_alumnos[df_alumnos[materia_seleccionada] == grupo_seleccionado][['Alumno', 'Alumno_Licuado']]

# 2. Traducir materia (ej: Literature -> Ingles)
materia_licuada = licuadora(materia_seleccionada)
traduccion = df_traductor[df_traductor['Original_Licuada'] == materia_licuada]
materia_a_buscar = traduccion.iloc[0]['Agrupada_Licuada'] if not traduccion.empty else materia_licuada

# 3. Buscar ausencias en el sótano (A, S, RE). 'LT' se ignora y queda presente.
historico_dia = df_historico[
    (df_historico['Fecha'] == fecha_str) & 
    (df_historico['Materia_Licuada'] == materia_a_buscar) &
    (df_historico['Codigo'].str.upper().isin(['A', 'S', 'RE'])) 
]
alumnos_con_falta = historico_dia['Alumno_Licuado'].tolist()

# 4. Clasificar el padrón
padron_ideal['Estado'] = padron_ideal['Alumno_Licuado'].apply(
    lambda x: "Ausente" if x in alumnos_con_falta else "Presente"
)

# --- VISUALIZACIÓN ---
st.subheader(f"Asistencia: {materia_seleccionada} - {grupo_seleccionado} ({fecha_str})")

col1, col2 = st.columns(2)
df_presentes = padron_ideal[padron_ideal['Estado'] == "Presente"]
df_ausentes = padron_ideal[padron_ideal['Estado'] == "Ausente"]

with col1:
    st.success(f"✅ Presentes ({len(df_presentes)})")
    st.dataframe(df_presentes[['Alumno']], use_container_width=True, hide_index=True)

with col2:
    st.error(f"❌ Ausentes ({len(df_ausentes)})")
    st.dataframe(df_ausentes[['Alumno']], use_container_width=True, hide_index=True)

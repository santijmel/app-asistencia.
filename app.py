import streamlit as st
import pandas as pd
import requests
import unicodedata

# --- CONFIGURACIÓN ---
st.set_page_config(page_title="Asistencia", page_icon="🏫", layout="wide")

# PEGA ACÁ TU URL LARGÚISIMA DE APPS SCRIPT (Entre las comillas)
URL_APPS_SCRIPT = "https://script.google.com/macros/s/AKfycbxfCpyXfNVSrDyNaH8xLz2Y4V3lcpq6tPvnQXKrBTnYIFerLY-4JhqWDJyyMymec3tr6g/exec"

def licuadora(texto):
    if pd.isna(texto): return ""
    texto = str(texto).strip().upper()
    return ''.join(c for c in unicodedata.normalize('NFD', texto) if unicodedata.category(c) != 'Mn')

def cargar_datos_seguros():
    respuesta = requests.get(URL_APPS_SCRIPT)
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
    
    return df_alumnos, df_historico, df_traductor

# --- LÓGICA DE MEMORIA (SESSION STATE) ---
if 'datos_cargados' not in st.session_state:
    try:
        with st.spinner('Cargando base de datos segura del colegio...'):
            a, h, t = cargar_datos_seguros()
            st.session_state.df_alumnos = a
            st.session_state.df_historico = h
            st.session_state.df_traductor = t
            st.session_state.datos_cargados = True
    except Exception as e:
        st.error(f"Error de conexión con Apps Script. Revisá que la URL sea la correcta.")
        st.stop()

df_alumnos = st.session_state.df_alumnos
df_historico = st.session_state.df_historico
df_traductor = st.session_state.df_traductor

# --- INTERFAZ PRINCIPAL ---
st.title("Control asistencia 1er año")

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

# Renombramos las columnas solo para la visualización
df_presentes.rename(columns={'Alumno': 'Estudiantes presentes'}, inplace=True)
df_ausentes.rename(columns={'Alumno': 'Estudiantes ausentes'}, inplace=True)

# 2. Mostramos el subtítulo claro con la fecha invertida (DD/MM/YYYY)
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

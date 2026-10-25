import streamlit as st
import pandas as pd
import unicodedata

# --- CONFIGURACIÓN ---
st.set_page_config(page_title="Control Asistencia", layout="wide")

# EL ID DE TU PLANILLA YA ESTÁ PUESTO ACÁ
ID_PLANILLA = "1Zg3ty9Cx3Cpl2MwKlc-dZruRL2hJWmW_R96Kjcx00HA"

# REEMPLAZÁ ESTOS NÚMEROS POR LOS QUE ANOTASTE EN EL PASO 1
GID_ALUMNOS = "110835160" 
GID_HISTORICO = "1515751968"
GID_TRADUCTOR = "891207346"

URL_ALUMNOS = f"https://docs.google.com/spreadsheets/d/{ID_PLANILLA}/export?format=csv&gid={GID_ALUMNOS}"
URL_HISTORICO = f"https://docs.google.com/spreadsheets/d/{ID_PLANILLA}/export?format=csv&gid={GID_HISTORICO}"
URL_TRADUCTOR = f"https://docs.google.com/spreadsheets/d/{ID_PLANILLA}/export?format=csv&gid={GID_TRADUCTOR}"

def licuadora(texto):
    if pd.isna(texto): return ""
    texto = str(texto).strip().upper()
    return ''.join(c for c in unicodedata.normalize('NFD', texto) if unicodedata.category(c) != 'Mn')

def cargar_datos_rapidos():
    df_alumnos = pd.read_csv(URL_ALUMNOS)
    df_alumnos.rename(columns={df_alumnos.columns[0]: 'Alumno'}, inplace=True)
    df_alumnos['Alumno_Licuado'] = df_alumnos['Alumno'].apply(licuadora)
    
    columnas_historico = ["Fecha", "Fecha_Duplicada", "Alumno", "Materia", "Bloque", "Codigo", "Extra1", "Extra2"]
    df_historico = pd.read_csv(URL_HISTORICO, names=columnas_historico, header=None) 
    df_historico['Alumno_Licuado'] = df_historico['Alumno'].apply(licuadora)
    df_historico['Materia_Licuada'] = df_historico['Materia'].apply(licuadora)
    df_historico['Codigo'] = df_historico['Codigo'].fillna("")
    df_historico['Fecha'] = pd.to_datetime(df_historico['Fecha'], errors='coerce').dt.strftime('%Y-%m-%d')
    
    df_traductor = pd.read_csv(URL_TRADUCTOR)
    df_traductor.columns = ["Original", "Agrupada"]
    df_traductor['Original_Licuada'] = df_traductor['Original'].apply(licuadora)
    df_traductor['Agrupada_Licuada'] = df_traductor['Agrupada'].apply(licuadora)
    
    return df_alumnos, df_historico, df_traductor

# --- LÓGICA DE MEMORIA (SESSION STATE) ---
# Esto hace que cargue datos NUEVOS al abrir la web, pero vuele al tocar los filtros.
if 'datos_cargados' not in st.session_state:
    try:
        with st.spinner('Cargando base de datos del colegio...'):
            a, h, t = cargar_datos_rapidos()
            st.session_state.df_alumnos = a
            st.session_state.df_historico = h
            st.session_state.df_traductor = t
            st.session_state.datos_cargados = True
    except Exception as e:
        st.error("Error leyendo los datos. Revisá los números GID y que la planilla tenga permiso 'Cualquier usuario con el vínculo'.")
        st.stop()

df_alumnos = st.session_state.df_alumnos
df_historico = st.session_state.df_historico
df_traductor = st.session_state.df_traductor

# --- INTERFAZ PRINCIPAL ---
st.title("Control asistencia 1er año")

# Filtros arriba, uno al lado del otro (en celular se apilan solos)
col_filtro1, col_filtro2, col_filtro3 = st.columns(3)

with col_filtro1:
    fecha_seleccionada = st.date_input("Día")
    fecha_str = fecha_seleccionada.strftime("%Y-%m-%d")

with col_filtro2:
    lista_materias = [col for col in df_alumnos.columns if col not in ['Alumno', 'Alumno_Licuado']]
    materia_seleccionada = st.selectbox("Materia", lista_materias)

with col_filtro3:
    grupos_disponibles = df_alumnos[materia_seleccionada].dropna().unique()
    grupo_seleccionado = st.selectbox("Grupo/Comisión", grupos_disponibles)

st.divider() # Línea gris separadora

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

df_presentes = padron_ideal[padron_ideal['Estado'] == "Presente"]
df_ausentes = padron_ideal[padron_ideal['Estado'] == "Ausente"]

# --- MARCADORES CON TOTALES (VISUALES Y EN NEGRITA) ---
col_tot1, col_tot2 = st.columns(2)
with col_tot1:
    st.success(f"### Total de presentes: {len(df_presentes)}")
with col_tot2:
    st.error(f"### Total de ausentes: {len(df_ausentes)}")

st.write("") # Espacio en blanco para que respire el diseño

# --- LISTAS ---
col_list1, col_list2 = st.columns(2)
with col_list1:
    st.dataframe(df_presentes[['Alumno']], use_container_width=True, hide_index=True)
with col_list2:
    st.dataframe(df_ausentes[['Alumno']], use_container_width=True, hide_index=True)

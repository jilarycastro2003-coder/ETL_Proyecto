"""
===============================================================================
DASHBOARD INTERACTIVO DE MONITOREO DE RIESGO Y FRAUDE (STREAMLIT)
===============================================================================
Descripción:
    Interfaz web de monitoreo en tiempo real conectada a Supabase (PostgreSQL).
    Proporciona métricas de alto nivel, filtrado dinámico, tablas de consulta
    y gráficos analíticos sobre el riesgo crediticio de las empresas.
"""

import streamlit as st
import pandas as pd
from sqlalchemy import create_engine
from streamlit_autorefresh import st_autorefresh  

# Actualiza la vista del navegador automáticamente cada 5 minutos (300,000 milisegundos)
st_autorefresh(interval=300000, key="datarefresh")  

# Configuración inicial de la página
st.set_page_config(
    page_title="Dashboard de Detección de Fraude",
    page_icon="🛡️",
    layout="wide"
)
# -----------------------------------------------------------------------------
# CONFIGURACIÓN DE LA PÁGINA WEB
# -----------------------------------------------------------------------------
st.set_page_config(
    page_title="Dashboard de Detección de Fraude",
    page_icon="🛡️",
    layout="wide"
)

st.title("🛡️ Sistema de Monitoreo de Riesgo y Detección de Fraude")
st.caption("Plataforma interactiva conectada a Supabase (PostgreSQL)")

# Cadena de conexión JDBC/SQLAlchemy usando el controlador psycopg2
DB_URI = "postgresql+psycopg2://postgres.hdavydolxksxctzvkedv:Jilary2318.@aws-0-ca-central-1.pooler.supabase.com:6543/postgres"
# -----------------------------------------------------------------------------
# EXTRACCIÓN Y CACHÉ DE DATOS
# -----------------------------------------------------------------------------
@st.cache_data(ttl=30)
def load_data():
    """
    Consulta la base de datos de Supabase y retorna DataFrames de Pandas.
    Usa caché con un TTL (Time To Live) de 30 segundos para optimizar 
    el rendimiento y reducir solicitudes a la base de datos.
    """
    engine = create_engine(DB_URI, connect_args={"connect_timeout": 10})
    df_apps = pd.read_sql("SELECT * FROM credit_applications ORDER BY application_date DESC;", engine)
    df_logs = pd.read_sql("SELECT * FROM etl_fraud_logs;", engine)
    return df_apps, df_logs


# -----------------------------------------------------------------------------
# LÓGICA PRINCIPAL Y RENDERIZADO DE LA INTERFAZ
# -----------------------------------------------------------------------------
with st.spinner("Conectando con la base de datos en Supabase..."):
    try:
        # Carga de datasets desde Supabase
        df_apps, df_logs = load_data()

        # Cálculo de métricas principales (KPIs)
        total_apps = len(df_apps)
        high_risk = len(df_apps[df_apps['risk_level'] == 'Alto'])
        med_risk = len(df_apps[df_apps['risk_level'] == 'Medio'])
        low_risk = len(df_apps[df_apps['risk_level'] == 'Bajo'])

        # Renderizado de métricas superiores
        col1, col2, col3, col4 = st.columns(4)
        col1.metric("Total Solicitudes", total_apps)
        col2.metric("Riesgo Alto 🚨", high_risk)
        col3.metric("Riesgo Medio ⚠️", med_risk)
        col4.metric("Riesgo Bajo ✅", low_risk)

        st.markdown("---")

        # ---------------------------------------------------------------------
        # BARRA LATERAL: FILTROS INTERACTIVOS
        # ---------------------------------------------------------------------
        st.sidebar.header("Filtros")
        opciones_riesgo = list(df_apps['risk_level'].unique()) if not df_apps.empty else []
        risk_filter = st.sidebar.multiselect(
            "Nivel de Riesgo:",
            options=opciones_riesgo,
            default=opciones_riesgo
        )

        # Aplicar filtro de nivel de riesgo al DataFrame
        df_filtered = df_apps[df_apps['risk_level'].isin(risk_filter)]

        # ---------------------------------------------------------------------
        # PESTAÑAS PRINCIPALES DE NAVEGACIÓN
        # ---------------------------------------------------------------------
        tab1, tab2, tab3 = st.tabs(["📊 Solicitudes de Crédito", "📈 Gráficos de Riesgo", "📝 Logs del ETL"])

        # Pestaña 1: Vista tabular detallada
        with tab1:
            st.subheader("Solicitudes Registradas")
            st.dataframe(df_filtered, use_container_width=True)

        # Pestaña 2: Gráficos de barras
        with tab2:
            st.subheader("Distribución de Riesgo Financiero")
            if not df_apps.empty:
                st.bar_chart(df_apps['risk_level'].value_counts())

        # Pestaña 3: Historial y auditoría
        with tab3:
            st.subheader("Historial de Ejecuciones del Pipeline ETL")
            st.dataframe(df_logs, use_container_width=True)

    except Exception as e:
        st.error(f"❌ Error de conexión a la base de datos: {e}")
    
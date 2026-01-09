import streamlit as st
import pandas as pd
import mysql.connector
from datetime import datetime

# 1. Configuración de página
st.set_page_config(page_title="Control Logístico Máster", layout="wide")

# 2. Conexión a TiDB
def get_db_connection():
    return mysql.connector.connect(
        host=st.secrets["tidb"]["host"],
        port=st.secrets["tidb"]["port"],
        user=st.secrets["tidb"]["user"],
        password=st.secrets["tidb"]["password"],
        database=st.secrets["tidb"]["database"],
        ssl_ca="/etc/ssl/certs/ca-certificates.crt" 
    )

# --- MENÚ LATERAL ---
st.sidebar.title("Navegación")
choice = st.sidebar.radio("Ir a:", ["📊 Dashboard Analítico", "📝 Nuevo Registro", "📁 Historial y Archivos"])

# ==========================================
# SECCIÓN: DASHBOARD ANALÍTICO
# ==========================================
if choice == "📊 Dashboard Analítico":
    st.title("📊 Dashboard de Control y Rentabilidad")
    
    try:
        conn = get_db_connection()
        df = pd.read_sql("SELECT * FROM logistica_v2", conn)
        conn.close()
        
        if not df.empty:
            # Preparar fechas
            df['fecha_pre_alerta_lm'] = pd.to_datetime(df['fecha_pre_alerta_lm'])
            
            # --- FILTROS SIDEBAR ---
            st.sidebar.divider()
            st.sidebar.subheader("📅 Filtros (Fecha Last Mile)")
            tipo_f = st.sidebar.selectbox("Tipo de Filtro:", ["Todo", "Mes/Año", "Rango de Fechas"])
            
            df_f = df.copy()
            if tipo_f == "Mes/Año":
                year = st.sidebar.selectbox("Año", sorted(df['fecha_pre_alerta_lm'].dt.year.unique(), reverse=True))
                month = st.sidebar.selectbox("Mes", range(1, 13), format_func=lambda x: ["Ene", "Feb", "Mar", "Abr", "May", "Jun", "Jul", "Ago", "Sep", "Oct", "Nov", "Dic"][x-1])
                df_f = df[(df['fecha_pre_alerta_lm'].dt.year == year) & (df['fecha_pre_alerta_lm'].dt.month == month)]
            elif tipo_f == "Rango de Fechas":
                rango = st.sidebar.date_input("Seleccione Rango", [])
                if len(rango) == 2:
                    df_f = df[(df['fecha_pre_alerta_lm'].dt.date >= rango[0]) & (df['fecha_pre_alerta_lm'].dt.date <= rango[1])]

            # --- RESUMEN GENERAL ---
            st.subheader("💡 Resumen General")
            k1, k2, k3, k4, k5, k6 = st.columns(6)
            
            utilidad = df_f['cc_services_calc'].sum() - df_f['total_costos'].sum()
            
            k1.metric("Ingresos CC", f"${df_f['cc_services_calc'].sum():,.2f}")
            k2.metric("Gastos Op.", f"${df_f['total_costos'].sum():,.2f}")
            k3.metric("Utilidad Neta", f"${utilidad:,.2f}")
            k4.metric("Total Paquetes", f"{int(df_f['paquetes'].sum()):,}")
            k5.metric("Cant. Másters", f"{len(df_f)}")
            k6.metric("Peso (KG)", f"{df_f['peso_kg'].sum():,.1f}")
            
            st.divider()
            
            # --- GRÁFICOS ---
            col_g1, col_g2 = st.columns(2)
            with col_g1:
                st.write("### 💸 Distribución de Gastos")
                gastos = {
                    'Cuadrilla': df_f['costo_cuadrilla'].sum(),
                    'Montacargas': df_f['montacargas'].sum(),
                    'Yales': df_f['yales'].sum(),
                    'Flete': df_f['flete_subcontrato'].sum(),
                    'Extras': df_f['servicio_extraordinario'].sum()
                }
                st.bar_chart(pd.Series(gastos))
            with col_g2:
                st.write("### 📦 ADIMEX: Calc vs Real")
                adimex_comp = {'Calculado': df_f['adimex_calc'].sum(), 'Pagado': df_f['adimex_pagado'].sum()}
                st.bar_chart(pd.Series(adimex_comp))
        else:
            st.info("Sin registros.")
    except Exception as e:
        st.error(f"Error en Dashboard: {e}")

# ==========================================
# SECCIÓN: NUEVO REGISTRO
# ==========================================
elif choice == "📝 Nuevo Registro":
    st.title("📝 Registro de Operación Máster")
    with st.form("main_form", clear_on_submit=True):
        t1, t2, t3 = st.tabs(["🚛 Carga", "💰 Costos", "📄 PDF"])
        with t1:
            c1, c2 = st.columns(2)
            mes = c1.selectbox("Mes", ["Enero", "Febrero", "Marzo", "Abril", "Mayo", "Junio", "Julio", "Agosto", "Septiembre", "Octubre", "Noviembre", "Diciembre"])
            f_fm = c1.date_input("Fecha FM")
            m_fm = c1.text_input("Máster FM")
            f_lm = c2.date_input("Fecha LM")
            m_lm = c2.text_input("Máster LM")
            paquetes = st.number_input("Paquetes", min_value=0)
            peso = st.number_input("Peso (KG)", min_value=0.0)
        with t2:
            c_cuadrilla = st.number_input("Costo Cuadrilla $", min_value=0.0)
            f_sub = st.number_input("Flete Sub $", min_value=0.0)
            adimex_pagado = st.number_input("ADIMEX Pagado $", min_value=0.0)
            # Otros campos simplificados por espacio, añade los que gustes
        with t3:
            archivo_pdf = st.file_uploader("Subir PDF", type=["pdf"])
        
        if st.form_submit_button("Guardar"):
            # Lógica de Insert (Mismo SQL anterior)
            st.success("Guardado (Simulación - Asegúrate de incluir el SQL de INSERT aquí)")

# ==========================================
# SECCIÓN: HISTORIAL (TABLA LIMPIA)
# ==========================================
elif choice == "📁 Historial y Archivos":
    st.title("📁 Historial de Operaciones")
    try:
        conn = get_db_connection()
        df = pd.read_sql("SELECT * FROM logistica_v2 ORDER BY fecha_pre_alerta_lm DESC", conn)
        
        if not df.empty:
            # Buscador de PDF por Máster
            df_pdf = df[df['pdf_nombre'].notnull()]
            sel = st.selectbox("Buscar PDF por Máster FM:", ["---"] + df_pdf['master_fm'].tolist())
            if sel != "---":
                cursor = conn.cursor()
                cursor.execute("SELECT pdf_nombre, pdf_archivo FROM logistica_v2 WHERE master_fm = %s", (sel,))
                res = cursor.fetchone()
                if res:
                    st.download_button(f"⬇️ Descargar {res[0]}", res[1], file_name=res[0])
            
            st.divider()
            # Tabla sin índice (sin columna vacía a la izquierda)
            st.dataframe(df.drop(columns=['pdf_archivo']), use_container_width=True, hide_index=True)
        else:
            st.info("Sin datos.")
        conn.close()
    except Exception as e:
        st.error(f"Error: {e}")

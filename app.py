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
            st.subheader("💡 Resumen de Operación")
            m1, m2, m3, m4, m5, m6 = st.columns(6)
            
            total_servicios_cc = df_f['cc_services_calc'].sum()
            total_gastos_op = df_f['total_costos'].sum()
            utilidad_neta = total_servicios_cc - total_gastos_op
            
            m1.metric("Ingresos CC", f"${total_servicios_cc:,.2f}")
            m2.metric("Gastos Op.", f"${total_gastos_op:,.2f}")
            m3.metric("Utilidad Neta", f"${utilidad_neta:,.2f}")
            m4.metric("Paquetes", f"{int(df_f['paquetes'].sum()):,} Pq")
            m5.metric("Másters", f"{len(df_f)}")
            m6.metric("Peso Total", f"{df_f['peso_kg'].sum():,.1f} Kg")
            
            st.divider()

            # --- SECCIÓN ADIMEX ---
            st.subheader("🔍 Detalle ADIMEX")
            a1, a2, a3 = st.columns(3)
            total_adimex_calc = df_f['adimex_calc'].sum()
            total_adimex_pagado = df_f['adimex_pagado'].sum()
            total_dif_adimex = df_f['dif_adimex'].sum()
            
            a1.metric("ADIMEX Calculado", f"${total_adimex_calc:,.2f}")
            a2.metric("ADIMEX Real Pagado", f"${total_adimex_pagado:,.2f}")
            a3.metric("Diferencia", f"${total_dif_adimex:,.2f}", delta=-total_dif_adimex, delta_color="inverse")
            
            st.divider()
            
            # --- GRÁFICOS ---
            col_g1, col_g2 = st.columns(2)
            with col_g1:
                st.write("### 💸 Distribución de Gastos")
                gastos = {'Cuadrilla': df_f['costo_cuadrilla'].sum(), 'Montacargas': df_f['montacargas'].sum(), 'Yales': df_f['yales'].sum(), 'Flete': df_f['flete_subcontrato'].sum(), 'Extras': df_f['servicio_extraordinario'].sum()}
                st.bar_chart(pd.Series(gastos))
            with col_g2:
                st.write("### 📊 Comparativa ADIMEX")
                st.bar_chart(pd.Series({'Calculado': total_adimex_calc, 'Pagado': total_adimex_pagado}))
        else:
            st.info("Sin registros.")
    except Exception as e:
        st.error(f"Error: {e}")

# ==========================================
# SECCIÓN: HISTORIAL Y ARCHIVOS (CON FORMATO)
# ==========================================
elif choice == "📁 Historial y Archivos":
    st.title("📁 Historial de Operaciones")
    try:
        conn = get_db_connection()
        df = pd.read_sql("SELECT * FROM logistica_v2 ORDER BY fecha_pre_alerta_lm DESC", conn)
        conn.close()
        
        if not df.empty:
            st.subheader("⬇️ Descarga de Comprobantes")
            df_pdf = df[df['pdf_nombre'].notnull()]
            sel = st.selectbox("Buscar por Máster First Mile:", ["---"] + df_pdf['master_fm'].tolist())
            if sel != "---":
                conn = get_db_connection()
                cursor = conn.cursor()
                cursor.execute("SELECT pdf_nombre, pdf_archivo FROM logistica_v2 WHERE master_fm = %s", (sel,))
                res = cursor.fetchone()
                conn.close()
                if res:
                    st.download_button(f"⬇️ Descargar PDF de {sel}", res[1], file_name=res[0])
            
            st.divider()
            st.subheader("📋 Registro de Datos")
            
            # Formateo de columnas en la tabla
            st.dataframe(
                df.drop(columns=['pdf_archivo']), 
                use_container_width=True, 
                hide_index=True,
                column_config={
                    "paquetes": st.column_config.NumberColumn("Paquetes", format="%d Pq"),
                    "peso_kg": st.column_config.NumberColumn("Peso (KG)", format="%.1f Kg"),
                    "cc_services_calc": st.column_config.NumberColumn("CC Services", format="$ %.2f"),
                    "costo_cuadrilla": st.column_config.NumberColumn("Costo Cuadrilla", format="$ %.2f"),
                    "montacargas": st.column_config.NumberColumn("Montacargas", format="$ %.2f"),
                    "yales": st.column_config.NumberColumn("Yales", format="$ %.2f"),
                    "servicio_extraordinario": st.column_config.NumberColumn("Serv. Extra", format="$ %.2f"),
                    "flete_subcontrato": st.column_config.NumberColumn("Flete Sub.", format="$ %.2f"),
                    "total_costos": st.column_config.NumberColumn("Total Costos", format="$ %.2f"),
                    "adimex_calc": st.column_config.NumberColumn("ADIMEX Calc.", format="$ %.2f"),
                    "adimex_pagado": st.column_config.NumberColumn("ADIMEX Pagado", format="$ %.2f"),
                    "dif_adimex": st.column_config.NumberColumn("Dif. ADIMEX", format="$ %.2f"),
                    "dif_servicios": st.column_config.NumberColumn("Dif. Servicios", format="$ %.2f"),
                }
            )
        else:
            st.info("Sin datos.")
    except Exception as e:
        st.error(f"Error: {e}")

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
            f_fm = c1.date_input("Fecha First Mile")
            m_fm = c1.text_input("Máster First Mile")
            f_lm = c2.date_input("Fecha Last Mile")
            m_lm = c2.text_input("Máster Last Mile")
            paquetes = st.number_input("Cantidad Paquetes", min_value=0)
            peso = st.number_input("Peso Total (KG)", min_value=0.0)
            cajas = st.number_input("Cajas", min_value=0)
        with t2:
            ca, cb = st.columns(2)
            p_cuadrilla = ca.number_input("Personas Cuadrilla", min_value=0)
            c_cuadrilla = ca.number_input("Costo Cuadrilla $", min_value=0.0)
            montacargas = ca.number_input("Costo Montacargas $", min_value=0.0)
            yales = ca.number_input("Costo Yales $", min_value=0.0)
            t_flete = cb.selectbox("Tipo Flete", ["PROPIO", "SUBCONTRATO"])
            t_camion = cb.text_input("Tipo Camión")
            f_sub = cb.number_input("Flete Subcontrato $", min_value=0.0)
            s_extra = cb.number_input("Servicio Extraordinario $", min_value=0.0)
            adimex_pagado = st.number_input("ADIMEX Pagado $", min_value=0.0)
        with t3:
            archivo_pdf = st.file_uploader("Subir PDF", type=["pdf"])
        
        if st.form_submit_button("🚀 GUARDAR REGISTRO"):
            cc_services = paquetes * 0.84
            adimex_calc = peso * 0.35
            total_costos = c_cuadrilla + montacargas + yales + s_extra + f_sub
            dif_adimex = adimex_calc - adimex_pagado
            dif_servicios = cc_services - total_costos
            pdf_data = archivo_pdf.read() if archivo_pdf else None
            pdf_name = archivo_pdf.name if archivo_pdf else None

            try:
                conn = get_db_connection()
                cursor = conn.cursor()
                sql = "INSERT INTO logistica_v2 (mes, fecha_pre_alerta_fm, master_fm, fecha_pre_alerta_lm, master_lm, cajas, paquetes, peso_kg, cc_services_calc, cant_personas_cuadrilla, costo_cuadrilla, montacargas, yales, servicio_extraordinario, tipo_flete, tipo_camion, flete_subcontrato, total_costos, adimex_calc, adimex_pagado, dif_adimex, dif_servicios, pdf_nombre, pdf_archivo) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)"
                cursor.execute(sql, (mes, f_fm, m_fm, f_lm, m_lm, cajas, paquetes, peso, cc_services, p_cuadrilla, c_cuadrilla, montacargas, yales, s_extra, t_flete, t_camion, f_sub, total_costos, adimex_calc, adimex_pagado, dif_adimex, dif_servicios, pdf_name, pdf_data))
                conn.commit()
                st.success(f"✅ Registro {m_fm} guardado.")
                conn.close()
            except Exception as e:
                st.error(f"Error: {e}")

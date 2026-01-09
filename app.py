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
            # --- FILA 1: MÉTRICAS CLAVE ---
            st.subheader("💡 Resumen General")
            k1, k2, k3, k4 = st.columns(4)
            
            total_servicios = df['cc_services_calc'].sum()
            total_gastos = df['total_costos'].sum()
            utilidad = total_servicios - total_gastos
            total_peso = df['peso_kg'].sum()
            
            k1.metric("Ingresos Servicios CC", f"${total_servicios:,.2f}")
            k2.metric("Gastos Operativos", f"${total_gastos:,.2f}")
            k3.metric("Utilidad Neta", f"${utilidad:,.2f}", delta=f"{utilidad:,.2f}")
            k4.metric("Volumen Total (KG)", f"{total_peso:,.1f} kg")
            
            st.divider()
            
            # --- FILA 2: COMPARATIVA ADIMEX ---
            st.subheader("🔍 Análisis ADIMEX (Calculado vs Pagado)")
            c1, c2, c3 = st.columns(3)
            
            calc_adimex = df['adimex_calc'].sum()
            pagado_adimex = df['adimex_pagado'].sum()
            dif_adimex = df['dif_adimex'].sum()
            
            c1.metric("ADIMEX Teórico ($0.35/kg)", f"${calc_adimex:,.2f}")
            c2.metric("ADIMEX Real Pagado", f"${pagado_adimex:,.2f}")
            c3.metric("Diferencia Total", f"${dif_adimex:,.2f}", delta=-dif_adimex, delta_color="inverse")
            
            st.divider()
            
            # --- FILA 3: GRÁFICOS ---
            g1, g2 = st.columns(2)
            
            with g1:
                st.write("### 📅 Operaciones por Mes (Cantidad de Másters)")
                masters_mes = df.groupby('mes')['master_fm'].count()
                st.bar_chart(masters_mes)
                
            with g2:
                st.write("### 💸 Desglose de Gastos Totales")
                # Sumatoria de gastos específicos
                gastos_data = {
                    'Cuadrilla': df['costo_cuadrilla'].sum(),
                    'Montacargas': df['montacargas'].sum(),
                    'Yales': df['yales'].sum(),
                    'Flete Sub.': df['flete_subcontrato'].sum(),
                    'Extras': df['servicio_extraordinario'].sum()
                }
                df_gastos = pd.DataFrame(list(gastos_data.items()), columns=['Concepto', 'Monto'])
                st.bar_chart(df_gastos.set_index('Concepto'))

        else:
            st.info("No hay datos suficientes para generar el dashboard. Ingrese registros primero.")
            
    except Exception as e:
        st.error(f"Error al cargar el Dashboard: {e}")

# ==========================================
# SECCIÓN: NUEVO REGISTRO
# ==========================================
elif choice == "📝 Nuevo Registro":
    st.title("📝 Registro de Operación Máster")
    
    with st.form("main_form", clear_on_submit=True):
        tab1, tab2, tab3 = st.tabs(["🚛 Info. de Carga", "💰 Costos Operativos", "📄 Documentación"])
        
        with tab1:
            col1, col2 = st.columns(2)
            with col1:
                mes = st.selectbox("Mes de Operación", ["Enero", "Febrero", "Marzo", "Abril", "Mayo", "Junio", "Julio", "Agosto", "Septiembre", "Octubre", "Noviembre", "Diciembre"])
                f_fm = st.date_input("Fecha Pre Alerta FM")
                m_fm = st.text_input("Máster First Mile")
            with col2:
                f_lm = st.date_input("Fecha Pre Alerta LM")
                m_lm = st.text_input("Máster Last Mile")
            
            c1, c2, c3 = st.columns(3)
            cajas = c1.number_input("Cajas", min_value=0)
            paquetes = c2.number_input("Paquetes", min_value=0)
            peso = c3.number_input("Peso (KG)", min_value=0.0)

        with tab2:
            ca, cb = st.columns(2)
            with ca:
                p_cuadrilla = st.number_input("Personas Cuadrilla", min_value=0)
                c_cuadrilla = st.number_input("Costo Cuadrilla $", min_value=0.0)
                montacargas = st.number_input("Montacargas $", min_value=0.0)
                yales = st.number_input("Yales $", min_value=0.0)
            with cb:
                t_flete = st.selectbox("Tipo Flete", ["Local", "Nacional", "Foráneo"])
                t_camion = st.text_input("Tipo Camión")
                f_sub = st.number_input("Flete Subcontrato $", min_value=0.0)
                s_extra = st.number_input("Servicio Extraordinario $", min_value=0.0)
            
            adimex_pagado = st.number_input("ADIMEX Pagado $", min_value=0.0)

        with tab3:
            archivo_pdf = st.file_uploader("Subir Comprobante (PDF)", type=["pdf"])

        enviar = st.form_submit_button("🚀 GUARDAR REGISTRO", use_container_width=True)

        if enviar:
            # Cálculos
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
                sql = """INSERT INTO logistica_v2 
                (mes, fecha_pre_alerta_fm, master_fm, fecha_pre_alerta_lm, master_lm, cajas, paquetes, peso_kg, 
                cc_services_calc, cant_personas_cuadrilla, costo_cuadrilla, montacargas, yales, servicio_extraordinario, 
                tipo_flete, tipo_camion, flete_subcontrato, total_costos, adimex_calc, adimex_pagado, dif_adimex, 
                dif_servicios, pdf_nombre, pdf_archivo) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)"""
                
                cursor.execute(sql, (mes, f_fm, m_fm, f_lm, m_lm, cajas, paquetes, peso, cc_services, p_cuadrilla, 
                                     c_cuadrilla, montacargas, yales, s_extra, t_flete, t_camion, f_sub, 
                                     total_costos, adimex_calc, adimex_pagado, dif_adimex, dif_servicios, pdf_name, pdf_data))
                conn.commit()
                st.success(f"✅ Registro {m_fm} guardado.")
                conn.close()
            except Exception as e:
                st.error(f"Error: {e}")

# ==========================================
# SECCIÓN: HISTORIAL Y ARCHIVOS
# ==========================================
elif choice == "📁 Historial y Archivos":
    st.title("📁 Historial Completo")
    
    try:
        conn = get_db_connection()
        df = pd.read_sql("SELECT * FROM logistica_v2 ORDER BY id DESC", conn)
        
        if not df.empty:
            # Selector de descarga
            st.subheader("⬇️ Descargar Comprobante por Máster")
            df_pdf = df[df['pdf_nombre'].notnull()]
            master_sel = st.selectbox("Seleccione Máster:", ["---"] + df_pdf['master_fm'].tolist())
            
            if master_sel != "---":
                cursor = conn.cursor()
                cursor.execute("SELECT pdf_nombre, pdf_archivo FROM logistica_v2 WHERE master_fm = %s LIMIT 1", (master_sel,))
                res = cursor.fetchone()
                if res:
                    st.download_button(f"Descargar PDF: {res[0]}", res[1], file_name=res[0])

            st.divider()
            
            # Tabla interactiva
            st.subheader("📋 Registros")
            st.dataframe(df.drop(columns=['pdf_archivo']), use_container_width=True)
            
        else:
            st.info("Sin registros.")
        conn.close()
    except Exception as e:
        st.error(f"Error: {e}")

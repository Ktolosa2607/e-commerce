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

# --- SECCIÓN: NUEVO REGISTRO (MEJORADO) ---
if choice == "📝 Nuevo Registro":
    st.title("📝 Registro de Operación Máster")
    st.info("Complete la información organizada por categorías para un mejor control.")

    with st.form("main_form", clear_on_submit=True):
        tab1, tab2, tab3 = st.tabs(["🚛 Info. de Carga", "💰 Costos Operativos", "📄 Documentación"])
        
        with tab1:
            col1, col2 = st.columns(2)
            with col1:
                mes = st.selectbox("Mes de Operación", ["Enero", "Febrero", "Marzo", "Abril", "Mayo", "Junio", "Julio", "Agosto", "Septiembre", "Octubre", "Noviembre", "Diciembre"])
                f_fm = st.date_input("Fecha Pre Alerta First Mile")
                m_fm = st.text_input("Máster First Mile (Referencia)")
            with col2:
                f_lm = st.date_input("Fecha Pre Alerta Last Mile")
                m_lm = st.text_input("Máster Last Mile (Referencia)")
            
            st.divider()
            c1, c2, c3 = st.columns(3)
            cajas = c1.number_input("Total Cajas", min_value=0, step=1)
            paquetes = c2.number_input("Total Paquetes", min_value=0, step=1)
            peso = c3.number_input("Peso Total (KG)", min_value=0.0, step=0.1)

        with tab2:
            col_a, col_b = st.columns(2)
            with col_a:
                st.subheader("Personal y Equipo")
                p_cuadrilla = st.number_input("Personas en Cuadrilla", min_value=0)
                c_cuadrilla = st.number_input("Costo Cuadrilla ($)", min_value=0.0)
                montacargas = st.number_input("Costo Montacargas ($)", min_value=0.0)
                yales = st.number_input("Costo Yales ($)", min_value=0.0)
            with col_b:
                st.subheader("Transporte y Extras")
                t_flete = st.selectbox("Tipo de Flete", ["Propio", "Subcontratado Local", "Subcontratado Foráneo"])
                t_camion = st.text_input("Tipo de Camión")
                f_sub = st.number_input("Costo Flete Subcontrato ($)", min_value=0.0)
                s_extra = st.number_input("Servicios Extraordinarios ($)", min_value=0.0)
            
            st.divider()
            adimex_pagado = st.number_input("Monto Pagado a ADIMEX ($)", min_value=0.0, help="Monto real de la factura")

        with tab3:
            st.subheader("Archivos Adjuntos")
            archivo_pdf = st.file_uploader("Subir Comprobante ADIMEX / Guía (PDF)", type=["pdf"])
            st.caption("El archivo se guardará asociado al número de Máster First Mile.")

        st.divider()
        enviar = st.form_submit_button("🚀 GUARDAR REGISTRO COMPLETO", use_container_width=True)

        if enviar:
            # Cálculos automáticos
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
                st.success(f"✅ ¡Éxito! Máster {m_fm} registrado correctamente.")
                conn.close()
            except Exception as e:
                st.error(f"Error al guardar: {e}")

# --- SECCIÓN: HISTORIAL Y ARCHIVOS (ORGANIZADO) ---
elif choice == "📁 Historial y Archivos":
    st.title("📁 Control y Seguimiento de Másters")
    
    try:
        conn = get_db_connection()
        # Traemos todo ordenado por fecha de creación
        df = pd.read_sql("SELECT * FROM logistica_v2 ORDER BY id DESC", conn)
        
        if not df.empty:
            # BUSCADOR Y DESCARGA
            st.subheader("🔍 Buscar y Descargar PDF")
            col_search, col_down = st.columns([2, 1])
            
            # Filtramos solo los que tienen PDF para la lista de descarga
            df_con_pdf = df[df['pdf_nombre'].notnull()]
            lista_masters = df_con_pdf['master_fm'].tolist()
            
            with col_search:
                master_seleccionado = st.selectbox("Seleccione el Máster para descargar su comprobante:", ["Seleccione..."] + lista_masters)
            
            with col_down:
                if master_seleccionado != "Seleccione...":
                    cursor = conn.cursor()
                    cursor.execute("SELECT pdf_nombre, pdf_archivo FROM logistica_v2 WHERE master_fm = %s LIMIT 1", (master_seleccionado,))
                    res = cursor.fetchone()
                    if res and res[1]:
                        st.download_button(f"⬇️ Descargar PDF de {master_seleccionado}", res[1], file_name=res[0], use_container_width=True)

            st.divider()
            
            # VISUALIZACIÓN DE TABLA COMPLETA
            st.subheader("📋 Detalle General de Operaciones")
            # Reorganizamos columnas para que lo más importante esté al principio
            columnas_ordenadas = [
                'mes', 'master_fm', 'fecha_pre_alerta_fm', 'master_lm', 'paquetes', 'peso_kg', 
                'cc_services_calc', 'total_costos', 'adimex_calc', 'adimex_pagado', 'dif_adimex', 'dif_servicios'
            ]
            st.dataframe(df[columnas_ordenadas], use_container_width=True)
            
            # DETALLE EXPANDIBLE POR REGISTRO
            st.subheader("📖 Vista Detallada por Máster")
            for i, row in df.iterrows():
                with st.expander(f"📦 Máster: {row['master_fm']} | Mes: {row['mes']} | Peso: {row['peso_kg']} KG"):
                    c1, c2, c3 = st.columns(3)
                    c1.write(f"**First Mile:** {row['fecha_pre_alerta_fm']}")
                    c1.write(f"**Last Mile:** {row['fecha_pre_alerta_lm']}")
                    c1.write(f"**Máster LM:** {row['master_lm']}")
                    
                    c2.write(f"**CC Services ($0.84):** ${row['cc_services_calc']:,.2f}")
                    c2.write(f"**Gastos Operativos:** ${row['total_costos']:,.2f}")
                    c2.write(f"**Diferencia Servicios:** ${row['dif_servicios']:,.2f}")
                    
                    c3.write(f"**ADIMEX Calc ($0.35):** ${row['adimex_calc']:,.2f}")
                    c3.write(f"**ADIMEX Pagado:** ${row['adimex_pagado']:,.2f}")
                    c3.write(f"**Diferencia ADIMEX:** ${row['dif_adimex']:,.2f}")
                    
                    st.info(f"Flete: {row['tipo_flete']} | Camión: {row['tipo_camion']} | Cuadrilla: {row['cant_personas_cuadrilla']} pers.")

        else:
            st.info("No se encontraron registros en la base de datos.")
        conn.close()
    except Exception as e:
        st.error(f"Error al cargar historial: {e}")

# --- SECCIÓN: DASHBOARD (MISMAS MÉTRICAS) ---
elif choice == "📊 Dashboard":
    # (Aquí iría el código del dashboard anterior)
    st.title("Dashboard en construcción...")

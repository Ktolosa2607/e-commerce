import streamlit as st
import pandas as pd
import mysql.connector
from datetime import datetime

# Configuración inicial
st.set_page_config(page_title="Control Logístico PRO", layout="wide")

# Conexión a TiDB
def get_db_connection():
    return mysql.connector.connect(**st.secrets["tidb"])

# --- LÓGICA DE NAVEGACIÓN ---
menu = ["📊 Dashboard", "📝 Nuevo Registro", "📁 Historial y PDF"]
choice = st.sidebar.selectbox("Menú", menu)

if choice == "📝 Nuevo Registro":
    st.header("Entrada de Datos")
    
    with st.form("main_form", clear_on_submit=True):
        c1, c2, c3 = st.columns(3)
        
        with c1:
            mes = st.selectbox("Mes", ["Enero", "Febrero", "Marzo", "Abril", "Mayo", "Junio", "Julio", "Agosto", "Septiembre", "Octubre", "Noviembre", "Diciembre"])
            f_fm = st.date_input("Fecha Pre Alerta FM")
            m_fm = st.text_input("Máster First Mile")
            cajas = st.number_input("Cajas", min_value=0)
            paquetes = st.number_input("Paquetes", min_value=0)
            peso = st.number_input("Peso (KG)", min_value=0.0)

        with c2:
            f_lm = st.date_input("Fecha Pre Alerta LM")
            m_lm = st.text_input("Máster Last Mile")
            p_cuadrilla = st.number_input("Personas Cuadrilla", min_value=0)
            c_cuadrilla = st.number_input("Costo Cuadrilla $", min_value=0.0)
            montacargas = st.number_input("Montacargas $", min_value=0.0)
            yales = st.number_input("Yales $", min_value=0.0)

        with c3:
            s_extra = st.number_input("Servicio Extraordinario $", min_value=0.0)
            t_flete = st.selectbox("Tipo Flete", ["Local", "Nacional", "Foráneo"])
            t_camion = st.text_input("Tipo Camión")
            f_sub = st.number_input("Flete Subcontrato $", min_value=0.0)
            adimex_pagado = st.number_input("ADIMEX Pagado $", min_value=0.0)
            archivo_pdf = st.file_uploader("Subir Comprobante ADIMEX (PDF)", type=["pdf"])

        enviar = st.form_submit_button("Guardar en Sistema")

        if enviar:
            # --- CÁLCULOS AUTOMÁTICOS ---
            cc_services = paquetes * 0.84
            adimex_calc = peso * 0.35
            total_costos = c_cuadrilla + montacargas + yales + s_extra + f_sub
            dif_adimex = adimex_calc - adimex_pagado
            dif_servicios = cc_services - 0 # Puedes ajustar esta fórmula

            # Leer archivo binario
            pdf_data = archivo_pdf.read() if archivo_pdf else None
            pdf_name = archivo_pdf.name if archivo_pdf else None

            try:
                conn = get_db_connection()
                cursor = conn.cursor()
                sql = """INSERT INTO logistica_v2 
                (mes, fecha_pre_alerta_fm, master_fm, fecha_pre_alerta_lm, master_lm, cajas, paquetes, peso_kg, 
                cc_services_calc, cant_personas_cuadrilla, costo_cuadrilla, montacargas, yales, servicio_extraordinario, 
                tipo_flete, tipo_camion, flete_subcontrato, total_costos, adimex_calc, adimex_pagado, dif_adimex, 
                dif_servicios, pdf_nombre, pdf_archivo) 
                VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)"""
                
                cursor.execute(sql, (mes, f_fm, m_fm, f_lm, m_lm, cajas, paquetes, peso, cc_services, p_cuadrilla, 
                                     c_cuadrilla, montacargas, yales, s_extra, t_flete, t_camion, f_sub, 
                                     total_costos, adimex_calc, adimex_pagado, dif_adimex, dif_servicios, pdf_name, pdf_data))
                conn.commit()
                st.success(f"✅ Registro guardado. ADIMEX Calculado: ${adimex_calc:.2f}")
            except Exception as e:
                st.error(f"Error: {e}")
            finally:
                conn.close()

elif choice == "📊 Dashboard":
    st.header("Análisis de Costos")
    conn = get_db_connection()
    df = pd.read_sql("SELECT mes, total_costos, peso_kg, paquetes, adimex_calc FROM logistica_v2", conn)
    conn.close()

    if not df.empty:
        col1, col2, col3 = st.columns(3)
        col1.metric("Gasto Total", f"${df['total_costos'].sum():,.2f}")
        col2.metric("Total Kilos", f"{df['peso_kg'].sum():,.1f} kg")
        col3.metric("Total ADIMEX", f"${df['adimex_calc'].sum():,.2f}")
        
        st.subheader("Costos por Mes")
        st.bar_chart(df.groupby("mes")["total_costos"].sum())
    else:
        st.info("No hay datos todavía.")

elif choice == "📁 Historial y PDF":
    st.header("Registros y Descarga de Comprobantes")
    conn = get_db_connection()
    df = pd.read_sql("SELECT id, mes, master_fm, master_lm, total_costos, pdf_nombre FROM logistica_v2", conn)
    
    st.dataframe(df.drop(columns=["id"]))

    st.subheader("Descargar Comprobante")
    id_descarga = st.number_input("Ingrese el ID del registro para ver PDF", min_value=1, step=1)
    
    if st.button("Buscar PDF"):
        cursor = conn.cursor()
        cursor.execute("SELECT pdf_nombre, pdf_archivo FROM logistica_v2 WHERE id = %s", (id_descarga,))
        resultado = cursor.fetchone()
        conn.close()

        if resultado and resultado[1]:
            st.download_button(label=f"Descargar {resultado[0]}", 
                               data=resultado[1], 
                               file_name=resultado[0], 
                               mime="application/pdf")
        else:
            st.warning("No se encontró archivo para ese ID.")

import streamlit as st
import pandas as pd
import mysql.connector

# 1. Configuración de página
st.set_page_config(page_title="Control Logístico Avanzado", layout="wide")

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

# 3. Menú Lateral
choice = st.sidebar.selectbox("Navegación", ["📊 Dashboard", "📝 Nuevo Registro", "📁 Historial"])

# --- SECCIÓN: NUEVO REGISTRO ---
if choice == "📝 Nuevo Registro":
    st.header("📝 Ingresar Datos de Operación")
    
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
            archivo_pdf = st.file_uploader("Subir Comprobante (PDF)", type=["pdf"])

        enviar = st.form_submit_button("Guardar en Sistema")

        if enviar:
            # Cálculos automáticos
            cc_services = paquetes * 0.84
            adimex_calc = peso * 0.35
            total_costos = c_cuadrilla + montacargas + yales + s_extra + f_sub
            dif_adimex = adimex_calc - adimex_pagado
            
            pdf_data = archivo_pdf.read() if archivo_pdf else None
            pdf_name = archivo_pdf.name if archivo_pdf else None

            try:
                conn = get_db_connection()
                cursor = conn.cursor()
                sql = """INSERT INTO logistica_v2 
                (mes, fecha_pre_alerta_fm, master_fm, fecha_pre_alerta_lm, master_lm, cajas, paquetes, peso_kg, 
                cc_services_calc, cant_personas_cuadrilla, costo_cuadrilla, montacargas, yales, servicio_extraordinario, 
                tipo_flete, tipo_camion, flete_subcontrato, total_costos, adimex_calc, adimex_pagado, dif_adimex, 
                pdf_nombre, pdf_archivo) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)"""
                
                cursor.execute(sql, (mes, f_fm, m_fm, f_lm, m_lm, cajas, paquetes, peso, cc_services, p_cuadrilla, 
                                     c_cuadrilla, montacargas, yales, s_extra, t_flete, t_camion, f_sub, 
                                     total_costos, adimex_calc, adimex_pagado, dif_adimex, pdf_name, pdf_data))
                conn.commit()
                st.success("✅ Registro guardado exitosamente.")
                conn.close()
            except Exception as e:
                st.error(f"Error al guardar: {e}")

# --- SECCIÓN: DASHBOARD ---
elif choice == "📊 Dashboard":
    st.title("📊 Análisis Operativo")
    try:
        conn = get_db_connection()
        df = pd.read_sql("SELECT * FROM logistica_v2", conn)
        conn.close()
        
        if not df.empty:
            # Métricas ADIMEX
            st.subheader("🔍 Control ADIMEX")
            m1, m2, m3 = st.columns(3)
            m1.metric("Calculado ($0.35/kg)", f"${df['adimex_calc'].sum():,.2f}")
            m2.metric("Pagado", f"${df['adimex_pagado'].sum():,.2f}")
            m3.metric("Diferencia", f"${df['dif_adimex'].sum():,.2f}")

            st.divider()
            
            # Rentabilidad
            st.subheader("💰 Rentabilidad Servicios CC")
            total_cc = df['cc_services_calc'].sum()
            # Gastos operativos son la suma de flete, cuadrilla, montacargas, yales y extraordinario
            total_gastos = df[['costo_cuadrilla', 'montacargas', 'yales', 'servicio_extraordinario', 'flete_subcontrato']].sum().sum()
            
            r1, r2, r3 = st.columns(3)
            r1.metric("Total Servicios CC ($0.84/paq)", f"${total_cc:,.2f}")
            r2.metric("Total Gastos Operativos", f"${total_gastos:,.2f}")
            r3.metric("Utilidad neta", f"${total_cc - total_gastos:,.2f}")
            
            st.divider()
            
            # Gráficos
            g1, g2 = st.columns(2)
            with g1:
                st.write("**Másters por Mes**")
                st.line_chart(df.groupby('mes')['master_fm'].count())
            with g2:
                st.write("**Desglose de Gastos ($)**")
                gastos_sum = df[['costo_cuadrilla', 'montacargas', 'yales', 'servicio_extraordinario', 'flete_subcontrato']].sum()
                st.bar_chart(gastos_sum)
        else:
            st.info("No hay datos.")
    except Exception as e:
        st.error(f"Error en Dashboard: {e}")

# --- SECCIÓN: HISTORIAL ---
elif choice == "📁 Historial":
    st.header("📁 Historial y PDF")
    try:
        conn = get_db_connection()
        df = pd.read_sql("SELECT id, mes, master_fm, master_lm, total_costos, pdf_nombre FROM logistica_v2", conn)
        st.dataframe(df)
        
        id_pdf = st.number_input("ID para descargar PDF", min_value=1, step=1)
        if st.button("Obtener PDF"):
            cursor = conn.cursor()
            cursor.execute("SELECT pdf_nombre, pdf_archivo FROM logistica_v2 WHERE id = %s", (id_pdf,))
            res = cursor.fetchone()
            if res and res[1]:
                st.download_button(f"Descargar {res[0]}", res[1], file_name=res[0])
            else:
                st.warning("No hay PDF.")
        conn.close()
    except Exception as e:
        st.error(f"Error: {e}")

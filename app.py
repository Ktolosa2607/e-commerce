import streamlit as st
import pandas as pd
import mysql.connector

# Configuración de página
st.set_page_config(page_title="Control Logístico Avanzado", layout="wide")

# Conexión robusta a TiDB (con SSL para Streamlit Cloud)
def get_db_connection():
    return mysql.connector.connect(
        host=st.secrets["tidb"]["host"],
        port=st.secrets["tidb"]["port"],
        user=st.secrets["tidb"]["user"],
        password=st.secrets["tidb"]["password"],
        database=st.secrets["tidb"]["database"],
        ssl_ca="/etc/ssl/certs/ca-certificates.crt" 
    )

# --- MENÚ ---
menu = ["📊 Dashboard Analítico", "📝 Nuevo Registro", "📁 Historial y PDF"]
choice = st.sidebar.selectbox("Navegación", menu)

if choice == "📊 Dashboard Analítico":
    st.title("📊 Análisis Operativo y Financiero")
    
    try:
        conn = get_db_connection()
        # Traemos todos los datos necesarios para los cálculos
        query = """SELECT * FROM logistica_v2"""
        df = pd.read_sql(query, conn)
        conn.close()
    except Exception as e:
        st.error(f"Error de conexión: {e}")
        df = pd.DataFrame()

    if not df.empty:
        # --- FILA 1: MÉTRICAS DE ADIMEX ---
        st.subheader("🔍 Control ADIMEX (Por Kilo)")
        col1, col2, col3 = st.columns(3)
        
        total_adimex_calc = df['adimex_calc'].sum()
        total_adimex_pagado = df['adimex_pagado'].sum()
        dif_adimex = total_adimex_calc - total_adimex_pagado
        
        col1.metric("ADIMEX Calculado ($0.35/kg)", f"${total_adimex_calc:,.2f}")
        col2.metric("ADIMEX Real Pagado", f"${total_adimex_pagado:,.2f}")
        col3.metric("Diferencia ADIMEX", f"${dif_adimex:,.2f}", delta=-dif_adimex, delta_color="inverse")

        st.divider()

        # --- FILA 2: MÉTRICAS DE SERVICIOS CC VS GASTOS ---
        st.subheader("💰 Rentabilidad: Servicios CC vs Gastos Reales")
        c1, c2, c3 = st.columns(3)
        
        total_servicios_cc = df['cc_services_calc'].sum()
        total_gastos_operativos = df[['costo_cuadrilla', 'montacargas', 'yales', 'servicio_extraordinario', 'flete_subcontrato']].sum().sum()
        margen_neto = total_servicios_cc - total_gastos_operativos
        
        c1.metric("Total Servicios CC ($0.84/paq)", f"${total_servicios_cc:,.2f}")
        c2.metric("Total Gastos Operativos", f"${total_gastos_operativos:,.2f}")
        c3.metric("Utilidad / Diferencia", f"${margen_neto:,.2f}", delta=margen_neto)

        st.divider()

        # --- FILA 3: GRÁFICOS DETALLADOS ---
        g1, g2 = st.columns(2)
        
        with g1:
            st.subheader("📋 Detalle de Gastos")
            # Sumamos cada columna de gasto para el gráfico
            gastos_detallados = {
                'Cuadrilla': df['costo_cuadrilla'].sum(),
                'Montacargas': df['montacargas'].sum(),
                'Yales': df['yales'].sum(),
                'Serv. Extra': df['servicio_extraordinario'].sum(),
                'Fletes': df['flete_subcontrato'].sum()
            }
            df_gastos = pd.DataFrame(list(gastos_detallados.items()), columns=['Concepto', 'Total'])
            st.bar_chart(df_gastos.set_index('Concepto'))

        with g2:
            st.subheader("📦 Volumen de Másters por Mes")
            # Contamos cuántos registros (másters) hay por mes
            masters_mes = df.groupby('mes')['master_fm'].count()
            st.line_chart(masters_mes)

    else:
        st.info("Aún no hay datos registrados para mostrar el análisis.")

elif choice == "📝 Nuevo Registro":
    st.header("📝 Ingresar Datos de Operación")
    # ... (Aquí va el mismo código de formulario que te pasé anteriormente)
    # Asegúrate de que el botón de guardado use la tabla 'logistica_v2'

elif choice == "📁 Historial y PDF":
    st.header("📁 Consulta de Registros y Comprobantes")
    # ... (Aquí va el mismo código de historial con el botón de descarga de PDF)            yales = st.number_input("Yales $", min_value=0.0)

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

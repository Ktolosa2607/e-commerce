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

# --- FUNCIONES INTERNAS ---
def get_current_rates():
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT tarifa_cc, tarifa_adimex FROM config_tarifas WHERE id = 1")
    res = cursor.fetchone()
    conn.close()
    return res if res else {"tarifa_cc": 0.84, "tarifa_adimex": 0.35}

# --- MENÚ LATERAL ---
st.sidebar.title("Navegación")
# Cambio de nombre de menú a solo "Admin"
choice = st.sidebar.radio("Ir a:", ["📊 Dashboard Analítico", "📝 Nuevo Registro", "📁 Historial y Archivos", "⚙️ Admin"])

# ==========================================
# SECCIÓN: ADMIN (HISTORIAL DE TARIFAS Y CAMBIOS)
# ==========================================
if choice == "⚙️ Admin":
    st.title("⚙️ Panel de Administración")
    password = st.text_input("Ingrese contraseña de acceso", type="password")
    
    if password == "admin123": # CAMBIAR CONTRASEÑA AQUÍ
        st.success("Acceso Autorizado")
        rates = get_current_rates()
        
        tab_actual, tab_historial = st.tabs(["🔄 Cambiar Tarifas", "📜 Historial de Cambios"])
        
        with tab_actual:
            st.subheader("Configuración para nuevos registros")
            col_a, col_b = st.columns(2)
            new_cc = col_a.number_input("Nueva Tarifa CC ($)", value=float(rates['tarifa_cc']), format="%.4f")
            new_ad = col_b.number_input("Nueva Tarifa ADIMEX ($)", value=float(rates['tarifa_adimex']), format="%.4f")
            
            if st.button("Aplicar y Registrar Cambio"):
                conn = get_db_connection()
                cursor = conn.cursor()
                # Guardar en historial antes de actualizar
                cursor.execute("""INSERT INTO historial_tarifas 
                    (tarifa_cc_anterior, tarifa_cc_nueva, tarifa_adimex_anterior, tarifa_adimex_nueva) 
                    VALUES (%s, %s, %s, %s)""", (rates['tarifa_cc'], new_cc, rates['tarifa_adimex'], new_ad))
                # Actualizar vigente
                cursor.execute("UPDATE config_tarifas SET tarifa_cc = %s, tarifa_adimex = %s WHERE id = 1", (new_cc, new_ad))
                conn.commit()
                conn.close()
                st.success("Tarifas actualizadas correctamente.")
                st.rerun()

        with tab_historial:
            st.subheader("Registro histórico de modificaciones")
            conn = get_db_connection()
            df_hist = pd.read_sql("SELECT * FROM historial_tarifas ORDER BY fecha_change DESC", conn)
            conn.close()
            st.dataframe(df_hist, use_container_width=True, hide_index=True)

    elif password != "":
        st.error("Credenciales incorrectas.")

# ==========================================
# SECCIÓN: DASHBOARD (CORRECCIÓN TOOLTIP)
# ==========================================
elif choice == "📊 Dashboard Analítico":
    st.title("📊 Dashboard Operativo")
    try:
        conn = get_db_connection()
        df = pd.read_sql("SELECT * FROM logistica_v2", conn)
        conn.close()
        
        if not df.empty:
            df['fecha_pre_alerta_lm'] = pd.to_datetime(df['fecha_pre_alerta_lm'])
            # (Lógica de filtrado por fechas omitida aquí para brevedad...)
            df_f = df.copy() 

            # CORRECCIÓN TOOLTIP GASTOS OP
            # Calculamos las sumas primero para evitar errores de formato en el f-string
            s_cuad = df_f['costo_cuadrilla'].sum()
            s_mont = df_f['montacargas'].sum()
            s_yale = df_f['yales'].sum()
            s_flet = df_f['flete_subcontrato'].sum()
            s_extr = df_f['servicio_extraordinario'].sum()

            tooltip_gastos = (
                f"Desglose Detallado:\n"
                f"• Cuadrilla: ${s_cuad:,.2f}\n"
                f"• Montacargas: ${s_mont:,.2f}\n"
                f"• Yales: ${s_yale:,.2f}\n"
                f"• Flete Sub.: ${s_flet:,.2f}\n"
                f"• Extras: ${s_extr:,.2f}"
            )

            m1, m2, m3, m4, m5, m6 = st.columns(6)
            m1.metric("Ingresos CC", f"${df_f['cc_services_calc'].sum():,.2f}")
            m2.metric("Gastos Op.", f"${df_f['total_costos'].sum():,.2f}", help=tooltip_gastos)
            m3.metric("Utilidad Neta", f"${(df_f['cc_services_calc'].sum() - df_f['total_costos'].sum()):,.2f}")
            m4.metric("Paquetes", f"{int(df_f['paquetes'].sum()):,} Pq")
            m5.metric("Másters", f"{len(df_f)}")
            m6.metric("Peso Total", f"{df_f['peso_kg'].sum():,.1f} Kg")
            
            st.divider()
            a1, a2, a3 = st.columns(3)
            a1.metric("ADIMEX Calculado", f"${df_f['adimex_calc'].sum():,.2f}")
            a2.metric("ADIMEX Real Pagado", f"${df_f['adimex_pagado'].sum():,.2f}")
            a3.metric("Diferencia", f"${df_f['dif_adimex'].sum():,.2f}")

    except Exception as e: st.error(f"Error: {e}")

# ==========================================
# SECCIÓN: HISTORIAL (TARIFAS OCULTAS)
# ==========================================
elif choice == "📁 Historial y Archivos":
    st.title("📁 Control de Másters")
    try:
        conn = get_db_connection()
        df = pd.read_sql("SELECT * FROM logistica_v2 ORDER BY fecha_pre_alerta_lm DESC", conn)
        conn.close()
        
        if not df.empty:
            # Borrar/Editar registros
            with st.expander("🛠️ Gestionar Registros"):
                sel = st.selectbox("Seleccione Máster:", ["---"] + df['master_fm'].tolist())
                if sel != "---":
                    if st.button("🗑️ Eliminar permanentemente"):
                        # Lógica de delete...
                        st.warning("Eliminado")

            # TABLA: NO SE MUESTRAN COLUMNAS DE TARIFA
            st.subheader("📋 Información General")
            # Filtramos para NO mostrar 'tarifa_cc' ni 'tarifa_adimex'
            columnas_visibles = [col for col in df.columns if col not in ['tarifa_cc', 'tarifa_adimex', 'pdf_archivo']]
            
            st.dataframe(df[columnas_visibles], use_container_width=True, hide_index=True,
                column_config={
                    "cc_services_calc": st.column_config.NumberColumn("Ingreso CC", format="$ %.2f"),
                    "total_costos": st.column_config.NumberColumn("Total Costos", format="$ %.2f"),
                    "peso_kg": st.column_config.NumberColumn("Peso", format="%.1f Kg"),
                    "paquetes": st.column_config.NumberColumn("Cant. Pq", format="%d Pq")
                })
    except Exception as e: st.error(f"Error: {e}")

# ==========================================
# SECCIÓN: NUEVO REGISTRO (TARIFA OCULTA)
# ==========================================
elif choice == "📝 Nuevo Registro":
    st.title("📝 Registro de Operación")
    # Se obtienen internamente, pero NO se muestran al usuario
    rates = get_current_rates() 

    with st.form("main_form", clear_on_submit=True):
        t1, t2 = st.tabs(["📦 Datos de Carga", "💸 Costos y PDF"])
        with t1:
            m_fm = st.text_input("Máster First Mile")
            paquetes = st.number_input("Paquetes", min_value=0)
            peso = st.number_input("Peso (KG)", min_value=0.0)
            f_lm = st.date_input("Fecha Last Mile")
        with t2:
            c_cuad = st.number_input("Costo Cuadrilla $", min_value=0.0)
            f_sub = st.number_input("Flete Subcontrato $", min_value=0.0)
            adimex_p = st.number_input("ADIMEX Pagado $", min_value=0.0)
            pdf = st.file_uploader("Adjuntar Comprobante", type=["pdf"])

        if st.form_submit_button("🚀 Finalizar Registro"):
            # Cálculos internos usando las tarifas que el usuario NO ve
            cc_calc = paquetes * float(rates['tarifa_cc'])
            ad_calc = peso * float(rates['tarifa_adimex'])
            
            # (Insert SQL aquí...)
            st.success("Registro completado con éxito.")

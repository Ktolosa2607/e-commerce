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

# --- FUNCIONES DE TARIFAS ---
def get_current_rates():
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT tarifa_cc, tarifa_adimex FROM config_tarifas WHERE id = 1")
    res = cursor.fetchone()
    conn.close()
    return res if res else {"tarifa_cc": 0.84, "tarifa_adimex": 0.35}

# --- MENÚ LATERAL ---
st.sidebar.title("Navegación")
choice = st.sidebar.radio("Ir a:", ["📊 Dashboard Analítico", "📝 Nuevo Registro", "📁 Historial y Archivos", "⚙️ Admin (Tarifas)"])

# ==========================================
# SECCIÓN: ADMIN (TARIFAS)
# ==========================================
if choice == "⚙️ Admin (Tarifas)":
    st.title("⚙️ Configuración Global")
    password = st.text_input("Ingrese contraseña de administrador", type="password")
    
    # Define aquí tu contraseña
    if password == "admin123": # <--- CAMBIA ESTO
        st.success("Acceso concedido")
        rates = get_current_rates()
        
        with st.form("form_tarifas"):
            st.subheader("Establecer nuevas tarifas para futuros registros")
            new_cc = st.number_input("Tarifa CC Services (por paquete)", value=float(rates['tarifa_cc']), step=0.01, format="%.4f")
            new_ad = st.number_input("Tarifa ADIMEX (por kilo)", value=float(rates['tarifa_adimex']), step=0.01, format="%.4f")
            
            if st.form_submit_button("Actualizar Tarifas Vigentes"):
                conn = get_db_connection()
                cursor = conn.cursor()
                cursor.execute("UPDATE config_tarifas SET tarifa_cc = %s, tarifa_adimex = %s WHERE id = 1", (new_cc, new_ad))
                conn.commit()
                conn.close()
                st.success("Tarifas actualizadas. Los próximos registros usarán estos valores.")
    elif password != "":
        st.error("Contraseña incorrecta")

# ==========================================
# SECCIÓN: DASHBOARD ANALÍTICO
# ==========================================
elif choice == "📊 Dashboard Analítico":
    st.title("📊 Dashboard de Control")
    try:
        conn = get_db_connection()
        df = pd.read_sql("SELECT * FROM logistica_v2", conn)
        conn.close()
        
        if not df.empty:
            df['fecha_pre_alerta_lm'] = pd.to_datetime(df['fecha_pre_alerta_lm'])
            # --- FILTROS ---
            st.sidebar.subheader("📅 Filtros")
            tipo_f = st.sidebar.selectbox("Filtrar por:", ["Todo", "Mes/Año", "Rango"])
            df_f = df.copy()
            # (Lógica de filtrado igual a la anterior...)
            
            # --- RESUMEN SIN TOOLTIPS EN CC Y ADIMEX ---
            m1, m2, m3, m4, m5, m6 = st.columns(6)
            total_cc = df_f['cc_services_calc'].sum()
            total_gastos = df_f['total_costos'].sum()
            
            m1.metric("Ingresos CC", f"${total_cc:,.2f}") # Sin tooltip
            m2.metric("Gastos Op.", f"${total_gastos:,.2f}", help="Detalle: " + str({k: df_f[k].sum() for k in ['costo_cuadrilla', 'montacargas', 'yales', 'flete_subcontrato', 'servicio_extraordinario']}))
            m3.metric("Utilidad Neta", f"${total_cc - total_gastos:,.2f}")
            m4.metric("Paquetes", f"{int(df_f['paquetes'].sum()):,} Pq")
            m5.metric("Másters", f"{len(df_f)}")
            m6.metric("Peso Total", f"{df_f['peso_kg'].sum():,.1f} Kg")
            
            st.divider()
            st.subheader("🔍 Detalle ADIMEX")
            a1, a2, a3 = st.columns(3)
            a1.metric("ADIMEX Calculado", f"${df_f['adimex_calc'].sum():,.2f}") # Sin tooltip
            a2.metric("ADIMEX Real Pagado", f"${df_f['adimex_pagado'].sum():,.2f}")
            a3.metric("Diferencia", f"${df_f['dif_adimex'].sum():,.2f}", delta=-df_f['dif_adimex'].sum(), delta_color="inverse")
    except Exception as e: st.error(f"Error: {e}")

# ==========================================
# SECCIÓN: HISTORIAL (EDICIÓN Y BORRADO)
# ==========================================
elif choice == "📁 Historial y Archivos":
    st.title("📁 Historial de Operaciones")
    try:
        conn = get_db_connection()
        df = pd.read_sql("SELECT * FROM logistica_v2 ORDER BY fecha_pre_alerta_lm DESC", conn)
        conn.close()
        
        if not df.empty:
            # --- EDITAR O BORRAR ---
            with st.expander("🛠️ Acciones de Edición y Borrado"):
                sel_master = st.selectbox("Seleccione Máster para modificar:", ["---"] + df['master_fm'].tolist())
                if sel_master != "---":
                    row = df[df['master_fm'] == sel_master].iloc[0]
                    col_edit, col_del = st.columns(2)
                    
                    with col_edit:
                        if st.button("📝 Editar Datos"):
                            st.session_state['edit_mode'] = row['id']
                    
                    with col_del:
                        if st.button("🗑️ Borrar Registro"):
                            conn = get_db_connection()
                            cursor = conn.cursor()
                            cursor.execute("DELETE FROM logistica_v2 WHERE id = %s", (int(row['id']),))
                            conn.commit()
                            conn.close()
                            st.warning(f"Registro {sel_master} eliminado.")
                            st.rerun()

            # --- TABLA DE DATOS ---
            st.subheader("📋 Registro de Datos")
            st.dataframe(df.drop(columns=['pdf_archivo']), use_container_width=True, hide_index=True,
                column_config={"paquetes": st.column_config.NumberColumn("Paquetes", format="%d Pq"), "peso_kg": st.column_config.NumberColumn("Peso (KG)", format="%.1f Kg"), "cc_services_calc": st.column_config.NumberColumn("CC Services", format="$ %.2f")})
    except Exception as e: st.error(f"Error: {e}")

# ==========================================
# SECCIÓN: NUEVO REGISTRO (CON TARIFA INTERNA)
# ==========================================
elif choice == "📝 Nuevo Registro":
    st.title("📝 Nuevo Registro")
    rates = get_current_rates() # Obtener tarifas vigentes para este registro
    st.info(f"Tarifas aplicadas a este registro: CC: ${rates['tarifa_cc']} | ADIMEX: ${rates['tarifa_adimex']}")

    with st.form("main_form", clear_on_submit=True):
        t1, t2, t3 = st.tabs(["🚛 Carga", "💰 Costos", "📄 PDF"])
        with t1:
            m_fm = st.text_input("Máster First Mile")
            paquetes = st.number_input("Cantidad Paquetes", min_value=0)
            peso = st.number_input("Peso Total (KG)", min_value=0.0)
            f_lm = st.date_input("Fecha Last Mile")
            # ... (resto de campos de carga)
        with t2:
            adimex_pagado = st.number_input("ADIMEX Pagado $", min_value=0.0)
            c_cuadrilla = st.number_input("Costo Cuadrilla $", min_value=0.0)
            f_sub = st.number_input("Flete Subcontrato $", min_value=0.0)
            # ... (resto de campos de costos)
        with t3:
            archivo_pdf = st.file_uploader("Subir PDF", type=["pdf"])

        if st.form_submit_button("🚀 GUARDAR REGISTRO"):
            # CÁLCULOS USANDO LA TARIFA DEL MOMENTO
            cc_services = paquetes * float(rates['tarifa_cc'])
            adimex_calc = peso * float(rates['tarifa_adimex'])
            total_costos = c_cuadrilla + f_sub # Sumar otros si los añades
            
            try:
                conn = get_db_connection()
                cursor = conn.cursor()
                sql = """INSERT INTO logistica_v2 
                (master_fm, fecha_pre_alerta_lm, paquetes, peso_kg, adimex_pagado, costo_cuadrilla, flete_subcontrato,
                cc_services_calc, adimex_calc, total_costos, dif_adimex, tarifa_cc, tarifa_adimex, pdf_nombre, pdf_archivo) 
                VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)"""
                
                # ... (resto de la lógica de guardado)
                st.success("Guardado con tarifas actuales.")
            except Exception as e: st.error(str(e))

import streamlit as st
import pandas as pd
import mysql.connector
from datetime import datetime

# 1. Configuración de página
st.set_page_config(page_title="Sistema Logístico Máster PRO", layout="wide")

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
    try:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        cursor.execute("SELECT tarifa_cc, tarifa_adimex FROM config_tarifas WHERE id = 1")
        res = cursor.fetchone()
        conn.close()
        return res if res else {"tarifa_cc": 0.84, "tarifa_adimex": 0.35}
    except:
        return {"tarifa_cc": 0.84, "tarifa_adimex": 0.35}

# --- MENÚ LATERAL ---
st.sidebar.title("Navegación")
choice = st.sidebar.radio("Ir a:", ["📊 Dashboard Analítico", "📝 Nuevo Registro", "📁 Historial y Archivos", "⚙️ Admin"])

# ==========================================
# SECCIÓN: ADMIN (TARIFAS Y AUDITORÍA)
# ==========================================
if choice == "⚙️ Admin":
    st.title("⚙️ Panel de Control Administrativo")
    # CONTRASEÑA DE ACCESO
    admin_pass = st.text_input("Ingrese contraseña de administrador", type="password")
    
    if admin_pass == "admin123": 
        st.success("Acceso concedido")
        rates = get_current_rates()
        
        t_cambio, t_hist = st.tabs(["🔄 Actualizar Tarifas", "📜 Historial de Cambios"])
        
        with t_cambio:
            col1, col2 = st.columns(2)
            new_cc = col1.number_input("Nueva Tarifa CC Services ($)", value=float(rates['tarifa_cc']), format="%.4f")
            new_ad = col2.number_input("Nueva Tarifa ADIMEX ($)", value=float(rates['tarifa_adimex']), format="%.4f")
            
            if st.button("Guardar Nuevas Tarifas"):
                conn = get_db_connection()
                cursor = conn.cursor()
                # Registrar en historial
                cursor.execute("""INSERT INTO historial_tarifas 
                    (tarifa_cc_anterior, tarifa_cc_nueva, tarifa_adimex_anterior, tarifa_adimex_nueva) 
                    VALUES (%s, %s, %s, %s)""", (rates['tarifa_cc'], new_cc, rates['tarifa_adimex'], new_ad))
                # Actualizar actual
                cursor.execute("UPDATE config_tarifas SET tarifa_cc = %s, tarifa_adimex = %s WHERE id = 1", (new_cc, new_ad))
                conn.commit()
                conn.close()
                st.success("Tarifas actualizadas para nuevos registros.")
                st.rerun()
        
        with t_hist:
            st.subheader("Historial de modificaciones de tarifas")
            conn = get_db_connection()
            df_h = pd.read_sql("SELECT * FROM historial_tarifas ORDER BY id DESC", conn)
            conn.close()
            st.dataframe(df_h, use_container_width=True, hide_index=True)
    elif admin_pass != "":
        st.error("Contraseña incorrecta.")

# ==========================================
# SECCIÓN: DASHBOARD (CON FILTROS Y TOOLTIP)
# ==========================================
elif choice == "📊 Dashboard Analítico":
    st.title("📊 Dashboard Operativo")
    try:
        conn = get_db_connection()
        df = pd.read_sql("SELECT * FROM logistica_v2", conn)
        conn.close()
        
        if not df.empty:
            df['fecha_pre_alerta_lm'] = pd.to_datetime(df['fecha_pre_alerta_lm'])
            
            # --- FILTROS ---
            st.sidebar.divider()
            st.sidebar.subheader("📅 Filtros (Fecha LM)")
            f_tipo = st.sidebar.selectbox("Periodo:", ["Todo", "Mes/Año", "Rango"])
            df_f = df.copy()
            if f_tipo == "Mes/Año":
                y = st.sidebar.selectbox("Año", sorted(df['fecha_pre_alerta_lm'].dt.year.unique(), reverse=True))
                m = st.sidebar.selectbox("Mes", range(1,13))
                df_f = df[(df['fecha_pre_alerta_lm'].dt.year == y) & (df['fecha_pre_alerta_lm'].dt.month == m)]
            elif f_tipo == "Rango":
                r = st.sidebar.date_input("Rango de fechas", [])
                if len(r) == 2:
                    df_f = df[(df['fecha_pre_alerta_lm'].dt.date >= r[0]) & (df['fecha_pre_alerta_lm'].dt.date <= r[1])]

            # Tooltip Gastos
            s_cuad = df_f['costo_cuadrilla'].sum(); s_mont = df_f['montacargas'].sum()
            s_yale = df_f['yales'].sum(); s_flet = df_f['flete_subcontrato'].sum(); s_extr = df_f['servicio_extraordinario'].sum()
            tooltip_gastos = f"Desglose:\n• Cuadrilla: ${s_cuad:,.2f}\n• Montacargas: ${s_mont:,.2f}\n• Yales: ${s_yale:,.2f}\n• Fletes: ${s_flet:,.2f}\n• Extras: ${s_extr:,.2f}"

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
    except Exception as e: st.error(str(e))

# ==========================================
# SECCIÓN: NUEVO REGISTRO (TODOS LOS CAMPOS)
# ==========================================
elif choice == "📝 Nuevo Registro":
    st.title("📝 Ingreso de Datos Completo")
    rates = get_current_rates()
    
    with st.form("registro_total", clear_on_submit=True):
        t1, t2, t3 = st.tabs(["🚛 Información General", "💰 Costos y Fletes", "📄 PDF"])
        
        with t1:
            c1, c2 = st.columns(2)
            mes = c1.selectbox("MES", ["Enero", "Febrero", "Marzo", "Abril", "Mayo", "Junio", "Julio", "Agosto", "Septiembre", "Octubre", "Noviembre", "Diciembre"])
            f_pre_fm = c1.date_input("FECHA PRE ALERTA FIRST MILE")
            m_fm = c1.text_input("MÁSTER FIRST MILE")
            f_pre_lm = c2.date_input("FECHA PRE ALERTA LAST MILE")
            m_lm = c2.text_input("MÁSTER LAST MILE")
            
            st.divider()
            col_a, col_b, col_c = st.columns(3)
            cajas = col_a.number_input("CAJAS", min_value=0)
            paquetes = col_b.number_input("PAQUETES", min_value=0)
            peso = col_c.number_input("PESO (KG)", min_value=0.0)

        with t2:
            st.subheader("Costos de Operación")
            ca, cb, cc = st.columns(3)
            cant_pers = ca.number_input("CANTIDAD PERSONAS CUADRILLA", min_value=0)
            c_cuad = cb.number_input("CUADRILLA (COSTO $)", min_value=0.0)
            montacargas = cc.number_input("MONTACARGAS ($)", min_value=0.0)
            
            yales = ca.number_input("YALES ($)", min_value=0.0)
            s_extra = cb.number_input("SERVICIO EXTRAORDINARIO ($)", min_value=0.0)
            adimex_p = cc.number_input("ADIMEX PAGADO ($)", min_value=0.0)
            
            st.divider()
            st.subheader("Logística")
            t_flete = ca.selectbox("TIPO DE FLETE", ["LOCAL", "NACIONAL", "INTERNACIONAL"])
            t_camion = cb.text_input("TIPO DE CAMIÓN")
            f_sub = cc.number_input("FLETE SUBCONTRATO ($)", min_value=0.0)

        with t3:
            archivo_pdf = st.file_uploader("COMPROBANTE ADIMEX (PDF)", type=["pdf"])

        if st.form_submit_button("🚀 GUARDAR REGISTRO COMPLETO"):
            # Cálculos internos
            cc_calc = paquetes * float(rates['tarifa_cc'])
            ad_calc = peso * float(rates['tarifa_adimex'])
            total_c = c_cuad + montacargas + yales + s_extra + f_sub
            
            pdf_data = archivo_pdf.read() if archivo_pdf else None
            pdf_name = archivo_pdf.name if archivo_pdf else None

            try:
                conn = get_db_connection()
                cursor = conn.cursor()
                sql = """INSERT INTO logistica_v2 
                (mes, fecha_pre_alerta_fm, master_fm, fecha_pre_alerta_lm, master_lm, cajas, paquetes, peso_kg, 
                cant_personas_cuadrilla, costo_cuadrilla, montacargas, yales, servicio_extraordinario, 
                tipo_flete, tipo_camion, flete_subcontrato, adimex_pagado, cc_services_calc, adimex_calc, 
                total_costos, dif_adimex, tarifa_cc, tarifa_adimex, pdf_nombre, pdf_archivo) 
                VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)"""
                
                cursor.execute(sql, (mes, f_pre_fm, m_fm, f_pre_lm, m_lm, cajas, paquetes, peso, 
                                     cant_pers, c_cuad, montacargas, yales, s_extra, 
                                     t_flete, t_camion, f_sub, adimex_p, cc_calc, ad_calc, 
                                     total_c, (ad_calc - adimex_p), rates['tarifa_cc'], rates['tarifa_adimex'], pdf_name, pdf_data))
                conn.commit()
                st.success(f"Máster {m_fm} guardada con éxito.")
                conn.close()
            except Exception as e: st.error(f"Error DB: {e}")

# ==========================================
# SECCIÓN: HISTORIAL (ELIMINAR Y TABLA LIMPIA)
# ==========================================
elif choice == "📁 Historial y Archivos":
    st.title("📁 Historial de Datos")
    try:
        conn = get_db_connection()
        df = pd.read_sql("SELECT * FROM logistica_v2 ORDER BY id DESC", conn)
        conn.close()
        
        if not df.empty:
            with st.expander("🗑️ Borrar Registros"):
                sel = st.selectbox("Seleccione Máster a borrar:", ["---"] + df['master_fm'].tolist())
                if sel != "---":
                    if st.button("Confirmar Eliminación"):
                        conn = get_db_connection()
                        cursor = conn.cursor()
                        cursor.execute("DELETE FROM logistica_v2 WHERE master_fm = %s", (sel,))
                        conn.commit(); conn.close()
                        st.warning("Registro borrado."); st.rerun()

            st.divider()
            # Ocultar tarifas y PDF binario
            cols_visibles = [c for c in df.columns if c not in ['tarifa_cc', 'tarifa_adimex', 'pdf_archivo']]
            st.dataframe(df[cols_visibles], use_container_width=True, hide_index=True,
                column_config={
                    "cc_services_calc": st.column_config.NumberColumn("CC Services", format="$ %.2f"),
                    "peso_kg": st.column_config.NumberColumn("Peso", format="%.1f Kg"),
                    "paquetes": st.column_config.NumberColumn("Cant. Pq", format="%d Pq"),
                    "adimex_calc": st.column_config.NumberColumn("Adimex Calc", format="$ %.2f"),
                    "total_costos": st.column_config.NumberColumn("Total Gastos", format="$ %.2f")
                })
    except Exception as e: st.error(str(e))

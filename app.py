import streamlit as st
import pandas as pd
import mysql.connector
from datetime import datetime

# --- CONFIGURACIÓN E INTERFAZ ---
st.set_page_config(page_title="Sistema Logístico Máster PRO", layout="wide")

def get_db_connection():
    return mysql.connector.connect(
        host=st.secrets["tidb"]["host"],
        port=st.secrets["tidb"]["port"],
        user=st.secrets["tidb"]["user"],
        password=st.secrets["tidb"]["password"],
        database=st.secrets["tidb"]["database"],
        ssl_ca="/etc/ssl/certs/ca-certificates.crt" 
    )

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

# --- NAVEGACIÓN ---
choice = st.sidebar.radio("Menú Principal", ["📊 Dashboard Analítico", "📝 Nuevo Registro", "📁 Historial y Gestión", "⚙️ Admin"])

# ==========================================
# SECCIÓN: DASHBOARD ANALÍTICO (COMPLETO)
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
            f_tipo = st.sidebar.selectbox("Filtrar por:", ["Todo", "Mes/Año", "Rango"])
            df_f = df.copy()
            if f_tipo == "Mes/Año":
                y = st.sidebar.selectbox("Año", sorted(df['fecha_pre_alerta_lm'].dt.year.unique(), reverse=True))
                m = st.sidebar.selectbox("Mes", range(1,13))
                df_f = df[(df['fecha_pre_alerta_lm'].dt.year == y) & (df['fecha_pre_alerta_lm'].dt.month == m)]
            elif f_tipo == "Rango":
                r = st.sidebar.date_input("Rango de fechas", [])
                if len(r) == 2:
                    df_f = df[(df['fecha_pre_alerta_lm'].dt.date >= r[0]) & (df['fecha_pre_alerta_lm'].dt.date <= r[1])]

            # Tooltip Gastos detallado
            g_cuad = df_f['costo_cuadrilla'].sum(); g_mont = df_f['montacargas'].sum()
            g_yale = df_f['yales'].sum(); g_flet = df_f['flete_subcontrato'].sum(); g_extr = df_f['servicio_extraordinario'].sum()
            
            tooltip_g = f"DESGLOSE DE GASTOS:\n• Cuadrilla: ${g_cuad:,.2f}\n• Montacargas: ${g_mont:,.2f}\n• Yales: ${g_yale:,.2f}\n• Fletes: ${g_flet:,.2f}\n• Extras: ${g_extr:,.2f}"

            st.subheader("💡 Resumen de Operación")
            m1, m2, m3, m4, m5, m6 = st.columns(6)
            m1.metric("Ingresos CC", f"${df_f['cc_services_calc'].sum():,.2f}")
            m2.metric("Gastos Op.", f"${df_f['total_costos'].sum():,.2f}", help=tooltip_g)
            m3.metric("Utilidad Neta", f"${(df_f['cc_services_calc'].sum() - df_f['total_costos'].sum()):,.2f}")
            m4.metric("Paquetes", f"{int(df_f['paquetes'].sum()):,} Pq")
            m5.metric("Másters", f"{len(df_f)}")
            m6.metric("Peso Total", f"{df_f['peso_kg'].sum():,.1f} Kg")
            
            st.divider()
            st.subheader("🔍 Control ADIMEX")
            a1, a2, a3 = st.columns(3)
            a1.metric("ADIMEX Calculado", f"${df_f['adimex_calc'].sum():,.2f}")
            a2.metric("ADIMEX Real Pagado", f"${df_f['adimex_pagado'].sum():,.2f}")
            a3.metric("Diferencia ADIMEX", f"${df_f['dif_adimex'].sum():,.2f}", delta=-df_f['dif_adimex'].sum(), delta_color="inverse")
        else: st.info("No hay datos registrados.")
    except Exception as e: st.error(f"Error: {e}")

# ==========================================
# SECCIÓN: NUEVO REGISTRO (TODOS LOS CAMPOS)
# ==========================================
elif choice == "📝 Nuevo Registro":
    st.title("📝 Registro de Operación Completo")
    rates = get_current_rates()
    
    with st.form("form_registro", clear_on_submit=True):
        t1, t2, t3 = st.tabs(["🚛 Información Carga", "💰 Costos y Fletes", "📄 Documento"])
        with t1:
            c1, c2 = st.columns(2)
            mes = c1.selectbox("Mes", ["Enero", "Febrero", "Marzo", "Abril", "Mayo", "Junio", "Julio", "Agosto", "Septiembre", "Octubre", "Noviembre", "Diciembre"])
            f_fm = c1.date_input("Fecha Pre Alerta First Mile")
            m_fm = c1.text_input("Máster First Mile")
            f_lm = c2.date_input("Fecha Pre Alerta Last Mile")
            m_lm = c2.text_input("Máster Last Mile")
            
            st.divider()
            cajas = st.number_input("Cajas", min_value=0)
            paq = st.number_input("Paquetes", min_value=0)
            peso = st.number_input("Peso (KG)", min_value=0.0)

        with t2:
            ca, cb, cc = st.columns(3)
            p_cuad = ca.number_input("Cant. Personas Cuadrilla", min_value=0)
            c_cuad = cb.number_input("Costo Cuadrilla $", min_value=0.0)
            mont = cc.number_input("Montacargas $", min_value=0.0)
            yale = ca.number_input("Yales $", min_value=0.0)
            extr = cb.number_input("Servicio Extraordinario $", min_value=0.0)
            ad_p = cc.number_input("ADIMEX Pagado $", min_value=0.0)
            
            st.divider()
            t_flete = ca.selectbox("Tipo de Flete", ["LOCAL", "NACIONAL", "FORÁNEO"])
            t_camion = cb.text_input("Tipo de Camión")
            f_sub = cc.number_input("Flete Subcontrato $", min_value=0.0)

        with t3:
            up_pdf = st.file_uploader("Subir Comprobante ADIMEX (PDF)", type="pdf")

        if st.form_submit_button("🚀 Guardar Registro"):
            cc_calc = paq * float(rates['tarifa_cc'])
            ad_calc = peso * float(rates['tarifa_adimex'])
            tot_c = c_cuad + mont + yale + extr + f_sub
            
            try:
                conn = get_db_connection()
                cursor = conn.cursor()
                sql = """INSERT INTO logistica_v2 (mes, fecha_pre_alerta_fm, master_fm, fecha_pre_alerta_lm, master_lm, 
                         cajas, paquetes, peso_kg, cant_personas_cuadrilla, costo_cuadrilla, montacargas, yales, 
                         servicio_extraordinario, tipo_flete, tipo_camion, flete_subcontrato, adimex_pagado, 
                         cc_services_calc, adimex_calc, total_costos, dif_adimex, dif_servicios, 
                         tarifa_cc, tarifa_adimex, pdf_nombre, pdf_archivo) 
                         VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)"""
                cursor.execute(sql, (mes, f_fm, m_fm, f_lm, m_lm, cajas, paq, peso, p_cuad, c_cuad, mont, yale, extr, 
                                     t_flete, t_camion, f_sub, ad_p, cc_calc, ad_calc, tot_c, (ad_calc-ad_p), (cc_calc-tot_c), 
                                     rates['tarifa_cc'], rates['tarifa_adimex'], up_pdf.name if up_pdf else None, up_pdf.read() if up_pdf else None))
                conn.commit(); conn.close()
                st.success("¡Registro guardado exitosamente!")
            except Exception as e: st.error(f"Error: {e}")

# ==========================================
# SECCIÓN: HISTORIAL Y GESTIÓN (EDICIÓN Y BORRADO)
# ==========================================
elif choice == "📁 Historial y Gestión":
    st.title("📁 Gestión de Registros")
    try:
        conn = get_db_connection()
        df = pd.read_sql("SELECT * FROM logistica_v2 ORDER BY id DESC", conn)
        conn.close()
        
        if not df.empty:
            sel_m = st.selectbox("Seleccione Máster FM:", ["---"] + df['master_fm'].tolist())
            if sel_m != "---":
                row = df[df['master_fm'] == sel_m].iloc[0]
                c1, c2, c3 = st.columns(3)
                if c1.button("🗑️ Borrar"):
                    conn = get_db_connection(); cur = conn.cursor()
                    cur.execute("DELETE FROM logistica_v2 WHERE id=%s", (int(row['id']),))
                    conn.commit(); conn.close(); st.rerun()
                if row['pdf_archivo']: c2.download_button("📥 Descargar PDF", row['pdf_archivo'], row['pdf_nombre'])
                
                with st.expander("📝 Editar Datos de este Registro"):
                    with st.form("edit_form"):
                        e_paq = st.number_input("Paquetes", value=int(row['paquetes']))
                        e_peso = st.number_input("Peso", value=float(row['peso_kg']))
                        e_ad_p = st.number_input("ADIMEX Pagado", value=float(row['adimex_pagado']))
                        e_cuad = st.number_input("Costo Cuadrilla", value=float(row['costo_cuadrilla']))
                        e_flete = st.number_input("Flete Sub", value=float(row['flete_subcontrato']))
                        e_extra = st.number_input("Extraordinario", value=float(row['servicio_extraordinario']))
                        e_pdf = st.file_uploader("Cambiar PDF", type="pdf")
                        
                        if st.form_submit_button("Actualizar Todo"):
                            # Recalcular usando tarifas originales del registro
                            n_cc = e_paq * float(row['tarifa_cc'])
                            n_ad = e_peso * float(row['tarifa_adimex'])
                            n_tot = e_cuad + e_flete + e_extra + float(row['montacargas']) + float(row['yales'])
                            
                            conn = get_db_connection(); cur = conn.cursor()
                            cur.execute("""UPDATE logistica_v2 SET paquetes=%s, peso_kg=%s, adimex_pagado=%s, costo_cuadrilla=%s, 
                                           flete_subcontrato=%s, servicio_extraordinario=%s, cc_services_calc=%s, adimex_calc=%s, 
                                           total_costos=%s, dif_adimex=%s, dif_servicios=%s WHERE id=%s""",
                                        (e_paq, e_peso, e_ad_p, e_cuad, e_flete, e_extra, n_cc, n_ad, n_tot, (n_ad-e_ad_p), (n_cc-n_tot), int(row['id'])))
                            if e_pdf: cur.execute("UPDATE logistica_v2 SET pdf_nombre=%s, pdf_archivo=%s WHERE id=%s", (e_pdf.name, e_pdf.read(), int(row['id'])))
                            conn.commit(); conn.close(); st.success("Registro Actualizado"); st.rerun()

            st.dataframe(df.drop(columns=['pdf_archivo', 'tarifa_cc', 'tarifa_adimex']), use_container_width=True, hide_index=True)
    except Exception as e: st.error(str(e))

# ==========================================
# SECCIÓN: ADMIN (TARIFAS)
# ==========================================
elif choice == "⚙️ Admin":
    st.title("⚙️ Administración de Tarifas")
    if st.text_input("Contraseña", type="password") == "admin123":
        rates = get_current_rates()
        t1, t2 = st.tabs(["Tarifas Vigentes", "Historial de Cambios"])
        with t1:
            n_cc = st.number_input("Tarifa CC Services", value=float(rates['tarifa_cc']), format="%.4f")
            n_ad = st.number_input("Tarifa ADIMEX", value=float(rates['tarifa_adimex']), format="%.4f")
            if st.button("Actualizar para nuevos registros"):
                conn = get_db_connection(); cur = conn.cursor()
                cur.execute("INSERT INTO historial_tarifas (tarifa_cc_anterior, tarifa_cc_nueva, tarifa_adimex_anterior, tarifa_adimex_nueva) VALUES (%s,%s,%s,%s)", (rates['tarifa_cc'], n_cc, rates['tarifa_adimex'], n_ad))
                cur.execute("UPDATE config_tarifas SET tarifa_cc=%s, tarifa_adimex=%s WHERE id=1", (n_cc, n_ad))
                conn.commit(); conn.close(); st.success("Tarifas actualizadas."); st.rerun()
        with t2:
            conn = get_db_connection(); h = pd.read_sql("SELECT * FROM historial_tarifas ORDER BY id DESC", conn); conn.close()
            st.dataframe(h, hide_index=True)

import streamlit as st
import pandas as pd
import mysql.connector
from datetime import datetime

# --- CONFIGURACIÓN E INTERFAZ ---
st.set_page_config(page_title="Sistema Logístico Máster", layout="wide")

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
choice = st.sidebar.radio("Menú Principal", ["📊 Dashboard", "📝 Nuevo Registro", "📁 Historial y Gestión", "⚙️ Admin"])

# ==========================================
# SECCIÓN: DASHBOARD (SIN ERRORES)
# ==========================================
if choice == "📊 Dashboard":
    st.title("📊 Análisis Operativo")
    try:
        conn = get_db_connection()
        df = pd.read_sql("SELECT * FROM logistica_v2", conn)
        conn.close()
        
        if not df.empty:
            df['fecha_pre_alerta_lm'] = pd.to_datetime(df['fecha_pre_alerta_lm'])
            
            # Tooltip Gastos
            s_cuad = df['costo_cuadrilla'].sum(); s_mont = df['montacargas'].sum()
            s_yale = df['yales'].sum(); s_flet = df['flete_subcontrato'].sum(); s_extr = df['servicio_extraordinario'].sum()
            tooltip_gastos = f"Detalle:\n• Cuadrilla: ${s_cuad:,.2f}\n• Montacargas: ${s_mont:,.2f}\n• Yales: ${s_yale:,.2f}\n• Fletes: ${s_flet:,.2f}\n• Extras: ${s_extr:,.2f}"

            st.subheader("💡 Resumen Financiero")
            c1, c2, c3 = st.columns(3)
            c1.metric("Ingresos CC", f"${df['cc_services_calc'].sum():,.2f}")
            c2.metric("Gastos Op.", f"${df['total_costos'].sum():,.2f}", help=tooltip_gastos)
            c3.metric("Utilidad Neta", f"${(df['cc_services_calc'].sum() - df['total_costos'].sum()):,.2f}")

            st.divider()
            v1, v2, v3, v4 = st.columns(4)
            v1.metric("Paquetes", f"{int(df['paquetes'].sum()):,} Pq")
            v2.metric("Másters", f"{len(df)} Uds")
            v3.metric("Peso", f"{df['peso_kg'].sum():,.1f} Kg")
            v4.metric("Diferencia ADIMEX", f"${df['dif_adimex'].sum():,.2f}")
        else: st.info("Sin datos.")
    except Exception as e: st.error(f"Error Dashboard: {e}")

# ==========================================
# SECCIÓN: NUEVO REGISTRO
# ==========================================
elif choice == "📝 Nuevo Registro":
    st.title("📝 Nuevo Registro")
    rates = get_current_rates()
    with st.form("form_reg", clear_on_submit=True):
        t1, t2, t3 = st.tabs(["Carga", "Costos", "Archivo"])
        with t1:
            mes = st.selectbox("Mes", ["Enero", "Febrero", "Marzo", "Abril", "Mayo", "Junio", "Julio", "Agosto", "Septiembre", "Octubre", "Noviembre", "Diciembre"])
            m_fm = st.text_input("Máster First Mile")
            m_lm = st.text_input("Máster Last Mile")
            f_lm = st.date_input("Fecha Last Mile")
            paq = st.number_input("Paquetes", min_value=0)
            peso = st.number_input("Peso (KG)", min_value=0.0)
            cajas = st.number_input("Cajas", min_value=0)
        with t2:
            c_cuad = st.number_input("Cuadrilla $", min_value=0.0)
            mont = st.number_input("Montacargas $", min_value=0.0)
            yale = st.number_input("Yales $", min_value=0.0)
            extr = st.number_input("Extras $", min_value=0.0)
            f_sub = st.number_input("Flete $", min_value=0.0)
            ad_p = st.number_input("ADIMEX Pagado $", min_value=0.0)
            t_flete = st.selectbox("Flete", ["LOCAL", "FORANEO"])
            t_camion = st.text_input("Camión")
            pers = st.number_input("Personas", min_value=0)
        with t3:
            up_pdf = st.file_uploader("PDF", type="pdf")

        if st.form_submit_button("Guardar"):
            cc_c = paq * float(rates['tarifa_cc'])
            ad_c = peso * float(rates['tarifa_adimex'])
            tot_c = c_cuad + mont + yale + extr + f_sub
            pdf_b = up_pdf.read() if up_pdf else None
            
            try:
                conn = get_db_connection()
                cursor = conn.cursor()
                sql = "INSERT INTO logistica_v2 (mes, master_fm, master_lm, fecha_pre_alerta_lm, paquetes, peso_kg, cajas, costo_cuadrilla, montacargas, yales, servicio_extraordinario, flete_subcontrato, adimex_pagado, tipo_flete, tipo_camion, cant_personas_cuadrilla, cc_services_calc, adimex_calc, total_costos, dif_adimex, dif_servicios, tarifa_cc, tarifa_adimex, pdf_nombre, pdf_archivo) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)"
                cursor.execute(sql, (mes, m_fm, m_lm, f_lm, paq, peso, cajas, c_cuad, mont, yale, extr, f_sub, ad_p, t_flete, t_camion, pers, cc_c, ad_c, tot_c, (ad_c-ad_p), (cc_c-tot_c), rates['tarifa_cc'], rates['tarifa_adimex'], up_pdf.name if up_pdf else None, pdf_b))
                conn.commit(); conn.close()
                st.success("Guardado.")
            except Exception as e: st.error(str(e))

# ==========================================
# SECCIÓN: HISTORIAL Y GESTIÓN (EDICIÓN COMPLETA)
# ==========================================
elif choice == "📁 Historial y Gestión":
    st.title("📁 Gestión Integral")
    try:
        conn = get_db_connection()
        df = pd.read_sql("SELECT * FROM logistica_v2 ORDER BY id DESC", conn)
        conn.close()
        
        if not df.empty:
            sel_m = st.selectbox("Seleccione Máster para gestionar:", ["---"] + df['master_fm'].tolist())
            if sel_m != "---":
                row = df[df['master_fm'] == sel_m].iloc[0]
                col1, col2, col3 = st.columns(3)
                
                if col1.button("🗑️ Borrar"):
                    conn = get_db_connection(); c = conn.cursor(); c.execute("DELETE FROM logistica_v2 WHERE id=%s",(int(row['id']),)); conn.commit(); conn.close(); st.rerun()
                
                if row['pdf_archivo']: col2.download_button("📥 PDF", row['pdf_archivo'], row['pdf_nombre'])
                
                with st.expander("📝 EDITAR TODO EL REGISTRO"):
                    with st.form("edit_form"):
                        # Se precargan TODOS los datos
                        ed_paq = st.number_input("Paquetes", value=int(row['paquetes']))
                        ed_peso = st.number_input("Peso", value=float(row['peso_kg']))
                        ed_ad_p = st.number_input("ADIMEX Pagado", value=float(row['adimex_pagado']))
                        ed_cuad = st.number_input("Costo Cuadrilla", value=float(row['costo_cuadrilla']))
                        ed_flete = st.number_input("Costo Flete", value=float(row['flete_subcontrato']))
                        ed_mont = st.number_input("Montacargas", value=float(row['montacargas']))
                        ed_yale = st.number_input("Yales", value=float(row['yales']))
                        ed_extra = st.number_input("Extras", value=float(row['servicio_extraordinario']))
                        ed_pdf = st.file_uploader("Actualizar PDF", type="pdf")
                        
                        if st.form_submit_button("Actualizar"):
                            # Recalcular usando las tarifas originales del registro
                            n_cc = ed_paq * float(row['tarifa_cc'])
                            n_ad = ed_peso * float(row['tarifa_adimex'])
                            n_tot = ed_cuad + ed_flete + ed_mont + ed_yale + ed_extra
                            
                            conn = get_db_connection(); c = conn.cursor()
                            c.execute("""UPDATE logistica_v2 SET paquetes=%s, peso_kg=%s, adimex_pagado=%s, costo_cuadrilla=%s, 
                                      flete_subcontrato=%s, montacargas=%s, yales=%s, servicio_extraordinario=%s, 
                                      cc_services_calc=%s, adimex_calc=%s, total_costos=%s, dif_adimex=%s, dif_servicios=%s 
                                      WHERE id=%s""", 
                                      (ed_paq, ed_peso, ed_ad_p, ed_cuad, ed_flete, ed_mont, ed_yale, ed_extra, 
                                       n_cc, n_ad, n_tot, (n_ad-ed_ad_p), (n_cc-n_tot), int(row['id'])))
                            if ed_pdf:
                                c.execute("UPDATE logistica_v2 SET pdf_nombre=%s, pdf_archivo=%s WHERE id=%s", (ed_pdf.name, ed_pdf.read(), int(row['id'])))
                            conn.commit(); conn.close(); st.success("Editado."); st.rerun()

            st.dataframe(df.drop(columns=['pdf_archivo','tarifa_cc','tarifa_adimex']), use_container_width=True, hide_index=True)
    except Exception as e: st.error(str(e))

# ==========================================
# SECCIÓN: ADMIN (RESTAURADA)
# ==========================================
elif choice == "⚙️ Admin":
    st.title("⚙️ Administración")
    if st.text_input("Contraseña", type="password") == "admin123":
        rates = get_current_rates()
        t1, t2 = st.tabs(["Tarifas", "Historial"])
        with t1:
            n_cc = st.number_input("Tarifa CC", value=float(rates['tarifa_cc']), format="%.4f")
            n_ad = st.number_input("Tarifa ADIMEX", value=float(rates['tarifa_adimex']), format="%.4f")
            if st.button("Actualizar"):
                conn = get_db_connection(); c = conn.cursor()
                c.execute("INSERT INTO historial_tarifas (tarifa_cc_anterior, tarifa_cc_nueva, tarifa_adimex_anterior, tarifa_adimex_nueva) VALUES (%s,%s,%s,%s)",(rates['tarifa_cc'], n_cc, rates['tarifa_adimex'], n_ad))
                c.execute("UPDATE config_tarifas SET tarifa_cc=%s, tarifa_adimex=%s WHERE id=1",(n_cc, n_ad))
                conn.commit(); conn.close(); st.success("Listo.")
        with t2:
            conn = get_db_connection(); h = pd.read_sql("SELECT * FROM historial_tarifas ORDER BY id DESC", conn); conn.close()
            st.dataframe(h, hide_index=True)

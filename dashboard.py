import streamlit as st
import pandas as pd

# --------------------------------------------------------------------
# CONFIG GENERAL
# --------------------------------------------------------------------
st.set_page_config(
    page_title="Experta | Modelos de N",
    page_icon="🌽",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Estilo Experta
st.markdown(
    """
    <style>
    .main {
        background-color: #f4f6fa;
    }
    h1, h2, h3, h4 {
        color: #003b5c;
        font-family: "Segoe UI", sans-serif;
    }
    section[data-testid="stSidebar"] {
        background-color: #e6edf5;
    }
    .stButton>button {
        background-color: #0074a6;
        color: white;
        border-radius: 20px;
        border: none;
        padding: 0.35rem 1.2rem;
        font-weight: 600;
    }
    .stButton>button:hover {
        background-color: #005a80;
    }
    .stDataFrame {
        background-color: white;
        border-radius: 10px;
        padding: 0.5rem;
    }
    </style>
    """,
    unsafe_allow_html=True
)

# --------------------------------------------------------------------
# FUNCIONES DE CÁLCULO
# --------------------------------------------------------------------
def conv_ppm_a_kg_ha(ppm: float, profundidad_cm: float, bd: float) -> float:
    """Conversión genérica de ppm a kg/ha."""
    return ppm * profundidad_cm * bd * 0.1


def calcular_n_tradicional(mo, no3_0_20, no3_20_60, rinde_obj,
                           bd, req_n_tn, min_pct,
                           n_arrancador, pct_n_fert, ef_fert_pct):
    """
    Modelo 1 – Tradicional: usa MO (%) + N-NO3 medido 0–20 y 20–60.
    """
    # N-NO3 0–20 y 20–60
    n_no3_0_20 = conv_ppm_a_kg_ha(no3_0_20, 20, bd)
    n_no3_20_60 = conv_ppm_a_kg_ha(no3_20_60, 40, bd)
    total_n_no3 = n_no3_0_20 + n_no3_20_60

    # Mineralización desde MO (%)
    stock_n_org = mo * 1250
    aporte_mineral = stock_n_org * (min_pct / 100.0)

    # N disponible total
    disp_n = total_n_no3 + aporte_mineral + n_arrancador

    # Rinde sin fertilizar
    rinde_sf = disp_n / req_n_tn * 1000.0

    # Requerimiento total de N para el rinde objetivo
    req_total_n = req_n_tn * (rinde_obj / 1000.0)

    # N requerido del fertilizante
    n_fert_necesario = (req_total_n - disp_n) / (ef_fert_pct / 100.0)

    # Dosis de fertilizante
    dosis_fert = n_fert_necesario / (pct_n_fert / 100.0)

    return total_n_no3, aporte_mineral, disp_n, rinde_sf, n_fert_necesario, dosis_fert


def calcular_n_modelo2(not_pct, tipo_muestreo, no3_0_20_ppm, no3_20_40_ppm,
                       rinde_obj, bd, req_n_tn, min_pct_not,
                       n_arrancador, pct_n_fert, ef_fert_pct):
    """
    Modelo 2 – Estimación NOT:
    - Conversión 0–20: N-NO3 (ppm)*DAP*2
    - Solo 0–20: 20–60 = N_0_20 * 2.35
    - 0–20 y 20–40: 40–60 (ppm) = NO3_20_40 * 1.29 + 1.03
                      luego a kg/ha con el mismo factor DAP*2
    - Mineralización basada en NOT (%):
      Min_kg_ha = 10000*0.2*DAP*1000*(NOT/100)*(min%/100)
    """

    detalle_muestreo = {}

    n_0_20_kg = no3_0_20_ppm * bd * 2
    detalle_muestreo["N-NO3_0_20_kg"] = n_0_20_kg

    if tipo_muestreo == "Solo 0–20 (estimar 20–60)":
        # OJO: esto ya representa N total 0–60
        n_0_60_kg = n_0_20_kg * 2.35
        n_total = n_0_60_kg

        detalle_muestreo["N-NO3_0_60_kg"] = n_0_60_kg
        detalle_muestreo["N-NO3_20_40_kg"] = None
        detalle_muestreo["N-NO3_40_60_kg"] = None

    elif tipo_muestreo == "0–20 y 20–40 (estimar 40–60)":
        # acá sí sumamos capa por capa
        n_20_40_kg = no3_20_40_ppm * bd * 2
        no3_40_60_est_ppm = no3_20_40_ppm * 1.29 + 1.03
        n_40_60_kg = no3_40_60_est_ppm * bd * 2

        n_total = n_0_20_kg + n_20_40_kg + n_40_60_kg

        detalle_muestreo["N-NO3_20_40_kg"] = n_20_40_kg
        detalle_muestreo["N-NO3_40_60_kg"] = n_40_60_kg
        detalle_muestreo["N-NO3_20_60_kg"] = None
    else:
        detalle_muestreo["N-NO3_20_40_kg"] = None
        detalle_muestreo["N-NO3_40_60_kg"] = None
        detalle_muestreo["N-NO3_20_60_kg"] = None

    # Mineralización desde NOT (%)
    # NOT ingresado en %, por ej. 0.09
    mineralizacion_kg = 10000 * 0.2 * bd * 1000 * (not_pct / 100.0) * (min_pct_not / 100.0)

    # N disponible total
    disp_n = n_total + mineralizacion_kg + n_arrancador

    # Rinde sin fertilizar
    rinde_sf = disp_n / req_n_tn * 1000.0

    # Requerimiento total de N para el rinde objetivo
    req_total_n = req_n_tn * (rinde_obj / 1000.0)

    # N requerido del fertilizante
    n_fert_necesario = (req_total_n - disp_n) / (ef_fert_pct / 100.0)

    # Dosis de fertilizante
    dosis_fert = n_fert_necesario / (pct_n_fert / 100.0)

    return n_total, mineralizacion_kg, disp_n, rinde_sf, n_fert_necesario, dosis_fert, detalle_muestreo


# --------------------------------------------------------------------
# ESTADO: N° DE AMBIENTES
# --------------------------------------------------------------------
if "n_ambientes" not in st.session_state:
    st.session_state["n_ambientes"] = 1

def agregar_ambiente():
    st.session_state["n_ambientes"] += 1

def quitar_ambiente():
    if st.session_state["n_ambientes"] > 1:
        st.session_state["n_ambientes"] -= 1


# --------------------------------------------------------------------
# SELECTOR DE MODELO
# --------------------------------------------------------------------
st.sidebar.header("Modelo de cálculo")

modelo = st.sidebar.radio(
    "Elegí el modelo:",
    ["Modelo tradicional", "Modelo 2 (estimación + NOT)"]
)

st.sidebar.markdown("---")
st.sidebar.write(f"Ambientes / lotes actuales: **{st.session_state['n_ambientes']}**")

col_b1, col_b2 = st.sidebar.columns(2)
with col_b1:
    st.button("➕ Agregar", on_click=agregar_ambiente)
with col_b2:
    st.button("➖ Quitar", on_click=quitar_ambiente)

st.sidebar.markdown("---")

# Parámetros globales
bd = st.sidebar.number_input("Densidad aparente (Mg/m³)", value=1.25, step=0.01)
req_n_tn = st.sidebar.number_input("Requerimiento del cultivo (kg N/tn)", value=23.0, step=0.5)
n_arrancador = st.sidebar.number_input("N arrancador (kg/ha)", value=7.0, step=0.5)
pct_n_fert = st.sidebar.number_input("% N del fertilizante", value=46.0, step=0.5)
ef_fert_pct = st.sidebar.number_input("Eficiencia del fertilizante (%)", value=100.0, step=1.0)

if modelo == "Modelo tradicional":
    min_pct = st.sidebar.number_input("Mineralización estimada MO (%)", value=2.5, step=0.1)
    st.sidebar.markdown(
        "_Usa MO (%), N-NO₃ medido 0–20 y 20–60, y %min sobre MO._"
    )
else:
    min_pct_not = st.sidebar.number_input("Mineralización sobre NOT (%)", value=2.5, step=0.1)
    st.sidebar.markdown(
        "_Usa NOT (% N orgánico total) y estima N Profundidad de muestreo_"
    )

# --------------------------------------------------------------------
# CABECERA
# --------------------------------------------------------------------
st.markdown("### Experta | Modelos de nitrógeno")

if modelo == "Modelo tradicional":
    st.title("Modelo tradicional – Balance N suelo + fertilizante")
else:
    st.title("Modelo 2 – Estimación a partir de ecuaciones")

st.markdown("---")

# --------------------------------------------------------------------
# INPUTS POR AMBIENTE / LOTE
# --------------------------------------------------------------------
st.header("Datos por ambiente / lote")

inputs = []

for i in range(st.session_state["n_ambientes"]):
    exp = st.expander(f"Ambiente / lote {i+1}", expanded=True if i == 0 else False)
    with exp:
        c1, c2, c3 = st.columns(3)

        with c1:
            nombre = st.text_input(
                f"Nombre {i+1}",
                value=f"Ambiente {i+1}",
                key=f"nombre_{i}"
            )

        if modelo == "Modelo tradicional":
            # ---------- MODELO 1 ----------
            with c1:
                mo = st.number_input(
                    f"MO 0–20 (%) {i+1}",
                    value=1.50,
                    step=0.01,
                    key=f"mo_{i}"
                )

            with c2:
                no3_0_20 = st.number_input(
                    f"N-NO₃ 0–20 (ppm) {i+1}",
                    value=23.0,
                    step=0.1,
                    key=f"no3_0_20_trad_{i}"
                )
                no3_20_60 = st.number_input(
                    f"N-NO₃ 20–60 (ppm) {i+1}",
                    value=11.8,
                    step=0.1,
                    key=f"no3_20_60_trad_{i}"
                )

            with c3:
                rinde_obj = st.number_input(
                    f"Rinde objetivo (kg/ha) {i+1}",
                    value=10000.0 + i * 1000.0,
                    step=100.0,
                    key=f"rinde_trad_{i}"
                )

            inputs.append({
                "nombre": nombre,
                "mo": mo,
                "no3_0_20": no3_0_20,
                "no3_20_60": no3_20_60,
                "rinde_obj": rinde_obj
            })

        else:
            # ---------- MODELO 2 ----------
            with c1:
                tipo_muestreo = st.selectbox(
                    f"Tipo de muestreo {i+1}",
                    ["Solo 0–20 (estimar 20–60)",
                     "0–20 y 20–40 (estimar 40–60)"],
                    key=f"tipo_m_{i}"
                )

            with c2:
                no3_0_20 = st.number_input(
                    f"N-NO₃ 0–20 (ppm) {i+1}",
                    value=15.0,
                    step=0.1,
                    key=f"no3_0_20_m2_{i}"
                )

                if tipo_muestreo == "0–20 y 20–40 (estimar 40–60)":
                    no3_20_40 = st.number_input(
                        f"N-NO₃ 20–40 (ppm) {i+1}",
                        value=15.0,
                        step=0.1,
                        key=f"no3_20_40_m2_{i}"
                    )
                else:
                    no3_20_40 = None

            with c3:
                not_pct = st.number_input(
                    f"NOT 0–20 (%) {i+1}",
                    value=0.09,
                    step=0.01,
                    format="%.2f",
                    key=f"not_{i}"
                )
                rinde_obj = st.number_input(
                    f"Rinde objetivo (kg/ha) {i+1}",
                    value=12000.0,
                    step=100.0,
                    key=f"rinde_m2_{i}"
                )

            inputs.append({
                "nombre": nombre,
                "tipo_muestreo": tipo_muestreo,
                "no3_0_20": no3_0_20,
                "no3_20_40": no3_20_40,
                "not_pct": not_pct,
                "rinde_obj": rinde_obj
            })

st.markdown("---")

# --------------------------------------------------------------------
# CÁLCULO Y TABLAS
# --------------------------------------------------------------------
if modelo == "Modelo tradicional":
    if st.button("Calcular modelo tradicional para todos los ambientes/lotes"):
        resultados = []

        for data in inputs:
            total_n_no3, aporte_mineral, disp_n, rinde_sf, n_fert_necesario, dosis_fert = calcular_n_tradicional(
                mo=data["mo"],
                no3_0_20=data["no3_0_20"],
                no3_20_60=data["no3_20_60"],
                rinde_obj=data["rinde_obj"],
                bd=bd,
                req_n_tn=req_n_tn,
                min_pct=min_pct,
                n_arrancador=n_arrancador,
                pct_n_fert=pct_n_fert,
                ef_fert_pct=ef_fert_pct,
            )

            resultados.append({
                "Ambiente / lote": data["nombre"],
                "N-NO₃ total (kg/ha)": round(total_n_no3, 1),
                "Mineralización desde MO (kg/ha)": round(aporte_mineral, 1),
                "N disponible total (kg/ha)": round(disp_n, 1),
                "Rinde sin fertilizar (kg/ha)": round(rinde_sf, 0),
                "N a aportar por fert. (kg/ha)": round(n_fert_necesario, 1),
                "Dosis fertilizante (kg/ha)": round(dosis_fert, 1),
            })

        df_result = pd.DataFrame(resultados)
        st.subheader("Tabla resumen – Modelo tradicional")
        st.dataframe(df_result, use_container_width=True)

        csv = df_result.to_csv(index=False).encode("utf-8")
        st.download_button(
            label="📥 Descargar tabla en CSV (Excel)",
            data=csv,
            file_name="modelo_tradicional_nitrógeno.csv",
            mime="text/csv",
        )

else:
    if st.button("Calcular Modelo 2 (estimación + NOT) para todos los ambientes/lotes"):
        resultados = []

        for data in inputs:
            n_no3_total, mineralizacion_kg, disp_n, rinde_sf, n_fert_necesario, dosis_fert, detalle = calcular_n_modelo2(
                not_pct=data["not_pct"],
                tipo_muestreo=data["tipo_muestreo"],
                no3_0_20_ppm=data["no3_0_20"],
                no3_20_40_ppm=data["no3_20_40"],
                rinde_obj=data["rinde_obj"],
                bd=bd,
                req_n_tn=req_n_tn,
                min_pct_not=min_pct_not,
                n_arrancador=n_arrancador,
                pct_n_fert=pct_n_fert,
                ef_fert_pct=ef_fert_pct,
            )

            resultados.append({
                "Ambiente / lote": data["nombre"],
                "Tipo muestreo": data["tipo_muestreo"],
                "N-NO₃ total (kg/ha)": round(n_no3_total, 1),
                "Mineralización desde NOT (kg/ha)": round(mineralizacion_kg, 1),
                "N disponible total (kg/ha)": round(disp_n, 1),
                "Rinde sin fertilizar (kg/ha)": round(rinde_sf, 0),
                "N a aportar por fert. (kg/ha)": round(n_fert_necesario, 1),
                "Dosis fertilizante (kg/ha)": round(dosis_fert, 1),
            })

        df_result = pd.DataFrame(resultados)
        st.subheader("Tabla resumen – Modelo 2 (estimación + NOT)")
        st.dataframe(df_result, use_container_width=True)

        csv = df_result.to_csv(index=False).encode("utf-8")
        st.download_button(
            label="📥 Descargar tabla en CSV (Excel)",
            data=csv,
            file_name="modelo2_not_nprofundo_nitrógeno.csv",
            mime="text/csv",
        )

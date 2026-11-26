from datetime import date
import pandas as pd
import plotly.express as px
import streamlit as st
from supabase import Client, create_client

# --- CONFIGURACIÓN DE PÁGINA ---
st.set_page_config(page_title="PROYECTO DK", page_icon="🏋️", layout="wide")


# --- CONEXIÓN A SUPABASE ---
@st.cache_resource
def init_connection() -> Client:
  url = st.secrets["SUPABASE_URL"]
  key = st.secrets["SUPABASE_KEY"]
  return create_client(url, key)


supabase = init_connection()

# --- CONSTANTES DE COMPETENCIA ---
FECHA_INICIO = date(2026, 12, 1)
FECHA_FIN = date(2027, 6, 1)
COMPETIDORES = ["BENJAMIN", "VICENTE"]  


# --- FUNCIONES DE DATOS ---
def cargar_datos() -> pd.DataFrame:
  res = (
      supabase.table("registros_gym")
      .select("*")
      .order("fecha", desc=False)
      .execute()
  )
  df = pd.DataFrame(res.data)
  if not df.empty:
    df["fecha"] = pd.to_datetime(df["fecha"])
    # Semana relativa desde el 1 de diciembre
    df["semana"] = (
        (df["fecha"] - pd.to_datetime(FECHA_INICIO)).dt.days // 7
    ) + 1
    df["semana"] = df["semana"].clip(lower=1)

    # Cálculo de Fuerza Relativa (kg levantados / peso corporal)
    df["fr_banca"] = (df["press_banca"] / df["peso_corporal"]).round(2)
    df["fr_remo"] = (df["remo_t"] / df["peso_corporal"]).round(2)
    df["fr_hack"] = (df["hack_squat"] / df["peso_corporal"]).round(2)
    df["fr_total"] = (df["fr_banca"] + df["fr_remo"] + df["fr_hack"]).round(2)
  return df


def guardar_registro(fecha, competidor, peso_corp, banca, remo, hack):
  data = {
      "fecha": str(fecha),
      "competidor": competidor,
      "peso_corporal": float(peso_corp),
      "press_banca": float(banca),
      "remo_t": float(remo),
      "hack_squat": float(hack),
  }
  supabase.table("registros_gym").insert(data).execute()


# --- INTERFAZ PRINCIPAL ---
st.title("🏆 Competencia de Fuerza: 1 Dic — 1 Jun")

tab_dashboard, tab_registro, tab_historial = st.tabs(
    ["📊 Tablero Cara a Cara", "➕ Nuevo Registro", "📋 Historial"]
)

df = cargar_datos()

# ==================== TAB 1: DASHBOARD ====================
with tab_dashboard:
  if df.empty:
    st.info(
        "Aún no hay registros. Ve a la pestaña **➕ Nuevo Registro** para"
        " cargar la Semana 1."
    )
  else:
    # Último registro de cada competidor
    ultimos = df.sort_values("fecha").groupby("competidor").last().reset_index()

    st.subheader("Último Estado Registrado")
    cols = st.columns(len(ultimos))
    for idx, row in ultimos.iterrows():
      with cols[idx]:
        st.markdown(f"### {row['competidor']}")
        c1, c2 = st.columns(2)
        c1.metric("Peso Corporal", f"{row['peso_corporal']:.1f} kg")
        c2.metric(
            "Índice Fuerza Relativa",
            f"{row['fr_total']:.2f}x",
            help="Suma de (Banca + Remo + Hack) / Peso Corporal",
        )
        st.caption(
            f"Banca: **{row['press_banca']} kg** ({row['fr_banca']}x) | Remo:"
            f" **{row['remo_t']} kg** ({row['fr_remo']}x) | Hack:"
            f" **{row['hack_squat']} kg** ({row['fr_hack']}x)"
        )

    st.divider()

    # Selector de vista: Peso Absoluto vs Fuerza Relativa
    modo = st.radio(
        "Métrica a comparar en gráficos:",
        ["Peso Absoluto (kg)", "Fuerza Relativa (kg levantado / peso corporal)"],
        horizontal=True,
    )

    es_relativa = modo.startswith("Fuerza Relativa")

    # Gráficos comparativos por ejercicio
    col_g1, col_g2 = st.columns(2)

    with col_g1:
      y_banca = "fr_banca" if es_relativa else "press_banca"
      fig_banca = px.line(
          df,
          x="fecha",
          y=y_banca,
          color="competidor",
          markers=True,
          title="Press Banca",
          labels={"fecha": "Fecha", y_banca: "Ratio" if es_relativa else "kg"},
      )
      st.plotly_chart(fig_banca, use_container_width=True)

      y_hack = "fr_hack" if es_relativa else "hack_squat"
      fig_hack = px.line(
          df,
          x="fecha",
          y=y_hack,
          color="competidor",
          markers=True,
          title="Hack Squat",
          labels={"fecha": "Fecha", y_hack: "Ratio" if es_relativa else "kg"},
      )
      st.plotly_chart(fig_hack, use_container_width=True)

    with col_g2:
      y_remo = "fr_remo" if es_relativa else "remo_t"
      fig_remo = px.line(
          df,
          x="fecha",
          y=y_remo,
          color="competidor",
          markers=True,
          title="Remo en T",
          labels={"fecha": "Fecha", y_remo: "Ratio" if es_relativa else "kg"},
      )
      st.plotly_chart(fig_remo, use_container_width=True)

      fig_peso = px.line(
          df,
          x="fecha",
          y="peso_corporal",
          color="competidor",
          markers=True,
          title="Evolución Peso Corporal (kg)",
          labels={"fecha": "Fecha", "peso_corporal": "kg"},
      )
      st.plotly_chart(fig_peso, use_container_width=True)

    # Tabla resumen de progreso (% de mejora desde el primer registro)
    st.subheader("📈 Progreso Acumulado (% desde inicio)")
    resumen_progreso = []
    for comp, grupo in df.sort_values("fecha").groupby("competidor"):
      primero = grupo.iloc[0]
      ultimo = grupo.iloc[-1]

      def pct(ini, fin):
        return f"{((fin - ini) / ini * 100):+.1f}%" if ini > 0 else "0.0%"

      resumen_progreso.append({
          "Competidor": comp,
          "Registros": len(grupo),
          "Peso Corp.": (
              f"{primero['peso_corporal']} → {ultimo['peso_corporal']} kg"
              f" ({pct(primero['peso_corporal'], ultimo['peso_corporal'])})"
          ),
          "Press Banca": (
              f"{primero['press_banca']} → {ultimo['press_banca']} kg"
              f" ({pct(primero['press_banca'], ultimo['press_banca'])})"
          ),
          "Remo en T": (
              f"{primero['remo_t']} → {ultimo['remo_t']} kg"
              f" ({pct(primero['remo_t'], ultimo['remo_t'])})"
          ),
          "Hack Squat": (
              f"{primero['hack_squat']} → {ultimo['hack_squat']} kg"
              f" ({pct(primero['hack_squat'], ultimo['hack_squat'])})"
          ),
          "Fuerza Relativa Total": (
              f"{primero['fr_total']}x → {ultimo['fr_total']}x"
              f" ({pct(primero['fr_total'], ultimo['fr_total'])})"
          ),
      })
    st.dataframe(
        pd.DataFrame(resumen_progreso),
        use_container_width=True,
        hide_index=True,
    )

# ==================== TAB 2: FORMULARIO ====================
with tab_registro:
  st.subheader("Registrar marcas de la semana")
  with st.form("form_registro", clear_on_submit=True):
    col1, col2 = st.columns(2)
    with col1:
      competidor = st.selectbox("Competidor", COMPETIDORES)
      fecha_reg = st.date_input("Fecha de medición", value=date.today())
      peso_corp = st.number_input(
          "Peso corporal (kg)", min_value=30.0, max_value=250.0, step=0.1
      )
    with col2:
      banca = st.number_input(
          "Press Banca (kg)", min_value=0.0, max_value=400.0, step=1.25
      )
      remo = st.number_input(
          "Remo en T (kg)", min_value=0.0, max_value=400.0, step=1.25
      )
      hack = st.number_input(
          "Hack Squat (kg)", min_value=0.0, max_value=600.0, step=2.5
      )

    submitted = st.form_submit_button(
        "💾 Guardar registro", use_container_width=True
    )
    if submitted:
      if peso_corp <= 0:
        st.error("El peso corporal debe ser mayor a 0.")
      else:
        guardar_registro(fecha_reg, competidor, peso_corp, banca, remo, hack)
        st.success(f"Registro guardado para {competidor} ({fecha_reg}).")
        st.rerun()

# ==================== TAB 3: HISTORIAL Y BORRADO ====================
with tab_historial:
  st.subheader("Base de datos completa")
  if df.empty:
    st.write("Sin datos todavía.")
  else:
    cols_mostrar = [
        "id",
        "fecha",
        "semana",
        "competidor",
        "peso_corporal",
        "press_banca",
        "remo_t",
        "hack_squat",
        "fr_total",
    ]
    st.dataframe(
        df[cols_mostrar].sort_values("fecha", ascending=False),
        use_container_width=True,
        hide_index=True,
    )

    with st.expander("🗑️ Eliminar un registro por error"):
      id_borrar = st.number_input("ID del registro a eliminar", min_value=1, step=1)
      if st.button("Eliminar registro"):
        supabase.table("registros_gym").delete().eq("id", id_borrar).execute()
        st.warning(f"Registro #{id_borrar} eliminado.")
        st.rerun()
import streamlit as st
from pymongo import MongoClient
from datetime import datetime, timezone, timedelta
import pytz
import pandas as pd

# === CONFIG ===
st.set_page_config(page_title="🛴🚲 Registro de Patinetas y Bicicletas – CC VIVA Envigado", layout="centered")
st.markdown("## 🛴🚲 Registro de Patinetas y Bicicletas – CC VIVA Envigado")

# MongoDB
client = MongoClient(st.secrets["mongo_uri"])
db = client["check_viva"]
coleccion = db["ingresos"]

# Zona horaria
zona_col = pytz.timezone("America/Bogota")

def formatear_duracion(inicio, fin):
    if isinstance(inicio, str):
        inicio = datetime.fromisoformat(inicio)
    if isinstance(fin, str):
        fin = datetime.fromisoformat(fin)
    if inicio.tzinfo is None:
        inicio = inicio.replace(tzinfo=timezone.utc)
    if fin.tzinfo is None:
        fin = fin.replace(tzinfo=timezone.utc)
    duracion = fin - inicio
    dias = duracion.days
    horas, rem = divmod(duracion.seconds, 3600)
    minutos, segundos = divmod(rem, 60)
    if dias > 0:
        return f"{dias}d {horas:02}:{minutos:02}:{segundos:02}"
    else:
        return f"{horas:02}:{minutos:02}:{segundos:02}"

st.markdown("### 🟢 Ingreso de vehículo")
with st.form("form_ingreso"):
    cedula_ingreso = st.text_input("Número de cédula", key="cedula_ingreso")
    datos_existente = coleccion.find_one({"cedula": cedula_ingreso, "estado": {"$ne": "finalizado"}}) if cedula_ingreso else None

    if datos_existente:
        nombre_default = datos_existente.get("nombre", "")
        tipo_default = datos_existente.get("tipo", "Patineta")
        marca_default = datos_existente.get("marca", "")
    else:
        nombre_default = ""
        tipo_default = "Patineta"
        marca_default = ""

    nombre = st.text_input("Nombre completo", value=nombre_default)
    tipo = st.selectbox("Tipo de vehículo", ["Patineta", "Bicicleta"], index=0 if tipo_default == "Patineta" else 1)
    marca = st.text_input("Marca o referencia", value=marca_default)
    enviar = st.form_submit_button("Registrar ingreso")

if enviar:
    if datos_existente:
        st.warning("Ya hay un vehículo con esta cédula sin registrar salida.")
    elif not nombre or not cedula_ingreso or not marca:
        st.error("Por favor completa todos los campos.")
    else:
        ingreso = datetime.now(tz=zona_col)
        coleccion.insert_one({
            "nombre": nombre,
            "cedula": cedula_ingreso,
            "tipo": tipo,
            "marca": marca,
            "ingreso": ingreso,
            "estado": "activo"
        })
        st.success("Ingreso registrado exitosamente.")
        st.experimental_rerun()

# === SALIDA ===
st.markdown("### 🔴 Registrar salida")
cedula_salida = st.text_input("Número de cédula para salida", key="cedula_salida")
vehiculo_activo = coleccion.find_one({"cedula": cedula_salida, "estado": "activo"})

if vehiculo_activo:
    st.info(f"Vehículo encontrado: {vehiculo_activo['tipo'].capitalize()} – {vehiculo_activo['marca']}")
    if st.button("Registrar salida ahora"):
        salida_hora = datetime.now(tz=zona_col)
        duracion_str = formatear_duracion(vehiculo_activo["ingreso"], salida_hora)
        duracion_min = int((salida_hora - vehiculo_activo["ingreso"]).total_seconds() / 60)
        coleccion.update_one(
            {"_id": vehiculo_activo["_id"]},
            {"$set": {
                "salida": salida_hora,
                "estado": "finalizado",
                "duracion_str": duracion_str,
                "duracion_min": duracion_min
            }}
        )
        st.success(f"Salida registrada. Duración: {duracion_str}")
        st.experimental_rerun()
else:
    if cedula_salida:
        st.warning("❌ No hay ingresos activos para esta cédula.")

# === VEHÍCULOS ACTIVOS ===
st.markdown("### 🚧 Vehículos actualmente parqueados")
activos = list(coleccion.find({"estado": "activo"}))
if activos:
    df_activos = pd.DataFrame(activos)[["nombre", "cedula", "tipo", "marca", "ingreso"]]
    df_activos["ingreso"] = pd.to_datetime(df_activos["ingreso"]).dt.tz_convert(zona_col).dt.strftime("%Y-%m-%d %H:%M:%S")
    df_activos.index = df_activos.index + 1
    st.dataframe(df_activos)
else:
    st.info("No hay vehículos actualmente parqueados.")

# === HISTORIAL FINALIZADOS ===
st.markdown("### 📜 Últimos ingresos finalizados")
finalizados = list(coleccion.find({"estado": "finalizado"}).sort("salida", -1))
if finalizados:
    df_finalizados = pd.DataFrame(finalizados)[["nombre", "cedula", "tipo", "marca", "ingreso", "salida", "duracion_str"]]
    df_finalizados["ingreso"] = pd.to_datetime(df_finalizados["ingreso"]).dt.tz_convert(zona_col).dt.strftime("%Y-%m-%d %H:%M:%S")
    df_finalizados["salida"] = pd.to_datetime(df_finalizados["salida"]).dt.tz_convert(zona_col).dt.strftime("%Y-%m-%d %H:%M:%S")
    df_finalizados.index = df_finalizados.index + 1
    st.dataframe(df_finalizados)
else:
    st.info("No hay registros finalizados.")
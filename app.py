import streamlit as st
from pymongo import MongoClient
from datetime import datetime
import pytz
import pandas as pd

# Configuración inicial
st.set_page_config(page_title="🛴🚲 Registro de Patinetas y Bicicletas – CC VIVA Envigado", layout="centered")
st.markdown("## 🛴🚲 Registro de Patinetas y Bicicletas – CC VIVA Envigado")

# Zona horaria de Colombia
zona_col = pytz.timezone("America/Bogota")

# Conexión a MongoDB
client = MongoClient(st.secrets["mongo_uri"])
db = client["check_viva"]
col_ingresos = db["ingresos"]

# Función para formatear duración
def formatear_duracion(inicio, fin):
    if inicio.tzinfo is None:
        inicio = zona_col.localize(inicio)
    if fin.tzinfo is None:
        fin = zona_col.localize(fin)
    duracion = fin - inicio
    dias = duracion.days
    horas, rem = divmod(duracion.seconds, 3600)
    minutos, segundos = divmod(rem, 60)
    partes = []
    if dias > 0:
        partes.append(f"{dias}d")
    partes.append(f"{horas:02}:{minutos:02}:{segundos:02}")
    return " ".join(partes)

# === Ingreso ===
st.markdown("### 🟢 Ingreso de vehículo")

cedula_ingreso = st.text_input("Número de cédula", key="ced_ing")
registro_existente = col_ingresos.find_one({"cedula": cedula_ingreso, "estado": "activo"}) if cedula_ingreso else None

if registro_existente:
    st.success(f"Vehículo ya registrado: {registro_existente['tipo'].capitalize()} – {registro_existente['marca']}")
else:
    with st.form("form_ingreso"):
        nombre = st.text_input("Nombre completo", key="nom")
        tipo = st.selectbox("Tipo de vehículo", ["Patineta", "Bicicleta"], key="tipo")
        marca = st.text_input("Marca o referencia", key="marca")
        enviar = st.form_submit_button("Registrar ingreso")

        if enviar:
            if not (nombre and cedula_ingreso and tipo and marca):
                st.error("Por favor completa todos los campos.")
            else:
                now = datetime.now(zona_col)
                col_ingresos.insert_one({
                    "cedula": cedula_ingreso,
                    "nombre": nombre,
                    "tipo": tipo.lower(),
                    "marca": marca,
                    "ingreso": now,
                    "estado": "activo"
                })
                st.success("✅ Ingreso registrado correctamente.")
                st.experimental_rerun()

# === Salida ===
st.markdown("### 🔴 Registrar salida")

cedula_salida = st.text_input("Número de cédula para salida", key="ced_salida")
vehiculo_activo = col_ingresos.find_one({"cedula": cedula_salida, "estado": "activo"}) if cedula_salida else None

if vehiculo_activo:
    st.info(f"Vehículo encontrado: {vehiculo_activo['tipo'].capitalize()} – {vehiculo_activo['marca']}")
    if st.button("Registrar salida ahora"):
        salida_hora = datetime.now(zona_col)
        duracion_str = formatear_duracion(vehiculo_activo["ingreso"], salida_hora)
        duracion_min = int((salida_hora - vehiculo_activo["ingreso"]).total_seconds() / 60)
        col_ingresos.update_one(
            {"_id": vehiculo_activo["_id"]},
            {"$set": {
                "salida": salida_hora,
                "estado": "finalizado",
                "duracion_str": duracion_str,
                "duracion_min": duracion_min
            }}
        )
        st.success(f"✅ Salida registrada. Duración: {duracion_str}")
        st.experimental_rerun()

# === Parqueados actuales ===
st.markdown("### 🚧 Vehículos actualmente parqueados")

activos = list(col_ingresos.find({"estado": "activo"}))
if activos:
    df_activos = pd.DataFrame(activos)[["nombre", "cedula", "tipo", "marca", "ingreso"]]
    df_activos["ingreso"] = pd.to_datetime(df_activos["ingreso"]).dt.tz_convert(zona_col).dt.strftime("%Y-%m-%d %H:%M:%S")
    df_activos.rename(columns={
        "nombre": "Nombre", "cedula": "Cédula", "tipo": "Tipo", "marca": "Marca", "ingreso": "Hora de ingreso"
    }, inplace=True)
    st.dataframe(df_activos)
else:
    st.info("No hay vehículos actualmente parqueados.")

# === Finalizados ===
st.markdown("### 📜 Últimos ingresos finalizados")

finalizados = list(col_ingresos.find({"estado": "finalizado"}).sort("salida", -1).limit(15))
if finalizados:
    df_finalizados = pd.DataFrame(finalizados)[["nombre", "cedula", "tipo", "marca", "ingreso", "salida", "duracion_str"]]
    df_finalizados["ingreso"] = pd.to_datetime(df_finalizados["ingreso"]).dt.tz_convert(zona_col).dt.strftime("%Y-%m-%d %H:%M:%S")
    df_finalizados["salida"] = pd.to_datetime(df_finalizados["salida"]).dt.tz_convert(zona_col).dt.strftime("%Y-%m-%d %H:%M:%S")
    df_finalizados.rename(columns={
        "nombre": "Nombre", "cedula": "Cédula", "tipo": "Tipo", "marca": "Marca",
        "ingreso": "Hora ingreso", "salida": "Hora salida", "duracion_str": "Duración"
    }, inplace=True)
    st.dataframe(df_finalizados)
else:
    st.info("No hay registros finalizados.")
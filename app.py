import streamlit as st
from pymongo import MongoClient
from datetime import datetime
import pytz
import pandas as pd

# === CONFIGURACIÓN ===
st.set_page_config(page_title="🛴🚲 Registro de Patinetas y Bicicletas – CC VIVA Envigado", layout="centered")
st.title("🛴🚲 Registro de Patinetas y Bicicletas – CC VIVA Envigado")
zona_col = pytz.timezone("America/Bogota")

# === CONEXIÓN MONGO ===
client = MongoClient(st.secrets["mongo_uri"])
db = client.check_viva
vehiculos = db.vehiculos
ingresos = db.ingresos

orden_tipo = {"Patineta": 0, "Bicicleta": 1}

# === FUNCIÓN DURACIÓN ===
def formatear_duracion(inicio, fin):
    duracion = fin - inicio
    dias = duracion.days
    horas, rem = divmod(duracion.seconds, 3600)
    minutos, segundos = divmod(rem, 60)
    partes = []
    if dias > 0:
        partes.append(f"{dias} día{'s' if dias > 1 else ''}")
    partes.append(f"{horas:02}:{minutos:02}:{segundos:02}")
    return " – ".join(partes)

# === INGRESO ===
st.subheader("🟢 Ingreso de vehículo")
with st.form("ingreso_form"):
    nombre = st.text_input("Nombre completo")
    cedula = st.text_input("Número de cédula")
    tipo = st.selectbox("Tipo de vehículo", ["Patineta", "Bicicleta"])
    marca = st.text_input("Marca o referencia")
    submitted = st.form_submit_button("Registrar ingreso")

    if submitted:
        if ingresos.find_one({"cedula": cedula, "salida": None}):
            st.warning("⚠️ Ya hay un ingreso activo para esta cédula.")
        else:
            ingreso_dt = datetime.now(tz=zona_col)
            vehiculos.update_one({"cedula": cedula}, {"$set": {
                "nombre": nombre,
                "cedula": cedula,
                "tipo": tipo,
                "marca": marca
            }}, upsert=True)
            ingresos.insert_one({
                "nombre": nombre,
                "cedula": cedula,
                "tipo": tipo,
                "marca": marca,
                "ingreso": ingreso_dt,
                "salida": None,
                "duracion": None
            })
            st.success(f"✅ Ingreso registrado para {nombre} ({tipo} – {marca})")

# === SALIDA ===
st.subheader("🔴 Registrar salida")
cedula_salida = st.text_input("Cédula para salida (ingresa manualmente)")

vehiculo_activo = ingresos.find_one({"cedula": cedula_salida, "salida": None})
if vehiculo_activo:
    st.info(f"{vehiculo_activo['nombre']} — Vehículo encontrado: {vehiculo_activo['tipo'].capitalize()} – {vehiculo_activo['marca']}")
    if st.button("Registrar salida ahora"):
        salida_hora = datetime.now(tz=zona_col)
        duracion_str = formatear_duracion(vehiculo_activo["ingreso"], salida_hora)
        ingresos.update_one(
            {"_id": vehiculo_activo["_id"]},
            {"$set": {"salida": salida_hora, "duracion": duracion_str}}
        )
        st.success(f"🚪 Salida registrada. Duración: {duracion_str}")
        st.experimental_rerun()
else:
    if cedula_salida:
        st.error("❌ No hay ingresos activos para esta cédula.")

# === VEHÍCULOS PARQUEADOS ===
st.subheader("🚧 Vehículos actualmente parqueados")
parqueados = list(ingresos.find({"salida": None}))
if parqueados:
    parqueados.sort(key=lambda x: orden_tipo.get(x["tipo"], 99))
    data = [{
        "#": i + 1,
        "Nombre": r["nombre"],
        "Cédula": r["cedula"],
        "Tipo": r["tipo"].capitalize(),
        "Marca": r["marca"],
        "Hora ingreso": r["ingreso"].astimezone(zona_col).strftime("%Y-%m-%d %H:%M:%S")
    } for i, r in enumerate(parqueados)]
    df = pd.DataFrame(data)
    st.dataframe(df.set_index("#"), use_container_width=True)
else:
    st.info("No hay vehículos actualmente parqueados.")

# === HISTORIAL FINALIZADOS ===
st.subheader("📜 Historial de registros finalizados")
finalizados = list(ingresos.find({"salida": {"$ne": None}}).sort("salida", -1).limit(20))
if finalizados:
    data = [{
        "#": i + 1,
        "Nombre": r["nombre"],
        "Cédula": r["cedula"],
        "Tipo": r["tipo"].capitalize(),
        "Marca": r["marca"],
        "Ingreso": r["ingreso"].astimezone(zona_col).strftime("%Y-%m-%d %H:%M:%S"),
        "Salida": r["salida"].astimezone(zona_col).strftime("%Y-%m-%d %H:%M:%S"),
        "Duración": r["duracion"]
    } for i, r in enumerate(finalizados)]
    df = pd.DataFrame(data)
    st.dataframe(df.set_index("#"), use_container_width=True)
else:
    st.info("No hay registros finalizados.")
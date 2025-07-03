import streamlit as st
import pymongo
from datetime import datetime
import pytz
import pandas as pd
from bson.objectid import ObjectId

# === CONFIG ===
st.set_page_config(page_title="🛴🚲 Registro de Patinetas y Bicicletas – CC VIVA Envigado", layout="centered")
MONGO_URI = st.secrets["mongo_uri"]
client = pymongo.MongoClient(MONGO_URI)
db = client.check_viva
usuarios_col = db.usuarios
vehiculos_col = db.vehiculos
ingresos_col = db.ingresos

# === ZONA HORARIA ===
CO = pytz.timezone("America/Bogota")

# === FUNCIONES ===

def registrar_ingreso(nombre, cedula, tipo, marca):
    usuarios_col.update_one(
        {"cedula": cedula},
        {"$set": {"nombre": nombre, "cedula": cedula}},
        upsert=True,
    )
    vehiculos_col.update_one(
        {"cedula": cedula, "tipo": tipo.lower()},
        {"$set": {"marca": marca, "tipo": tipo.lower(), "cedula": cedula}},
        upsert=True,
    )
    ingresos_col.insert_one({
        "nombre": nombre,
        "cedula": cedula,
        "tipo": tipo.lower(),
        "marca": marca,
        "hora_ingreso": datetime.now(CO),
        "activo": True,
    })

def registrar_salida(cedula):
    registros = list(ingresos_col.find({"cedula": cedula, "activo": True}))
    if not registros:
        st.error("❌ No hay ingresos activos para esta cédula.")
        return

    seleccionado = registros[0]
    ingreso_dt = seleccionado["hora_ingreso"]

    # Asegurar timezone-aware
    if ingreso_dt.tzinfo is None or ingreso_dt.tzinfo.utcoffset(ingreso_dt) is None:
        ingreso_dt = CO.localize(ingreso_dt)
    else:
        ingreso_dt = ingreso_dt.astimezone(CO)

    salida_hora = datetime.now(CO)
    duracion_min = int((salida_hora - ingreso_dt).total_seconds() / 60)

    ingresos_col.update_one(
        {"_id": seleccionado["_id"]},
        {"$set": {
            "activo": False,
            "hora_salida": salida_hora,
            "duracion_min": duracion_min
        }}
    )
    st.success(f"✅ Salida registrada. Duración: {duracion_min} minutos.")


# === UI ===

st.markdown("## 🟢 Ingreso de vehículo")
with st.form("ingreso"):
    nombre = st.text_input("Nombre completo")
    cedula = st.text_input("Número de cédula")
    tipo = st.selectbox("Tipo de vehículo", ["Patineta", "Bicicleta"])
    marca = st.text_input("Marca o referencia")

    if st.form_submit_button("Registrar ingreso"):
        if not all([nombre, cedula, tipo, marca]):
            st.warning("⚠️ Por favor completa todos los campos.")
        else:
            registrar_ingreso(nombre, cedula, tipo, marca)
            st.success("✅ Ingreso registrado correctamente.")


st.markdown("## 🔴 Registrar salida")
cedula_salida = st.text_input("Selecciona cédula para registrar salida")

if cedula_salida:
    registros_activos = list(ingresos_col.find({"cedula": cedula_salida, "activo": True}))
    if registros_activos:
        vehiculo = registros_activos[0]
        st.info(f"Vehículo encontrado: {vehiculo['tipo'].capitalize()} – {vehiculo['marca']}")
        if st.button("Registrar salida ahora"):
            registrar_salida(cedula_salida)
    else:
        st.warning("❌ No hay ingresos activos para esta cédula.")

# === TABLA PARQUEADOS ===
st.markdown("## 🛑🚧 Vehículos actualmente parqueados")
parqueados = list(ingresos_col.find({"activo": True}))
for r in parqueados:
    r["tipo"] = r.get("tipo", "").capitalize()

orden_tipo = {"Patineta": 0, "Bicicleta": 1}
parqueados.sort(key=lambda x: orden_tipo.get(x.get("tipo", ""), 99))

if parqueados:
    df_parqueados = pd.DataFrame([{
        "N°": idx + 1,
        "Nombre": r["nombre"],
        "Cédula": r["cedula"],
        "Tipo": r["tipo"],
        "Marca": r["marca"],
        "Hora ingreso": r["hora_ingreso"].astimezone(CO).strftime("%Y-%m-%d %H:%M")
    } for idx, r in enumerate(parqueados)])
    st.dataframe(df_parqueados, hide_index=True)
else:
    st.info("No hay vehículos actualmente parqueados.")

# === TABLA HISTORIAL ===
st.markdown("## 📜 Historial de registros finalizados")
finalizados = list(ingresos_col.find({"activo": False}).sort("hora_salida", -1))

if finalizados:
    df_finalizados = pd.DataFrame([{
        "N°": idx + 1,
        "Nombre": r["nombre"],
        "Cédula": r["cedula"],
        "Tipo": r.get("tipo", "").capitalize(),
        "Marca": r["marca"],
        "Ingreso": r["hora_ingreso"].astimezone(CO).strftime("%Y-%m-%d %H:%M"),
        "Salida": r["hora_salida"].astimezone(CO).strftime("%Y-%m-%d %H:%M"),
        "Duración (min)": r.get("duracion_min", "")
    } for idx, r in enumerate(finalizados)])
    st.dataframe(df_finalizados, hide_index=True)
else:
    st.info("No hay registros finalizados aún.")
from datetime import datetime
import pytz
import streamlit as st
from pymongo import MongoClient
import pandas as pd

# Configuración inicial
st.set_page_config(page_title="🛴🚲 Registro de Patinetas y Bicicletas – CC VIVA Envigado", layout="centered")
client = MongoClient(st.secrets["mongo_uri"])
db = client["check_viva"]
coleccion = db["registros"]
zona_col = pytz.timezone("America/Bogota")

# Función de duración legible
def formatear_duracion(inicio, fin):
    if not isinstance(inicio, datetime):
        inicio = datetime.fromisoformat(str(inicio))
    if not isinstance(fin, datetime):
        fin = datetime.fromisoformat(str(fin))
    duracion = fin - inicio
    dias = duracion.days
    horas, rem = divmod(duracion.seconds, 3600)
    minutos, segundos = divmod(rem, 60)
    partes = []
    if dias > 0:
        partes.append(f"{dias} días")
    partes.append(f"{horas:02}:{minutos:02}:{segundos:02}")
    return " ".join(partes)

# Título principal
st.title("🛴🚲 Registro de Patinetas y Bicicletas – CC VIVA Envigado")

# === INGRESO ===
st.subheader("🟢 Ingreso de vehículo")
cedula_ing = st.text_input("Número de cédula", key="cedula_ing")

registro = coleccion.find_one({"cedula": cedula_ing})
ya_parqueado = coleccion.find_one({"cedula": cedula_ing, "salida": None})

if cedula_ing:
    if registro and not ya_parqueado:
        st.info("✅ Usuario encontrado. Completa para registrar ingreso.")
        nombre = registro["nombre"]
        tipo = registro["tipo"]
        marca = registro["marca"]
        st.text(f"Nombre: {nombre}")
        st.text(f"Tipo: {tipo.capitalize()}")
        st.text(f"Marca: {marca}")
    elif ya_parqueado:
        st.warning("⚠️ Ya existe un ingreso activo para esta cédula.")
        nombre = ya_parqueado["nombre"]
        tipo = ya_parqueado["tipo"]
        marca = ya_parqueado["marca"]
    else:
        nombre = st.text_input("Nombre completo")
        tipo = st.selectbox("Tipo de vehículo", ["Patineta", "Bicicleta"])
        marca = st.text_input("Marca o referencia")

    if st.button("Registrar ingreso"):
        if ya_parqueado:
            st.warning("Ya existe un ingreso activo.")
        elif not nombre or not marca:
            st.error("Completa todos los campos.")
        else:
            coleccion.insert_one({
                "nombre": nombre,
                "cedula": cedula_ing,
                "tipo": tipo.lower(),
                "marca": marca,
                "ingreso": datetime.now(zona_col),
                "salida": None
            })
            st.success("✅ Ingreso registrado correctamente.")
            st.experimental_rerun()

# === SALIDA ===
st.subheader("🔴 Registrar salida")
cedula_sal = st.text_input("Número de cédula para salida")

registro_salida = coleccion.find_one({"cedula": cedula_sal, "salida": None})
if registro_salida:
    st.info(f"Vehículo encontrado: {registro_salida['tipo'].capitalize()} – {registro_salida['marca']}")
    if st.button("Registrar salida ahora"):
        hora_salida = datetime.now(zona_col)
        duracion = formatear_duracion(registro_salida["ingreso"], hora_salida)
        coleccion.update_one({"_id": registro_salida["_id"]}, {"$set": {"salida": hora_salida}})
        st.success(f"✅ Salida registrada. Duración: {duracion}")
        st.experimental_rerun()
elif cedula_sal:
    st.error("❌ No hay ingresos activos para esta cédula.")

# === PARQUEADOS ===
st.subheader("🚧 Vehículos actualmente parqueados")
parqueados = list(coleccion.find({"salida": None}))
if parqueados:
    df_activos = pd.DataFrame([{
        "Nombre": p["nombre"],
        "Cédula": p["cedula"],
        "Tipo": p["tipo"].capitalize(),
        "Marca": p["marca"],
        "Ingreso": p["ingreso"].astimezone(zona_col).strftime("%Y-%m-%d %H:%M:%S")
    } for p in parqueados])
    df_activos.index = range(1, len(df_activos) + 1)
    st.dataframe(df_activos)
else:
    st.info("No hay vehículos actualmente parqueados.")

# === HISTORIAL FINALIZADOS ===
st.subheader("📜 Últimos ingresos finalizados")
finalizados = list(coleccion.find({"salida": {"$ne": None}}).sort("salida", -1).limit(10))
if finalizados:
    df_fin = pd.DataFrame([{
        "Nombre": f["nombre"],
        "Cédula": f["cedula"],
        "Tipo": f["tipo"].capitalize(),
        "Marca": f["marca"],
        "Ingreso": f["ingreso"].astimezone(zona_col).strftime("%Y-%m-%d %H:%M:%S"),
        "Salida": f["salida"].astimezone(zona_col).strftime("%Y-%m-%d %H:%M:%S"),
        "Duración": formatear_duracion(f["ingreso"], f["salida"])
    } for f in finalizados])
    df_fin.index = range(1, len(df_fin) + 1)
    st.dataframe(df_fin)
else:
    st.info("No hay registros finalizados.")
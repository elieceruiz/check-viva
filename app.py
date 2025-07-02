from datetime import datetime
import pytz
import streamlit as st
from pymongo import MongoClient
import pandas as pd

# === CONFIG ===
st.set_page_config(page_title="🚲 Check VIVA", layout="centered")
st.title("🚲 Registro de Patinetas y Bicicletas – CC VIVA Envigado")

# === CONEXIÓN MONGO ===
MONGO_URI = st.secrets["mongo_uri"]
client = MongoClient(MONGO_URI)
db = client.check_viva
usuarios = db.usuarios
ingresos = db.ingresos

# === ZONA HORARIA ===
CO = pytz.timezone("America/Bogota")
ahora = datetime.now(CO)
orden_tipo = {"patineta": 0, "bicicleta": 1}

# === FUNCIÓN FORMATO DURACIÓN ===
def formatear_duracion(inicio, fin):
    duracion = fin - inicio
    dias = duracion.days
    horas, rem = divmod(duracion.seconds, 3600)
    minutos, segundos = divmod(rem, 60)
    if dias > 0:
        return f"{dias}d {horas:02d}:{minutos:02d}:{segundos:02d}"
    else:
        return f"{horas:02d}:{minutos:02d}:{segundos:02d}"

# === INGRESO ===
st.subheader("🟢 Ingreso de vehículo")
cedula = st.text_input("Número de cédula", max_chars=15)

if cedula:
    usuario = usuarios.find_one({"cedula": cedula})
    if usuario:
        nombre = usuario["nombre"]
        st.success(f"Usuario encontrado: {nombre}")
    else:
        nombre = st.text_input("Nombre completo")
        if nombre:
            if st.button("Registrar nuevo usuario"):
                usuarios.insert_one({
                    "cedula": cedula,
                    "nombre": nombre,
                    "fecha_registro": ahora
                })
                st.success("✅ Usuario registrado. Ahora puedes registrar el ingreso.")
                st.rerun()

    if usuario or nombre:
        with st.form("form_ingreso"):
            tipo = st.selectbox("Tipo de vehículo", ["Patineta", "Bicicleta"])
            marca = st.text_input("Marca y referencia", max_chars=50)
            color = st.text_input("Color o señas distintivas (opcional)", max_chars=50)
            candado = st.text_input("Candado entregado (opcional)", max_chars=30)
            submitted = st.form_submit_button("🟢 Registrar ingreso")

            if submitted:
                ingresos.insert_one({
                    "cedula": cedula,
                    "nombre": usuario["nombre"] if usuario else nombre,
                    "tipo": tipo.lower(),
                    "marca": marca,
                    "color": color,
                    "candado": candado,
                    "ingreso": ahora,
                    "salida": None,
                    "estado": "activo"
                })
                st.success("🚲 Ingreso registrado correctamente.")
                st.rerun()

# === SALIDA ===
st.subheader("🔴 Registrar salida")
cedula_salida = st.text_input("Buscar por cédula para registrar salida", key="salida")

if cedula_salida:
    activo = ingresos.find_one({"cedula": cedula_salida, "estado": "activo"})
    if activo:
        st.info(f"Vehículo encontrado: {activo['tipo'].capitalize()} – {activo['marca']}")
        if st.button("Registrar salida ahora"):
            salida_hora = datetime.now(CO)
            duracion_str = formatear_duracion(activo["ingreso"], salida_hora)
            duracion_min = int((salida_hora - activo["ingreso"]).total_seconds() / 60)

            ingresos.update_one(
                {"_id": activo["_id"]},
                {"$set": {
                    "salida": salida_hora,
                    "estado": "finalizado",
                    "duracion_min": duracion_min,
                    "duracion_str": duracion_str
                }}
            )
            st.success(f"✅ Salida registrada. El vehículo estuvo bajo cuidado durante **{duracion_str}**.")
            st.experimental_rerun()
    else:
        st.warning("❌ No hay ingreso activo para esta cédula.")

# === PARQUEADOS ACTUALMENTE ===
st.subheader("🚧 Vehículos actualmente parqueados")
parqueados = list(ingresos.find({"estado": "activo"}))
parqueados.sort(key=lambda x: orden_tipo.get(x["tipo"], 99))

if parqueados:
    data = []
    for r in parqueados:
        ahora = datetime.now(CO)
        duracion = formatear_duracion(r["ingreso"], ahora)
        data.append({
            "Nombre": r["nombre"],
            "Cédula": r["cedula"],
            "Tipo": r["tipo"].capitalize(),
            "Marca": r["marca"],
            "Ingreso": r["ingreso"].astimezone(CO).strftime("%Y-%m-%d %H:%M"),
            "Duración actual": duracion,
            "Candado": r.get("candado", "")
        })
    st.dataframe(pd.DataFrame(data), use_container_width=True)
else:
    st.info("No hay vehículos actualmente parqueados.")

# === HISTORIAL DE FINALIZADOS ===
st.subheader("📜 Historial de registros finalizados")
historial = list(ingresos.find({"estado": "finalizado"}).sort("salida", -1).limit(10))
historial.sort(key=lambda x: orden_tipo.get(x["tipo"], 99))

if historial:
    data = []
    for r in historial:
        data.append({
            "Nombre": r["nombre"],
            "Cédula": r["cedula"],
            "Tipo": r["tipo"].capitalize(),
            "Marca": r["marca"],
            "Ingreso": r["ingreso"].astimezone(CO).strftime("%Y-%m-%d %H:%M"),
            "Salida": r["salida"].astimezone(CO).strftime("%Y-%m-%d %H:%M"),
            "Duración": r.get("duracion_str", "-"),
            "Candado": r.get("candado", "")
        })
    st.dataframe(pd.DataFrame(data), use_container_width=True)
else:
    st.info("No hay registros finalizados aún.")

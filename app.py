import streamlit as st
from datetime import datetime
import pytz
from pymongo import MongoClient
import pandas as pd

# === CONFIGURACIÓN ===
st.set_page_config(page_title="🛴🚲 Check VIVA", layout="centered")
st.title("🛴🚲 Registro de Patinetas y Bicicletas – CC VIVA Envigado")
zona_col = pytz.timezone("America/Bogota")

# === CONEXIÓN MONGO ===
client = MongoClient(st.secrets["mongo_uri"])
db = client.check_viva
usuarios = db.usuarios
vehiculos = db.vehiculos
ingresos = db.ingresos

# === UTILS ===
def ahora():
    return datetime.now(zona_col)

def formatear_duracion(inicio, fin):
    duracion = fin - inicio
    dias = duracion.days
    horas, rem = divmod(duracion.seconds, 3600)
    minutos, segundos = divmod(rem, 60)
    if dias > 0:
        return f"{dias}d {horas:02}:{minutos:02}:{segundos:02}"
    return f"{horas:02}:{minutos:02}:{segundos:02}"

# === INGRESO ===
st.subheader("🟢 Ingreso de vehículo")
cedula = st.text_input("Número de cédula")

if cedula:
    usuario = usuarios.find_one({"cedula": cedula})
    vehiculo = vehiculos.find_one({"cedula": cedula})

    if usuario and vehiculo:
        st.success(f"Vehículo registrado previamente: {vehiculo['tipo'].capitalize()} – {vehiculo['marca']}")
        if st.button("Registrar ingreso"):
            ingreso = {
                "cedula": cedula,
                "nombre": usuario["nombre"],
                "tipo": vehiculo["tipo"],
                "marca": vehiculo["marca"],
                "color": vehiculo.get("color", ""),
                "candado": vehiculo.get("candado", ""),
                "ingreso": ahora(),
                "salida": None,
                "estado": "activo"
            }
            ingresos.insert_one(ingreso)
            st.success("✅ Ingreso registrado.")
            st.rerun()
    else:
        nombre = st.text_input("Nombre completo")
        tipo = st.selectbox("Tipo de vehículo", ["Patineta", "Bicicleta"])
        marca = st.text_input("Marca o referencia")
        color = st.text_input("Color (opcional)")
        candado = st.text_input("Candado (opcional)")

        if st.button("Registrar usuario y vehículo + ingreso"):
            usuarios.insert_one({"cedula": cedula, "nombre": nombre})
            vehiculos.insert_one({
                "cedula": cedula,
                "tipo": tipo.lower(),
                "marca": marca,
                "color": color,
                "candado": candado
            })
            ingresos.insert_one({
                "cedula": cedula,
                "nombre": nombre,
                "tipo": tipo.lower(),
                "marca": marca,
                "color": color,
                "candado": candado,
                "ingreso": ahora(),
                "salida": None,
                "estado": "activo"
            })
            st.success("✅ Usuario, vehículo e ingreso registrados.")
            st.rerun()

# === SALIDA ===
st.subheader("🔴 Registrar salida")
cedula_salida = st.text_input("Número de cédula para salida")

if cedula_salida:
    vehiculo_activo = ingresos.find_one({"cedula": cedula_salida, "estado": "activo"})
    if vehiculo_activo:
        salida_hora = ahora()
        ingreso_dt = vehiculo_activo["ingreso"]
        duracion = formatear_duracion(ingreso_dt, salida_hora)
        duracion_min = int((salida_hora - ingreso_dt).total_seconds() / 60)

        ingresos.update_one(
            {"_id": vehiculo_activo["_id"]},
            {"$set": {
                "salida": salida_hora,
                "estado": "finalizado",
                "duracion_str": duracion,
                "duracion_min": duracion_min
            }}
        )
        st.success(f"✅ Salida registrada. Duración: {duracion}")
        st.rerun()
    else:
        st.info("No hay ingreso activo para esta cédula.")

# === PARQUEADOS ACTUALMENTE ===
st.subheader("🚧 Vehículos actualmente parqueados")
activos = list(ingresos.find({"estado": "activo"}))
if activos:
    df_activos = pd.DataFrame(activos)
    df_activos["Hora ingreso"] = pd.to_datetime(df_activos["ingreso"]).dt.tz_localize("UTC").dt.tz_convert(zona_col).dt.strftime("%Y-%m-%d %H:%M")
    df_activos = df_activos[["nombre", "cedula", "tipo", "marca", "Hora ingreso", "candado"]]
    df_activos.columns = ["Nombre", "Cédula", "Tipo", "Marca", "Hora ingreso", "Candado"]
    st.dataframe(df_activos, use_container_width=True)
else:
    st.info("No hay vehículos actualmente parqueados.")

# === HISTORIAL FINALIZADOS ===
st.subheader("📜 Últimos ingresos finalizados")
finalizados = list(ingresos.find({"estado": "finalizado"}).sort("salida", -1).limit(10))
if finalizados:
    df_finalizados = pd.DataFrame(finalizados)
    df_finalizados["ingreso"] = pd.to_datetime(df_finalizados["ingreso"]).dt.tz_localize("UTC").dt.tz_convert(zona_col).dt.strftime("%Y-%m-%d %H:%M")
    df_finalizados["salida"] = pd.to_datetime(df_finalizados["salida"]).dt.tz_localize("UTC").dt.tz_convert(zona_col).dt.strftime("%Y-%m-%d %H:%M")
    df_finalizados = df_finalizados[["nombre", "cedula", "tipo", "marca", "ingreso", "salida", "duracion_str", "candado"]]
    df_finalizados.columns = ["Nombre", "Cédula", "Tipo", "Marca", "Ingreso", "Salida", "Duración", "Candado"]
    st.dataframe(df_finalizados, use_container_width=True)
else:
    st.info("No hay registros finalizados aún.")
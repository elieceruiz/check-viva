import streamlit as st
from datetime import datetime
import pytz
import pandas as pd
from pymongo import MongoClient

# === CONFIGURACIÓN ===
st.set_page_config(page_title="🛴🚲 Registro de Patinetas y Bicicletas – CC VIVA Envigado", layout="centered")
zona_col = pytz.timezone("America/Bogota")
client = MongoClient(st.secrets["mongo_uri"])
db = client.check_viva
ingresos = db.ingresos
vehiculos = db.vehiculos

# === UTILIDADES ===
def ahora_col():
    return datetime.now(tz=pytz.utc).astimezone(zona_col)

def calcular_duracion(inicio, fin):
    if inicio.tzinfo:
        inicio = inicio.astimezone(pytz.utc).replace(tzinfo=None)
    if fin.tzinfo:
        fin = fin.astimezone(pytz.utc).replace(tzinfo=None)
    duracion = fin - inicio
    dias = duracion.days
    horas, rem = divmod(duracion.seconds, 3600)
    minutos, segundos = divmod(rem, 60)
    return f"{dias}d {horas:02d}:{minutos:02d}:{segundos:02d}" if dias else f"{horas:02d}:{minutos:02d}:{segundos:02d}"

# === FORMULARIO DE INGRESO ===
st.title("🛴🚲 Registro de Patinetas y Bicicletas – CC VIVA Envigado")
st.subheader("🟢 Ingreso de vehículo")

cedula = st.text_input("Número de cédula").strip()

if cedula:
    vehiculo = vehiculos.find_one({"cedula": cedula})
    if vehiculo:
        nombre = vehiculo["nombre"]
        tipo = vehiculo["tipo"]
        marca = vehiculo["marca"]
        st.success(f"Vehículo encontrado: {tipo} – {marca}")
        if st.button("Registrar ingreso"):
            ya_activo = ingresos.find_one({"cedula": cedula, "estado": "activo"})
            if ya_activo:
                st.warning("⚠️ Ya hay un ingreso activo para esta cédula.")
            else:
                ingresos.insert_one({
                    "cedula": cedula,
                    "nombre": nombre,
                    "tipo": tipo,
                    "marca": marca,
                    "ingreso": ahora_col(),
                    "estado": "activo",
                    "candado": "No"
                })
                st.success("✅ Ingreso registrado correctamente.")
                st.experimental_rerun()
    else:
        st.info("🔍 No se encontró un vehículo con esta cédula. Completa los datos para registrarlo.")
        with st.form("form_registro_manual"):
            nombre = st.text_input("Nombre completo")
            tipo = st.selectbox("Tipo de vehículo", ["Patineta", "Bicicleta"])
            marca = st.text_input("Marca o referencia")
            submitted = st.form_submit_button("Guardar y registrar ingreso")
            if submitted and nombre and tipo and marca:
                vehiculos.insert_one({"cedula": cedula, "nombre": nombre, "tipo": tipo, "marca": marca})
                ingresos.insert_one({
                    "cedula": cedula,
                    "nombre": nombre,
                    "tipo": tipo,
                    "marca": marca,
                    "ingreso": ahora_col(),
                    "estado": "activo",
                    "candado": "No"
                })
                st.success("✅ Vehículo registrado e ingreso guardado.")
                st.experimental_rerun()
            elif submitted:
                st.error("❗ Por favor completa todos los campos.")

# === FORMULARIO DE SALIDA ===
st.subheader("🔴 Registrar salida")
cedula_salida = st.text_input("Número de cédula para salida")

if cedula_salida:
    vehiculo_activo = ingresos.find_one({"cedula": cedula_salida, "estado": "activo"})
    if vehiculo_activo:
        salida_hora = ahora_col()
        duracion = calcular_duracion(vehiculo_activo["ingreso"], salida_hora)
        ingresos.update_one(
            {"_id": vehiculo_activo["_id"]},
            {"$set": {
                "salida": salida_hora,
                "estado": "finalizado",
                "duracion_str": duracion
            }}
        )
        st.success(f"✅ Salida registrada. Duración: {duracion}")
        st.experimental_rerun()
    else:
        st.warning("❌ No hay ingreso activo para esta cédula.")

# === VISUALIZACIÓN: ACTIVOS ===
st.subheader("🚧 Vehículos actualmente parqueados")
activos = list(ingresos.find({"estado": "activo"}).sort("ingreso", -1))
if activos:
    df_activos = pd.DataFrame(activos)
    df_activos["Hora ingreso"] = pd.to_datetime(df_activos["ingreso"]).dt.tz_localize(None).dt.strftime("%Y-%m-%d %H:%M:%S")
    df_activos = df_activos[["nombre", "cedula", "tipo", "marca", "Hora ingreso", "candado"]]
    df_activos.rename(columns={"nombre": "Nombre", "cedula": "Cédula", "tipo": "Tipo", "marca": "Marca", "candado": "Candado"}, inplace=True)
    st.dataframe(df_activos, use_container_width=True)
else:
    st.info("No hay vehículos actualmente parqueados.")

# === VISUALIZACIÓN: FINALIZADOS ===
st.subheader("📜 Últimos ingresos finalizados")
finalizados = list(ingresos.find({"estado": "finalizado"}).sort("salida", -1).limit(20))
if finalizados:
    df_finalizados = pd.DataFrame(finalizados)
    df_finalizados["Salida"] = pd.to_datetime(df_finalizados["salida"]).dt.tz_localize(None).dt.strftime("%Y-%m-%d %H:%M:%S")
    df_finalizados["Duración"] = df_finalizados["duracion_str"]
    df_finalizados = df_finalizados[["Salida", "Duración", "candado"]]
    df_finalizados.rename(columns={"candado": "Candado"}, inplace=True)
    st.dataframe(df_finalizados, use_container_width=True)
else:
    st.info("No hay registros finalizados.")
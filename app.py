import streamlit as st
from datetime import datetime
import pytz
import pymongo
import pandas as pd

# === CONFIGURACIÓN GENERAL ===
st.set_page_config(page_title="🛴🚲 Registro de Patinetas y Bicicletas – CC VIVA Envigado", layout="centered")
zona_col = pytz.timezone("America/Bogota")

# === CONEXIÓN MONGODB ===
client = pymongo.MongoClient(st.secrets["mongo_uri"])
db = client["check_viva"]
usuarios_col = db["usuarios"]
vehiculos_col = db["vehiculos"]
ingresos_col = db["ingresos"]

# === FUNCIONES ===
def formatear_duracion(inicio, fin):
    if not isinstance(inicio, datetime): inicio = pd.to_datetime(inicio)
    if not isinstance(fin, datetime): fin = pd.to_datetime(fin)
    if inicio.tzinfo is None: inicio = inicio.tz_localize("UTC").tz_convert(zona_col)
    if fin.tzinfo is None: fin = fin.tz_localize("UTC").tz_convert(zona_col)
    duracion = fin - inicio
    return str(duracion).split(".")[0]

def mostrar_datos_vehiculo(cedula):
    vehiculo = vehiculos_col.find_one({"cedula": cedula})
    if vehiculo:
        detalles = f"""
**Vehículo registrado:**

- Tipo: {vehiculo.get('tipo', '')}
- Marca: {vehiculo.get('marca', '')}
- Color: {vehiculo.get('color', '')}
- Candado: {vehiculo.get('candado', '')}
"""
        st.success(detalles)
    else:
        st.info("No hay vehículo registrado con esta cédula.")

# === INTERFAZ ===
st.title("🛴🚲 Registro de Patinetas y Bicicletas – CC VIVA Envigado")

# --- REGISTRO DE INGRESO ---
st.subheader("🟢 Ingreso de vehículo")
with st.form("ingreso_form"):
    cedula_ingreso = st.text_input("Número de cédula", max_chars=15)
    submitted_ingreso = st.form_submit_button("Registrar ingreso")
    if submitted_ingreso and cedula_ingreso:
        usuario = usuarios_col.find_one({"cedula": cedula_ingreso})
        if not usuario:
            st.warning("Usuario no registrado. Por favor completa los datos.")
            nombre = st.text_input("Nombre completo", key="nombre_ingreso")
            tipo = st.selectbox("Tipo de vehículo", ["patineta", "bicicleta"], index=0, key="tipo_ingreso")
            marca = st.text_input("Marca o referencia", key="marca_ingreso")
            color = st.text_input("Color del vehículo", key="color_ingreso")
            candado = st.selectbox("¿Tiene candado?", ["Sí", "No"], key="candado_ingreso")

            if st.form_submit_button("Guardar nuevo ingreso"):
                now = datetime.now(zona_col)
                usuarios_col.insert_one({"cedula": cedula_ingreso, "nombre": nombre})
                vehiculos_col.insert_one({
                    "cedula": cedula_ingreso,
                    "tipo": tipo,
                    "marca": marca,
                    "color": color,
                    "candado": candado
                })
                ingresos_col.insert_one({
                    "cedula": cedula_ingreso,
                    "nombre": nombre,
                    "tipo": tipo,
                    "marca": marca,
                    "color": color,
                    "candado": candado,
                    "ingreso": now
                })
                st.success("Ingreso registrado exitosamente.")
                st.experimental_rerun()
        else:
            vehiculo = vehiculos_col.find_one({"cedula": cedula_ingreso})
            nombre = usuario["nombre"]
            now = datetime.now(zona_col)
            if vehiculo:
                ingresos_col.insert_one({
                    "cedula": cedula_ingreso,
                    "nombre": nombre,
                    "tipo": vehiculo.get("tipo", ""),
                    "marca": vehiculo.get("marca", ""),
                    "color": vehiculo.get("color", ""),
                    "candado": vehiculo.get("candado", ""),
                    "ingreso": now
                })
                st.success("Ingreso registrado correctamente.")
                mostrar_datos_vehiculo(cedula_ingreso)
                st.experimental_rerun()
            else:
                st.warning("No se encontró vehículo registrado con esta cédula.")

# --- REGISTRO DE SALIDA ---
st.subheader("🔴 Registrar salida")
cedula_salida = st.text_input("Número de cédula para salida")
if cedula_salida:
    ingreso_activo = ingresos_col.find_one({"cedula": cedula_salida, "salida": {"$exists": False}})
    if ingreso_activo:
        salida_hora = datetime.now(zona_col)
        ingreso_dt = ingreso_activo["ingreso"]
        duracion_str = formatear_duracion(ingreso_dt, salida_hora)

        ingresos_col.update_one(
            {"_id": ingreso_activo["_id"]},
            {"$set": {
                "salida": salida_hora,
                "duracion": duracion_str
            }}
        )
        st.success(f"Salida registrada. Duración: {duracion_str}")
        st.experimental_rerun()
    else:
        st.warning("❌ No hay vehículo activo para esta cédula.")

# --- VEHÍCULOS PARQUEADOS ACTUALMENTE ---
st.subheader("🚧 Vehículos actualmente parqueados")
activos = list(ingresos_col.find({"salida": {"$exists": False}}))
if activos:
    df_activos = pd.DataFrame(activos)
    df_activos["ingreso"] = pd.to_datetime(df_activos["ingreso"]).dt.tz_convert(zona_col).dt.strftime("%Y-%m-%d %H:%M:%S")
    df_activos = df_activos[["cedula", "tipo", "marca", "color", "candado", "ingreso"]]
    df_activos.index = range(len(df_activos), 0, -1)
    st.dataframe(df_activos, use_container_width=True)
else:
    st.info("No hay vehículos actualmente parqueados.")

# --- HISTÓRICO DE INGRESOS FINALIZADOS ---
st.subheader("📜 Últimos ingresos finalizados")
finalizados = list(ingresos_col.find({"salida": {"$exists": True}}).sort("salida", -1))
if finalizados:
    df_finalizados = pd.DataFrame(finalizados)
    df_finalizados["ingreso"] = pd.to_datetime(df_finalizados["ingreso"]).dt.tz_convert(zona_col).dt.strftime("%Y-%m-%d %H:%M:%S")
    df_finalizados["salida"] = pd.to_datetime(df_finalizados["salida"]).dt.tz_convert(zona_col).dt.strftime("%Y-%m-%d %H:%M:%S")
    df_finalizados = df_finalizados[["cedula", "nombre", "tipo", "marca", "color", "candado", "ingreso", "salida", "duracion"]]
    df_finalizados.index = range(len(df_finalizados), 0, -1)
    st.dataframe(df_finalizados, use_container_width=True)
else:
    st.info("No hay registros finalizados.")
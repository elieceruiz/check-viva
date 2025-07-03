import streamlit as st
from pymongo import MongoClient
from datetime import datetime
import pytz
import pandas as pd

# === CONFIG ===
st.set_page_config(page_title="🛴🚲 Check VIVA", layout="centered")
st.title("🛴🚲 Registro de Patinetas y Bicicletas – CC VIVA Envigado")

# === CONEXIÓN MONGO ===
MONGO_URI = st.secrets["mongo_uri"]
client = MongoClient(MONGO_URI)
db = client.check_viva
usuarios = db.usuarios
vehiculos = db.vehiculos

# === ZONA HORARIA ===
zona_col = pytz.timezone("America/Bogota")
ahora = datetime.now(zona_col)

# === INGRESO DE VEHÍCULO ===
st.subheader("🟢 Ingreso de vehículo")

cedula = st.text_input("Número de cédula")
usuario = usuarios.find_one({"cedula": cedula}) if cedula else None

if usuario:
    st.success(f"Usuario encontrado: {usuario['nombre']}")
    with st.form("form_registro_vehiculo"):
        tipo = st.selectbox("Tipo de vehículo", ["Patineta", "Bicicleta"])
        marca = st.text_input("Marca o referencia")
        color = st.text_input("Color o señas distintivas (opcional)")
        candado = st.text_input("Candado entregado (opcional)")
        confirmar = st.form_submit_button("🟢 Registrar ingreso")

        if confirmar:
            if tipo and marca:
                vehiculos.insert_one({
                    "cedula": cedula,
                    "nombre": usuario["nombre"],
                    "tipo": tipo.lower(),
                    "marca": marca,
                    "color": color,
                    "candado": candado,
                    "ingreso": ahora,
                    "estado": "activo"
                })
                st.success("✅ Ingreso de vehículo registrado.")
                st.rerun()
            else:
                st.warning("Marca y tipo son obligatorios.")
else:
    if cedula:
        nombre = st.text_input("Nombre completo")
        with st.form("form_nuevo_usuario"):
            tipo = st.selectbox("Tipo de vehículo", ["Patineta", "Bicicleta"], key="nuevo_tipo")
            marca = st.text_input("Marca o referencia", key="nuevo_marca")
            color = st.text_input("Color o señas distintivas (opcional)", key="nuevo_color")
            candado = st.text_input("Candado entregado (opcional)", key="nuevo_candado")
            confirmar = st.form_submit_button("🟢 Registrar nuevo usuario y vehículo")

            if confirmar:
                if nombre and tipo and marca:
                    usuarios.insert_one({
                        "cedula": cedula,
                        "nombre": nombre,
                        "fecha_registro": ahora
                    })
                    vehiculos.insert_one({
                        "cedula": cedula,
                        "nombre": nombre,
                        "tipo": tipo.lower(),
                        "marca": marca,
                        "color": color,
                        "candado": candado,
                        "ingreso": ahora,
                        "estado": "activo"
                    })
                    st.success("✅ Usuario y vehículo registrados.")
                    st.rerun()
                else:
                    st.warning("Todos los campos obligatorios deben completarse.")

# === VISTA DE PARQUEADOS ACTIVOS ===
st.subheader("🚧 Vehículos actualmente parqueados")
activos = list(vehiculos.find({"estado": "activo"}).sort("ingreso", -1))

if activos:
    df_activos = pd.DataFrame(activos)
    df_activos["Hora ingreso"] = pd.to_datetime(df_activos["ingreso"]).dt.tz_localize("UTC").dt.tz_convert(zona_col).dt.strftime("%Y-%m-%d %H:%M:%S")
    df_activos.index = range(1, len(df_activos)+1)  # Arranca en 1
    st.dataframe(df_activos[["nombre", "cedula", "tipo", "marca", "color", "candado", "Hora ingreso"]], use_container_width=True)
else:
    st.info("No hay vehículos actualmente parqueados.")

# === HISTORIAL DE SALIDAS ===
st.subheader("📜 Últimos ingresos finalizados")
finalizados = list(vehiculos.find({"estado": "finalizado"}).sort("salida", -1).limit(10))

if finalizados:
    df_final = pd.DataFrame(finalizados)
    df_final["Ingreso"] = pd.to_datetime(df_final["ingreso"]).dt.tz_localize("UTC").dt.tz_convert(zona_col).dt.strftime("%Y-%m-%d %H:%M")
    df_final["Salida"] = pd.to_datetime(df_final["salida"]).dt.tz_localize("UTC").dt.tz_convert(zona_col).dt.strftime("%Y-%m-%d %H:%M")
    df_final.index = range(1, len(df_final)+1)  # Arranca en 1
    st.dataframe(df_final[["nombre", "cedula", "tipo", "marca", "Ingreso", "Salida", "duracion_str"]], use_container_width=True)
else:
    st.info("No hay registros finalizados aún.")
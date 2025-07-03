import streamlit as st
from pymongo import MongoClient
from datetime import datetime
import pandas as pd
import pytz

# === CONFIGURACIÓN INICIAL ===
st.set_page_config(page_title="🛴🚲 Check VIVA", layout="centered")
st.title("🛴🚲 Registro de Patinetas y Bicicletas – CC VIVA Envigado")
zona_col = pytz.timezone("America/Bogota")
ahora = datetime.now(zona_col)

# === CONEXIÓN MONGODB ===
MONGO_URI = st.secrets["mongo_uri"]
client = MongoClient(MONGO_URI)
db = client.check_viva
usuarios = db.usuarios
vehiculos = db.vehiculos

# === BANDERA DE CÉDULA DESPUÉS DE RERUN ===
if "cedula_temp" in st.session_state:
    cedula_ing = st.session_state["cedula_temp"]
    st.session_state.pop("cedula_temp")
else:
    cedula_ing = st.text_input("Número de cédula")

# === BLOQUE DE INGRESO ===
if cedula_ing:
    usuario = usuarios.find_one({"cedula": cedula_ing})

    if not usuario:
        nombre = st.text_input("Nombre completo")
        if nombre and st.button("Registrar nuevo usuario"):
            usuarios.insert_one({
                "cedula": cedula_ing,
                "nombre": nombre,
                "fecha_registro": ahora
            })
            st.session_state["cedula_temp"] = cedula_ing
            st.success("✅ Usuario registrado correctamente.")
            st.rerun()
    else:
        st.success(f"Usuario encontrado: {usuario['nombre']}")
        with st.form("form_vehiculo"):
            tipo = st.selectbox("Tipo de vehículo", ["Patineta", "Bicicleta"])
            marca = st.text_input("Marca o referencia")
            color = st.text_input("Color o señas distintivas (opcional)")
            candado = st.text_input("Candado entregado (opcional)")
            confirmar = st.form_submit_button("🟢 Registrar ingreso")

            if confirmar:
                vehiculos.insert_one({
                    "cedula": cedula_ing,
                    "nombre": usuario["nombre"],
                    "tipo": tipo.lower(),
                    "marca": marca,
                    "color": color,
                    "candado": candado,
                    "ingreso": ahora,
                    "estado": "activo"
                })
                st.success("🟢 Vehículo registrado correctamente.")
                st.rerun()

# === SALIDA ===
st.subheader("🔴 Registrar salida")
cedula_salida = st.text_input("Número de cédula para salida")

if cedula_salida:
    vehiculo_activo = vehiculos.find_one({"cedula": cedula_salida, "estado": "activo"})
    if vehiculo_activo:
        salida = datetime.now(zona_col)
        ingreso = vehiculo_activo["ingreso"]
        if ingreso.tzinfo is None:
            ingreso = zona_col.localize(ingreso)
        duracion = salida - ingreso
        minutos = int(duracion.total_seconds() / 60)
        duracion_str = str(duracion).split(".")[0]  # sin microsegundos

        vehiculos.update_one(
            {"_id": vehiculo_activo["_id"]},
            {"$set": {
                "salida": salida,
                "estado": "finalizado",
                "duracion_str": duracion_str,
                "duracion_min": minutos
            }}
        )
        st.success(f"✅ Salida registrada. Duración: {duracion_str}")
        st.rerun()
    else:
        st.warning("❌ No hay vehículo activo registrado con esa cédula.")

# === MOSTRAR REGISTROS ===
st.subheader("🚧 Vehículos actualmente parqueados")
activos = list(vehiculos.find({"estado": "activo"}))
if activos:
    df_activos = pd.DataFrame(activos)
    df_activos["Hora ingreso"] = pd.to_datetime(df_activos["ingreso"]).dt.tz_localize("UTC").dt.tz_convert(zona_col).dt.strftime("%Y-%m-%d %H:%M:%S")
    df_activos = df_activos[["nombre", "cedula", "tipo", "marca", "Hora ingreso", "candado"]]
    df_activos.columns = ["Nombre", "Cédula", "Tipo", "Marca", "Hora ingreso", "Candado"]
    st.dataframe(df_activos, use_container_width=True)
else:
    st.info("No hay vehículos actualmente parqueados.")

st.subheader("📜 Últimos ingresos finalizados")
finalizados = list(vehiculos.find({"estado": "finalizado"}).sort("salida", -1).limit(10))
if finalizados:
    df_finalizados = pd.DataFrame(finalizados)
    df_finalizados["Ingreso"] = pd.to_datetime(df_finalizados["ingreso"]).dt.tz_localize("UTC").dt.tz_convert(zona_col).dt.strftime("%Y-%m-%d %H:%M:%S")
    df_finalizados["Salida"] = pd.to_datetime(df_finalizados["salida"]).dt.tz_localize("UTC").dt.tz_convert(zona_col).dt.strftime("%Y-%m-%d %H:%M:%S")
    df_finalizados = df_finalizados[["nombre", "cedula", "tipo", "marca", "Ingreso", "Salida", "duracion_str", "candado"]]
    df_finalizados.columns = ["Nombre", "Cédula", "Tipo", "Marca", "Ingreso", "Salida", "Duración", "Candado"]
    st.dataframe(df_finalizados, use_container_width=True)
else:
    st.info("No hay registros finalizados aún.")

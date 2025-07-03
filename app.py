from datetime import datetime
import pytz
import streamlit as st
from pymongo import MongoClient
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
ingresos = db.ingresos

# === ZONA HORARIA ===
zona_col = pytz.timezone("America/Bogota")
ahora = datetime.now(zona_col)

# === INGRESO ===
st.subheader("🟢 Ingreso de vehículo")
cedula = st.text_input("Número de cédula")

if cedula:
    usuario = usuarios.find_one({"cedula": cedula})
    vehiculo = vehiculos.find_one({"cedula": cedula})

    if usuario and vehiculo:
        st.success(f"✅ {usuario['nombre']} – {vehiculo['tipo'].capitalize()} – {vehiculo['marca']}")
        if st.button("Registrar ingreso"):
            ingresos.insert_one({
                "cedula": cedula,
                "nombre": usuario["nombre"],
                "tipo": vehiculo["tipo"],
                "marca": vehiculo["marca"],
                "color": vehiculo["color"],
                "candado": vehiculo["candado"],
                "ingreso": ahora,
                "salida": None,
                "estado": "activo"
            })
            st.success("Ingreso registrado exitosamente.")
            st.rerun()
    else:
        with st.form("form_nuevo_ingreso"):
            nombre = st.text_input("Nombre completo")
            tipo = st.selectbox("Tipo de vehículo", ["patineta", "bicicleta"])
            marca = st.text_input("Marca o referencia")
            color = st.text_input("Color o señas distintivas")
            candado = st.text_input("Candado entregado (opcional)", value="No")
            submitted = st.form_submit_button("Registrar nuevo ingreso")

            if submitted and nombre and tipo and marca:
                usuarios.insert_one({
                    "cedula": cedula,
                    "nombre": nombre
                })
                vehiculos.insert_one({
                    "cedula": cedula,
                    "tipo": tipo,
                    "marca": marca,
                    "color": color,
                    "candado": candado
                })
                ingresos.insert_one({
                    "cedula": cedula,
                    "nombre": nombre,
                    "tipo": tipo,
                    "marca": marca,
                    "color": color,
                    "candado": candado,
                    "ingreso": ahora,
                    "salida": None,
                    "estado": "activo"
                })
                st.success("Usuario, vehículo e ingreso registrados exitosamente.")
                st.rerun()
            elif submitted:
                st.warning("Por favor completa todos los campos obligatorios.")

# === SALIDA ===
st.subheader("🔴 Registrar salida")
cedula_salida = st.text_input("Número de cédula para salida")

if cedula_salida:
    activo = ingresos.find_one({"cedula": cedula_salida, "estado": "activo"})
    if activo:
        if st.button("Registrar salida ahora"):
            salida_hora = datetime.now(zona_col)
            ingreso_hora = activo["ingreso"]
            if ingreso_hora.tzinfo is None:
                ingreso_hora = zona_col.localize(ingreso_hora)
            duracion = salida_hora - ingreso_hora
            duracion_str = str(duracion).split(".")[0]
            ingresos.update_one(
                {"_id": activo["_id"]},
                {"$set": {
                    "salida": salida_hora,
                    "estado": "finalizado",
                    "duracion": duracion_str
                }}
            )
            st.success(f"Salida registrada. Duración: {duracion_str}")
            st.rerun()
    else:
        st.info("No hay ingreso activo para esta cédula.")

# === PARQUEADOS ===
st.subheader("🚧 Vehículos actualmente parqueados")
activos = list(ingresos.find({"estado": "activo"}).sort("ingreso", -1))
if activos:
    df_activos = pd.DataFrame(activos)
    df_activos["Hora ingreso"] = pd.to_datetime(df_activos["ingreso"])
    df_activos["Hora ingreso"] = df_activos["Hora ingreso"].dt.tz_localize("UTC").dt.tz_convert(zona_col).dt.strftime("%Y-%m-%d %H:%M:%S")
    df_activos.index = range(len(df_activos), 0, -1)
    st.dataframe(df_activos[["nombre", "cedula", "tipo", "marca", "Hora ingreso", "candado"]], use_container_width=True)
else:
    st.info("No hay vehículos actualmente parqueados.")

# === HISTORIAL ===
st.subheader("📜 Últimos ingresos finalizados")
finalizados = list(ingresos.find({"estado": "finalizado"}).sort("salida", -1).limit(10))
if finalizados:
    df_finalizados = pd.DataFrame(finalizados)
    df_finalizados["Ingreso"] = pd.to_datetime(df_finalizados["ingreso"])
    df_finalizados["Salida"] = pd.to_datetime(df_finalizados["salida"])
    df_finalizados["Ingreso"] = df_finalizados["Ingreso"].dt.tz_localize("UTC").dt.tz_convert(zona_col).dt.strftime("%Y-%m-%d %H:%M:%S")
    df_finalizados["Salida"] = df_finalizados["Salida"].dt.tz_localize("UTC").dt.tz_convert(zona_col).dt.strftime("%Y-%m-%d %H:%M:%S")
    df_finalizados.index = range(len(df_finalizados), 0, -1)
    st.dataframe(df_finalizados[["nombre", "cedula", "tipo", "marca", "Ingreso", "Salida", "duracion", "candado"]], use_container_width=True)
else:
    st.info("No hay ingresos finalizados aún.")
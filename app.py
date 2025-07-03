from datetime import datetime
import pytz
import streamlit as st
from pymongo import MongoClient
import pandas as pd

# === CONFIG ===
st.set_page_config(page_title="🛴🚲 Check VIVA", layout="centered")
st.title("🛴🚲 Registro de Patinetas y Bicicletas – CC VIVA Envigado")

# === CONEXIONES Y ZONAS ===
MONGO_URI = st.secrets["mongo_uri"]
cliente = MongoClient(MONGO_URI)
db = cliente.check_viva
usuarios = db.usuarios
vehiculos = db.vehiculos
ingresos = db.ingresos
zona_col = pytz.timezone("America/Bogota")

# === FUNCIÓN FORMATO DURACIÓN ===
def formatear_duracion(inicio, fin):
    if not inicio.tzinfo:
        inicio = zona_col.localize(inicio)
    if not fin.tzinfo:
        fin = zona_col.localize(fin)
    delta = fin - inicio
    dias = delta.days
    horas, rem = divmod(delta.seconds, 3600)
    minutos, segundos = divmod(rem, 60)
    if dias > 0:
        return f"{dias}d {horas:02}:{minutos:02}:{segundos:02}"
    return f"{horas:02}:{minutos:02}:{segundos:02}"

# === INGRESO DE VEHÍCULO ===
st.subheader("🟢 Ingreso de vehículo")
cedula = st.text_input("Número de cédula")

if cedula:
    usuario = usuarios.find_one({"cedula": cedula})
    if usuario:
        nombre = usuario["nombre"]
        st.success(f"Usuario: {nombre}")
        vehiculo = vehiculos.find_one({"cedula": cedula})
    else:
        nombre = st.text_input("Nombre completo")
        if nombre and st.button("Registrar nuevo usuario"):
            usuarios.insert_one({"cedula": cedula, "nombre": nombre})
            st.success("✅ Usuario registrado.")
            st.rerun()

    if usuario or nombre:
        with st.form("form_vehiculo"):
            tipo = st.selectbox("Tipo de vehículo", ["Patineta", "Bicicleta"])
            marca = st.text_input("Marca o referencia")
            color = st.text_input("Color o señas distintivas (opcional)")
            candado = st.text_input("Candado entregado (opcional)")
            submit = st.form_submit_button("🟢 Registrar ingreso")

            if submit and marca:
                vehiculos.update_one(
                    {"cedula": cedula},
                    {"$set": {
                        "tipo": tipo.lower(),
                        "marca": marca,
                        "color": color,
                        "candado": candado
                    }},
                    upsert=True
                )
                now = datetime.now(zona_col)
                ingresos.insert_one({
                    "cedula": cedula,
                    "nombre": nombre if not usuario else usuario["nombre"],
                    "tipo": tipo.lower(),
                    "marca": marca,
                    "color": color,
                    "candado": candado,
                    "ingreso": now,
                    "estado": "activo"
                })
                st.success("✅ Ingreso registrado.")
                st.rerun()

# === SALIDA DE VEHÍCULO ===
st.subheader("🔴 Registrar salida")
cedula_salida = st.text_input("Número de cédula para salida")

if cedula_salida:
    vehiculo_activo = ingresos.find_one({"cedula": cedula_salida, "estado": "activo"})
    if vehiculo_activo:
        st.info(f"Vehículo encontrado: {vehiculo_activo['tipo'].capitalize()} – {vehiculo_activo['marca']}")
        if st.button("Registrar salida"):
            salida = datetime.now(zona_col)
            ingreso = vehiculo_activo["ingreso"]
            if not ingreso.tzinfo:
                ingreso = zona_col.localize(ingreso)
            duracion_str = formatear_duracion(ingreso, salida)
            duracion_min = int((salida - ingreso).total_seconds() // 60)

            ingresos.update_one(
                {"_id": vehiculo_activo["_id"]},
                {"$set": {
                    "salida": salida,
                    "estado": "finalizado",
                    "duracion_str": duracion_str,
                    "duracion_min": duracion_min
                }}
            )
            st.success(f"✅ Salida registrada. Duración: {duracion_str}")
            st.rerun()
    else:
        st.warning("No hay ingreso activo para esa cédula.")

# === VEHÍCULOS PARQUEADOS ===
st.subheader("🚧 Vehículos actualmente parqueados")
activos = list(ingresos.find({"estado": "activo"}))
if activos:
    df_activos = pd.DataFrame(activos)
    df_activos["Hora ingreso"] = pd.to_datetime(df_activos["ingreso"]).dt.tz_localize(zona_col, nonexistent='NaT', ambiguous='NaT', errors='coerce')
    df_activos["Hora ingreso"] = df_activos["Hora ingreso"].dt.strftime("%Y-%m-%d %H:%M:%S")
    df_activos = df_activos[["nombre", "cedula", "tipo", "marca", "Hora ingreso", "candado"]]
    df_activos.columns = ["Nombre", "Cédula", "Tipo", "Marca", "Hora ingreso", "Candado"]
    st.dataframe(df_activos, use_container_width=True)
else:
    st.info("No hay vehículos actualmente parqueados.")

# === HISTORIAL DE FINALIZADOS ===
st.subheader("📜 Últimos ingresos finalizados")
finalizados = list(ingresos.find({"estado": "finalizado"}).sort("salida", -1).limit(10))
if finalizados:
    df_finalizados = pd.DataFrame(finalizados)
    df_finalizados["ingreso"] = pd.to_datetime(df_finalizados["ingreso"])
    df_finalizados["salida"] = pd.to_datetime(df_finalizados["salida"])
    df_finalizados["ingreso"] = df_finalizados["ingreso"].dt.tz_localize(zona_col, nonexistent='NaT', ambiguous='NaT', errors='coerce')
    df_finalizados["salida"] = df_finalizados["salida"].dt.tz_localize(zona_col, nonexistent='NaT', ambiguous='NaT', errors='coerce')
    df_finalizados["Ingreso"] = df_finalizados["ingreso"].dt.strftime("%Y-%m-%d %H:%M:%S")
    df_finalizados["Salida"] = df_finalizados["salida"].dt.strftime("%Y-%m-%d %H:%M:%S")
    df_finalizados = df_finalizados[["nombre", "cedula", "tipo", "marca", "Ingreso", "Salida", "duracion_str", "candado"]]
    df_finalizados.columns = ["Nombre", "Cédula", "Tipo", "Marca", "Ingreso", "Salida", "Duración", "Candado"]
    st.dataframe(df_finalizados, use_container_width=True)
else:
    st.info("No hay registros finalizados.")
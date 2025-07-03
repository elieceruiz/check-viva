import streamlit as st
from datetime import datetime
import pytz
from pymongo import MongoClient
import pandas as pd

# === CONFIGURACIÓN ===
st.set_page_config(page_title="🛴🚲 Check VIVA", layout="centered")
st.title("🛴🚲 Registro de Patinetas y Bicicletas – CC VIVA Envigado")

# === CONEXIÓN MONGODB ===
MONGO_URI = st.secrets["mongo_uri"]
client = MongoClient(MONGO_URI)
db = client.check_viva
vehiculos = db.vehiculos
ingresos = db.ingresos

zona_col = pytz.timezone("America/Bogota")
ahora = datetime.now(tz=zona_col)

# === FUNCIÓN DURACIÓN ===
def formatear_duracion(inicio, fin):
    if inicio.tzinfo is None:
        inicio = zona_col.localize(inicio)
    if fin.tzinfo is None:
        fin = zona_col.localize(fin)
    duracion = fin - inicio
    dias = duracion.days
    horas, rem = divmod(duracion.seconds, 3600)
    minutos, segundos = divmod(rem, 60)
    if dias > 0:
        return f"{dias}d {horas:02}:{minutos:02}:{segundos:02}"
    else:
        return f"{horas:02}:{minutos:02}:{segundos:02}"

# === INGRESO ===
st.subheader("🟢 Ingreso de vehículo")
cedula_ingreso = st.text_input("Número de cédula")

if cedula_ingreso:
    vehiculo = vehiculos.find_one({"cedula": cedula_ingreso})

    if vehiculo and "marca" in vehiculo:
        st.info(f"Vehículo ya registrado: {vehiculo['tipo'].capitalize()} – {vehiculo['marca']}")
        if st.button("Registrar ingreso"):
            ingresos.insert_one({
                "cedula": cedula_ingreso,
                "nombre": vehiculo["nombre"],
                "tipo": vehiculo["tipo"],
                "marca": vehiculo["marca"],
                "ingreso": ahora,
                "estado": "activo",
                "candado": vehiculo.get("candado", "")
            })
            st.success("✅ Ingreso registrado.")
            st.experimental_rerun()

    else:
        with st.form("nuevo_usuario"):
            nombre = st.text_input("Nombre completo")
            tipo = st.selectbox("Tipo de vehículo", ["Patineta", "Bicicleta"])
            marca = st.text_input("Marca o referencia")
            candado = st.text_input("Candado entregado (opcional)")
            confirmar = st.form_submit_button("Registrar usuario e ingreso")

            if confirmar and nombre and tipo and marca:
                vehiculos.insert_one({
                    "cedula": cedula_ingreso,
                    "nombre": nombre,
                    "tipo": tipo.lower(),
                    "marca": marca,
                    "candado": candado,
                    "registro": ahora
                })

                ingresos.insert_one({
                    "cedula": cedula_ingreso,
                    "nombre": nombre,
                    "tipo": tipo.lower(),
                    "marca": marca,
                    "ingreso": ahora,
                    "estado": "activo",
                    "candado": candado
                })

                st.success("✅ Usuario y vehículo registrados.")
                st.experimental_rerun()
            elif confirmar:
                st.warning("Por favor completa todos los campos obligatorios.")

# === SALIDA ===
st.subheader("🔴 Registrar salida")
cedula_salida = st.text_input("Número de cédula para salida")

if cedula_salida:
    vehiculo_activo = ingresos.find_one({"cedula": cedula_salida, "estado": "activo"})
    if vehiculo_activo:
        st.info(f"Vehículo encontrado: {vehiculo_activo['tipo'].capitalize()} – {vehiculo_activo['marca']}")
        if st.button("Registrar salida"):
            salida = datetime.now(tz=zona_col)
            ingreso = vehiculo_activo["ingreso"]
            if ingreso.tzinfo is None:
                ingreso = zona_col.localize(ingreso)
            duracion_str = formatear_duracion(ingreso, salida)
            duracion_min = int((salida - ingreso).total_seconds() / 60)

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
            st.experimental_rerun()
    else:
        st.warning("❌ No hay ingreso activo para esa cédula.")

# === PARQUEADOS ACTUALMENTE ===
st.subheader("🚧 Vehículos actualmente parqueados")
activos = list(ingresos.find({"estado": "activo"}).sort("ingreso", -1))
if activos:
    df_activos = pd.DataFrame(activos)
    df_activos["Hora ingreso"] = pd.to_datetime(df_activos["ingreso"]).dt.tz_localize(None)
    df_activos["Hora ingreso"] = df_activos["Hora ingreso"].dt.strftime("%Y-%m-%d %H:%M:%S")
    df_activos = df_activos[["nombre", "cedula", "tipo", "marca", "Hora ingreso", "candado"]]
    df_activos.rename(columns={
        "nombre": "Nombre",
        "cedula": "Cédula",
        "tipo": "Tipo",
        "marca": "Marca",
        "candado": "Candado"
    }, inplace=True)
    df_activos.index += 1
    st.dataframe(df_activos, use_container_width=True)
else:
    st.info("No hay vehículos actualmente parqueados.")

# === HISTORIAL ===
st.subheader("📜 Últimos ingresos finalizados")
finalizados = list(ingresos.find({"estado": "finalizado"}).sort("salida", -1).limit(20))
if finalizados:
    df_finalizados = pd.DataFrame(finalizados)
    df_finalizados["Ingreso"] = pd.to_datetime(df_finalizados["ingreso"]).dt.tz_localize(None)
    df_finalizados["Salida"] = pd.to_datetime(df_finalizados["salida"]).dt.tz_localize(None)
    df_finalizados["Ingreso"] = df_finalizados["Ingreso"].dt.strftime("%Y-%m-%d %H:%M:%S")
    df_finalizados["Salida"] = df_finalizados["Salida"].dt.strftime("%Y-%m-%d %H:%M:%S")
    df_finalizados = df_finalizados[["nombre", "cedula", "tipo", "marca", "Ingreso", "Salida", "duracion_str"]]
    df_finalizados.rename(columns={
        "nombre": "Nombre",
        "cedula": "Cédula",
        "tipo": "Tipo",
        "marca": "Marca",
        "duracion_str": "Duración"
    }, inplace=True)
    df_finalizados.index += 1
    st.dataframe(df_finalizados, use_container_width=True)
else:
    st.info("No hay ingresos finalizados aún.")
from datetime import datetime
import pytz
import streamlit as st
from pymongo import MongoClient
import pandas as pd

# === CONFIGURACIÓN ===
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

# === FUNCIONES ===
def formatear_duracion(inicio, fin):
    if inicio.tzinfo is None:
        inicio = zona_col.localize(inicio)
    if fin.tzinfo is None:
        fin = zona_col.localize(fin)
    duracion = fin - inicio
    dias = duracion.days
    horas, rem = divmod(duracion.seconds, 3600)
    minutos, _ = divmod(rem, 60)
    if dias > 0:
        return f"{dias}d {horas:02d}:{minutos:02d}"
    else:
        return f"{horas:02d}:{minutos:02d}"

# === INGRESO VEHÍCULO ===
st.subheader("🟢 Ingreso de vehículo")
cedula = st.text_input("Número de cédula")

if cedula:
    usuario = usuarios.find_one({"cedula": cedula})
    vehiculo = vehiculos.find_one({"cedula": cedula})

    if not usuario:
        nombre = st.text_input("Nombre completo")
        if nombre and st.button("Registrar usuario"):
            usuarios.insert_one({"cedula": cedula, "nombre": nombre})
            st.success("✅ Usuario registrado. Ahora continúa con el ingreso.")
            st.rerun()
    else:
        nombre = usuario["nombre"]
        st.info(f"Usuario registrado: {nombre}")

    if usuario:
        if vehiculo:
            st.info("Vehículo registrado previamente.")
            if st.button("🟢 Registrar ingreso ahora"):
                ingresos.insert_one({
                    "cedula": cedula,
                    "nombre": nombre,
                    "tipo": vehiculo["tipo"],
                    "marca": vehiculo["marca"],
                    "color": vehiculo.get("color", ""),
                    "candado": vehiculo.get("candado", ""),
                    "ingreso": ahora,
                    "salida": None,
                    "estado": "activo"
                })
                st.success("🚲 Ingreso registrado correctamente.")
                st.rerun()
        else:
            st.warning("⚠️ No hay vehículo registrado para esta cédula. Ingrésalo a continuación:")
            with st.form("form_vehiculo"):
                tipo = st.selectbox("Tipo de vehículo", ["Patineta", "Bicicleta"])
                marca = st.text_input("Marca o referencia")
                color = st.text_input("Color o señas distintivas (opcional)")
                candado = st.text_input("Candado entregado (opcional)", value="No")
                submit_vehiculo = st.form_submit_button("Registrar vehículo e ingreso")

                if submit_vehiculo:
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
                        "ingreso": ahora,
                        "salida": None,
                        "estado": "activo"
                    })
                    st.success("✅ Vehículo e ingreso registrados correctamente.")
                    st.rerun()

# === SALIDA VEHÍCULO ===
st.subheader("🔴 Registrar salida")
cedula_salida = st.text_input("Número de cédula para salida")

if cedula_salida:
    vehiculo_activo = ingresos.find_one({"cedula": cedula_salida, "estado": "activo"})
    if vehiculo_activo:
        if st.button("Registrar salida"):
            salida_hora = datetime.now(zona_col)
            ingreso_dt = vehiculo_activo["ingreso"]
            duracion_str = formatear_duracion(ingreso_dt, salida_hora)
            duracion_min = int((salida_hora - ingreso_dt).total_seconds() / 60)

            ingresos.update_one(
                {"_id": vehiculo_activo["_id"]},
                {"$set": {
                    "salida": salida_hora,
                    "estado": "finalizado",
                    "duracion_min": duracion_min,
                    "duracion_str": duracion_str
                }}
            )
            st.success(f"✅ Salida registrada. Duración: {duracion_str}")
            st.rerun()
    else:
        st.warning("❌ No hay ingreso activo para esta cédula.")

# === VEHÍCULOS ACTUALMENTE PARQUEADOS ===
st.subheader("🚧 Vehículos actualmente parqueados")
activos = list(ingresos.find({"estado": "activo"}).sort("ingreso", -1))
if activos:
    df_activos = pd.DataFrame(activos)
    df_activos["Hora ingreso"] = pd.to_datetime(df_activos["ingreso"])
    df_activos["Hora ingreso"] = df_activos["Hora ingreso"].dt.tz_localize(None)
    df_activos = df_activos[["nombre", "cedula", "tipo", "marca", "Hora ingreso", "candado"]]
    df_activos.columns = ["Nombre", "Cédula", "Tipo", "Marca", "Hora ingreso", "Candado"]
    df_activos.index = range(len(df_activos), 0, -1)
    st.dataframe(df_activos, use_container_width=True)
else:
    st.info("No hay vehículos actualmente parqueados.")

# === HISTORIAL FINALIZADOS ===
st.subheader("📜 Últimos ingresos finalizados")
finalizados = list(ingresos.find({"estado": "finalizado"}).sort("salida", -1).limit(10))
if finalizados:
    df_finalizados = pd.DataFrame(finalizados)
    df_finalizados["ingreso"] = pd.to_datetime(df_finalizados["ingreso"])
    df_finalizados["salida"] = pd.to_datetime(df_finalizados["salida"])
    df_finalizados["ingreso"] = df_finalizados["ingreso"].dt.tz_localize(None)
    df_finalizados["salida"] = df_finalizados["salida"].dt.tz_localize(None)
    df_finalizados = df_finalizados[["nombre", "cedula", "tipo", "marca", "ingreso", "salida", "duracion_str"]]
    df_finalizados.columns = ["Nombre", "Cédula", "Tipo", "Marca", "Ingreso", "Salida", "Duración"]
    df_finalizados.index = range(len(df_finalizados), 0, -1)
    st.dataframe(df_finalizados, use_container_width=True)
else:
    st.info("No hay registros finalizados aún.")
from datetime import datetime
import pytz
import streamlit as st
from pymongo import MongoClient
import pandas as pd
from dateutil.parser import parse

# === CONFIGURACIÓN GENERAL ===
st.set_page_config(page_title="🛴🚲 Check VIVA", layout="centered")
st.title("🛴🚲 Registro de Patinetas y Bicicletas – CC VIVA Envigado")

# === CONEXIÓN A MONGO ===
MONGO_URI = st.secrets["mongo_uri"]
client = MongoClient(MONGO_URI)
db = client.check_viva
col_usuarios = db.usuarios
col_ingresos = db.ingresos

# === ZONA HORARIA COLOMBIA ===
zona_col = pytz.timezone("America/Bogota")
ahora = datetime.now(zona_col)

# === FUNCIÓN PARA FORMATO DE DURACIÓN ===
def formatear_duracion(inicio, fin):
    try:
        if not isinstance(inicio, datetime):
            inicio = parse(str(inicio))
        if not isinstance(fin, datetime):
            fin = parse(str(fin))
        if inicio.tzinfo is None:
            inicio = zona_col.localize(inicio)
        if fin.tzinfo is None:
            fin = zona_col.localize(fin)
        duracion = fin - inicio
        dias = duracion.days
        horas, rem = divmod(duracion.seconds, 3600)
        minutos, segundos = divmod(rem, 60)
        if dias > 0:
            return f"{dias}d {horas:02d}:{minutos:02d}:{segundos:02d}"
        else:
            return f"{horas:02d}:{minutos:02d}:{segundos:02d}"
    except:
        return "—"

# === INGRESO DE VEHÍCULO ===
st.markdown("### 🟢 Ingreso de vehículo")
cedula = st.text_input("Número de cédula")

if cedula:
    usuario = col_usuarios.find_one({"cedula": cedula})
    if usuario:
        st.success(f"Usuario: {usuario['nombre']}")
        nombre = usuario['nombre']
    else:
        nombre = st.text_input("Nombre completo")

    tipo = st.selectbox("Tipo de vehículo", ["Patineta", "Bicicleta"])
    marca = st.text_input("Marca o referencia")

    if nombre and tipo and marca:
        if st.button("Registrar ingreso"):
            if not usuario:
                col_usuarios.insert_one({"cedula": cedula, "nombre": nombre})

            ya_activo = col_ingresos.find_one({"cedula": cedula, "estado": "activo"})
            if ya_activo:
                st.warning("Ya hay un vehículo activo con esta cédula.")
            else:
                col_ingresos.insert_one({
                    "cedula": cedula,
                    "nombre": nombre,
                    "tipo": tipo.lower(),
                    "marca": marca,
                    "ingreso": ahora,
                    "estado": "activo"
                })
                st.success("Ingreso registrado.")
                st.rerun()
    else:
        st.info("Por favor completa todos los campos.")

# === REGISTRAR SALIDA ===
st.markdown("### 🔴 Registrar salida")
cedula_salida = st.text_input("Número de cédula para salida")

if cedula_salida:
    vehiculo_activo = col_ingresos.find_one({"cedula": cedula_salida, "estado": "activo"})
    if vehiculo_activo:
        if st.button("Registrar salida"):
            salida_hora = datetime.now(zona_col)
            ingreso_dt = parse(str(vehiculo_activo["ingreso"]))
            if ingreso_dt.tzinfo is None:
                ingreso_dt = zona_col.localize(ingreso_dt)
            duracion_str = formatear_duracion(ingreso_dt, salida_hora)
            duracion_min = int((salida_hora - ingreso_dt).total_seconds() / 60)

            col_ingresos.update_one(
                {"_id": vehiculo_activo["_id"]},
                {"$set": {
                    "salida": salida_hora,
                    "estado": "finalizado",
                    "duracion_str": duracion_str,
                    "duracion_min": duracion_min
                }}
            )
            st.success(f"Salida registrada. Duración: {duracion_str}")
            st.rerun()
    else:
        st.warning("No se encontró ingreso activo para esta cédula.")

# === VEHÍCULOS ACTUALMENTE PARQUEADOS ===
st.markdown("### 🚧 Vehículos actualmente parqueados")
parqueados = list(col_ingresos.find({"estado": "activo"}).sort("ingreso", -1))

if parqueados:
    df_activos = pd.DataFrame(parqueados)
    df_activos = df_activos[["nombre", "cedula", "tipo", "marca", "ingreso"]]
    df_activos.rename(columns={
        "nombre": "Nombre", "cedula": "Cédula", "tipo": "Tipo", "marca": "Marca", "ingreso": "Hora ingreso"
    }, inplace=True)
    df_activos["Hora ingreso"] = pd.to_datetime(df_activos["Hora ingreso"]).dt.tz_localize(zona_col, nonexistent='NaT', ambiguous='NaT', errors='coerce').dt.strftime("%Y-%m-%d %H:%M:%S")
    st.dataframe(df_activos, use_container_width=True)
else:
    st.info("No hay vehículos actualmente parqueados.")

# === HISTORIAL DE FINALIZADOS ===
st.markdown("### 📜 Últimos ingresos finalizados")
finalizados = list(col_ingresos.find({"estado": "finalizado"}).sort("salida", -1).limit(15))
if finalizados:
    df_finalizados = pd.DataFrame(finalizados)[["nombre", "cedula", "tipo", "marca", "ingreso", "salida", "duracion_str"]]
    
    df_finalizados["ingreso"] = pd.to_datetime(df_finalizados["ingreso"])
    df_finalizados["salida"] = pd.to_datetime(df_finalizados["salida"])

    if df_finalizados["ingreso"].dt.tz is None:
        df_finalizados["ingreso"] = df_finalizados["ingreso"].dt.tz_localize(zona_col)
    else:
        df_finalizados["ingreso"] = df_finalizados["ingreso"].dt.tz_convert(zona_col)

    if df_finalizados["salida"].dt.tz is None:
        df_finalizados["salida"] = df_finalizados["salida"].dt.tz_localize(zona_col)
    else:
        df_finalizados["salida"] = df_finalizados["salida"].dt.tz_convert(zona_col)

    df_finalizados["ingreso"] = df_finalizados["ingreso"].dt.strftime("%Y-%m-%d %H:%M:%S")
    df_finalizados["salida"] = df_finalizados["salida"].dt.strftime("%Y-%m-%d %H:%M:%S")

    df_finalizados.rename(columns={
        "nombre": "Nombre", "cedula": "Cédula", "tipo": "Tipo", "marca": "Marca",
        "ingreso": "Hora ingreso", "salida": "Hora salida", "duracion_str": "Duración"
    }, inplace=True)

    st.dataframe(df_finalizados, use_container_width=True)
else:
    st.info("No hay registros finalizados.")
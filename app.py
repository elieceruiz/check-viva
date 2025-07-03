import streamlit as st
import pandas as pd
from pymongo import MongoClient
from datetime import datetime
from dateutil.parser import parse

# --- CONFIGURACIÓN ---
st.set_page_config(page_title="🛴🚲 Check VIVA", layout="centered")
st.title("🛴🚲 Registro de Patinetas y Bicicletas – CC VIVA Envigado")

# --- CONEXIÓN ---
client = MongoClient(st.secrets["mongo_uri"])
db = client["check_viva"]
usuarios_col = db["usuarios"]
vehiculos_col = db["vehiculos"]
ingresos_col = db["ingresos"]

# --- ZONA HORARIA LOCAL ---
zona_col = "America/Bogota"

# --- UTILIDADES ---
def obtener_vehiculo(cedula):
    return vehiculos_col.find_one({"cedula": cedula})

def obtener_usuario(cedula):
    return usuarios_col.find_one({"cedula": cedula})

def formatear_duracion(inicio, fin):
    try:
        if not isinstance(inicio, datetime):
            inicio = parse(str(inicio))
        if not isinstance(fin, datetime):
            fin = parse(str(fin))
        duracion = fin - inicio
        dias = duracion.days
        horas, rem = divmod(duracion.seconds, 3600)
        minutos, segundos = divmod(rem, 60)
        if dias > 0:
            return f"{dias}d {horas:02d}:{minutos:02d}:{segundos:02d}"
        else:
            return f"{horas:02d}:{minutos:02d}:{segundos:02d}"
    except Exception:
        return "—"

# --- INGRESO ---
st.subheader("🟢 Ingreso de vehículo")
cedula_ingreso = st.text_input("Número de cédula")

if cedula_ingreso:
    usuario = obtener_usuario(cedula_ingreso)
    vehiculo = obtener_vehiculo(cedula_ingreso)

    if usuario and vehiculo:
        st.success(f"Vehículo registrado: {vehiculo['tipo'].capitalize()} – {vehiculo['marca']}")
        st.write(f"🔹 Nombre: {usuario['nombre']}")
        st.write(f"🔹 Color: {vehiculo['color']}")
        st.write(f"🔹 Candado: {vehiculo['candado']}")
        if st.button("Registrar ingreso"):
            now = datetime.now()
            ingresos_col.insert_one({
                "cedula": cedula_ingreso,
                "nombre": usuario["nombre"],
                "tipo": vehiculo["tipo"],
                "marca": vehiculo["marca"],
                "color": vehiculo["color"],
                "candado": vehiculo["candado"],
                "ingreso": now,
                "estado": "activo"
            })
            st.success("✅ Ingreso registrado.")
            st.rerun()

    else:
        with st.form("registro_completo"):
            nombre = st.text_input("Nombre completo")
            tipo = st.selectbox("Tipo de vehículo", ["Patineta", "Bicicleta"])
            marca = st.text_input("Marca o referencia")
            color = st.text_input("Color")
            candado = st.text_input("Candado", value="No")
            submit = st.form_submit_button("Registrar usuario y vehículo")

            if submit and nombre and marca:
                now = datetime.now()
                usuarios_col.insert_one({
                    "cedula": cedula_ingreso,
                    "nombre": nombre
                })
                vehiculos_col.insert_one({
                    "cedula": cedula_ingreso,
                    "tipo": tipo.lower(),
                    "marca": marca,
                    "color": color,
                    "candado": candado
                })
                ingresos_col.insert_one({
                    "cedula": cedula_ingreso,
                    "nombre": nombre,
                    "tipo": tipo.lower(),
                    "marca": marca,
                    "color": color,
                    "candado": candado,
                    "ingreso": now,
                    "estado": "activo"
                })
                st.success("✅ Usuario, vehículo e ingreso registrados.")
                st.rerun()

# --- SALIDA ---
st.subheader("🔴 Registrar salida")
cedula_salida = st.text_input("Número de cédula para salida")

if cedula_salida:
    vehiculo_activo = ingresos_col.find_one({"cedula": cedula_salida, "estado": "activo"})
    if vehiculo_activo:
        st.write(f"🔹 {vehiculo_activo['tipo'].capitalize()} – {vehiculo_activo['marca']}")
        if st.button("Registrar salida"):
            salida_hora = datetime.now()
            ingreso_dt = parse(str(vehiculo_activo["ingreso"]))
            duracion_str = formatear_duracion(ingreso_dt, salida_hora)
            duracion_min = int((salida_hora - ingreso_dt).total_seconds() / 60)
            ingresos_col.update_one(
                {"_id": vehiculo_activo["_id"]},
                {"$set": {
                    "salida": salida_hora,
                    "estado": "finalizado",
                    "duracion_str": duracion_str,
                    "duracion_min": duracion_min
                }}
            )
            st.success(f"✅ Salida registrada. Duración: {duracion_str}.")
            st.rerun()
    else:
        st.warning("No hay ingreso activo con esa cédula.")

# --- VEHÍCULOS PARQUEADOS ---
st.subheader("🚧 Vehículos actualmente parqueados")
ingresos_activos = list(ingresos_col.find({"estado": "activo"}).sort("ingreso", -1))

if not ingresos_activos:
    st.info("No hay vehículos parqueados.")
else:
    df_activos = pd.DataFrame(ingresos_activos)
    df_activos["ingreso"] = pd.to_datetime(df_activos["ingreso"]).dt.strftime("%Y-%m-%d %H:%M:%S")
    df_activos.index = range(len(df_activos), 0, -1)
    st.dataframe(df_activos[["cedula", "nombre", "tipo", "marca", "color", "candado", "ingreso"]])

# --- HISTORIAL FINALIZADOS ---
st.subheader("📜 Últimos ingresos finalizados")
ingresos_finalizados = list(ingresos_col.find({"estado": "finalizado"}).sort("salida", -1).limit(15))

if not ingresos_finalizados:
    st.info("No hay registros finalizados.")
else:
    df_finalizados = pd.DataFrame(ingresos_finalizados)
    df_finalizados["ingreso"] = pd.to_datetime(df_finalizados["ingreso"]).dt.strftime("%Y-%m-%d %H:%M:%S")
    df_finalizados["salida"] = pd.to_datetime(df_finalizados["salida"]).dt.strftime("%Y-%m-%d %H:%M:%S")
    df_finalizados.index = range(len(df_finalizados), 0, -1)
    st.dataframe(df_finalizados[["cedula", "nombre", "tipo", "marca", "color", "candado", "ingreso", "salida", "duracion_str"]])
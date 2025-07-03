import streamlit as st
import pymongo
import pandas as pd
from datetime import datetime, timedelta
import pytz

# === CONFIGURACIÓN ===
st.set_page_config(page_title="🛴🚲 Registro de Patinetas y Bicicletas – CC VIVA Envigado", layout="centered")

# Conexión MongoDB
client = pymongo.MongoClient(st.secrets["mongo_uri"])
db = client["check_viva"]
usuarios_col = db["usuarios"]
vehiculos_col = db["vehiculos"]
ingresos_col = db["ingresos"]

zona_col = pytz.timezone("America/Bogota")

def formatear_duracion(inicio, fin):
    if inicio.tzinfo is None:
        inicio = zona_col.localize(inicio)
    if fin.tzinfo is None:
        fin = zona_col.localize(fin)
    duracion = fin - inicio
    dias = duracion.days
    horas, rem = divmod(duracion.seconds, 3600)
    minutos, segundos = divmod(rem, 60)
    return f"{dias}d {horas:02}:{minutos:02}:{segundos:02}"

st.title("🛴🚲 Registro de Patinetas y Bicicletas – CC VIVA Envigado")

# === INGRESO ===
st.header("🟢 Ingreso de vehículo")
cedula_ing = st.text_input("Número de cédula", key="ced_ing")

if cedula_ing:
    usuario = usuarios_col.find_one({"cedula": cedula_ing})
    if usuario:
        vehiculo = vehiculos_col.find_one({"cedula": cedula_ing})
        if vehiculo:
            st.info(f"Vehículo registrado: {vehiculo['tipo'].capitalize()} – {vehiculo['marca']}, Color: {vehiculo.get('color', 'N/A')}, Candado: {vehiculo.get('candado', 'N/A')}")
            if st.button("Registrar ingreso"):
                ahora = datetime.now(zona_col)
                ingresos_col.insert_one({
                    "cedula": cedula_ing,
                    "tipo": vehiculo["tipo"],
                    "marca": vehiculo["marca"],
                    "ingreso": ahora,
                    "nombre": usuario["nombre"],
                    "candado": vehiculo.get("candado", "N/A"),
                    "color": vehiculo.get("color", "N/A")
                })
                st.success("Ingreso registrado correctamente.")
                st.rerun()
        else:
            st.warning("Cédula registrada, pero sin vehículo. Agrega uno primero.")
    else:
        with st.form("nuevo_usuario"):
            nombre = st.text_input("Nombre completo")
            tipo = st.selectbox("Tipo de vehículo", ["Patineta", "Bicicleta"])
            marca = st.text_input("Marca o referencia")
            color = st.text_input("Color")
            candado = st.selectbox("¿Usa candado?", ["Sí", "No"])
            enviar = st.form_submit_button("Registrar nuevo usuario y vehículo")
            if enviar and nombre and marca:
                usuarios_col.insert_one({"cedula": cedula_ing, "nombre": nombre})
                vehiculos_col.insert_one({
                    "cedula": cedula_ing,
                    "tipo": tipo.lower(),
                    "marca": marca,
                    "color": color,
                    "candado": candado
                })
                ahora = datetime.now(zona_col)
                ingresos_col.insert_one({
                    "cedula": cedula_ing,
                    "tipo": tipo.lower(),
                    "marca": marca,
                    "ingreso": ahora,
                    "nombre": nombre,
                    "candado": candado,
                    "color": color
                })
                st.success("Usuario, vehículo e ingreso registrados correctamente.")
                st.rerun()

# === SALIDA ===
st.header("🔴 Registrar salida")
cedula_sal = st.text_input("Número de cédula para salida", key="ced_sal")

if cedula_sal:
    vehiculo_activo = ingresos_col.find_one({"cedula": cedula_sal, "salida": {"$exists": False}})
    if vehiculo_activo:
        salida_hora = datetime.now(zona_col)
        ingreso_dt = vehiculo_activo["ingreso"]
        if ingreso_dt.tzinfo is None:
            ingreso_dt = zona_col.localize(ingreso_dt)
        duracion_str = formatear_duracion(ingreso_dt, salida_hora)
        ingresos_col.update_one(
            {"_id": vehiculo_activo["_id"]},
            {"$set": {"salida": salida_hora, "duracion": duracion_str}}
        )
        st.success(f"Salida registrada. Duración: {duracion_str}")
        st.rerun()
    else:
        st.info("No hay ingreso activo con esa cédula.")

# === PARQUEADOS ACTUALMENTE ===
st.header("🚧 Vehículos actualmente parqueados")
activos = list(ingresos_col.find({"salida": {"$exists": False}}))
if activos:
    df_activos = pd.DataFrame(activos)
    df_activos["Hora ingreso"] = pd.to_datetime(df_activos["ingreso"]).dt.tz_localize(zona_col, nonexistent='NaT', ambiguous='NaT').dt.strftime("%Y-%m-%d %H:%M:%S")
    df_activos = df_activos[["nombre", "cedula", "tipo", "marca", "Hora ingreso", "candado"]]
    df_activos.index = range(len(df_activos), 0, -1)
    st.dataframe(df_activos, use_container_width=True)
else:
    st.info("No hay vehículos actualmente parqueados.")

# === HISTÓRICO DE INGRESOS FINALIZADOS ===
st.header("📜 Últimos ingresos finalizados")
finalizados = list(ingresos_col.find({"salida": {"$exists": True}}).sort("salida", -1).limit(20))
if finalizados:
    df_finalizados = pd.DataFrame(finalizados)
    df_finalizados["Ingreso"] = pd.to_datetime(df_finalizados["ingreso"]).dt.tz_localize(zona_col, nonexistent='NaT', ambiguous='NaT').dt.strftime("%Y-%m-%d %H:%M:%S")
    df_finalizados["Salida"] = pd.to_datetime(df_finalizados["salida"]).dt.tz_localize(zona_col, nonexistent='NaT', ambiguous='NaT').dt.strftime("%Y-%m-%d %H:%M:%S")
    columnas_necesarias = ["nombre", "cedula", "tipo", "marca", "Ingreso", "Salida", "duracion", "candado"]
    columnas_presentes = [col for col in columnas_necesarias if col in df_finalizados.columns]
    df_finalizados = df_finalizados[columnas_presentes]
    df_finalizados.index = range(len(df_finalizados), 0, -1)
    st.dataframe(df_finalizados, use_container_width=True)
else:
    st.info("No hay ingresos finalizados aún.")
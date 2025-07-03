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
vehiculos = db.vehiculos
ingresos = db.ingresos

# === ZONA HORARIA ===
zona_col = pytz.timezone("America/Bogota")

def formatear_duracion(inicio, fin):
    if not inicio.tzinfo:
        inicio = zona_col.localize(inicio)
    if not fin.tzinfo:
        fin = zona_col.localize(fin)
    duracion = fin - inicio
    dias = duracion.days
    horas, rem = divmod(duracion.seconds, 3600)
    minutos, segundos = divmod(rem, 60)
    return f"{dias}d " if dias > 0 else "" + f"{horas:02}:{minutos:02}:{segundos:02}"

# === INGRESO DE VEHÍCULO ===
st.subheader("🟢 Ingreso de vehículo")
cedula = st.text_input("Número de cédula", max_chars=15)

if cedula:
    vehiculo = vehiculos.find_one({"cedula": cedula})
    if vehiculo:
        st.info("Vehículo registrado previamente.")
        nombre = vehiculo.get("nombre", "")
        tipo = vehiculo.get("tipo", "")
        marca = vehiculo.get("marca", "")
        color = vehiculo.get("color", "")
        candado = vehiculo.get("candado", "")
    else:
        nombre = st.text_input("Nombre completo")
        tipo = st.selectbox("Tipo de vehículo", ["Patineta", "Bicicleta"])
        marca = st.text_input("Marca o referencia")
        color = st.text_input("Color o señas distintivas (opcional)")
        candado = st.text_input("Candado entregado (opcional)")

    if nombre and tipo and marca:
        if st.button("Registrar ingreso"):
            ahora = datetime.now(zona_col)

            if not vehiculo:
                vehiculos.insert_one({
                    "cedula": cedula,
                    "nombre": nombre,
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
            st.success("✅ Ingreso registrado correctamente.")
            st.stop()
    elif st.button("Registrar ingreso"):
        st.warning("Por favor completa todos los campos obligatorios.")

# === SALIDA DE VEHÍCULO ===
st.subheader("🔴 Registrar salida")
cedula_salida = st.text_input("Número de cédula para salida")

if cedula_salida:
    vehiculo_activo = ingresos.find_one({"cedula": cedula_salida, "estado": "activo"})
    if vehiculo_activo:
        salida_hora = datetime.now(zona_col)
        ingreso_hora = vehiculo_activo["ingreso"]
        if not ingreso_hora.tzinfo:
            ingreso_hora = zona_col.localize(ingreso_hora)

        duracion = salida_hora - ingreso_hora
        duracion_str = formatear_duracion(ingreso_hora, salida_hora)

        ingresos.update_one(
            {"_id": vehiculo_activo["_id"]},
            {"$set": {
                "salida": salida_hora,
                "estado": "finalizado",
                "duracion_min": int(duracion.total_seconds() / 60),
                "duracion_str": duracion_str
            }}
        )
        st.success(f"✅ Salida registrada. Duración: {duracion_str}")
        st.stop()
    else:
        st.warning("❌ No hay vehículo activo con esa cédula.")

# === VEHÍCULOS PARQUEADOS ACTUALMENTE ===
st.subheader("🚧 Vehículos actualmente parqueados")
activos = list(ingresos.find({"estado": "activo"}))
if activos:
    df_activos = pd.DataFrame(activos)
    df_activos["Hora ingreso"] = pd.to_datetime(df_activos["ingreso"]).dt.tz_localize(zona_col, nonexistent='NaT', ambiguous='NaT', errors='coerce').dt.strftime("%Y-%m-%d %H:%M:%S")
    df_activos.index = range(1, len(df_activos) + 1)
    st.dataframe(df_activos[["nombre", "cedula", "tipo", "marca", "Hora ingreso", "candado"]].rename(columns={
        "nombre": "Nombre",
        "cedula": "Cédula",
        "tipo": "Tipo",
        "marca": "Marca",
        "Hora ingreso": "Hora ingreso",
        "candado": "Candado"
    }), use_container_width=True)
else:
    st.info("No hay vehículos actualmente parqueados.")

# === HISTORIAL DE INGRESOS FINALIZADOS ===
st.subheader("📜 Últimos ingresos finalizados")
finalizados = list(ingresos.find({"estado": "finalizado"}).sort("salida", -1).limit(10))
if finalizados:
    df_finalizados = pd.DataFrame(finalizados)
    df_finalizados["ingreso"] = pd.to_datetime(df_finalizados["ingreso"])
    df_finalizados["salida"] = pd.to_datetime(df_finalizados["salida"])
    df_finalizados["ingreso"] = df_finalizados["ingreso"].dt.tz_localize(zona_col, nonexistent='NaT', ambiguous='NaT', errors='coerce').dt.strftime("%Y-%m-%d %H:%M:%S")
    df_finalizados["salida"] = df_finalizados["salida"].dt.tz_localize(zona_col, nonexistent='NaT', ambiguous='NaT', errors='coerce').dt.strftime("%Y-%m-%d %H:%M:%S")
    df_finalizados.index = range(1, len(df_finalizados) + 1)
    st.dataframe(df_finalizados[["nombre", "cedula", "tipo", "marca", "ingreso", "salida", "duracion_str", "candado"]].rename(columns={
        "nombre": "Nombre",
        "cedula": "Cédula",
        "tipo": "Tipo",
        "marca": "Marca",
        "ingreso": "Ingreso",
        "salida": "Salida",
        "duracion_str": "Duración",
        "candado": "Candado"
    }), use_container_width=True)
else:
    st.info("No hay ingresos finalizados recientes.")
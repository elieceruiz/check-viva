import streamlit as st
import pymongo
import pandas as pd
from datetime import datetime, timedelta
import pytz

# Configuración
st.set_page_config(page_title="🛴🚲 Registro de Patinetas y Bicicletas – CC VIVA Envigado", layout="centered")
MONGO_URI = st.secrets["mongo_uri"]
client = pymongo.MongoClient(MONGO_URI)
db = client["check_viva"]
col_usuarios = db["usuarios"]
col_vehiculos = db["vehiculos"]
col_ingresos = db["ingresos"]

zona_col = pytz.timezone("America/Bogota")

# Función para formatear duración
def formatear_duracion(inicio, fin):
    if inicio.tzinfo is None:
        inicio = inicio.replace(tzinfo=pytz.UTC).astimezone(zona_col)
    else:
        inicio = inicio.astimezone(zona_col)

    if fin.tzinfo is None:
        fin = fin.replace(tzinfo=pytz.UTC).astimezone(zona_col)
    else:
        fin = fin.astimezone(zona_col)

    duracion = fin - inicio
    dias = duracion.days
    horas, rem = divmod(duracion.seconds, 3600)
    minutos, segundos = divmod(rem, 60)
    partes = []
    if dias > 0:
        partes.append(f"{dias}d")
    partes.append(f"{horas}h")
    partes.append(f"{minutos}m")
    partes.append(f"{segundos}s")
    return " ".join(partes)

st.title("🛴🚲 Registro de Patinetas y Bicicletas – CC VIVA Envigado")

# 🟢 Ingreso de vehículo
st.subheader("🟢 Ingreso de vehículo")
cedula_ingreso = st.text_input("Número de cédula", key="cedula_ingreso")

if cedula_ingreso:
    usuario = col_usuarios.find_one({"cedula": cedula_ingreso})
    vehiculo = col_vehiculos.find_one({"cedula": cedula_ingreso})
    ingreso_activo = col_ingresos.find_one({"cedula": cedula_ingreso, "salida": None})

    if ingreso_activo:
        st.warning("Este vehículo ya está registrado como parqueado.")
    elif usuario and vehiculo:
        st.info(f"Vehículo registrado: {vehiculo['tipo'].capitalize()} – {vehiculo['marca']} – {vehiculo['color']} – Candado: {vehiculo['candado']}")
        if st.button("Registrar ingreso"):
            ingreso = {
                "cedula": cedula_ingreso,
                "ingreso": datetime.utcnow(),  # Se guarda en UTC
                "salida": None
            }
            col_ingresos.insert_one(ingreso)
            st.success("Ingreso registrado exitosamente.")
            st.rerun()
    else:
        with st.form("registro_usuario"):
            nombre = st.text_input("Nombre completo")
            tipo = st.selectbox("Tipo de vehículo", ["Patineta", "Bicicleta"])
            marca = st.text_input("Marca o referencia")
            color = st.text_input("Color")
            candado = st.selectbox("¿Tiene candado?", ["Sí", "No"])
            if st.form_submit_button("Registrar usuario y vehículo"):
                col_usuarios.insert_one({"cedula": cedula_ingreso, "nombre": nombre})
                col_vehiculos.insert_one({
                    "cedula": cedula_ingreso,
                    "tipo": tipo.lower(),
                    "marca": marca,
                    "color": color,
                    "candado": candado
                })
                col_ingresos.insert_one({
                    "cedula": cedula_ingreso,
                    "ingreso": datetime.utcnow(),  # UTC
                    "salida": None
                })
                st.success("Usuario, vehículo e ingreso registrados exitosamente.")
                st.rerun()

# 🔴 Registrar salida
st.subheader("🔴 Registrar salida")
cedula_salida = st.text_input("Número de cédula para salida", key="cedula_salida")

if cedula_salida:
    ingreso = col_ingresos.find_one({"cedula": cedula_salida, "salida": None})
    usuario = col_usuarios.find_one({"cedula": cedula_salida})
    vehiculo = col_vehiculos.find_one({"cedula": cedula_salida})
    if ingreso and usuario and vehiculo:
        salida = datetime.utcnow()  # UTC
        duracion = formatear_duracion(ingreso["ingreso"], salida)
        col_ingresos.update_one({"_id": ingreso["_id"]}, {"$set": {"salida": salida}})
        st.success(f"Salida registrada. Duración: {duracion}")
        st.rerun()
    else:
        st.error("No se encontró ingreso activo para esa cédula.")

# 🚧 Vehículos actualmente parqueados
st.subheader("🚧 Vehículos actualmente parqueados")
activos = list(col_ingresos.find({"salida": None}))
registros = []
for r in activos:
    veh = col_vehiculos.find_one({"cedula": r["cedula"]}) or {}
    usu = col_usuarios.find_one({"cedula": r["cedula"]}) or {}
    ingreso_local = r["ingreso"].replace(tzinfo=pytz.UTC).astimezone(zona_col)
    tiempo = formatear_duracion(r["ingreso"], datetime.utcnow())
    registros.append({
        "nombre": usu.get("nombre", ""),
        "cedula": r["cedula"],
        "tipo": veh.get("tipo", "").capitalize(),
        "marca": veh.get("marca", ""),
        "ingreso": ingreso_local.strftime("%Y-%m-%d %H:%M:%S"),
        "candado": veh.get("candado", ""),
        "tiempo": tiempo
    })

if registros:
    df_activos = pd.DataFrame(registros)
    df_activos = df_activos.sort_values(by="ingreso", ascending=False)
    df_activos.index = range(len(df_activos), 0, -1)
    st.dataframe(df_activos[["nombre", "cedula", "tipo", "marca", "ingreso", "candado", "tiempo"]], use_container_width=True)
else:
    st.info("No hay vehículos actualmente parqueados.")

# 📜 Últimos ingresos finalizados
st.subheader("📜 Últimos ingresos finalizados")
finalizados = list(col_ingresos.find({"salida": {"$ne": None}}).sort("salida", -1).limit(15))
historial = []
for f in finalizados:
    veh = col_vehiculos.find_one({"cedula": f["cedula"]}) or {}
    usu = col_usuarios.find_one({"cedula": f["cedula"]}) or {}
    ingreso_local = f["ingreso"].replace(tzinfo=pytz.UTC).astimezone(zona_col)
    salida_local = f["salida"].replace(tzinfo=pytz.UTC).astimezone(zona_col)
    duracion = formatear_duracion(f["ingreso"], f["salida"])
    historial.append({
        "nombre": usu.get("nombre", ""),
        "cedula": f["cedula"],
        "tipo": veh.get("tipo", "").capitalize(),
        "marca": veh.get("marca", ""),
        "Ingreso": ingreso_local.strftime("%Y-%m-%d %H:%M:%S"),
        "Salida": salida_local.strftime("%Y-%m-%d %H:%M:%S"),
        "duracion": duracion,
        "candado": veh.get("candado", "")
    })

if historial:
    df_finalizados = pd.DataFrame(historial)
    df_finalizados = df_finalizados.sort_values(by="Salida", ascending=False)
    df_finalizados.index = range(len(df_finalizados), 0, -1)
    st.dataframe(df_finalizados[["nombre", "cedula", "tipo", "marca", "Ingreso", "Salida", "duracion", "candado"]], use_container_width=True)
else:
    st.info("No hay registros finalizados todavía.")
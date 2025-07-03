from datetime import datetime
import pytz
import streamlit as st
from pymongo import MongoClient
import pandas as pd
from dateutil.parser import parse

# === CONFIGURACIÓN ===
st.set_page_config(page_title="🛴🚲 Check VIVA", layout="centered")
st.title("🛴🚲 Registro de Patinetas y Bicicletas – CC VIVA Envigado")

# === CONEXIONES Y ZONA HORARIA ===
MONGO_URI = st.secrets["mongo_uri"]
client = MongoClient(MONGO_URI)
db = client.check_viva
usuarios = db.usuarios
vehiculos = db.vehiculos
ingresos = db.ingresos
zona_col = pytz.timezone("America/Bogota")
ahora = datetime.now(zona_col)

# === FUNCIONES ===
def formatear_duracion(inicio, fin):
    try:
        inicio = parse(str(inicio))
        fin = parse(str(fin))
        duracion = fin - inicio
        dias = duracion.days
        horas, rem = divmod(duracion.seconds, 3600)
        minutos, segundos = divmod(rem, 60)
        return f"{dias}d {horas:02}:{minutos:02}:{segundos:02}" if dias > 0 else f"{horas:02}:{minutos:02}:{segundos:02}"
    except:
        return "—"

def tz_aware(dt):
    return dt if dt.tzinfo else zona_col.localize(dt)

# === SESIÓN TEMPORAL ===
if "registro_usuario_exitoso" not in st.session_state:
    st.session_state.registro_usuario_exitoso = False

if "vehiculo_registrado" not in st.session_state:
    st.session_state.vehiculo_registrado = False

# === INGRESO ===
st.subheader("🟢 Ingreso de vehículo")
cedula_ing = st.text_input("Número de cédula", key="cedula_ing")

if cedula_ing:
    usuario = usuarios.find_one({"cedula": cedula_ing})

    if usuario:
        st.success(f"👤 Usuario encontrado: {usuario['nombre']}")
    else:
        nombre_nuevo = st.text_input("Nombre completo", key="nuevo_nombre")
        if nombre_nuevo and st.button("Registrar nuevo usuario"):
            usuarios.insert_one({
                "cedula": cedula_ing,
                "nombre": nombre_nuevo,
                "fecha_registro": ahora
            })
            st.success("✅ Usuario registrado.")
            usuario = {"cedula": cedula_ing, "nombre": nombre_nuevo}

    if usuario:
        with st.form("form_vehiculo"):
            tipo = st.selectbox("Tipo de vehículo", ["Patineta", "Bicicleta"])
            marca = st.text_input("Marca o referencia")
            color = st.text_input("Color o señas distintivas (opcional)")
            candado = st.text_input("Candado entregado (opcional)")
            registrar = st.form_submit_button("🟢 Registrar ingreso")

            if registrar and marca:
                vehiculos.insert_one({
                    "cedula": usuario["cedula"],
                    "nombre": usuario["nombre"],
                    "tipo": tipo.lower(),
                    "marca": marca,
                    "color": color,
                    "candado": candado,
                    "registro": ahora
                })
                ingresos.insert_one({
                    "cedula": usuario["cedula"],
                    "nombre": usuario["nombre"],
                    "tipo": tipo.lower(),
                    "marca": marca,
                    "color": color,
                    "candado": candado,
                    "ingreso": ahora,
                    "estado": "activo"
                })
                st.success("🚲 Vehículo registrado y se marcó ingreso al parqueadero.")
                st.session_state.vehiculo_registrado = True

# === SALIDA ===
st.subheader("🔴 Registrar salida")
cedula_salida = st.text_input("Número de cédula para salida", key="cedula_salida")

if cedula_salida:
    vehiculo_activo = ingresos.find_one({"cedula": cedula_salida, "estado": "activo"})

    if vehiculo_activo:
        st.info(f"Vehículo encontrado: {vehiculo_activo['tipo'].capitalize()} – {vehiculo_activo['marca']}")
        if st.button("Confirmar salida"):
            salida = datetime.now(zona_col)
            ingreso_dt = tz_aware(parse(str(vehiculo_activo["ingreso"])))
            duracion_str = formatear_duracion(ingreso_dt, salida)
            duracion_min = int((salida - ingreso_dt).total_seconds() / 60)

            ingresos.update_one(
                {"_id": vehiculo_activo["_id"]},
                {"$set": {
                    "salida": salida,
                    "estado": "finalizado",
                    "duracion_min": duracion_min,
                    "duracion_str": duracion_str
                }}
            )
            st.success(f"✅ Salida registrada. Duración: {duracion_str}")
    else:
        st.warning("No hay ingresos activos con esa cédula.")

# === VEHÍCULOS ACTUALMENTE PARQUEADOS ===
st.subheader("🚧 Vehículos actualmente parqueados")
activos = list(ingresos.find({"estado": "activo"}).sort("ingreso", -1))

if activos:
    df_activos = pd.DataFrame(activos)
    df_activos["Hora ingreso"] = pd.to_datetime(df_activos["ingreso"])
    df_activos["Hora ingreso"] = df_activos["Hora ingreso"].dt.tz_localize(None).dt.strftime("%Y-%m-%d %H:%M:%S")
    df_activos = df_activos.reset_index(drop=True)
    df_activos.index += 1
    st.dataframe(df_activos[["nombre", "cedula", "tipo", "marca", "Hora ingreso", "candado"]], use_container_width=True)
else:
    st.info("No hay vehículos actualmente parqueados.")

# === HISTORIAL FINALIZADOS ===
st.subheader("📜 Últimos ingresos finalizados")
finalizados = list(ingresos.find({"estado": "finalizado"}).sort("salida", -1).limit(10))

if finalizados:
    df_finalizados = pd.DataFrame(finalizados)
    df_finalizados["Ingreso"] = pd.to_datetime(df_finalizados["ingreso"]).dt.tz_localize(None).dt.strftime("%Y-%m-%d %H:%M")
    df_finalizados["Salida"] = pd.to_datetime(df_finalizados["salida"]).dt.tz_localize(None).dt.strftime("%Y-%m-%d %H:%M")
    df_finalizados = df_finalizados.reset_index(drop=True)
    df_finalizados.index += 1
    st.dataframe(df_finalizados[["nombre", "cedula", "tipo", "marca", "Ingreso", "Salida", "duracion_str", "candado"]], use_container_width=True)
else:
    st.info("No hay registros finalizados aún.")
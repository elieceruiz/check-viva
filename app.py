import streamlit as st
from pymongo import MongoClient
from datetime import datetime
from dateutil.parser import parse
import pytz
import pandas as pd

# Configuración
st.set_page_config(page_title="🛴🚲 Check VIVA", layout="centered")
st.title("🛴🚲 Registro de Patinetas y Bicicletas – CC VIVA Envigado")
zona_col = pytz.timezone("America/Bogota")
ahora = datetime.now(zona_col)

# Conexión a MongoDB
MONGO_URI = st.secrets["mongo_uri"]
client = MongoClient(MONGO_URI)
db = client.check_viva
usuarios = db.usuarios
ingresos = db.ingresos

# Orden hegemónico
orden_tipo = {"patineta": 0, "bicicleta": 1}

# Función robusta para duración
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
            return f"{dias}d {horas:02}:{minutos:02}:{segundos:02}"
        else:
            return f"{horas:02}:{minutos:02}:{segundos:02}"
    except Exception:
        return "—"

# Ingreso de vehículo
st.subheader("🟢 Ingreso de vehículo")
cedula = st.text_input("Número de cédula")

if cedula:
    vehiculos_previos = list(ingresos.find({"cedula": cedula}).sort("ingreso", -1))
    if vehiculos_previos:
        ultimo = vehiculos_previos[0]
        nombre_default = ultimo.get("nombre", "")
        tipo_default = ultimo.get("tipo", "").capitalize()
        marca_default = ultimo.get("marca", "")
        color_default = ultimo.get("color", "")
        candado_default = ultimo.get("candado", "")
    else:
        nombre_default = tipo_default = marca_default = color_default = candado_default = ""

    with st.form("form_ingreso"):
        nombre = st.text_input("Nombre completo", value=nombre_default)
        tipo = st.selectbox("Tipo de vehículo", ["Patineta", "Bicicleta"], index=0 if tipo_default == "Patineta" else 1)
        marca = st.text_input("Marca o referencia", value=marca_default)
        color = st.text_input("Color o señas distintivas (opcional)", value=color_default)
        candado = st.text_input("Candado entregado (opcional)", value=candado_default)
        submit = st.form_submit_button("🟢 Registrar ingreso")

        if submit:
            if nombre and marca:
                usuarios.update_one(
                    {"cedula": cedula},
                    {"$set": {
                        "cedula": cedula,
                        "nombre": nombre,
                        "tipo": tipo.lower(),
                        "marca": marca,
                        "color": color,
                        "candado": candado
                    }},
                    upsert=True
                )

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

                st.success("🚲 Ingreso registrado exitosamente.")
                st.rerun()
            else:
                st.warning("Por favor completa todos los campos.")

# Salida
st.subheader("🔴 Registrar salida")
cedula_salida = st.text_input("Número de cédula para salida")

if cedula_salida:
    vehiculo_activo = ingresos.find_one({"cedula": cedula_salida, "estado": "activo"})
    if vehiculo_activo:
        salida_hora = datetime.now(zona_col)
        ingreso_dt = vehiculo_activo["ingreso"]
        if not ingreso_dt.tzinfo:
            ingreso_dt = ingreso_dt.replace(tzinfo=pytz.UTC).astimezone(zona_col)

        duracion_str = formatear_duracion(ingreso_dt, salida_hora)
        duracion_min = int((salida_hora - ingreso_dt).total_seconds() / 60)

        ingresos.update_one(
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
        st.warning("No se encontró ningún vehículo activo con esa cédula.")

# Vehículos parqueados
st.subheader("🚧 Vehículos actualmente parqueados")
activos = list(ingresos.find({"estado": "activo"}).sort("ingreso", -1))

if activos:
    df_activos = pd.DataFrame(activos)
    df_activos["Tipo"] = df_activos["tipo"].str.capitalize()
    df_activos["Hora ingreso"] = pd.to_datetime(df_activos["ingreso"], utc=True, errors="coerce").dt.tz_convert(zona_col).dt.strftime("%Y-%m-%d %H:%M:%S")
    df_activos = df_activos[["nombre", "cedula", "Tipo", "marca", "Hora ingreso", "candado"]]
    df_activos.index = range(1, len(df_activos) + 1)
    st.dataframe(df_activos, use_container_width=True)
else:
    st.info("No hay vehículos actualmente parqueados.")

# Historial
st.subheader("📜 Últimos ingresos finalizados")
finalizados = list(ingresos.find({"estado": "finalizado"}).sort("salida", -1).limit(20))

if finalizados:
    df_finalizados = pd.DataFrame(finalizados)
    df_finalizados["Tipo"] = df_finalizados["tipo"].str.capitalize()
    df_finalizados["Ingreso"] = pd.to_datetime(df_finalizados["ingreso"], utc=True, errors="coerce").dt.tz_convert(zona_col).dt.strftime("%Y-%m-%d %H:%M:%S")
    df_finalizados["Salida"] = pd.to_datetime(df_finalizados["salida"], utc=True, errors="coerce").dt.tz_convert(zona_col).dt.strftime("%Y-%m-%d %H:%M:%S")
    df_finalizados = df_finalizados[["nombre", "cedula", "Tipo", "marca", "Ingreso", "Salida", "duracion_str", "candado"]]
    df_finalizados.index = range(1, len(df_finalizados) + 1)
    st.dataframe(df_finalizados, use_container_width=True)
else:
    st.info("No hay registros finalizados aún.")
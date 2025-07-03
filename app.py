import streamlit as st
import pandas as pd
from pymongo import MongoClient
from datetime import datetime
from dateutil.parser import parse
import pytz

# Configuración inicial
st.set_page_config(page_title="🛴🚲 Check VIVA", layout="centered")
st.title("🛴🚲 Registro de Patinetas y Bicicletas – CC VIVA Envigado")
zona_col = pytz.timezone("America/Bogota")
ahora = datetime.now(zona_col)

# Conexión a MongoDB
client = MongoClient(st.secrets["mongo_uri"])
db = client.check_viva
usuarios = db.usuarios
vehiculos = db.vehiculos
ingresos = db.ingresos

orden_tipo = {"patineta": 0, "bicicleta": 1}

# Función duración
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
        return f"{horas:02d}:{minutos:02d}:{segundos:02d}"
    except Exception:
        return "—"

# 🟢 Ingreso de vehículo
st.subheader("🟢 Ingreso de vehículo")
cedula = st.text_input("Número de cédula", max_chars=15)

if cedula:
    usuario = usuarios.find_one({"cedula": cedula})
    vehiculo = vehiculos.find_one({"cedula": cedula})

    if usuario and vehiculo:
        st.success("Vehículo registrado previamente.")
        if st.button("Registrar ingreso"):
            ingresos.insert_one({
                "cedula": cedula,
                "tipo": vehiculo["tipo"],
                "marca": vehiculo["marca"],
                "color": vehiculo.get("color", ""),
                "candado": vehiculo.get("candado", ""),
                "ingreso": ahora,
                "salida": None,
                "estado": "activo"
            })
            st.rerun()
    else:
        nombre = st.text_input("Nombre completo") if not usuario else usuario["nombre"]
        tipo = st.selectbox("Tipo de vehículo", ["Patineta", "Bicicleta"]).lower()
        marca = st.text_input("Marca o referencia")
        color = st.text_input("Color o señas distintivas (opcional)", max_chars=50)
        candado = st.text_input("Candado entregado (opcional)", max_chars=30)

        if nombre and tipo and marca:
            if st.button("Registrar nuevo usuario y vehículo"):
                if not usuario:
                    usuarios.insert_one({"cedula": cedula, "nombre": nombre})
                if not vehiculo:
                    vehiculos.insert_one({
                        "cedula": cedula,
                        "tipo": tipo,
                        "marca": marca,
                        "color": color,
                        "candado": candado
                    })
                ingresos.insert_one({
                    "cedula": cedula,
                    "tipo": tipo,
                    "marca": marca,
                    "color": color,
                    "candado": candado,
                    "ingreso": ahora,
                    "salida": None,
                    "estado": "activo"
                })
                st.rerun()
        elif st.button("Registrar nuevo usuario y vehículo"):
            st.warning("Por favor completa todos los campos.")

# 🔴 Registrar salida
st.subheader("🔴 Registrar salida")
cedula_salida = st.text_input("Número de cédula para salida", key="salida_cedula")

if cedula_salida:
    vehiculo_activo = ingresos.find_one({"cedula": cedula_salida, "estado": "activo"})
    if vehiculo_activo:
        salida_hora = datetime.now(zona_col)
        ingreso_dt = parse(str(vehiculo_activo["ingreso"]))
        if ingreso_dt.tzinfo is None:
            ingreso_dt = zona_col.localize(ingreso_dt)
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
        st.success(f"✅ Salida registrada. Duración: {duracion_str}")
        st.rerun()
    else:
        st.info("No hay ingreso activo para esa cédula.")

# 🚧 Vehículos actualmente parqueados
st.subheader("🚧 Vehículos actualmente parqueados")
activos = list(ingresos.find({"estado": "activo"}).sort("ingreso", -1))

if activos:
    df_activos = pd.DataFrame(activos)
    df_activos["Hora ingreso"] = pd.to_datetime(df_activos["ingreso"])

    if df_activos["Hora ingreso"].dt.tz is None:
        df_activos["Hora ingreso"] = df_activos["Hora ingreso"].dt.tz_localize(zona_col)
    else:
        df_activos["Hora ingreso"] = df_activos["Hora ingreso"].dt.tz_convert(zona_col)

    df_activos["Hora ingreso"] = df_activos["Hora ingreso"].dt.strftime("%Y-%m-%d %H:%M:%S")
    df_activos = df_activos.sort_values(by="tipo", key=lambda x: x.map(orden_tipo))
    df_activos.reset_index(drop=True, inplace=True)
    df_activos.index = df_activos.index + 1
    st.dataframe(df_activos[["cedula", "tipo", "marca", "color", "candado", "Hora ingreso"]])
else:
    st.info("No hay vehículos actualmente parqueados.")

# 📜 Últimos ingresos finalizados
st.subheader("📜 Últimos ingresos finalizados")
finalizados = list(ingresos.find({"estado": "finalizado"}).sort("salida", -1).limit(10))

if finalizados:
    df_finalizados = pd.DataFrame(finalizados)
    df_finalizados["ingreso"] = pd.to_datetime(df_finalizados["ingreso"])
    df_finalizados["salida"] = pd.to_datetime(df_finalizados["salida"])

    for col in ["ingreso", "salida"]:
        if df_finalizados[col].dt.tz is None:
            df_finalizados[col] = df_finalizados[col].dt.tz_localize(zona_col)
        else:
            df_finalizados[col] = df_finalizados[col].dt.tz_convert(zona_col)

        df_finalizados[col] = df_finalizados[col].dt.strftime("%Y-%m-%d %H:%M:%S")

    df_finalizados = df_finalizados.sort_values(by="tipo", key=lambda x: x.map(orden_tipo))
    df_finalizados.reset_index(drop=True, inplace=True)
    df_finalizados.index = range(len(df_finalizados), 0, -1)

    st.dataframe(df_finalizados[["cedula", "tipo", "marca", "color", "candado", "ingreso", "salida", "duracion_str"]])
else:
    st.info("No hay registros finalizados aún.")
import streamlit as st
from datetime import datetime
from pymongo import MongoClient
import pytz
import pandas as pd

# Config
st.set_page_config(page_title="🛴🚲 Check VIVA", layout="centered")
st.title("🛴🚲 Registro de Patinetas y Bicicletas – CC VIVA Envigado")
zona_col = pytz.timezone("America/Bogota")
ahora = datetime.now(zona_col)

# Conexión MongoDB
client = MongoClient(st.secrets["mongo_uri"])
db = client.check_viva
usuarios = db.usuarios
vehiculos = db.vehiculos
ingresos = db.ingresos

# Función duración
def formatear_duracion(inicio, fin):
    try:
        if inicio.tzinfo is None:
            inicio = zona_col.localize(inicio)
        if fin.tzinfo is None:
            fin = zona_col.localize(fin)
        duracion = fin - inicio
        dias = duracion.days
        horas, rem = divmod(duracion.seconds, 3600)
        minutos, segundos = divmod(rem, 60)
        return f"{dias}d {horas:02}:{minutos:02}:{segundos:02}" if dias else f"{horas:02}:{minutos:02}:{segundos:02}"
    except:
        return "—"

# =============================
# 🟢 Ingreso de vehículo
# =============================
st.markdown("## 🟢 Ingreso de vehículo")
cedula = st.text_input("Número de cédula")

if cedula:
    vehiculo = vehiculos.find_one({"cedula": cedula})
    usuario = usuarios.find_one({"cedula": cedula})

    if vehiculo and usuario:
        st.success("Vehículo registrado previamente.")
        if st.button("Registrar ingreso"):
            ahora = datetime.now(zona_col)
            ingresos.insert_one({
                "cedula": cedula,
                "nombre": usuario["nombre"],
                "tipo": vehiculo["tipo"],
                "marca": vehiculo["marca"],
                "color": vehiculo.get("color", ""),
                "candado": vehiculo.get("candado", "No"),
                "ingreso": ahora,
                "salida": None,
                "estado": "activo"
            })
            st.success("✅ Ingreso registrado correctamente.")
            st.rerun()
    else:
        nombre = st.text_input("Nombre completo")
        tipo = st.selectbox("Tipo de vehículo", ["Patineta", "Bicicleta"])
        marca = st.text_input("Marca o referencia")
        color = st.text_input("Color o señas distintivas (opcional)")
        candado = st.text_input("Candado entregado (opcional)", value="No")

        if nombre and tipo and marca:
            if st.button("Registrar vehículo y guardar ingreso"):
                ahora = datetime.now(zona_col)

                usuarios.insert_one({
                    "cedula": cedula,
                    "nombre": nombre,
                    "fecha_registro": ahora
                })

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

                st.success("✅ Registro completo. Vehículo ingresado.")
                st.rerun()
        else:
            st.warning("Por favor completa todos los campos.")

# =============================
# 🔴 Registrar salida
# =============================
st.markdown("## 🔴 Registrar salida")
cedula_salida = st.text_input("Número de cédula para salida")

if cedula_salida:
    vehiculo_activo = ingresos.find_one({"cedula": cedula_salida, "estado": "activo"})
    if vehiculo_activo:
        st.info(f"Vehículo activo: {vehiculo_activo['tipo'].capitalize()} – {vehiculo_activo['marca']}")
        if st.button("Registrar salida ahora"):
            salida_hora = datetime.now(zona_col)
            ingreso_dt = vehiculo_activo["ingreso"]

            if ingreso_dt.tzinfo is None:
                ingreso_dt = zona_col.localize(ingreso_dt)

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

# =============================
# 🚧 Vehículos actualmente parqueados
# =============================
st.markdown("## 🚧 Vehículos actualmente parqueados")
activos = list(ingresos.find({"estado": "activo"}).sort("ingreso", -1))

if activos:
    df_activos = pd.DataFrame(activos)
    df_activos["Hora ingreso"] = pd.to_datetime(df_activos["ingreso"])
    df_activos["Hora ingreso"] = df_activos["Hora ingreso"].dt.tz_localize(zona_col, nonexistent='NaT', ambiguous='NaT', errors='coerce').dt.strftime("%Y-%m-%d %H:%M:%S")
    df_activos.index = range(len(df_activos), 0, -1)
    st.dataframe(df_activos[["nombre", "cedula", "tipo", "marca", "Hora ingreso", "candado"]], use_container_width=True)
else:
    st.info("No hay vehículos actualmente parqueados.")

# =============================
# 📜 Últimos ingresos finalizados
# =============================
st.markdown("## 📜 Últimos ingresos finalizados")
finalizados = list(ingresos.find({"estado": "finalizado"}).sort("salida", -1).limit(10))

if finalizados:
    df_finalizados = pd.DataFrame(finalizados)
    df_finalizados["ingreso"] = pd.to_datetime(df_finalizados["ingreso"])
    df_finalizados["salida"] = pd.to_datetime(df_finalizados["salida"])
    df_finalizados["ingreso"] = df_finalizados["ingreso"].dt.tz_localize(zona_col, nonexistent='NaT', ambiguous='NaT', errors='coerce').dt.strftime("%Y-%m-%d %H:%M:%S")
    df_finalizados["salida"] = df_finalizados["salida"].dt.tz_localize(zona_col, nonexistent='NaT', ambiguous='NaT', errors='coerce').dt.strftime("%Y-%m-%d %H:%M:%S")
    df_finalizados.index = range(len(df_finalizados), 0, -1)
    st.dataframe(df_finalizados[["nombre", "cedula", "tipo", "marca", "ingreso", "salida", "duracion_str", "candado"]], use_container_width=True)
else:
    st.info("No hay ingresos finalizados recientes.")
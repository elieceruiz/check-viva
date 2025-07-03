import streamlit as st
from pymongo import MongoClient
from datetime import datetime
import pytz
import pandas as pd

# === CONFIG ===
st.set_page_config(page_title="🛴🚲 Check VIVA", layout="centered")
st.title("🛴🚲 Registro de Patinetas y Bicicletas – CC VIVA Envigado")

# === MONGO ===
client = MongoClient(st.secrets["mongo_uri"])
db = client.check_viva
usuarios = db.usuarios
vehiculos = db.vehiculos
ingresos = db.ingresos

zona_col = pytz.timezone("America/Bogota")

# === FORMATO DURACIÓN ===
def formatear_duracion(inicio, fin):
    if inicio.tzinfo is None:
        inicio = inicio.replace(tzinfo=pytz.UTC)
    if fin.tzinfo is None:
        fin = fin.replace(tzinfo=pytz.UTC)
    duracion = fin - inicio
    dias = duracion.days
    horas, rem = divmod(duracion.seconds, 3600)
    minutos, segundos = divmod(rem, 60)
    if dias > 0:
        return f"{dias}d {horas:02}:{minutos:02}:{segundos:02}"
    return f"{horas:02}:{minutos:02}:{segundos:02}"

# === INGRESO VEHÍCULO ===
st.subheader("🟢 Ingreso de vehículo")
cedula = st.text_input("Número de cédula")

if cedula:
    usuario = usuarios.find_one({"cedula": cedula})
    vehiculo = vehiculos.find_one({"cedula": cedula})

    if usuario and vehiculo:
        st.success("Vehículo registrado previamente.")
        st.markdown(f"- 👤 **{usuario['nombre']}**")
        st.markdown(f"- 🚲 **{vehiculo['tipo'].capitalize()}** – {vehiculo['marca']}")
        st.markdown(f"- 🎨 Color: {vehiculo.get('color', '—')} | 🔒 Candado: {vehiculo.get('candado', '—')}")

        if st.button("Registrar ingreso ahora"):
            ahora = datetime.now(pytz.UTC)
            ingresos.insert_one({
                "cedula": cedula,
                "nombre": usuario["nombre"],
                "tipo": vehiculo["tipo"],
                "marca": vehiculo["marca"],
                "color": vehiculo.get("color", ""),
                "candado": vehiculo.get("candado", ""),
                "ingreso": ahora,
                "salida": None
            })
            st.success("✅ Ingreso registrado.")
            st.experimental_rerun()

    else:
        st.warning("No se encontró registro previo. Ingresa los datos.")
        with st.form("registro_manual"):
            nombre = st.text_input("Nombre completo")
            tipo = st.selectbox("Tipo de vehículo", ["patineta", "bicicleta"])
            marca = st.text_input("Marca o referencia")
            color = st.text_input("Color", placeholder="Negra, Azul...")
            candado = st.text_input("Candado", placeholder="Sí / No")
            submitted = st.form_submit_button("Registrar y guardar")

            if submitted and nombre and tipo and marca:
                usuarios.insert_one({"cedula": cedula, "nombre": nombre})
                vehiculos.insert_one({
                    "cedula": cedula,
                    "tipo": tipo,
                    "marca": marca,
                    "color": color,
                    "candado": candado
                })
                ahora = datetime.now(pytz.UTC)
                ingresos.insert_one({
                    "cedula": cedula,
                    "nombre": nombre,
                    "tipo": tipo,
                    "marca": marca,
                    "color": color,
                    "candado": candado,
                    "ingreso": ahora,
                    "salida": None
                })
                st.success("✅ Usuario y vehículo registrados. Ingreso realizado.")
                st.experimental_rerun()
            elif submitted:
                st.error("Por favor completa todos los campos.")

# === SALIDA VEHÍCULO ===
st.subheader("🔴 Registrar salida")
cedula_salida = st.text_input("Número de cédula para salida")

if cedula_salida:
    vehiculo_activo = ingresos.find_one({"cedula": cedula_salida, "salida": None})
    if vehiculo_activo:
        st.markdown(f"👤 **{vehiculo_activo['nombre']}** | 🚲 **{vehiculo_activo['tipo'].capitalize()} – {vehiculo_activo['marca']}**")
        if st.button("Registrar salida ahora"):
            salida_hora = datetime.now(pytz.UTC)
            ingreso_hora = vehiculo_activo["ingreso"]
            duracion_str = formatear_duracion(ingreso_hora, salida_hora)
            ingresos.update_one(
                {"_id": vehiculo_activo["_id"]},
                {"$set": {"salida": salida_hora, "duracion_str": duracion_str}}
            )
            st.success(f"✅ Salida registrada. Duración: {duracion_str}")
            st.experimental_rerun()
    else:
        st.info("No hay ingreso activo para esa cédula.")

# === VEHÍCULOS ACTUALMENTE PARQUEADOS ===
st.markdown("🚧 **Vehículos actualmente parqueados**")

activos = list(ingresos.find({"salida": None}))

if activos:
    df_activos = pd.DataFrame(activos)
    df_activos["ingreso"] = pd.to_datetime(df_activos["ingreso"])
    df_activos["ingreso"] = df_activos["ingreso"].dt.tz_localize("UTC").dt.tz_convert(zona_col)
    df_activos["ingreso"] = df_activos["ingreso"].dt.strftime("%Y-%m-%d %H:%M:%S")
    df_activos = df_activos.sort_values(by="ingreso", ascending=False).reset_index(drop=True)
    df_activos.index = range(len(df_activos), 0, -1)
    columnas = ["cedula", "nombre", "tipo", "marca", "color", "candado", "ingreso"]
    columnas_presentes = [col for col in columnas if col in df_activos.columns]
    st.dataframe(df_activos[columnas_presentes], use_container_width=True)
else:
    st.info("No hay vehículos actualmente parqueados.")

# === HISTORIAL DE REGISTROS FINALIZADOS ===
st.markdown("📜 **Últimos ingresos finalizados**")

finalizados = list(ingresos.find({"salida": {"$ne": None}}).sort("salida", -1).limit(15))

if finalizados:
    df_finalizados = pd.DataFrame(finalizados)
    df_finalizados["ingreso"] = pd.to_datetime(df_finalizados["ingreso"])
    df_finalizados["salida"] = pd.to_datetime(df_finalizados["salida"])
    df_finalizados["ingreso"] = df_finalizados["ingreso"].dt.tz_localize("UTC").dt.tz_convert(zona_col)
    df_finalizados["salida"] = df_finalizados["salida"].dt.tz_localize("UTC").dt.tz_convert(zona_col)
    df_finalizados["ingreso"] = df_finalizados["ingreso"].dt.strftime("%Y-%m-%d %H:%M:%S")
    df_finalizados["salida"] = df_finalizados["salida"].dt.strftime("%Y-%m-%d %H:%M:%S")
    df_finalizados = df_finalizados.sort_values(by="salida", ascending=False).reset_index(drop=True)
    df_finalizados.index = range(len(df_finalizados), 0, -1)
    columnas = ["cedula", "nombre", "tipo", "marca", "ingreso", "salida", "duracion_str"]
    columnas_presentes = [col for col in columnas if col in df_finalizados.columns]
    st.dataframe(df_finalizados[columnas_presentes], use_container_width=True)
else:
    st.info("No hay ingresos finalizados aún.")
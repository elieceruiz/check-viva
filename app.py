from datetime import datetime
import pytz
import streamlit as st
from pymongo import MongoClient
import pandas as pd

# === CONFIGURACIÓN GENERAL ===
st.set_page_config(page_title="🛴🚲 Check VIVA", layout="centered")
st.title("🛴🚲 Registro de Patinetas y Bicicletas – CC VIVA Envigado")
zona_col = pytz.timezone("America/Bogota")

# === CONEXIÓN MONGO ===
client = MongoClient(st.secrets["mongo_uri"])
db = client.check_viva
usuarios = db.usuarios
ingresos = db.ingresos

# === FUNCIÓN PARA FORMATEAR DURACIÓN ===
def formatear_duracion(inicio, fin):
    if not isinstance(inicio, datetime):
        inicio = pd.to_datetime(inicio, utc=True)
    if not isinstance(fin, datetime):
        fin = pd.to_datetime(fin, utc=True)
    delta = fin - inicio
    dias = delta.days
    horas, rem = divmod(delta.seconds, 3600)
    minutos, segundos = divmod(rem, 60)
    if dias > 0:
        return f"{dias}d {horas:02}:{minutos:02}:{segundos:02}"
    else:
        return f"{horas:02}:{minutos:02}:{segundos:02}"

# === INGRESO DE VEHÍCULO ===
st.subheader("🟢 Ingreso de vehículo")
cedula_ing = st.text_input("Número de cédula")

if cedula_ing:
    usuario = usuarios.find_one({"cedula": cedula_ing})
    if usuario:
        nombre = usuario["nombre"]
        st.info(f"Usuario registrado: {nombre}")
    else:
        nombre = st.text_input("Nombre completo")
        if nombre and st.button("Registrar nuevo usuario"):
            usuarios.insert_one({
                "cedula": cedula_ing,
                "nombre": nombre,
                "fecha_registro": datetime.now(zona_col)
            })
            st.success("✅ Usuario registrado correctamente.")
            st.rerun()

    if usuario or nombre:
        with st.form("form_ingreso"):
            tipo = st.selectbox("Tipo de vehículo", ["Patineta", "Bicicleta"])
            marca = st.text_input("Marca o referencia")
            color = st.text_input("Color o señas distintivas (opcional)")
            candado = st.text_input("Candado entregado (opcional)")
            enviar = st.form_submit_button("🟢 Registrar ingreso")

            if enviar and marca:
                ingresos.insert_one({
                    "cedula": cedula_ing,
                    "nombre": usuario["nombre"] if usuario else nombre,
                    "tipo": tipo.lower(),
                    "marca": marca,
                    "color": color,
                    "candado": candado,
                    "ingreso": datetime.now(zona_col),
                    "estado": "activo"
                })
                st.success("🚲 Ingreso registrado correctamente.")
                st.rerun()
            elif enviar:
                st.warning("Por favor completa todos los campos.")

# === REGISTRAR SALIDA ===
st.subheader("🔴 Registrar salida")
cedula_sal = st.text_input("Número de cédula para salida")

if cedula_sal:
    vehiculo_activo = ingresos.find_one({"cedula": cedula_sal, "estado": "activo"})
    if vehiculo_activo:
        st.info(f"Vehículo encontrado: {vehiculo_activo.get('tipo','').capitalize()} – {vehiculo_activo.get('marca','')}")
        if st.button("Registrar salida ahora"):
            salida_hora = datetime.now(zona_col)
            ingreso_dt = pd.to_datetime(vehiculo_activo["ingreso"], utc=True)
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
        st.warning("No se encontró un vehículo activo con esa cédula.")

# === VEHÍCULOS ACTUALMENTE PARQUEADOS ===
st.subheader("🚧 Vehículos actualmente parqueados")
registros_activos = list(ingresos.find({"estado": "activo"}))
if registros_activos:
    df_activos = pd.DataFrame(registros_activos)
    columnas_necesarias = {"nombre", "cedula", "tipo", "marca", "ingreso", "candado"}
    if columnas_necesarias.issubset(df_activos.columns):
        df_activos["Tipo"] = df_activos["tipo"].str.capitalize()
        df_activos["Hora ingreso"] = pd.to_datetime(df_activos["ingreso"], utc=True, errors="coerce")
        df_activos["Hora ingreso"] = df_activos["Hora ingreso"].dt.tz_convert(zona_col).dt.strftime("%Y-%m-%d %H:%M:%S")
        df_activos = df_activos[["nombre", "cedula", "Tipo", "marca", "Hora ingreso", "candado"]]
        df_activos.index = range(1, len(df_activos) + 1)
        st.dataframe(df_activos, use_container_width=True)
    else:
        st.warning("Los registros activos no contienen todos los campos necesarios.")
else:
    st.info("No hay vehículos actualmente parqueados.")

# === ÚLTIMOS INGRESOS FINALIZADOS ===
st.subheader("📜 Últimos ingresos finalizados")
registros_finalizados = list(ingresos.find({"estado": "finalizado"}).sort("salida", -1).limit(10))
if registros_finalizados:
    df_finalizados = pd.DataFrame(registros_finalizados)
    columnas_necesarias = {"nombre", "cedula", "tipo", "marca", "ingreso", "salida", "duracion_str", "candado"}
    if columnas_necesarias.issubset(df_finalizados.columns):
        df_finalizados["Tipo"] = df_finalizados["tipo"].str.capitalize()
        df_finalizados["Ingreso"] = pd.to_datetime(df_finalizados["ingreso"], utc=True, errors="coerce").dt.tz_convert(zona_col).dt.strftime("%Y-%m-%d %H:%M:%S")
        df_finalizados["Salida"] = pd.to_datetime(df_finalizados["salida"], utc=True, errors="coerce").dt.tz_convert(zona_col).dt.strftime("%Y-%m-%d %H:%M:%S")
        df_finalizados = df_finalizados[["nombre", "cedula", "Tipo", "marca", "Ingreso", "Salida", "duracion_str", "candado"]]
        df_finalizados.index = range(1, len(df_finalizados) + 1)
        st.dataframe(df_finalizados, use_container_width=True)
    else:
        st.warning("Los registros finalizados no contienen todos los campos necesarios.")
else:
    st.info("No hay ingresos finalizados recientes.")
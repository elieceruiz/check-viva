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
usuarios = db.usuarios
vehiculos = db.vehiculos
ingresos = db.ingresos

# === ZONA HORARIA ===
zona_col = pytz.timezone("America/Bogota")
ahora = datetime.now(zona_col)

# === FUNCIÓN DURACIÓN ===
def calcular_duracion(inicio, fin):
    if not inicio.tzinfo:
        inicio = zona_col.localize(inicio)
    duracion = fin - inicio
    dias = duracion.days
    horas, rem = divmod(duracion.seconds, 3600)
    minutos, segundos = divmod(rem, 60)
    return f"{dias}d {horas:02d}:{minutos:02d}:{segundos:02d}" if dias else f"{horas:02d}:{minutos:02d}:{segundos:02d}"

# === INGRESO DE VEHÍCULO ===
st.subheader("🟢 Ingreso de vehículo")
cedula = st.text_input("Número de cédula", max_chars=15)

if cedula:
    usuario = usuarios.find_one({"cedula": cedula})
    if usuario:
        st.success(f"Usuario encontrado: {usuario['nombre']}")
        ultimo_vehiculo = vehiculos.find_one({"cedula": cedula}, sort=[("registro", -1)])
        with st.form("form_existente"):
            tipo = st.selectbox("Tipo de vehículo", ["Patineta", "Bicicleta"],
                                index=0 if (ultimo_vehiculo and ultimo_vehiculo["tipo"] == "patineta") else 1)
            marca = st.text_input("Marca o referencia", value=ultimo_vehiculo.get("marca", "") if ultimo_vehiculo else "")
            color = st.text_input("Color o señas distintivas (opcional)", value=ultimo_vehiculo.get("color", ""))
            candado = st.text_input("Candado entregado (opcional)", value=ultimo_vehiculo.get("candado", ""))
            registrar = st.form_submit_button("🟢 Registrar ingreso")
            if registrar and marca:
                vehiculos.insert_one({
                    "cedula": cedula,
                    "nombre": usuario["nombre"],
                    "tipo": tipo.lower(),
                    "marca": marca,
                    "color": color,
                    "candado": candado,
                    "registro": ahora
                })
                ingresos.insert_one({
                    "cedula": cedula,
                    "nombre": usuario["nombre"],
                    "tipo": tipo.lower(),
                    "marca": marca,
                    "color": color,
                    "candado": candado,
                    "ingreso": ahora,
                    "salida": None,
                    "estado": "activo"
                })
                st.success("✅ Vehículo registrado con ingreso.")
                st.rerun()
    else:
        nombre = st.text_input("Nombre completo")
        if nombre:
            with st.form("form_nuevo"):
                tipo = st.selectbox("Tipo de vehículo", ["Patineta", "Bicicleta"])
                marca = st.text_input("Marca o referencia")
                color = st.text_input("Color o señas distintivas (opcional)")
                candado = st.text_input("Candado entregado (opcional)")
                registrar = st.form_submit_button("🟢 Registrar usuario e ingreso")
                if registrar and marca:
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
                        "candado": candado,
                        "registro": ahora
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
                    st.success("✅ Usuario y vehículo registrados con ingreso.")
                    st.rerun()

# === REGISTRAR SALIDA ===
st.subheader("🔴 Registrar salida")
cedula_salida = st.text_input("Número de cédula para salida")

if cedula_salida:
    vehiculo_activo = ingresos.find_one({"cedula": cedula_salida, "estado": "activo"})
    if vehiculo_activo:
        st.info(f"Vehículo encontrado: {vehiculo_activo['tipo'].capitalize()} – {vehiculo_activo['marca']}")
        if st.button("Registrar salida ahora"):
            salida_hora = datetime.now(zona_col)
            ingreso_hora = vehiculo_activo["ingreso"]
            if not ingreso_hora.tzinfo:
                ingreso_hora = zona_col.localize(ingreso_hora)
            duracion_str = calcular_duracion(ingreso_hora, salida_hora)
            duracion_min = int((salida_hora - ingreso_hora).total_seconds() // 60)
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
        st.warning("❌ No hay ingreso activo para esta cédula.")

# === VEHÍCULOS PARQUEADOS ACTUALMENTE ===
st.subheader("🚧 Vehículos actualmente parqueados")
parqueados = list(ingresos.find({"estado": "activo"}).sort("ingreso", -1))
if parqueados:
    df_activos = pd.DataFrame(parqueados)
    df_activos["Hora ingreso"] = pd.to_datetime(df_activos["ingreso"])
    df_activos["Hora ingreso"] = df_activos["Hora ingreso"].dt.tz_localize(None)
    df_activos["Hora ingreso"] = df_activos["Hora ingreso"].dt.strftime("%Y-%m-%d %H:%M:%S")
    df_activos = df_activos[["nombre", "cedula", "tipo", "marca", "Hora ingreso", "candado"]]
    df_activos.rename(columns={
        "nombre": "Nombre",
        "cedula": "Cédula",
        "tipo": "Tipo",
        "marca": "Marca",
        "candado": "Candado"
    }, inplace=True)
    st.dataframe(df_activos, use_container_width=True)
else:
    st.info("No hay vehículos actualmente parqueados.")

# === HISTORIAL DE FINALIZADOS ===
st.subheader("📜 Últimos ingresos finalizados")
finalizados = list(ingresos.find({"estado": "finalizado"}).sort("salida", -1).limit(10))
if finalizados:
    df_finalizados = pd.DataFrame(finalizados)
    df_finalizados["Ingreso"] = pd.to_datetime(df_finalizados["ingreso"])
    df_finalizados["Salida"] = pd.to_datetime(df_finalizados["salida"])
    df_finalizados["Ingreso"] = df_finalizados["Ingreso"].dt.tz_localize(None).dt.strftime("%Y-%m-%d %H:%M:%S")
    df_finalizados["Salida"] = df_finalizados["Salida"].dt.tz_localize(None).dt.strftime("%Y-%m-%d %H:%M:%S")
    df_finalizados = df_finalizados[["nombre", "cedula", "tipo", "marca", "Ingreso", "Salida", "duracion_str", "candado"]]
    df_finalizados.rename(columns={
        "nombre": "Nombre",
        "cedula": "Cédula",
        "tipo": "Tipo",
        "marca": "Marca",
        "duracion_str": "Duración",
        "candado": "Candado"
    }, inplace=True)
    st.dataframe(df_finalizados, use_container_width=True)
else:
    st.info("No hay registros finalizados aún.")
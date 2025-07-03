from datetime import datetime
import pytz
import streamlit as st
from pymongo import MongoClient
import pandas as pd

# === CONFIGURACIÓN ===
st.set_page_config(page_title="🛴🚲 Check VIVA", layout="centered")
st.title("🛴🚲 Registro de Patinetas y Bicicletas – CC VIVA Envigado")

# === CONEXIÓN MONGO ===
MONGO_URI = st.secrets["mongo_uri"]
client = MongoClient(MONGO_URI)
db = client.check_viva
usuarios = db.usuarios
vehiculos = db.vehiculos
ingresos = db.ingresos

# === ZONA HORARIA COLOMBIA ===
zona_col = pytz.timezone("America/Bogota")

# === INGRESO DE VEHÍCULO ===
st.subheader("🟢 Ingreso de vehículo")
cedula = st.text_input("Número de cédula", max_chars=15)

if cedula:
    usuario = usuarios.find_one({"cedula": cedula})
    vehiculo = vehiculos.find_one({"cedula": cedula})

    if usuario and vehiculo:
        # Mostrar datos para confirmar
        st.info(f"🔎 **Datos encontrados:**\n\n"
                f"- **Nombre:** {usuario['nombre']}\n"
                f"- **Tipo de vehículo:** {vehiculo['tipo'].capitalize()}\n"
                f"- **Marca:** {vehiculo['marca']}\n"
                f"- **Color:** {vehiculo.get('color', '—')}\n"
                f"- **Candado:** {vehiculo.get('candado', '—')}")

        if st.button("Registrar ingreso ahora"):
            ahora = datetime.now(zona_col)
            ingresos.insert_one({
                "cedula": cedula,
                "nombre": usuario["nombre"],
                "tipo": vehiculo["tipo"],
                "marca": vehiculo["marca"],
                "color": vehiculo.get("color", ""),
                "candado": vehiculo.get("candado", ""),
                "ingreso": ahora,
                "salida": None,
                "estado": "activo"
            })
            st.success("🚲 Ingreso registrado correctamente.")
            st.rerun()

    else:
        # Si no está, pedir nombre y datos del vehículo
        nombre = st.text_input("Nombre completo") if not usuario else usuario["nombre"]
        tipo = st.selectbox("Tipo de vehículo", ["Patineta", "Bicicleta"])
        marca = st.text_input("Marca o referencia")
        color = st.text_input("Color (opcional)")
        candado = st.text_input("Candado entregado (opcional)", value="No")

        if nombre and marca:
            if st.button("Registrar nuevo usuario e ingreso"):
                ahora = datetime.now(zona_col)
                if not usuario:
                    usuarios.insert_one({"cedula": cedula, "nombre": nombre})
                if not vehiculo:
                    vehiculos.insert_one({
                        "cedula": cedula,
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
                st.success("✅ Usuario y vehículo registrados. Ingreso guardado.")
                st.rerun()
        else:
            st.warning("Por favor completa todos los campos obligatorios.")

# === SALIDA ===
st.subheader("🔴 Registrar salida")
cedula_salida = st.text_input("Número de cédula para salida", key="salida")

if cedula_salida:
    vehiculo_activo = ingresos.find_one({"cedula": cedula_salida, "estado": "activo"})
    if vehiculo_activo:
        if st.button("Registrar salida"):
            salida_hora = datetime.now(zona_col)
            ingreso_dt = vehiculo_activo["ingreso"]
            if ingreso_dt.tzinfo is None:
                ingreso_dt = zona_col.localize(ingreso_dt)
            duracion = salida_hora - ingreso_dt
            minutos = int(duracion.total_seconds() / 60)
            horas, rem = divmod(duracion.seconds, 3600)
            mins, _ = divmod(rem, 60)
            duracion_str = f"{duracion.days}d {horas:02d}:{mins:02d}" if duracion.days else f"{horas:02d}:{mins:02d}"
            ingresos.update_one(
                {"_id": vehiculo_activo["_id"]},
                {"$set": {
                    "salida": salida_hora,
                    "estado": "finalizado",
                    "duracion_min": minutos,
                    "duracion_str": duracion_str
                }}
            )
            st.success(f"Salida registrada. Duración: {duracion_str}")
            st.rerun()
    else:
        st.warning("No hay vehículo activo para esta cédula.")

# === PARQUEADOS ACTUALMENTE ===
st.subheader("🚧 Vehículos actualmente parqueados")
activos = list(ingresos.find({"estado": "activo"}).sort("ingreso", -1))

if activos:
    df_activos = pd.DataFrame(activos)
    df_activos["Hora ingreso"] = pd.to_datetime(df_activos["ingreso"]).dt.tz_localize("UTC").dt.tz_convert(zona_col).dt.strftime("%Y-%m-%d %H:%M:%S")
    df_activos = df_activos[["nombre", "cedula", "tipo", "marca", "Hora ingreso", "candado"]]
    df_activos.columns = ["Nombre", "Cédula", "Tipo", "Marca", "Hora ingreso", "Candado"]
    df_activos.index = range(len(df_activos), 0, -1)
    st.dataframe(df_activos, use_container_width=True)
else:
    st.info("No hay vehículos actualmente parqueados.")

# === REGISTROS FINALIZADOS ===
st.subheader("📜 Últimos ingresos finalizados")
finalizados = list(ingresos.find({"estado": "finalizado"}).sort("salida", -1).limit(10))

if finalizados:
    df_finalizados = pd.DataFrame(finalizados)
    df_finalizados["Ingreso"] = pd.to_datetime(df_finalizados["ingreso"]).dt.tz_localize("UTC").dt.tz_convert(zona_col).dt.strftime("%Y-%m-%d %H:%M:%S")
    df_finalizados["Salida"] = pd.to_datetime(df_finalizados["salida"]).dt.tz_localize("UTC").dt.tz_convert(zona_col).dt.strftime("%Y-%m-%d %H:%M:%S")
    df_finalizados["Duración"] = df_finalizados["duracion_str"]
    df_finalizados = df_finalizados[["nombre", "cedula", "tipo", "marca", "Ingreso", "Salida", "Duración", "candado"]]
    df_finalizados.columns = ["Nombre", "Cédula", "Tipo", "Marca", "Ingreso", "Salida", "Duración", "Candado"]
    df_finalizados.index = range(len(df_finalizados), 0, -1)
    st.dataframe(df_finalizados, use_container_width=True)
else:
    st.info("No hay registros finalizados aún.")
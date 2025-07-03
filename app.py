from datetime import datetime
import pytz
import streamlit as st
from pymongo import MongoClient
import pandas as pd
from dateutil.parser import parse
from bson.objectid import ObjectId

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
CO = pytz.timezone("America/Bogota")
orden_tipo = {"patineta": 0, "bicicleta": 1}

# === FUNCIONES ===
def ahora():
    return datetime.now(CO)

def safe_datetime(dt):
    if isinstance(dt, datetime):
        return dt
    try:
        return parse(str(dt))
    except:
        return datetime.now(CO)

def formatear_duracion(inicio, fin):
    try:
        inicio = safe_datetime(inicio)
        fin = safe_datetime(fin)
        duracion = fin - inicio
        dias = duracion.days
        horas, rem = divmod(duracion.seconds, 3600)
        minutos, segundos = divmod(rem, 60)
        if dias > 0:
            return f"{dias}d {horas:02d}:{minutos:02d}:{segundos:02d}"
        else:
            return f"{horas:02d}:{minutos:02d}:{segundos:02d}"
    except Exception:
        return "—"

# === INGRESO ===
st.subheader("🟢 Ingreso de vehículo")
cedula = st.text_input("Número de cédula", max_chars=15)

if cedula:
    usuario = usuarios.find_one({"cedula": cedula})
    nombre = usuario["nombre"] if usuario else st.text_input("Nombre completo")

    if usuario or nombre:
        vehiculos_usuario = list(vehiculos.find({"cedula": cedula}))
        opciones = [f"{v['tipo'].capitalize()} – {v['marca']}" for v in vehiculos_usuario]
        opciones.append("➕ Registrar nuevo vehículo")
        seleccion = st.selectbox("Selecciona un vehículo", opciones)

        if seleccion == "➕ Registrar nuevo vehículo":
            with st.form("nuevo_vehiculo"):
                tipo = st.selectbox("Tipo", ["Patineta", "Bicicleta"])
                marca = st.text_input("Marca y referencia")
                color = st.text_input("Color o señas distintivas (opcional)")
                candado = st.text_input("Candado entregado (opcional)")
                submit_vehiculo = st.form_submit_button("Registrar nuevo vehículo e ingreso")

                if submit_vehiculo:
                    if not usuario:
                        usuarios.insert_one({
                            "cedula": cedula,
                            "nombre": nombre,
                            "fecha_registro": ahora()
                        })

                    vehiculo_id = vehiculos.insert_one({
                        "cedula": cedula,
                        "tipo": tipo.lower(),
                        "marca": marca,
                        "color": color,
                        "candado": candado,
                        "fecha_registro": ahora()
                    }).inserted_id

                    ingresos.insert_one({
                        "cedula": cedula,
                        "nombre": nombre,
                        "vehiculo_id": vehiculo_id,
                        "ingreso": ahora(),
                        "salida": None,
                        "estado": "activo"
                    })
                    st.success("✅ Vehículo registrado e ingreso guardado.")
                    st.rerun()
        else:
            idx = opciones.index(seleccion)
            vehiculo = vehiculos_usuario[idx]
            if st.button("Registrar ingreso con este vehículo"):
                ingresos.insert_one({
                    "cedula": cedula,
                    "nombre": nombre,
                    "vehiculo_id": vehiculo["_id"],
                    "ingreso": ahora(),
                    "salida": None,
                    "estado": "activo"
                })
                st.success("✅ Ingreso registrado.")
                st.rerun()

# === SALIDA ===
st.subheader("🔴 Registrar salida")
cedula_salida = st.text_input("Buscar por cédula para salida", key="salida")

if cedula_salida:
    activo = ingresos.find_one({"cedula": cedula_salida, "estado": "activo"})
    if activo:
        vehiculo = vehiculos.find_one({"_id": ObjectId(activo["vehiculo_id"])})
        st.info(f"{vehiculo['tipo'].capitalize()} – {vehiculo['marca']}")
        if st.button("Registrar salida ahora"):
            salida_hora = ahora()
            ingreso_dt = safe_datetime(activo["ingreso"])
            duracion_str = formatear_duracion(ingreso_dt, salida_hora)
            duracion_min = int((salida_hora - ingreso_dt).total_seconds() / 60)

            ingresos.update_one(
                {"_id": activo["_id"]},
                {"$set": {
                    "salida": salida_hora,
                    "estado": "finalizado",
                    "duracion_min": duracion_min,
                    "duracion_str": duracion_str
                }}
            )
            st.success(f"✅ Salida registrada: {duracion_str}")
            st.rerun()
    else:
        st.warning("❌ No hay ingreso activo para esta cédula.")

# === PARQUEADOS ===
st.subheader("🚧 Vehículos actualmente parqueados")
parqueados = list(ingresos.find({"estado": "activo"}))
parqueados.sort(key=lambda x: orden_tipo.get(
    vehiculos.find_one({"_id": x["vehiculo_id"]})["tipo"], 99
))

if parqueados:
    data = []
    for i, r in enumerate(parqueados, start=1):
        v = vehiculos.find_one({"_id": r["vehiculo_id"]})
        ingreso_dt = safe_datetime(r["ingreso"])
        data.append({
            "#": i,
            "Nombre": r["nombre"],
            "Cédula": r["cedula"],
            "Tipo": v["tipo"].capitalize(),
            "Marca": v["marca"],
            "Ingreso": ingreso_dt.astimezone(CO).strftime("%Y-%m-%d %H:%M"),
            "Candado": v.get("candado", "")
        })
    st.dataframe(pd.DataFrame(data), use_container_width=True)
else:
    st.info("No hay vehículos parqueados actualmente.")

# === HISTORIAL ===
st.subheader("📜 Historial de registros finalizados")
historial = list(ingresos.find({"estado": "finalizado"}).sort("salida", -1).limit(10))

if historial:
    data = []
    for i, r in enumerate(historial, start=1):
        v = vehiculos.find_one({"_id": r["vehiculo_id"]})
        ingreso_dt = safe_datetime(r["ingreso"])
        salida_dt = safe_datetime(r["salida"])
        data.append({
            "#": i,
            "Nombre": r["nombre"],
            "Cédula": r["cedula"],
            "Tipo": v["tipo"].capitalize(),
            "Marca": v["marca"],
            "Ingreso": ingreso_dt.astimezone(CO).strftime("%Y-%m-%d %H:%M"),
            "Salida": salida_dt.astimezone(CO).strftime("%Y-%m-%d %H:%M"),
            "Duración": r.get("duracion_str", "—"),
            "Candado": v.get("candado", "")
        })
    st.dataframe(pd.DataFrame(data), use_container_width=True)
else:
    st.info("No hay registros finalizados aún.")
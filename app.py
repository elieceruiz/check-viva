from datetime import datetime
import pytz
import streamlit as st
from pymongo import MongoClient
import pandas as pd
from dateutil.parser import parse

# === CONFIG ===
st.set_page_config(page_title="🛴🚲 Check VIVA", layout="centered")
st.title("🛴🚲 Registro de Patinetas y Bicicletas – CC VIVA Envigado")

# === CONEXIÓN MONGO ===
MONGO_URI = st.secrets["mongo_uri"]
client = MongoClient(MONGO_URI)
db = client.check_viva
usuarios = db.usuarios
ingresos = db.ingresos

# === ZONA HORARIA ===
CO = pytz.timezone("America/Bogota")
ahora = datetime.now(CO)
orden_tipo = {"patineta": 0, "bicicleta": 1}

# === FUNCIONES ===
def formatear_duracion(inicio, fin):
    if not isinstance(inicio, datetime):
        inicio = parse(str(inicio))
    if not isinstance(fin, datetime):
        fin = parse(str(fin))
    duracion = fin - inicio
    dias = duracion.days
    horas, rem = divmod(duracion.seconds, 3600)
    minutos, segundos = divmod(rem, 60)
    return f"{dias}d {horas:02d}:{minutos:02d}:{segundos:02d}" if dias > 0 else f"{horas:02d}:{minutos:02d}:{segundos:02d}"

def safe_datetime(dt):
    if isinstance(dt, datetime):
        return dt
    try:
        return parse(str(dt))
    except:
        return datetime.now(CO)

# === INGRESO ===
st.subheader("🟢 Ingreso de vehículo")
cedula = st.text_input("Número de cédula", max_chars=15)

if cedula:
    usuario = usuarios.find_one({"cedula": cedula})
    if usuario:
        st.success(f"Usuario encontrado: {usuario['nombre']}")
        nombre = usuario["nombre"]
    else:
        nombre = st.text_input("Nombre completo")
        if nombre:
            st.info("Primera vez: completa los datos del vehículo para guardarlos con el usuario.")
    
    if nombre:
        with st.form("form_ingreso"):
            tipo = st.selectbox("Tipo de vehículo", ["Patineta", "Bicicleta"])
            marca = st.text_input("Marca y referencia", max_chars=50)
            color = st.text_input("Color o señas distintivas (opcional)", max_chars=50)
            candado = st.text_input("Candado entregado (opcional)", max_chars=30)
            submitted = st.form_submit_button("🟢 Registrar ingreso")

            if submitted:
                ahora = datetime.now(CO)
                ingreso_data = {
                    "cedula": cedula,
                    "nombre": nombre,
                    "tipo": tipo.lower(),
                    "marca": marca,
                    "color": color,
                    "candado": candado,
                    "ingreso": ahora,
                    "salida": None,
                    "estado": "activo"
                }
                ingresos.insert_one(ingreso_data)

                if not usuario:
                    usuarios.insert_one({
                        "cedula": cedula,
                        "nombre": nombre,
                        "vehiculos": [{
                            "tipo": tipo.lower(),
                            "marca": marca,
                            "color": color,
                            "candado": candado
                        }],
                        "fecha_registro": ahora
                    })

                st.success("✅ Ingreso registrado correctamente.")
                st.rerun()

# === SALIDA ===
st.subheader("🔴 Registrar salida")
cedula_salida = st.text_input("Número de cédula para salida", key="salida_manual")

if cedula_salida:
    activo = ingresos.find_one({"cedula": cedula_salida, "estado": "activo"})
    if activo:
        ingreso_dt = safe_datetime(activo["ingreso"])
        salida_hora = datetime.now(CO)
        duracion_str = formatear_duracion(ingreso_dt, salida_hora)
        duracion_min = int((salida_hora - ingreso_dt).total_seconds() / 60)

        st.info(f"Vehículo encontrado: {activo['tipo'].capitalize()} – {activo['marca']}")

        if st.button("Registrar salida ahora"):
            ingresos.update_one(
                {"_id": activo["_id"]},
                {"$set": {
                    "salida": salida_hora,
                    "estado": "finalizado",
                    "duracion_min": duracion_min,
                    "duracion_str": duracion_str
                }}
            )
            st.success(f"✅ Salida registrada. El vehículo estuvo bajo cuidado durante **{duracion_str}**.")
            st.rerun()
    else:
        st.warning("❌ No hay ingreso activo para esta cédula.")

# === PARQUEADOS ACTUALMENTE ===
st.subheader("🚧 Vehículos actualmente parqueados")
parqueados = list(ingresos.find({"estado": "activo"}))
parqueados.sort(key=lambda x: orden_tipo.get(x.get("tipo", ""), 99))

if parqueados:
    data = []
    for i, r in enumerate(parqueados, start=1):
        ingreso_dt = safe_datetime(r["ingreso"])
        data.append({
            "#": i,
            "Nombre": r["nombre"],
            "Cédula": r["cedula"],
            "Tipo": r.get("tipo", "").capitalize(),
            "Marca": r.get("marca", ""),
            "Ingreso": ingreso_dt.astimezone(CO).strftime("%Y-%m-%d %H:%M"),
            "Candado": r.get("candado", "")
        })
    st.dataframe(pd.DataFrame(data), use_container_width=True)
else:
    st.info("No hay vehículos actualmente parqueados.")

# === HISTORIAL DE REGISTROS FINALIZADOS ===
st.subheader("📜 Historial de registros finalizados")
historial = list(ingresos.find({"estado": "finalizado"}).sort("salida", -1).limit(10))
historial.sort(key=lambda x: orden_tipo.get(x.get("tipo", ""), 99))

if historial:
    data = []
    for i, r in enumerate(historial, start=1):
        ingreso_dt = safe_datetime(r["ingreso"])
        salida_dt = safe_datetime(r["salida"])
        data.append({
            "#": i,
            "Nombre": r["nombre"],
            "Cédula": r["cedula"],
            "Tipo": r.get("tipo", "").capitalize(),
            "Marca": r.get("marca", ""),
            "Ingreso": ingreso_dt.astimezone(CO).strftime("%Y-%m-%d %H:%M"),
            "Salida": salida_dt.astimezone(CO).strftime("%Y-%m-%d %H:%M"),
            "Duración": r.get("duracion_str", "—"),
            "Candado": r.get("candado", "")
        })
    st.dataframe(pd.DataFrame(data), use_container_width=True)
else:
    st.info("No hay registros finalizados aún.")
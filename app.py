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
vehiculos = db.vehiculos
ingresos = db.ingresos

# === ZONA HORARIA ===
CO = pytz.timezone("America/Bogota")
orden_tipo = {"patineta": 0, "bicicleta": 1}

# === FUNCIONES ===
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
    if usuario:
        st.success(f"Usuario encontrado: {usuario['nombre']}")
        nombre = usuario["nombre"]
    else:
        nombre = st.text_input("Nombre completo")
        if nombre:
            with st.form("form_nuevo"):
                tipo = st.selectbox("Tipo de vehículo", ["Patineta", "Bicicleta"])
                marca = st.text_input("Marca y referencia")
                color = st.text_input("Color o señas distintivas (opcional)")
                candado = st.text_input("Candado entregado (opcional)")
                submitted = st.form_submit_button("Registrar nuevo usuario e ingreso")
                if submitted:
                    ahora = datetime.now(CO)
                    vehiculo_doc = {
                        "cedula": cedula,
                        "tipo": tipo.lower(),
                        "marca": marca,
                        "color": color,
                        "candado": candado,
                        "fecha_registro": ahora
                    }
                    vehiculo_id = vehiculos.insert_one(vehiculo_doc).inserted_id
                    usuarios.insert_one({
                        "cedula": cedula,
                        "nombre": nombre,
                        "fecha_registro": ahora
                    })
                    ingresos.insert_one({
                        "cedula": cedula,
                        "nombre": nombre,
                        "vehiculo_id": vehiculo_id,
                        "ingreso": ahora,
                        "salida": None,
                        "estado": "activo"
                    })
                    st.success("✅ Usuario, vehículo e ingreso registrados.")
                    st.rerun()

    if usuario:
        with st.form("form_ingreso"):
            tipo = st.selectbox("Tipo de vehículo", ["Patineta", "Bicicleta"])
            marca = st.text_input("Marca y referencia")
            color = st.text_input("Color o señas distintivas (opcional)")
            candado = st.text_input("Candado entregado (opcional)")
            submitted = st.form_submit_button("🟢 Registrar ingreso")

            if submitted:
                ahora = datetime.now(CO)
                vehiculo_doc = {
                    "cedula": cedula,
                    "tipo": tipo.lower(),
                    "marca": marca,
                    "color": color,
                    "candado": candado,
                    "fecha_registro": ahora
                }
                vehiculo_id = vehiculos.insert_one(vehiculo_doc).inserted_id
                ingresos.insert_one({
                    "cedula": cedula,
                    "nombre": nombre,
                    "vehiculo_id": vehiculo_id,
                    "ingreso": ahora,
                    "salida": None,
                    "estado": "activo"
                })
                st.success("🚲 Ingreso registrado correctamente.")
                st.rerun()

# === SALIDA ===
st.subheader("🔴 Registrar salida")
cedulas_registradas = [u["cedula"] for u in usuarios.find({}, {"cedula": 1}) if u.get("cedula")]

if cedulas_registradas:
    cedula_salida = st.selectbox("Selecciona cédula para registrar salida", cedulas_registradas, key="salida")
else:
    cedula_salida = st.text_input("Ingresar cédula para registrar salida", key="salida_manual")

if cedula_salida:
    activo = ingresos.find_one({"cedula": cedula_salida, "estado": "activo"})
    if activo:
        vehiculo = vehiculos.find_one({"_id": activo.get("vehiculo_id")})
        tipo = vehiculo.get("tipo", "—").capitalize() if vehiculo else "—"
        marca = vehiculo.get("marca", "—") if vehiculo else "—"
        st.info(f"Vehículo encontrado: {tipo} – {marca}")

        if st.button("Registrar salida ahora"):
            try:
                salida_hora = datetime.now(CO)
                ingreso_dt = safe_datetime(activo.get("ingreso"))
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
                st.success(f"✅ Salida registrada. El vehículo estuvo bajo cuidado durante **{duracion_str}**.")
                st.rerun()
            except Exception as e:
                st.error(f"❌ Error al calcular duración: {str(e)}")
    else:
        st.warning("❌ No hay ingreso activo para esta cédula.")

# === PARQUEADOS ACTUALMENTE ===
st.subheader("🚧 Vehículos actualmente parqueados")
parqueados = list(ingresos.find({"estado": "activo"}))
parqueados.sort(key=lambda x: orden_tipo.get(vehiculos.find_one({"_id": x.get("vehiculo_id")}).get("tipo", ""), 99))

if parqueados:
    data = []
    for idx, r in enumerate(parqueados, start=1):
        v = vehiculos.find_one({"_id": r.get("vehiculo_id")}) or {}
        ingreso_dt = safe_datetime(r["ingreso"])
        data.append({
            "#": idx,
            "Nombre": r["nombre"],
            "Cédula": r["cedula"],
            "Tipo": v.get("tipo", "—").capitalize(),
            "Marca": v.get("marca", "—"),
            "Ingreso": ingreso_dt.astimezone(CO).strftime("%Y-%m-%d %H:%M"),
            "Candado": v.get("candado", "—")
        })
    st.dataframe(pd.DataFrame(data), use_container_width=True)
else:
    st.info("No hay vehículos actualmente parqueados.")

# === HISTORIAL DE FINALIZADOS ===
st.subheader("📜 Historial de registros finalizados")
historial = list(ingresos.find({"estado": "finalizado"}).sort("salida", -1).limit(10))

if historial:
    data = []
    for idx, r in enumerate(historial, start=1):
        v = vehiculos.find_one({"_id": r.get("vehiculo_id")}) or {}
        ingreso_dt = safe_datetime(r["ingreso"])
        salida_dt = safe_datetime(r["salida"])
        data.append({
            "#": idx,
            "Nombre": r["nombre"],
            "Cédula": r["cedula"],
            "Tipo": v.get("tipo", "—").capitalize(),
            "Marca": v.get("marca", "—"),
            "Ingreso": ingreso_dt.astimezone(CO).strftime("%Y-%m-%d %H:%M"),
            "Salida": salida_dt.astimezone(CO).strftime("%Y-%m-%d %H:%M"),
            "Duración": r.get("duracion_str", "—"),
            "Candado": v.get("candado", "—")
        })
    st.dataframe(pd.DataFrame(data), use_container_width=True)
else:
    st.info("No hay registros finalizados aún.")
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

# === UTILS ===
def safe_datetime(dt):
    try:
        if isinstance(dt, datetime):
            return dt if dt.tzinfo else dt.replace(tzinfo=CO)
        return parse(str(dt)).replace(tzinfo=CO)
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
        return f"{horas:02d}:{minutos:02d}:{segundos:02d}"
    except:
        return "—"

orden_tipo = {"patineta": 0, "bicicleta": 1}

# === INGRESO ===
st.subheader("🟢 Ingreso de vehículo")
cedula = st.text_input("Número de cédula", max_chars=15)

if cedula:
    usuario = usuarios.find_one({"cedula": cedula})
    if usuario:
        nombre = usuario["nombre"]
        st.success(f"Usuario encontrado: {nombre}")
    else:
        nombre = st.text_input("Nombre completo")
        if nombre and st.button("Registrar nuevo usuario"):
            usuarios.insert_one({
                "cedula": cedula,
                "nombre": nombre,
                "fecha_registro": datetime.now(CO)
            })
            st.success("✅ Usuario registrado. Ahora puedes registrar el ingreso.")
            st.rerun()

    if usuario or nombre:
        vehiculos_usuario = list(vehiculos.find({"cedula": cedula}))
        opciones = [f"{v['tipo'].capitalize()} – {v['marca']}" for v in vehiculos_usuario]
        seleccion = st.selectbox("Seleccionar vehículo", opciones + ["➕ Registrar nuevo vehículo"])

        if seleccion == "➕ Registrar nuevo vehículo":
            with st.form("form_nuevo_vehiculo"):
                tipo = st.selectbox("Tipo de vehículo", ["Patineta", "Bicicleta"])
                marca = st.text_input("Marca y referencia", max_chars=50)
                color = st.text_input("Color o señas distintivas (opcional)", max_chars=50)
                candado = st.text_input("Candado entregado (opcional)", max_chars=30)
                submitted = st.form_submit_button("Registrar ingreso")

                if submitted:
                    vehiculos.insert_one({
                        "cedula": cedula,
                        "tipo": tipo.lower(),
                        "marca": marca,
                        "color": color,
                        "candado": candado
                    })
                    ingresos.insert_one({
                        "cedula": cedula,
                        "nombre": usuario["nombre"] if usuario else nombre,
                        "tipo": tipo.lower(),
                        "marca": marca,
                        "color": color,
                        "candado": candado,
                        "ingreso": datetime.now(CO),
                        "salida": None,
                        "estado": "activo"
                    })
                    st.success("🚲 Vehículo registrado e ingreso almacenado.")
                    st.rerun()
        else:
            seleccionado = vehiculos_usuario[opciones.index(seleccion)]
            if st.button("Registrar ingreso"):
                ingresos.insert_one({
                    "cedula": cedula,
                    "nombre": usuario["nombre"] if usuario else nombre,
                    "tipo": seleccionado.get("tipo", "").lower(),
                    "marca": seleccionado.get("marca", ""),
                    "color": seleccionado.get("color", ""),
                    "candado": seleccionado.get("candado", ""),
                    "ingreso": datetime.now(CO),
                    "salida": None,
                    "estado": "activo"
                })
                st.success("✅ Ingreso registrado correctamente.")
                st.rerun()

# === SALIDA ===
st.subheader("🔴 Registrar salida")
cedula_salida = st.text_input("Ingresar cédula con ingreso activo", key="salida_manual")

if cedula_salida:
    activos = list(ingresos.find({"cedula": cedula_salida, "estado": "activo"}))
    if not activos:
        st.warning("❌ No hay ingresos activos para esta cédula.")
    elif len(activos) == 1:
        seleccionado = activos[0]
    else:
        opciones = [f"{v.get('tipo','—').capitalize()} – {v.get('marca','—')}" for v in activos]
        seleccion = st.selectbox("Selecciona el vehículo para registrar salida", opciones)
        seleccionado = activos[opciones.index(seleccion)]

    if activos:
        tipo = seleccionado.get("tipo", "—").capitalize()
        marca = seleccionado.get("marca", "—")
        st.info(f"Vehículo encontrado: {tipo} – {marca}")
        if st.button("Registrar salida ahora"):
            salida_hora = datetime.now(CO)
            ingreso_dt = safe_datetime(seleccionado.get("ingreso"))
            duracion_str = formatear_duracion(ingreso_dt, salida_hora)
            duracion_min = int((salida_hora - ingreso_dt).total_seconds() / 60)
            ingresos.update_one(
                {"_id": seleccionado["_id"]},
                {"$set": {
                    "salida": salida_hora,
                    "estado": "finalizado",
                    "duracion_min": duracion_min,
                    "duracion_str": duracion_str
                }}
            )
            st.success(f"✅ Salida registrada. Tiempo bajo cuidado: **{duracion_str}**.")
            st.rerun()

# === PARQUEADOS ACTUALMENTE ===
st.subheader("🚧 Vehículos actualmente parqueados")
parqueados = list(ingresos.find({"estado": "activo"}))
parqueados.sort(key=lambda x: orden_tipo.get(x.get("tipo", ""), 99))

if parqueados:
    data = []
    for i, r in enumerate(parqueados, 1):
        ingreso_dt = safe_datetime(r.get("ingreso"))
        data.append({
            "N°": i,
            "Nombre": r.get("nombre", "—"),
            "Cédula": r.get("cedula", "—"),
            "Tipo": r.get("tipo", "—").capitalize(),
            "Marca": r.get("marca", "—"),
            "Ingreso": ingreso_dt.astimezone(CO).strftime("%Y-%m-%d %H:%M"),
            "Candado": r.get("candado", "")
        })
    st.dataframe(pd.DataFrame(data), use_container_width=True)
else:
    st.info("No hay vehículos actualmente parqueados.")

# === HISTORIAL DE FINALIZADOS ===
st.subheader("📜 Historial de registros finalizados")
historial = list(ingresos.find({"estado": "finalizado"}).sort("salida", -1).limit(10))
historial.sort(key=lambda x: orden_tipo.get(x.get("tipo", ""), 99))

if historial:
    data = []
    for i, r in enumerate(historial, 1):
        ingreso_dt = safe_datetime(r.get("ingreso"))
        salida_dt = safe_datetime(r.get("salida"))
        data.append({
            "N°": i,
            "Nombre": r.get("nombre", "—"),
            "Cédula": r.get("cedula", "—"),
            "Tipo": r.get("tipo", "—").capitalize(),
            "Marca": r.get("marca", "—"),
            "Ingreso": ingreso_dt.astimezone(CO).strftime("%Y-%m-%d %H:%M"),
            "Salida": salida_dt.astimezone(CO).strftime("%Y-%m-%d %H:%M"),
            "Duración": r.get("duracion_str", "—"),
            "Candado": r.get("candado", "")
        })
    st.dataframe(pd.DataFrame(data), use_container_width=True)
else:
    st.info("No hay registros finalizados aún.")
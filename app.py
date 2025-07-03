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
def formatear_duracion(inicio, fin):
    if not isinstance(inicio, datetime):
        inicio = parse(str(inicio))
    if not isinstance(fin, datetime):
        fin = parse(str(fin))
    if inicio.tzinfo is None:
        inicio = CO.localize(inicio)
    if fin.tzinfo is None:
        fin = CO.localize(fin)
    duracion = fin - inicio
    dias = duracion.days
    horas, rem = divmod(duracion.seconds, 3600)
    minutos, segundos = divmod(rem, 60)
    if dias > 0:
        return f"{dias}d {horas:02d}:{minutos:02d}:{segundos:02d}"
    else:
        return f"{horas:02d}:{minutos:02d}:{segundos:02d}"

# === INGRESO ===
st.subheader("🟢 Ingreso de vehículo")
cedula = st.text_input("Número de cédula", max_chars=15)

if cedula:
    usuario = usuarios.find_one({"cedula": cedula})
    if usuario:
        st.success(f"Usuario encontrado: {usuario['nombre']}")
        vehiculos_usuario = list(vehiculos.find({"cedula": cedula}))
        if vehiculos_usuario:
            opciones = [f"{v['tipo'].capitalize()} – {v['marca']}" for v in vehiculos_usuario]
            seleccion = st.selectbox("Selecciona el vehículo", opciones + ["Agregar nuevo vehículo"])
            if seleccion != "Agregar nuevo vehículo":
                vehiculo = vehiculos_usuario[opciones.index(seleccion)]
            else:
                vehiculo = None
        else:
            vehiculo = None
    else:
        nombre = st.text_input("Nombre completo")
        if nombre:
            if st.button("Registrar usuario"):
                usuarios.insert_one({
                    "cedula": cedula,
                    "nombre": nombre,
                    "fecha_registro": datetime.now(CO)
                })
                st.success("✅ Usuario registrado. Continúa con el ingreso del vehículo.")
                st.experimental_rerun()
        vehiculo = None

    if usuario or nombre:
        st.markdown("### Datos del vehículo")
        tipo = st.selectbox("Tipo de vehículo", ["Patineta", "Bicicleta"])
        marca = st.text_input("Marca y referencia")
        color = st.text_input("Color o señas distintivas (opcional)")
        candado = st.text_input("Candado entregado (opcional)")

        if st.button("Registrar ingreso"):
            now = datetime.now(CO)
            nombre = usuario["nombre"] if usuario else nombre
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
                "ingreso": now,
                "salida": None,
                "estado": "activo"
            })
            st.success("✅ Ingreso registrado.")
            st.experimental_rerun()

# === SALIDA ===
st.subheader("🔴 Registrar salida")
cedula_salida = st.text_input("Número de cédula para salida")

if cedula_salida:
    activos = list(ingresos.find({"cedula": cedula_salida, "estado": "activo"}))
    if activos:
        seleccion = st.selectbox("Selecciona el vehículo a dar salida", [
            f"{v['tipo'].capitalize()} – {v['marca']}" for v in activos
        ])
        seleccionado = activos[[f"{v['tipo'].capitalize()} – {v['marca']}" for v in activos].index(seleccion)]

        if st.button("Registrar salida"):
            salida_hora = datetime.now(CO)
            ingreso_dt = parse(str(seleccionado["ingreso"]))
            if ingreso_dt.tzinfo is None:
                ingreso_dt = CO.localize(ingreso_dt)

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
            st.success(f"✅ Salida registrada. Duración: {duracion_str}")
            st.experimental_rerun()
    else:
        st.warning("No hay ingresos activos para esa cédula.")

# === PARQUEADOS ACTUALMENTE ===
st.subheader("🚧 Vehículos actualmente parqueados")
parqueados = list(ingresos.find({"estado": "activo"}))
parqueados.sort(key=lambda x: orden_tipo.get(x.get("tipo", ""), 99))

if parqueados:
    data = []
    for i, r in enumerate(parqueados, start=1):
        ingreso_dt = parse(str(r["ingreso"])).astimezone(CO)
        data.append({
            "#": i,
            "Nombre": r["nombre"],
            "Cédula": r["cedula"],
            "Tipo": r["tipo"].capitalize(),
            "Marca": r["marca"],
            "Ingreso": ingreso_dt.strftime("%Y-%m-%d %H:%M"),
            "Candado": r.get("candado", "")
        })
    st.dataframe(pd.DataFrame(data), use_container_width=True)
else:
    st.info("No hay vehículos actualmente parqueados.")

# === HISTORIAL DE SALIDAS ===
st.subheader("📜 Últimos ingresos finalizados")
historial = list(ingresos.find({"estado": "finalizado"}).sort("salida", -1).limit(10))
historial.sort(key=lambda x: orden_tipo.get(x.get("tipo", ""), 99))

if historial:
    data = []
    for i, r in enumerate(historial, start=1):
        ingreso_dt = parse(str(r["ingreso"])).astimezone(CO)
        salida_dt = parse(str(r["salida"])).astimezone(CO)
        data.append({
            "#": i,
            "Nombre": r["nombre"],
            "Cédula": r["cedula"],
            "Tipo": r["tipo"].capitalize(),
            "Marca": r["marca"],
            "Ingreso": ingreso_dt.strftime("%Y-%m-%d %H:%M"),
            "Salida": salida_dt.strftime("%Y-%m-%d %H:%M"),
            "Duración": r.get("duracion_str", "-"),
            "Candado": r.get("candado", "")
        })
    st.dataframe(pd.DataFrame(data), use_container_width=True)
else:
    st.info("No hay registros finalizados aún.")
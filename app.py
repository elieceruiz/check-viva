import streamlit as st
import pymongo
from datetime import datetime
from dateutil.parser import parse
import pytz
import pandas as pd

# === CONFIG ===
st.set_page_config(page_title="🛴🚲 Registro de Patinetas y Bicicletas – CC VIVA Envigado", layout="centered")
MONGO_URI = st.secrets["mongo_uri"]
client = pymongo.MongoClient(MONGO_URI)
db = client.check_viva
col_ingresos = db.ingresos
col_usuarios = db.usuarios
col_vehiculos = db.vehiculos

orden_tipo = {"Patineta": 0, "Bicicleta": 1}
tz = pytz.timezone("America/Bogota")

st.title("🛴🚲 Registro de Patinetas y Bicicletas – CC VIVA Envigado")

# === INGRESO ===
st.header("🟢 Ingreso de vehículo")
cedula_ing = st.text_input("Número de cédula")

if cedula_ing:
    usuario = col_usuarios.find_one({"cedula": cedula_ing})
    if not usuario:
        with st.form("nuevo_usuario"):
            st.warning("Cédula no registrada. Por favor ingrese los datos.")
            nombre = st.text_input("Nombre completo")
            tipo = st.selectbox("Tipo de vehículo", ["Patineta", "Bicicleta"])
            marca = st.text_input("Marca / Referencia")
            submitted = st.form_submit_button("Registrar")
            if submitted:
                col_usuarios.insert_one({
                    "cedula": cedula_ing,
                    "nombre": nombre,
                    "vehiculos": [{"tipo": tipo, "marca": marca}]
                })
                col_ingresos.insert_one({
                    "cedula": cedula_ing,
                    "nombre": nombre,
                    "tipo": tipo,
                    "marca": marca,
                    "hora_ingreso": datetime.now(tz),
                    "activo": True
                })
                st.success("Usuario y vehículo registrados con ingreso exitoso.")
    else:
        vehiculos = usuario.get("vehiculos", [])
        if not vehiculos:
            st.error("Este usuario no tiene vehículos registrados.")
        else:
            if len(vehiculos) == 1:
                seleccionado = vehiculos[0]
            else:
                opciones = [f"{v['tipo']} – {v['marca']}" for v in vehiculos]
                seleccion_str = st.selectbox("Selecciona el vehículo que va a ingresar", opciones)
                seleccionado = vehiculos[opciones.index(seleccion_str)]
            col_ingresos.insert_one({
                "cedula": cedula_ing,
                "nombre": usuario["nombre"],
                "tipo": seleccionado["tipo"],
                "marca": seleccionado["marca"],
                "hora_ingreso": datetime.now(tz),
                "activo": True
            })
            st.success(f"Ingreso registrado para {usuario['nombre']} – {seleccionado['tipo']}")

# === SALIDA ===
st.header("🔴 Registrar salida")
cedulas_activas = col_ingresos.distinct("cedula", {"activo": True})

cedula_sal = st.text_input("Seleccionar cédula con ingreso activo")

vehiculo_encontrado = None
if cedula_sal:
    registros_activos = list(col_ingresos.find({"cedula": cedula_sal, "activo": True}))
    if not registros_activos:
        st.error("❌ No hay ingresos activos para esta cédula.")
    elif len(registros_activos) == 1:
        vehiculo_encontrado = registros_activos[0]
    else:
        opciones = [f"{r['tipo']} – {r['marca']}" for r in registros_activos]
        seleccion_str = st.selectbox("Selecciona el vehículo a retirar", opciones)
        vehiculo_encontrado = registros_activos[opciones.index(seleccion_str)]

if vehiculo_encontrado:
    st.info(f"Vehículo encontrado: {vehiculo_encontrado['tipo']} – {vehiculo_encontrado['marca']}")
    if st.button("Registrar salida ahora"):
        salida_hora = datetime.now(tz)
        ingreso_dt = vehiculo_encontrado["hora_ingreso"]
        if ingreso_dt.tzinfo is None:
            ingreso_dt = tz.localize(ingreso_dt)
        duracion_min = int((salida_hora - ingreso_dt).total_seconds() / 60)
        col_ingresos.update_one(
            {"_id": vehiculo_encontrado["_id"]},
            {"$set": {
                "activo": False,
                "hora_salida": salida_hora,
                "duracion_min": duracion_min
            }}
        )
        st.success(f"Salida registrada. Duración: {duracion_min} minutos.")

# === TABLA PARQUEADOS ===
st.header("🚧 Vehículos actualmente parqueados")
parqueados = list(col_ingresos.find({"activo": True}))
parqueados.sort(key=lambda x: orden_tipo.get(x["tipo"], 99))

if parqueados:
    data = []
    for i, r in enumerate(parqueados, 1):
        data.append({
            "N°": i,
            "Nombre": r["nombre"],
            "Cédula": r["cedula"],
            "Tipo": r["tipo"].capitalize(),
            "Marca": r["marca"],
            "Ingreso": r["hora_ingreso"].astimezone(tz).strftime("%Y-%m-%d %H:%M")
        })
    st.dataframe(pd.DataFrame(data).set_index("N°"), use_container_width=True)
else:
    st.info("No hay vehículos actualmente parqueados.")

# === TABLA FINALIZADOS ===
st.header("📜 Historial de registros finalizados")
finalizados = list(col_ingresos.find({"activo": False}).sort("hora_salida", -1).limit(10))

if finalizados:
    data = []
    for i, r in enumerate(finalizados, 1):
        data.append({
            "N°": i,
            "Nombre": r["nombre"],
            "Cédula": r["cedula"],
            "Tipo": r["tipo"].capitalize(),
            "Marca": r["marca"],
            "Ingreso": r["hora_ingreso"].astimezone(tz).strftime("%Y-%m-%d %H:%M"),
            "Salida": r["hora_salida"].astimezone(tz).strftime("%Y-%m-%d %H:%M"),
            "Duración (min)": r["duracion_min"]
        })
    st.dataframe(pd.DataFrame(data).set_index("N°"), use_container_width=True)
else:
    st.info("No hay registros finalizados aún.")
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
ahora = datetime.now(CO)
orden_tipo = {"patineta": 0, "bicicleta": 1}

# === FUNCIONES ===
def formatear_duracion(inicio, fin):
    try:
        if not isinstance(inicio, datetime):
            inicio = parse(str(inicio))
        if not isinstance(fin, datetime):
            fin = parse(str(fin))
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
        nombre = usuario["nombre"]
        st.success(f"Usuario encontrado: {nombre}")

        vehiculos_usuario = list(vehiculos.find({"cedula": cedula}))

        if vehiculos_usuario:
            opciones = [f"{v['tipo'].capitalize()} – {v['marca']}" for v in vehiculos_usuario]
            seleccionado = st.selectbox("Selecciona el vehículo para registrar ingreso:", opciones)
            idx = opciones.index(seleccionado)
            vehiculo_sel = vehiculos_usuario[idx]

            if st.button("🟢 Registrar ingreso con este vehículo"):
                ingresos.insert_one({
                    "cedula": cedula,
                    "nombre": nombre,
                    "tipo": vehiculo_sel["tipo"],
                    "marca": vehiculo_sel["marca"],
                    "color": vehiculo_sel.get("color", ""),
                    "candado": vehiculo_sel.get("candado", ""),
                    "ingreso": ahora,
                    "salida": None,
                    "estado": "activo"
                })
                st.success("✅ Ingreso registrado.")
                st.rerun()

            st.markdown("---")
            st.markdown("¿Deseas registrar un **nuevo vehículo** para esta cédula?")
            with st.form("form_nuevo_vehiculo"):
                tipo = st.selectbox("Tipo de vehículo", ["Patineta", "Bicicleta"], key="nuevo_tipo_multi")
                marca = st.text_input("Marca y referencia", max_chars=50, key="nuevo_marca_multi")
                color = st.text_input("Color o señas distintivas (opcional)", max_chars=50, key="nuevo_color_multi")
                candado = st.text_input("Candado entregado (opcional)", max_chars=30, key="nuevo_candado_multi")
                submitted = st.form_submit_button("Registrar nuevo vehículo")
                if submitted:
                    vehiculos.insert_one({
                        "cedula": cedula,
                        "tipo": tipo.lower(),
                        "marca": marca,
                        "color": color,
                        "candado": candado,
                        "fecha_registro": ahora
                    })
                    st.success("🚲 Nuevo vehículo guardado correctamente.")
                    st.rerun()
        else:
            st.markdown("### Registrar primer vehículo para esta cédula")
            with st.form("form_vehiculo_primero"):
                tipo = st.selectbox("Tipo de vehículo", ["Patineta", "Bicicleta"], key="nuevo_tipo_unico")
                marca = st.text_input("Marca y referencia", max_chars=50, key="nuevo_marca_unico")
                color = st.text_input("Color o señas distintivas (opcional)", max_chars=50, key="nuevo_color_unico")
                candado = st.text_input("Candado entregado (opcional)", max_chars=30, key="nuevo_candado_unico")
                submitted = st.form_submit_button("Registrar vehículo e ingreso")
                if submitted:
                    vehiculos.insert_one({
                        "cedula": cedula,
                        "tipo": tipo.lower(),
                        "marca": marca,
                        "color": color,
                        "candado": candado,
                        "fecha_registro": ahora
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
                    st.success("✅ Vehículo e ingreso registrados correctamente.")
                    st.rerun()
    else:
        nombre = st.text_input("Nombre completo")
        if nombre:
            if st.button("Registrar nuevo usuario"):
                usuarios.insert_one({
                    "cedula": cedula,
                    "nombre": nombre,
                    "fecha_registro": ahora
                })
                st.success("✅ Usuario registrado.")
                st.rerun()

# === SALIDA ===
st.subheader("🔴 Registrar salida")
cedula_salida = st.text_input("Buscar cédula para registrar salida", key="salida")

if cedula_salida:
    activos = list(ingresos.find({"cedula": cedula_salida, "estado": "activo"}))
    if activos:
        if len(activos) == 1:
            seleccionado = activos[0]
        else:
            opciones = [f"{r['tipo'].capitalize()} – {r['marca']}" for r in activos]
            sel = st.selectbox("Selecciona el vehículo a retirar:", opciones)
            idx = opciones.index(sel)
            seleccionado = activos[idx]

        st.info(f"Vehículo encontrado: {seleccionado['tipo'].capitalize()} – {seleccionado['marca']}")
        if st.button("Registrar salida ahora"):
            salida_hora = datetime.now(CO)
            ingreso_dt = safe_datetime(seleccionado["ingreso"])
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
            st.success(f"✅ Salida registrada. Tiempo bajo cuidado: {duracion_str}")
            st.rerun()
    else:
        st.warning("❌ No hay ingresos activos para esta cédula.")

# === PARQUEADOS ===
st.subheader("🚧 Vehículos actualmente parqueados")
parqueados = list(ingresos.find({"estado": "activo"}))
parqueados.sort(key=lambda x: orden_tipo.get(x.get("tipo", "").lower(), 99))

if parqueados:
    data = []
    for i, r in enumerate(parqueados, 1):
        ingreso_dt = safe_datetime(r["ingreso"])
        data.append({
            "N°": i,
            "Nombre": r["nombre"],
            "Cédula": r["cedula"],
            "Tipo": r.get("tipo", "—").capitalize(),
            "Marca": r.get("marca", "—"),
            "Ingreso": ingreso_dt.astimezone(CO).strftime("%Y-%m-%d %H:%M"),
            "Candado": r.get("candado", "")
        })
    st.dataframe(pd.DataFrame(data), use_container_width=True)
else:
    st.info("No hay vehículos actualmente parqueados.")

# === HISTORIAL ===
st.subheader("📜 Historial de registros finalizados")
historial = list(ingresos.find({"estado": "finalizado"}).sort("salida", -1).limit(10))
historial.sort(key=lambda x: orden_tipo.get(x.get("tipo", "").lower(), 99))

if historial:
    data = []
    for i, r in enumerate(historial, 1):
        ingreso_dt = safe_datetime(r["ingreso"])
        salida_dt = safe_datetime(r["salida"])
        data.append({
            "N°": i,
            "Nombre": r["nombre"],
            "Cédula": r["cedula"],
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
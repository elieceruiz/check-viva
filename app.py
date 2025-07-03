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

# === UTILIDADES ===
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
    else:
        nombre = st.text_input("Nombre completo")
        if nombre and st.button("Registrar nuevo usuario"):
            usuarios.insert_one({
                "cedula": cedula,
                "nombre": nombre,
                "fecha_registro": ahora
            })
            st.success("✅ Usuario registrado.")
            st.rerun()

    if usuario or nombre:
        vehiculos_usuario = list(vehiculos.find({"cedula": cedula}))
        if vehiculos_usuario:
            opciones = [f"{v['tipo'].capitalize()} – {v['marca']}" for v in vehiculos_usuario]
            seleccion = st.selectbox("Selecciona un vehículo ya registrado o ingresa uno nuevo:", opciones + ["Nuevo vehículo"])
            if seleccion == "Nuevo vehículo":
                nuevo = True
            else:
                index = opciones.index(seleccion)
                vehiculo_usado = vehiculos_usuario[index]
                nuevo = False
        else:
            st.info("No hay vehículos registrados para este usuario.")
            nuevo = True

        if nuevo:
            with st.form("form_ingreso_nuevo"):
                tipo = st.selectbox("Tipo de vehículo", ["Patineta", "Bicicleta"])
                marca = st.text_input("Marca y referencia")
                color = st.text_input("Color o señas distintivas (opcional)")
                candado = st.text_input("Candado entregado (opcional)")
                submitted = st.form_submit_button("🟢 Registrar ingreso")
                if submitted:
                    vehiculo_id = vehiculos.insert_one({
                        "cedula": cedula,
                        "tipo": tipo.lower(),
                        "marca": marca,
                        "color": color,
                        "candado": candado
                    }).inserted_id
                    ingresos.insert_one({
                        "cedula": cedula,
                        "nombre": usuario["nombre"] if usuario else nombre,
                        "vehiculo_id": vehiculo_id,
                        "tipo": tipo.lower(),
                        "marca": marca,
                        "color": color,
                        "candado": candado,
                        "ingreso": ahora,
                        "salida": None,
                        "estado": "activo"
                    })
                    st.success("✅ Vehículo registrado e ingreso creado.")
                    st.rerun()
        else:
            if st.button("🟢 Registrar ingreso con vehículo seleccionado"):
                ingresos.insert_one({
                    "cedula": cedula,
                    "nombre": usuario["nombre"] if usuario else nombre,
                    "vehiculo_id": vehiculo_usado["_id"],
                    "tipo": vehiculo_usado["tipo"],
                    "marca": vehiculo_usado["marca"],
                    "color": vehiculo_usado.get("color", ""),
                    "candado": vehiculo_usado.get("candado", ""),
                    "ingreso": ahora,
                    "salida": None,
                    "estado": "activo"
                })
                st.success("🚲 Ingreso registrado correctamente.")
                st.rerun()

# === SALIDA ===
st.subheader("🔴 Registrar salida")
cedula_salida = st.text_input("Ingresar cédula para registrar salida", key="salida_manual")

if cedula_salida:
    activo = ingresos.find_one({"cedula": cedula_salida, "estado": "activo"})
    if activo:
        salida_hora = datetime.now(CO)
        ingreso_dt = safe_datetime(activo["ingreso"])
        try:
            duracion_str = formatear_duracion(ingreso_dt, salida_hora)
            duracion_min = int((salida_hora - ingreso_dt.astimezone(CO)).total_seconds() / 60)

            ingresos.update_one(
                {"_id": activo["_id"]},
                {"$set": {
                    "salida": salida_hora,
                    "estado": "finalizado",
                    "duracion_min": duracion_min,
                    "duracion_str": duracion_str
                }}
            )
            st.info(
                f"""
                ✅ **Salida registrada**

                **Vehículo:** {activo['tipo'].capitalize()} – {activo['marca']}
                **Cédula:** {activo['cedula']}
                **Duración:** {duracion_str}
                """
            )
            st.rerun()
        except Exception as e:
            st.error(f"❌ Error al calcular duración: {str(e)}")
    else:
        st.warning("❌ No hay ingreso activo para esta cédula.")

# === PARQUEADOS ACTUALMENTE ===
st.subheader("🚧 Vehículos actualmente parqueados")
parqueados = list(ingresos.find({"estado": "activo"}))
parqueados.sort(key=lambda x: orden_tipo.get(x["tipo"], 99))

if parqueados:
    data = []
    for r in parqueados:
        ingreso_dt = safe_datetime(r["ingreso"])
        data.append({
            "Nombre": r["nombre"],
            "Cédula": r["cedula"],
            "Tipo": r["tipo"].capitalize(),
            "Marca": r["marca"],
            "Ingreso": ingreso_dt.astimezone(CO).strftime("%Y-%m-%d %H:%M"),
            "Candado": r.get("candado", "")
        })
    df = pd.DataFrame(data)
    df.index += 1
    st.dataframe(df, use_container_width=True)
else:
    st.info("No hay vehículos actualmente parqueados.")

# === HISTORIAL DE FINALIZADOS ===
st.subheader("📜 Historial de registros finalizados")
historial = list(ingresos.find({"estado": "finalizado"}).sort("salida", -1).limit(10))
historial.sort(key=lambda x: orden_tipo.get(x["tipo"], 99))

if historial:
    data = []
    for r in historial:
        ingreso_dt = safe_datetime(r["ingreso"])
        salida_dt = safe_datetime(r["salida"])
        data.append({
            "Nombre": r["nombre"],
            "Cédula": r["cedula"],
            "Tipo": r["tipo"].capitalize(),
            "Marca": r["marca"],
            "Ingreso": ingreso_dt.astimezone(CO).strftime("%Y-%m-%d %H:%M"),
            "Salida": salida_dt.astimezone(CO).strftime("%Y-%m-%d %H:%M"),
            "Duración": r.get("duracion_str", "—"),
            "Candado": r.get("candado", "")
        })
    df = pd.DataFrame(data)
    df.index += 1
    st.dataframe(df, use_container_width=True)
else:
    st.info("No hay registros finalizados aún.")
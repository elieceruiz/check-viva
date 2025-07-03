import streamlit as st
from datetime import datetime, timezone, timedelta
import pymongo
import pytz
import pandas as pd
from dateutil.parser import parse

# Configuración
st.set_page_config(page_title="🛴🚲 Registro de Patinetas y Bicicletas – CC VIVA Envigado", layout="centered")
CO = pytz.timezone("America/Bogota")
MONGO_URI = st.secrets["mongo_uri"]
client = pymongo.MongoClient(MONGO_URI)
db = client.check_viva
usuarios = db.usuarios
ingresos = db.ingresos

# Función para formatear duración
def formatear_duracion(inicio, fin):
    inicio = inicio.astimezone(CO)
    fin = fin.astimezone(CO)
    duracion = fin - inicio
    dias = duracion.days
    horas, rem = divmod(duracion.seconds, 3600)
    minutos, segundos = divmod(rem, 60)
    partes = []
    if dias > 0:
        partes.append(f"{dias}d")
    partes.append(f"{horas}h {minutos}m {segundos}s")
    return " ".join(partes)

# Orden hegemónico
orden_tipo = {"Patineta": 0, "Bicicleta": 1}

st.title("🛴🚲 Registro de Patinetas y Bicicletas – CC VIVA Envigado")

# === REGISTRO DE INGRESO ===
st.subheader("🟢 Ingreso de vehículo")
with st.form("form_ingreso"):
    nombre = st.text_input("Nombre completo")
    cedula = st.text_input("Número de cédula")
    tipo = st.selectbox("Tipo de vehículo", ["Patineta", "Bicicleta"])
    marca = st.text_input("Marca o referencia")
    submitted = st.form_submit_button("Registrar ingreso")

    if submitted and cedula and nombre and marca:
        usuario = usuarios.find_one({"cedula": cedula})
        if not usuario:
            usuarios.insert_one({
                "nombre": nombre,
                "cedula": cedula,
                "vehiculos": [{
                    "tipo": tipo,
                    "marca": marca,
                    "por_defecto": True
                }]
            })
        else:
            ya_existe = any(v["tipo"] == tipo and v["marca"] == marca for v in usuario.get("vehiculos", []))
            if not ya_existe:
                usuarios.update_one(
                    {"cedula": cedula},
                    {"$push": {"vehiculos": {"tipo": tipo, "marca": marca, "por_defecto": False}}}
                )

        ingresos.insert_one({
            "cedula": cedula,
            "nombre": nombre,
            "tipo": tipo,
            "marca": marca,
            "ingreso": datetime.now(timezone.utc),
            "estado": "activo"
        })
        st.success("✅ Ingreso registrado exitosamente.")

# === REGISTRO DE SALIDA ===
st.subheader("🔴 Registrar salida")
cedula_salida = st.text_input("Número de cédula para salida")

if cedula_salida:
    vehiculo_activo = ingresos.find_one({"cedula": cedula_salida, "estado": "activo"})
    if vehiculo_activo:
        st.info(f"Vehículo encontrado: {vehiculo_activo['tipo']} – {vehiculo_activo['marca']}")
        if st.button("Registrar salida ahora"):
            salida_hora = datetime.now(timezone.utc)
            ingreso_dt = parse(str(vehiculo_activo["ingreso"]))
            duracion_str = formatear_duracion(ingreso_dt, salida_hora)
            ingresos.update_one(
                {"_id": vehiculo_activo["_id"]},
                {
                    "$set": {
                        "salida": salida_hora,
                        "estado": "finalizado",
                        "duracion_str": duracion_str
                    }
                }
            )
            st.success(f"✅ Salida registrada. Duración: {duracion_str}")
    else:
        st.warning("❌ No hay ingresos activos para esta cédula.")

# === VEHÍCULOS PARQUEADOS ===
st.subheader("🚧 Vehículos actualmente parqueados")
parqueados = list(ingresos.find({"estado": "activo"}))
if parqueados:
    parqueados.sort(key=lambda x: orden_tipo.get(x.get("tipo", ""), 99))
    data = []
    for i, r in enumerate(parqueados, start=1):
        ingreso_dt = parse(str(r["ingreso"])).astimezone(CO)
        data.append({
            "N°": i,
            "Nombre": r["nombre"],
            "Cédula": r["cedula"],
            "Tipo": r["tipo"].capitalize(),
            "Marca": r["marca"],
            "Ingreso": ingreso_dt.strftime("%Y-%m-%d %H:%M")
        })
    df = pd.DataFrame(data)
    st.dataframe(df.reset_index(drop=True), use_container_width=True)
else:
    st.info("No hay vehículos actualmente parqueados.")

# === HISTORIAL FINALIZADOS ===
st.subheader("📜 Últimos ingresos finalizados")
historial = list(ingresos.find({"estado": "finalizado"}).sort("salida", -1).limit(10))

if historial:
    historial.sort(key=lambda x: orden_tipo.get(x.get("tipo", ""), 99))
    data = []
    for i, r in enumerate(historial, start=1):
        ingreso_dt = parse(str(r["ingreso"])).astimezone(CO)
        salida_dt = parse(str(r["salida"])).astimezone(CO)
        data.append({
            "N°": i,
            "Nombre": r["nombre"],
            "Cédula": r["cedula"],
            "Tipo": r["tipo"].capitalize(),
            "Marca": r["marca"],
            "Ingreso": ingreso_dt.strftime("%Y-%m-%d %H:%M"),
            "Salida": salida_dt.strftime("%Y-%m-%d %H:%M"),
            "Duración": r.get("duracion_str", "-")
        })
    df = pd.DataFrame(data)
    st.dataframe(df.reset_index(drop=True), use_container_width=True)
else:
    st.info("No hay registros finalizados aún.")
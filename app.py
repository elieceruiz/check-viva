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

registro_exitoso = False
registro_info = {}

if cedula:
    usuario = usuarios.find_one({"cedula": cedula})
    if usuario:
        nombre = usuario["nombre"]
        st.success(f"Usuario encontrado: {nombre}")
    else:
        nombre = st.text_input("Nombre completo")

    if usuario or nombre:
        with st.form("form_ingreso"):
            tipo = st.selectbox("Tipo de vehículo", ["Patineta", "Bicicleta"])
            marca = st.text_input("Marca y referencia", max_chars=50)
            color = st.text_input("Color o señas distintivas (opcional)", max_chars=50)
            candado = st.text_input("Candado entregado (opcional)", max_chars=30)

            if usuario:
                submitted = st.form_submit_button("🟢 Registrar ingreso")
                if submitted:
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
                    st.success("🚲 Ingreso registrado correctamente.")
                    st.rerun()
            else:
                submitted = st.form_submit_button("Registrar nuevo usuario y vehículo")
                if submitted and nombre:
                    usuarios.insert_one({
                        "cedula": cedula,
                        "nombre": nombre,
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
                    st.success("✅ Usuario y vehículo registrados.")
                    registro_exitoso = True
                    registro_info = {
                        "Nombre": nombre,
                        "Cédula": cedula,
                        "Tipo": tipo,
                        "Marca": marca,
                        "Color": color,
                        "Candado": candado,
                        "Ingreso": ahora.strftime("%Y-%m-%d %H:%M")
                    }

# === CONFIRMACIÓN VISUAL ===
if registro_exitoso:
    st.subheader("📋 Resumen del registro")
    st.table(pd.DataFrame([registro_info]))

# (Las demás secciones de salida, parqueados y finalizados siguen como ya las tenés configuradas)
from datetime import datetime import pytz import streamlit as st from pymongo import MongoClient import pandas as pd from dateutil.parser import parse

=== CONFIG ===

st.set_page_config(page_title="🛴🚲 Check VIVA", layout="centered") st.title("🛴🚲 Registro de Patinetas y Bicicletas – CC VIVA Envigado")

=== CONEXIÓN MONGO ===

MONGO_URI = st.secrets["mongo_uri"] client = MongoClient(MONGO_URI) db = client.check_viva usuarios = db.usuarios ingresos = db.ingresos

=== ZONA HORARIA ===

CO = pytz.timezone("America/Bogota") ahora = datetime.now(CO) orden_tipo = {"patineta": 0, "bicicleta": 1}

=== FUNCIONES ===

def formatear_duracion(inicio, fin): try: if not isinstance(inicio, datetime): inicio = parse(str(inicio)) if not isinstance(fin, datetime): fin = parse(str(fin)) duracion = fin - inicio dias = duracion.days horas, rem = divmod(duracion.seconds, 3600) minutos, segundos = divmod(rem, 60) if dias > 0: return f"{dias}d {horas:02d}:{minutos:02d}:{segundos:02d}" else: return f"{horas:02d}:{minutos:02d}:{segundos:02d}" except Exception: return "—"

def safe_datetime(dt): if isinstance(dt, datetime): return dt try: return parse(str(dt)) except: return datetime.now(CO)

=== INGRESO ===

st.subheader("🟢 Ingreso de vehículo") cedula = st.text_input("Número de cédula", max_chars=15)

registro_exitoso = False registro_info = {}

if cedula: usuario = usuarios.find_one({"cedula": cedula}) if usuario: nombre = usuario["nombre"] st.success(f"Usuario encontrado: {nombre}") else: nombre = st.text_input("Nombre completo")

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

=== CONFIRMACIÓN VISUAL ===

if registro_exitoso: st.subheader("📋 Resumen del registro") st.table(pd.DataFrame([registro_info]))

=== SALIDA ===

st.subheader("🔴 Registrar salida") cedulas_registradas = [u["cedula"] for u in usuarios.find({}, {"cedula": 1}) if u.get("cedula")]

if cedulas_registradas: cedula_salida = st.selectbox("Buscar por cédula para registrar salida", cedulas_registradas, key="salida") else: cedula_salida = st.text_input("Ingresar cédula para registrar salida (sin sugerencias)", key="salida_manual")

if cedula_salida: activo = ingresos.find_one({"cedula": cedula_salida, "estado": "activo"}) if activo: st.info(f"Vehículo encontrado: {activo['tipo'].capitalize()} – {activo['marca']}") if st.button("Registrar salida ahora"): try: salida_hora = datetime.now(CO) ingreso_raw = activo.get("ingreso") ingreso_dt = safe_datetime(ingreso_raw)

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

=== PARQUEADOS ACTUALMENTE ===

st.subheader("🚧 Vehículos actualmente parqueados") parqueados = list(ingresos.find({"estado": "activo"})) parqueados.sort(key=lambda x: orden_tipo.get(x["tipo"], 99))

if parqueados: data = [] for r in parqueados: ingreso_dt = safe_datetime(r["ingreso"]) data.append({ "Nombre": r["nombre"], "Cédula": r["cedula"], "Tipo": r["tipo"].capitalize(), "Marca": r["marca"], "Ingreso": ingreso_dt.astimezone(CO).strftime("%Y-%m-%d %H:%M"), "Candado": r.get("candado", "") }) st.dataframe(pd.DataFrame(data), use_container_width=True) else: st.info("No hay vehículos actualmente parqueados.")

=== HISTORIAL DE FINALIZADOS ===

st.subheader("📜 Historial de registros finalizados") historial = list(ingresos.find({"estado": "finalizado"}).sort("salida", -1).limit(10)) historial.sort(key=lambda x: orden_tipo.get(x["tipo"], 99))

if historial: data = [] for r in historial: ingreso_dt = safe_datetime(r["ingreso"]) salida_dt = safe_datetime(r["salida"]) data.append({ "Nombre": r["nombre"], "Cédula": r["cedula"], "Tipo": r["tipo"].capitalize(), "Marca": r["marca"], "Ingreso": ingreso_dt.astimezone(CO).strftime("%Y-%m-%d %H:%M"), "Salida": salida_dt.astimezone(CO).strftime("%Y-%m-%d %H:%M"), "Duración": r.get("duracion_str", "—"), "Candado": r.get("candado", "") }) st.dataframe(pd.DataFrame(data), use_container_width=True) else: st.info("No hay registros finalizados aún.")


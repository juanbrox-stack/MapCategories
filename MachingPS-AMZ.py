import streamlit as st
import pandas as pd
import json
import os
import io
from thefuzz import process, fuzz

st.set_page_config(page_title="Mapeador Pro PS-AMZ", layout="wide")

KB_FILE = "knowledge_base.json"
REVISADOS_FILE = "revisados.json"


# --- FUNCIONES DE PERSISTENCIA ---
def load_json(path, default):
    if os.path.exists(path):
        try:
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
        except (json.JSONDecodeError, OSError):
            return default
    return default


def save_knowledge(mapping_dict):
    with open(KB_FILE, "w", encoding="utf-8") as f:
        json.dump(mapping_dict, f, ensure_ascii=False, indent=4)


def save_revisados(revisados_set):
    # Los sets no son serializables en JSON -> lo guardamos como lista ordenada
    with open(REVISADOS_FILE, "w", encoding="utf-8") as f:
        json.dump(sorted(revisados_set), f, ensure_ascii=False, indent=4)


# --- INICIALIZACIÓN DE ESTADOS ---
if 'kb' not in st.session_state:
    st.session_state.kb = load_json(KB_FILE, {})

if 'revisados' not in st.session_state:
    # Se carga desde disco como set de NOMBRES de categoría Amazon
    st.session_state.revisados = set(load_json(REVISADOS_FILE, []))


def cargar_categorias(df, incluir_sin_asignar=False):
    """Devuelve la lista de categorías (primera columna) limpia, sin nulos ni vacíos."""
    if df is None or not hasattr(df, "iloc") or df.shape[0] == 0 or df.shape[1] == 0:
        return None  # DataFrame no válido

    col = df.iloc[:, 0].dropna().astype(str).str.strip()
    col = col[col != ""]                       # descartar cadenas vacías
    valores = sorted(col.unique().tolist())
    if incluir_sin_asignar:
        return ["[ Sin asignar ]"] + valores
    return valores


st.title("🎯 Mapeador Pro de Categorías")

# --- SIDEBAR: FILTROS Y DESCARGA ---
st.sidebar.header("⚙️ Panel de Control")

ver_estado = st.sidebar.radio(
    "Filtrar vista:",
    ["Todas", "Pendientes de revisar", "Confirmadas/Memoria"]
)
min_score = st.sidebar.slider("Ocultar coincidencias superiores a (%):", 0, 100, 100)

st.sidebar.divider()

# --- 1. CARGA DE ARCHIVOS ---
col_u1, col_u2 = st.columns(2)
with col_u1:
    file_ps = st.file_uploader("📂 PrestaShop (.xlsx)", type=["xlsx"])
with col_u2:
    file_amz = st.file_uploader("📂 Amazon (.xlsx)", type=["xlsx"])

if file_ps and file_amz:
    try:
        df_ps = pd.read_excel(file_ps)
        df_amz = pd.read_excel(file_amz)
    except Exception as e:
        st.error(f"No se han podido leer los archivos Excel: {e}")
        st.stop()

    # --- Validación y construcción de listas de categorías ---
    cat_ps_list = cargar_categorias(df_ps, incluir_sin_asignar=True)
    cat_amz_list = cargar_categorias(df_amz, incluir_sin_asignar=False)

    if cat_ps_list is None:
        st.error("El archivo de PrestaShop está vacío o no tiene columnas válidas.")
        st.stop()
    if cat_amz_list is None:
        st.error("El archivo de Amazon está vacío o no tiene columnas válidas.")
        st.stop()

    # Lista de opciones PS reales (sin el placeholder "[ Sin asignar ]")
    opciones_ps = cat_ps_list[1:]

    final_mapping = []
    temp_kb = st.session_state.kb.copy()

    # --- 2. LÓGICA DE PROCESAMIENTO (Bucle principal) ---
    filas_mostradas = 0
    for i, cat_amz in enumerate(cat_amz_list):
        if cat_amz in st.session_state.kb:
            sugerencia = st.session_state.kb[cat_amz]
            score, metodo, color = 100, "💾 Memoria", "blue"
            es_pendiente = False
        else:
            resultado = None
            if opciones_ps:  # solo si hay categorías PS con las que comparar
                resultado = process.extractOne(
                    cat_amz, opciones_ps, scorer=fuzz.token_sort_ratio
                )

            if resultado:
                match, score = resultado
                sugerencia = match
                metodo = f"🤖 IA ({score}%)"
                color = "green" if score > 85 else "orange"
                es_pendiente = score < 95
            else:
                # Sin coincidencias posibles
                sugerencia, score = "[ Sin asignar ]", 0
                metodo, color = "⚠️ Sin coincidencia", "red"
                es_pendiente = True

        # ¿Esta categoría ya fue marcada como revisada? (por NOMBRE, persistente)
        ya_revisado = cat_amz in st.session_state.revisados

        # Lógica de Filtrado Visual
        mostrar = True
        if ya_revisado and ver_estado == "Pendientes de revisar":
            mostrar = False
        if ver_estado == "Pendientes de revisar" and not es_pendiente:
            mostrar = False
        if ver_estado == "Confirmadas/Memoria" and es_pendiente:
            mostrar = False
        if score > min_score:
            mostrar = False

        # Guardamos siempre el resultado actual para el Excel final
        current_selection = st.session_state.get(f"sel_{cat_amz}", sugerencia)
        temp_kb[cat_amz] = current_selection
        final_mapping.append({
            "ID": i + 1,
            "Categoría PrestaShop": current_selection,
            "Categoría Amazon": cat_amz
        })

        if mostrar:
            filas_mostradas += 1
            etiqueta = f"📦 {cat_amz}" + ("  ·  ✅ revisado" if ya_revisado else "")
            with st.expander(etiqueta, expanded=es_pendiente and not ya_revisado):
                c1, c2, c3 = st.columns([2, 1, 1])
                with c1:
                    idx_default = (
                        cat_ps_list.index(current_selection)
                        if current_selection in cat_ps_list else 0
                    )
                    st.selectbox(
                        "Mapear a:",
                        options=cat_ps_list,
                        index=idx_default,
                        key=f"sel_{cat_amz}"
                    )
                with c2:
                    st.write(f"Estado: :{color}[{metodo}]")
                with c3:
                    if ya_revisado:
                        if st.button("↩️ Desmarcar", key=f"btn_{cat_amz}"):
                            st.session_state.revisados.discard(cat_amz)
                            save_revisados(st.session_state.revisados)  # persistir
                            st.rerun()
                    else:
                        if st.button("✅ Revisado", key=f"btn_{cat_amz}"):
                            st.session_state.revisados.add(cat_amz)
                            save_revisados(st.session_state.revisados)  # persistir
                            st.rerun()

    if filas_mostradas == 0 and len(cat_amz_list) > 0:
        st.success("🎉 ¡Todo revisado para este filtro!")

    # --- 3. BOTÓN DE DESCARGA EN EL SIDEBAR ---
    st.sidebar.subheader("📥 Exportar Resultados")

    df_final = pd.DataFrame(final_mapping)
    # Limpiamos los "Sin asignar" para el Excel final
    df_export = df_final.copy()
    if not df_export.empty:
        df_export["Categoría PrestaShop"] = (
            df_export["Categoría PrestaShop"].replace("[ Sin asignar ]", "")
        )

    buffer = io.BytesIO()
    with pd.ExcelWriter(buffer, engine='openpyxl') as writer:
        df_export.to_excel(writer, index=False, sheet_name='Mapeo')

    st.sidebar.download_button(
        label="💾 Descargar Maestro Excel",
        data=buffer.getvalue(),
        file_name="maestro_mapeado.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        on_click=save_knowledge,
        args=(temp_kb,),
        use_container_width=True
    )

    # Contador de progreso
    st.sidebar.caption(
        f"Revisadas: {len(st.session_state.revisados)} / {len(cat_amz_list)}"
    )

    if st.sidebar.button("🔄 Resetear Sesión", use_container_width=True):
        st.session_state.revisados = set()
        save_revisados(st.session_state.revisados)  # limpiar también en disco
        st.rerun()

else:
    st.info("Sube los archivos Excel para activar las herramientas de mapeo.")

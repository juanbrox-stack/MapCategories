import streamlit as st
import pandas as pd
import json
import os
import io
from thefuzz import process, fuzz

st.set_page_config(page_title="Mapeador Pro PS-AMZ", layout="wide")

# --- INICIALIZACIÓN DE ESTADOS ---
if 'kb' not in st.session_state:
    if os.path.exists("knowledge_base.json"):
        with open("knowledge_base.json", "r", encoding="utf-8") as f:
            st.session_state.kb = json.load(f)
    else:
        st.session_state.kb = {}

if 'revisados' not in st.session_state:
    st.session_state.revisados = set()

def save_knowledge(mapping_dict):
    with open("knowledge_base.json", "w", encoding="utf-8") as f:
        json.dump(mapping_dict, f, ensure_ascii=False, indent=4)

st.title("🎯 Mapeador Pro de Categorías")

# --- SIDEBAR: FILTROS Y DESCARGA ---
st.sidebar.header("⚙️ Panel de Control")

ver_estado = st.sidebar.radio("Filtrar vista:", ["Todas", "Pendientes de revisar", "Confirmadas/Memoria"])
min_score = st.sidebar.slider("Ocultar coincidencias superiores a (%):", 0, 100, 100)

st.sidebar.divider()

# --- 1. CARGA DE ARCHIVOS ---
col_u1, col_u2 = st.columns(2)
with col_u1:
    file_ps = st.file_uploader("📂 PrestaShop (.xlsx)", type=["xlsx"])
with col_u2:
    file_amz = st.file_uploader("📂 Amazon (.xlsx)", type=["xlsx"])

if file_ps and file_amz:
    df_ps = pd.read_excel(file_ps)
    df_amz = pd.read_excel(file_amz)

    cat_ps_list = ["[ Sin asignar ]"] + sorted(df_ps.iloc[:, 0].astype(str).unique().tolist())
    cat_amz_list = df_amz.iloc[:, 0].astype(str).unique().tolist()

    final_mapping = []
    temp_kb = st.session_state.kb.copy()

    # --- 2. LÓGICA DE PROCESAMIENTO (Bucle principal) ---
    filas_mostradas = 0
    for i, cat_amz in enumerate(cat_amz_list):
        if cat_amz in st.session_state.kb:
            sugerencia, score, metodo, color = st.session_state.kb[cat_amz], 100, "💾 Memoria", "blue"
            es_pendiente = False
        else:
            match, score = process.extractOne(cat_amz, cat_ps_list[1:], scorer=fuzz.token_sort_ratio)
            sugerencia, metodo, color = match, f"🤖 IA ({score}%)", "green" if score > 85 else "orange"
            es_pendiente = score < 95

        # Lógica de Filtrado Visual
        mostrar = True
        if i in st.session_state.revisados and ver_estado == "Pendientes de revisar": 
            mostrar = False
        if ver_estado == "Pendientes de revisar" and not es_pendiente: mostrar = False
        if ver_estado == "Confirmadas/Memoria" and es_pendiente: mostrar = False
        if score > min_score: mostrar = False

        # Guardamos siempre el resultado actual para el Excel final
        # Si el usuario ya cambió algo en el selectbox, se captura mediante st.session_state
        current_selection = st.session_state.get(f"sel_{i}", sugerencia)
        temp_kb[cat_amz] = current_selection
        final_mapping.append({"ID": i + 1, "Categoría PrestaShop": current_selection, "Categoría Amazon": cat_amz})

        if mostrar:
            filas_mostradas += 1
            with st.expander(f"📦 {cat_amz}", expanded=es_pendiente):
                c1, c2, c3 = st.columns([2, 1, 1])
                with c1:
                    idx_default = cat_ps_list.index(current_selection) if current_selection in cat_ps_list else 0
                    st.selectbox(f"Mapear a:", options=cat_ps_list, index=idx_default, key=f"sel_{i}")
                with c2:
                    st.write(f"Estado: :{color}[{metodo}]")
                with c3:
                    if st.button("✅ Revisado", key=f"btn_{i}"):
                        st.session_state.revisados.add(i)
                        st.rerun()

    if filas_mostradas == 0 and len(cat_amz_list) > 0:
        st.success("🎉 ¡Todo revisado para este filtro!")

    # --- 3. BOTÓN DE DESCARGA EN EL SIDEBAR ---
    st.sidebar.subheader("📥 Exportar Resultados")
    
    df_final = pd.DataFrame(final_mapping)
    # Limpiamos los "Sin asignar" para el Excel final
    df_export = df_final.copy()
    df_export["Categoría PrestaShop"] = df_export["Categoría PrestaShop"].replace("[ Sin asignar ]", "")

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
    
    if st.sidebar.button("🔄 Resetear Sesión", use_container_width=True):
        st.session_state.revisados = set()
        st.rerun()

else:
    st.info("Sube los archivos Excel para activar las herramientas de mapeo.")
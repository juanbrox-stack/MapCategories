import streamlit as st
import pandas as pd
import json
import os
from thefuzz import process, fuzz

st.set_page_config(page_title="Mapeador Inteligente PS-AMZ", layout="wide")

# --- FUNCIONES DE PERSISTENCIA ---
DB_FILE = "knowledge_base.json"

def load_knowledge():
    if os.path.exists(DB_FILE):
        with open(DB_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}

def save_knowledge(mapping_dict):
    with open(DB_FILE, "w", encoding="utf-8") as f:
        json.dump(mapping_dict, f, ensure_ascii=False, indent=4)

# Cargar memoria al inicio
if 'kb' not in st.session_state:
    st.session_state.kb = load_knowledge()

st.title("🔄 Mapeador con Memoria: Amazon vs PrestaShop")

# --- 1. CARGA DE ARCHIVOS ---
col_u1, col_u2 = st.columns(2)
with col_u1:
    file_ps = st.file_uploader("Categorías PrestaShop (.xlsx)", type=["xlsx"])
with col_u2:
    file_amz = st.file_uploader("Categorías Amazon (.xlsx)", type=["xlsx"])

if file_ps and file_amz:
    df_ps = pd.read_excel(file_ps)
    df_amz = pd.read_excel(file_amz)

    # Limpieza y ordenación
    cat_ps_list = sorted(df_ps.iloc[:, 0].astype(str).unique().tolist())
    cat_amz_list = df_amz.iloc[:, 0].astype(str).unique().tolist()

    st.divider()
    st.subheader("🛠️ Validación de Mapeos")

    final_mapping = []
    new_knowledge = st.session_state.kb.copy()

    # --- 2. PROCESAMIENTO FILA POR FILA ---
    for i, cat_amz in enumerate(cat_amz_list):
        with st.container():
            c1, c2, c3 = st.columns([2, 2, 1])
            
            with c1:
                st.markdown(f"**Amazon:** `{cat_amz}`")
            
            # Lógica de Selección de Sugerencia
            # 1. Mirar en la memoria (Knowledge Base)
            # 2. Si no está, usar Fuzzy Matching
            if cat_amz in st.session_state.kb:
                sugerencia = st.session_state.kb[cat_amz]
                metodo = "💾 Memoria"
                color = "blue"
            else:
                match, score = process.extractOne(cat_amz, cat_ps_list, scorer=fuzz.token_sort_ratio)
                sugerencia = match
                metodo = f"🤖 IA ({score}%)"
                color = "green" if score > 80 else "orange"

            with c2:
                # El usuario puede cambiar la opción aquí
                idx_default = cat_ps_list.index(sugerencia) if sugerencia in cat_ps_list else 0
                seleccion_final = st.selectbox(
                    f"Asignar PS para fila {i+1}:",
                    options=cat_ps_list,
                    index=idx_default,
                    key=f"sel_{i}"
                )
                # Actualizamos la memoria temporal
                new_knowledge[cat_amz] = seleccion_final
            
            with c3:
                st.markdown(f":{color}[{metodo}]")
            
            final_mapping.append({
                "ID": i + 1,
                "Categoría PrestaShop": seleccion_final,
                "Categoría Amazon": cat_amz
            })
            st.divider()

    # --- 3. EXPORTACIÓN Y GUARDADO ---
    df_final = pd.DataFrame(final_mapping)
    
    st.subheader("✅ Resultado del Maestro")
    st.dataframe(df_final, use_container_width=True)

    # Al hacer clic en descargar, guardamos lo aprendido
    csv_data = df_final.to_csv(index=False).encode('utf-8')
    
    if st.download_button(
        label="📥 Descargar y Guardar Memoria",
        data=csv_data,
        file_name="maestro_mapeo.csv",
        mime="text/csv",
    ):
        save_knowledge(new_knowledge)
        st.session_state.kb = new_knowledge
        st.success("¡Mapeo guardado en la base de conocimientos!")

else:
    st.info("Sube los archivos para activar la memoria de mapeo.")
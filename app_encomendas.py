import streamlit as st
import gspread
import pandas as pd
import uuid
from datetime import date, time
import time as t 
from streamlit_autorefresh import st_autorefresh 

# --- CONFIGURAÇÕES DA CONFEITARIA DIGITAL ---

# ID da Planilha no seu Google Drive (SEU NOVO ID)
PLANILHA_ID = "141mq4MZ8q60H_-wFb1_MuX8dXa4YEjHMYI3BjNUPT3Y" 
ABA_NOME = "ENCOMENDAS" # O nome exato da sua aba

# Mapeamento de Colunas (DE: Coluna Antiga, PARA: Coluna Nova do Bolo)
# Isso garante que a lógica CRUD continue funcionando no Streamlit, mas com os nomes da sua planilha.
COLUNAS_SHEET = {
    'id_evento': 'ID_ENCOMENDA',  # Chave única para controle
    'titulo': 'Nome',             # Nome do cliente
    'descricao': 'Sabor',         # Sabor do bolo (agora é a descrição!)
    'data_evento': 'Data',        # Data da entrega
    'hora_evento': 'Horario',     # Horário da entrega
    'local': 'Torre e APT',       # Local virou Torre/APT
    'prioridade': 'Prioridade',   # Prioridade (mantemos para gestão de tempo)
    'status': 'Status'            # Status (Pendente/Entregue)
}

# Invertemos o mapeamento para usar nas funções de leitura e exibição
COLUNAS_INVERTIDAS = {v: k for k, v in COLUNAS_SHEET.items()}
COLUNAS_EXIBICAO = list(COLUNAS_SHEET.values())

# --- CONFIGURAÇÃO DA GOVERNANÇA (Conexão Segura e Resiliente) ---
# O seu código de conexão estava perfeito! Manteremos o retry e o cache.

@st.cache_resource
def conectar_sheets():
    """Tenta conectar ao Google Sheets usando Streamlit Secrets com lógica de Retentativa."""
    MAX_RETRIES = 3
    
    # Inicia a lógica de retry
    for attempt in range(MAX_RETRIES):
        try:
            # st.secrets["gspread"] vem do arquivo secrets.toml
            gc = gspread.service_account_from_dict(st.secrets["gspread"])
            
            spreadsheet = gc.open_by_key(PLANILHA_ID)
            sheet = spreadsheet.worksheet(ABA_NOME)
            
            st.sidebar.success("✅ Conexão com a Confeitaria Digital (Google Sheets) estabelecida.")
            return sheet
        
        except Exception as e:
            if attempt < MAX_RETRIES - 1:
                wait_time = 2 ** attempt
                st.sidebar.warning(f"⚠️ Falha de conexão momentânea (Tentativa {attempt + 1}/{MAX_RETRIES}). Retentando em {wait_time}s...")
                t.sleep(wait_time) 
            else:
                st.error(f"🚨 Erro fatal ao conectar após {MAX_RETRIES} tentativas. Verifique as permissões da Conta de Serviço. Erro: {e}")
                return None
    return None


# --- FUNÇÕES CORE DO CRUD (Adaptadas para Encomendas) ---

# R (Read) - Lê todos os eventos
def carregar_eventos(sheet):
    """Lê todos os registros e retorna como DataFrame."""
    
    if sheet is None:
         return pd.DataFrame()
         
    try:
        dados = sheet.get_all_records()
        df = pd.DataFrame(dados)
        
        # Garante que o DataFrame tem as colunas esperadas para o CRUD
        # Renomeia as colunas do Sheets (Nome, Sabor...) para as chaves internas (titulo, descricao...)
        df.rename(columns=COLUNAS_INVERTIDAS, inplace=True) 
        
        return df
    except Exception as e:
        st.error(f"Erro ao carregar dados do Sheets: {e}")
        return pd.DataFrame()

# C (Create) - Adiciona uma nova encomenda
def adicionar_evento(sheet, dados_do_form):
    """Insere uma nova linha de encomenda no Sheets, usando a ordem correta das colunas."""
    
    # ORDEM DA PLANILHA: ID_ENCOMENDA, Nome, Sabor, Torre e APT, Data, Horario, Prioridade, Status
    nova_linha = [
        dados_do_form.get('id_evento'),
        dados_do_form.get('titulo'),
        dados_do_form.get('descricao'),
        dados_do_form.get('local'),       # Mapeado para Torre e APT
        dados_do_form.get('data_evento'),
        dados_do_form.get('hora_evento'),
        dados_do_form.get('prioridade'),
        dados_do_form.get('status')
    ]
    
    sheet.append_row(nova_linha, value_input_option='USER_ENTERED')
    st.success("🎉 Encomenda de bolo registrada. Mais um doce compromisso. **A lista abaixo será atualizada automaticamente em 20 segundos.**")
    conectar_sheets.clear()

# U (Update) - Atualiza uma encomenda existente
def atualizar_evento(sheet, id_evento, novos_dados):
    """Busca a linha pelo ID e atualiza os dados da linha."""
    try:
        # Nota: O gspread busca pelo conteúdo da célula. Precisamos da coluna do ID.
        coluna_id = COLUNAS_SHEET['id_evento'] # 'ID_ENCOMENDA'
        cell = sheet.find(id_evento, in_column=sheet.col_values(1).index(coluna_id) + 1) # Encontra na coluna 1 (A)

        linha_index = cell.row 

        # ORDEM DA PLANILHA: ID_ENCOMENDA, Nome, Sabor, Torre e APT, Data, Horario, Prioridade, Status
        valores_atualizados = [
            novos_dados['id_evento'],
            novos_dados['titulo'],
            novos_dados['descricao'],
            novos_dados['local'],
            novos_dados['data_evento'],
            novos_dados['hora_evento'],
            novos_dados['prioridade'],
            novos_dados['status']
        ]

        # Atualiza a linha completa a partir da coluna A
        sheet.update(f'A{linha_index}:{chr(ord("A") + len(valores_atualizados)-1)}{linha_index}', [valores_atualizados])
        
        st.success(f"🔄 Encomenda {id_evento[:8]}... atualizada. Foco no sabor. **A lista será atualizada automaticamente em 20 segundos.**") 
        conectar_sheets.clear()
        return True

    except gspread.exceptions.CellNotFound:
        st.error(f"🚫 ID de Encomenda '{id_evento[:8]}...' não encontrado. O cliente fugiu!")
        return False
    except Exception as e:
        st.error(f"🚫 Erro ao atualizar a encomenda: {e}")
        return False

# D (Delete) - Remove uma encomenda
def deletar_evento(sheet, id_evento):
    """Busca a linha pelo ID e a deleta."""
    try:
        coluna_id = COLUNAS_SHEET['id_evento'] # 'ID_ENCOMENDA'
        cell = sheet.find(id_evento, in_column=sheet.col_values(1).index(coluna_id) + 1) # Encontra na coluna 1 (A)
        
        linha_index = cell.row

        sheet.delete_rows(linha_index)
        st.success(f"🗑️ Encomenda {id_evento[:8]}... deletada. Bolo cancelado, menos estresse. **A lista será atualizada automaticamente em 20 segundos.**")
        conectar_sheets.clear()
        return True
    except gspread.exceptions.CellNotFound:
        st.error(f"🚫 ID de Encomenda '{id_evento[:8]}...' não encontrado. Impossível apagar um bolo que já foi comido.")
        return False
    except Exception as e:
        st.error(f"🚫 Erro ao deletar a encomenda: {e}")
        return False


# --- INTERFACE STREAMLIT (UI) - TELA ÚNICA ---

st.set_page_config(layout="wide")
st.title("🎂 AGENDA DIGITAL DE ENCOMENDAS DE BOLO")

sheet = conectar_sheets()

if sheet is None:
    st.stop()


# === SEÇÃO 1: CRIAR NOVA ENCOMENDA ===
st.header("REGISTRAR NOVA ENCOMENDA")

with st.form("form_nova_encomenda", clear_on_submit=True):
    col1, col2 = st.columns(2)
    
    with col1:
        # Mapeado para 'titulo' (Nome do Cliente)
        nome_cliente = st.text_input("NOME DO CLIENTE (LGPD ATENÇÃO!):", max_chars=100) 
        
        # Mapeado para 'local' (Torre e APT)
        torre_apt = st.text_input("Torre e APT (ou Endereço):") 
        
        # Mapeado para 'data_evento'
        data_entrega = st.date_input("Data de Entrega:", date.today(), format="DD/MM/YYYY") 
    
    with col2:
        # Mapeado para 'prioridade'
        opcoes_prioridade = ["Média", "Alta", "Baixa"]
        prioridade = st.selectbox("Prioridade de Produção:", opcoes_prioridade)
        
        # Mapeado para 'hora_evento'
        hora_entrega = st.time_input("Horário Combinado:", time(9, 0)) 
        
        # Mapeado para 'status'
        opcoes_status_inicial = ['Pendente', 'Rascunho']
        status_inicial = st.selectbox("Status Inicial:", opcoes_status_inicial)
    
    # Mapeado para 'descricao' (Sabor do Bolo)
    sabor_bolo = st.text_area("SABOR do Bolo / DETALHES da Decoração:")
    
    submit_button = st.form_submit_button("Salvar Encomenda (CRIAÇÃO)")

    if submit_button:
        # Verificação mínima
        if nome_cliente and data_entrega and sabor_bolo: 
            dados_para_sheet = {
                'id_evento': str(uuid.uuid4()),
                'titulo': nome_cliente,
                'descricao': sabor_bolo,
                'data_evento': data_entrega.strftime('%Y-%m-%d'), 
                'hora_evento': hora_entrega.strftime('%H:%M'),
                'local': torre_apt,
                'prioridade': prioridade,
                'status': status_inicial
            }
            adicionar_evento(sheet, dados_para_sheet)
            
        else:
            st.warning("O Nome do Cliente, o Sabor e a Data são obrigatórios. Não complique a receita.")
            

st.divider() 

# === SEÇÃO 2: VISUALIZAR E GERENCIAR (R, U, D) ===

# Configuração de Auto-Refresh (A cada 20 segundos)
st_autorefresh(interval=20000, key="data_refresh_key")
st.info("🔄 **ATUALIZAÇÃO AUTOMÁTICA** (A cada 20 segundos). Assim você não perde a encomenda.")

st.header("📋 MINHAS ENCOMENDAS (O Calendário da Produção)")

df_encomendas = carregar_eventos(sheet) 

if df_encomendas.empty:
    st.info("SEM REGISTROS DE ENCOMENDAS. O forno está frio.")
else:
    
    df_display = df_encomendas.copy()
    
    # Formatação de Data/Hora para exibição
    if 'data_evento' in df_display.columns:
        df_display['data_evento'] = pd.to_datetime(df_display['data_evento'], errors='coerce').dt.strftime('%d/%m/%Y')
    
    # Renomeia as colunas internas para nomes de exibição amigáveis
    df_display.rename(columns={
        'id_evento': 'ID (Interno)', 
        'titulo': 'Nome', 
        'descricao': 'Sabor/Detalhes',
        'local': 'Torre e APT',
        'data_evento': 'Data',
        'hora_evento': 'Hora',
        'prioridade': 'Prioridade',
        'status': 'Status'
    }, inplace=True)
    
    # Exibe apenas as colunas relevantes na ordem certa
    colunas_finais = ['Data', 'Hora', 'Nome', 'Sabor/Detalhes', 'Torre e APT', 'Status', 'Prioridade', 'ID (Interno)']
    
    # Display principal (Filtrável por data)
    st.dataframe(
        df_display[colunas_finais].sort_values(by=['Data', 'Hora'], ascending=True), 
        use_container_width=True, 
        hide_index=True
    )
    
    st.divider()
    st.subheader("🛠️ Edição e Exclusão de Encomendas")

    if not df_encomendas.empty:
        
        eventos_atuais = df_encomendas['id_evento'].tolist()
        
        # Função para formatar o SelectBox (ID + Nome)
        def formatar_selecao(id_val):
            # Usamos as chaves internas para buscar no DataFrame
            nome_cliente = df_encomendas[df_encomendas['id_evento'] == id_val]['titulo'].iloc[0] 
            data_evento = df_encomendas[df_encomendas['id_evento'] == id_val]['data_evento'].iloc[0]
            
            return f"{data_evento} | {nome_cliente} ({id_val[:4]}...)"

        evento_selecionado_id = st.selectbox(
            "Selecione a Encomenda para Ação (Edição/Exclusão):",
            options=eventos_atuais,
            index=0 if eventos_atuais else None,
            format_func=formatar_selecao
        )
    
    if evento_selecionado_id:
        # Busca os dados do evento usando a chave interna ('titulo', 'descricao', etc.)
        evento_dados = df_encomendas[df_encomendas['id_evento'] == evento_selecionado_id].iloc[0]

        col_u, col_d = st.columns([3, 1])

        with col_u:
            st.markdown("##### Atualizar Encomenda Selecionada")
            with st.form("form_update_encomenda"):
                # Campos de Edição (Usando as chaves internas para os valores iniciais)
                novo_nome = st.text_input("NOME DO CLIENTE", value=evento_dados['titulo'])
                novo_sabor = st.text_area("Sabor/Detalhes", value=evento_dados['descricao'])

                col_data_hora, col_local_prioridade = st.columns(2)

                with col_data_hora:
                    # Converte string YYYY-MM-DD para objeto date para o date_input
                    novo_data = st.date_input(
                        "Data de Entrega", 
                        value=pd.to_datetime(evento_dados['data_evento']).date(),
                        format="DD/MM/YYYY"
                    )
                    # Converte HH:MM para objeto time para o time_input
                    novo_hora_str = evento_dados['hora_evento']
                    novo_hora = st.time_input("Horário Combinado", value=time(int(novo_hora_str[:2]), int(novo_hora_str[3:])))
                
                with col_local_prioridade:
                    novo_torre_apt = st.text_input("Torre e APT (ou Endereço)", value=evento_dados['local'])
                    opcoes_prioridade_update = ["Alta", "Média", "Baixa"]
                    novo_prioridade = st.selectbox("Prioridade de Produção", opcoes_prioridade_update, index=opcoes_prioridade_update.index(evento_dados['prioridade']))
                    opcoes_status_update = ['Pendente', 'Entregue', 'Cancelado']
                    novo_status = st.selectbox("Status", opcoes_status_update, index=opcoes_status_update.index(evento_dados['status']))

                update_button = st.form_submit_button("Salvar Atualizações da Encomenda (Update)")

                if update_button:
                    # Monta o dicionário de dados atualizados com as CHAVES INTERNAS
                    dados_atualizados = {
                        'id_evento': evento_selecionado_id, 
                        'titulo': novo_nome,
                        'descricao': novo_sabor,
                        'data_evento': novo_data.strftime('%Y-%m-%d'),
                        'hora_evento': novo_hora.strftime('%H:%M'),
                        'local': novo_torre_apt,
                        'prioridade': novo_prioridade,
                        'status': novo_status
                    }
                    atualizar_evento(sheet, evento_selecionado_id, dados_atualizados)
                        
        
        with col_d:
            st.markdown("##### Excluir Encomenda")
            st.warning(f"Excluindo a encomenda do cliente: **{evento_dados['titulo']}**")
            
            if st.button("🔴 EXCLUIR ENCOMENDA (Delete)", type="primary"):
                deletar_evento(sheet, evento_selecionado_id)

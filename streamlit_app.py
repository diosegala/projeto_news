# main_quatro.py - Interface baseada em formulário estruturado
import streamlit as st
from datetime import datetime
from src.auth import require_login_ui
from src.config import Config
from src.newsletter_generator import NewsletterGenerator



# Configuração da página
st.set_page_config(
    page_title="Gerador de Newsletter", 
    page_icon="📰", 
    layout="wide"
)



def main():
    try:
        # Exige login antes de mostrar o app
        if not require_login_ui():
            st.stop()
            
        st.title("📰 Gerador de Newsletter: Estrutura Personalizada")
        
        # Sidebar com informações
        display_sidebar_info()
        
        # Seleção do modelo
        chosen_model = st.sidebar.selectbox(
            "Modelo de IA",
            Config.MODEL_CHOICES,
            index=0
        )
        
        # Interface principal
        tab_structure, tab_generate = st.tabs(["🏗️ Estruturar Newsletter", "🚀 Gerar"])
        
        with tab_structure:
            handle_newsletter_structure()
            
        with tab_generate:
            handle_newsletter_generation(chosen_model)
            
    except Exception as e:
        st.error("Ocorreu um erro ao renderizar a página.")
        st.exception(e)

def display_sidebar_info():
    """Exibe informações de configuração na sidebar"""
    config = Config()
    st.sidebar.markdown("### 🔑 Status das APIs")
    st.sidebar.write("OpenAI:", "✅" if config.OPENAI_API_KEY else "❌")
    st.sidebar.write("Google (Gemini):", "✅" if config.GOOGLE_API_KEY else "❌")
    st.sidebar.write("Google Docs:", "✅" if config.sa_configured() else "❌")

def handle_newsletter_structure():
    """Interface para estruturar a newsletter"""
    st.subheader("🏗️ Estruture sua Newsletter")
    
    # Inicializar estado da sessão
    if 'newsletter_structure' not in st.session_state:
        st.session_state.newsletter_structure = {
            'lead_links': [],
            'sections': [],
            'agenda_links': []
        }
    
    # Seção de Abertura
    st.markdown("### 📰 Matéria de Abertura")
    
    col1, col2 = st.columns([3, 1])
    with col1:
        lead_links = st.text_area(
            "Links para a matéria de abertura (um por linha)",
            value='\n'.join(st.session_state.newsletter_structure['lead_links']),
            height=100,
            placeholder="https://exemplo.com/link1\nhttps://exemplo.com/link2"
        )
    
    with col2:
        st.metric("Links", len([l for l in lead_links.split('\n') if l.strip()]))
    
    # Atualizar links de abertura
    if lead_links:
        st.session_state.newsletter_structure['lead_links'] = [
            link.strip() for link in lead_links.split('\n') if link.strip()
        ]
    
    # Seções da Newsletter
    st.markdown("### 📊 Seções da Newsletter")
    
    # Controles para adicionar/remover seções
    col1, col2, col3 = st.columns([2, 2, 4])
    
    with col1:
        if st.button("➕ Adicionar Seção"):
            st.session_state.newsletter_structure['sections'].append({
                'name': '',
                'notes': [],
                'headlines': []
            })
            st.rerun()
    
    with col2:
        if st.button("➖ Remover Última") and st.session_state.newsletter_structure['sections']:
            st.session_state.newsletter_structure['sections'].pop()
            st.rerun()
    
    with col3:
        sections_count = len(st.session_state.newsletter_structure['sections'])
        st.metric("Total de Seções", sections_count)
    
    # Formulário para cada seção
    for i, section in enumerate(st.session_state.newsletter_structure['sections']):
        with st.expander(f"Seção {i+1}: {section.get('name', 'Sem nome')}", expanded=True):
            
            # Nome da seção
            section_name = st.selectbox(
                "Nome da seção",
                ["", "Vendas e Locação", "Construção e Incorporação", "Mundo", "Estamos de olho", "Outro"],
                index=0 if not section.get('name') else (
                    ["", "Vendas e Locação", "Construção e Incorporação", "Mundo", "Estamos de olho", "Outro"].index(section['name'])
                    if section['name'] in ["", "Vendas e Locação", "Construção e Incorporação", "Mundo", "Estamos de olho", "Outro"]
                    else 5
                ),
                key=f"section_name_{i}"
            )
            
            # Campo customizado se "Outro"
            if section_name == "Outro":
                section_name = st.text_input(
                    "Nome personalizado da seção",
                    value=section.get('name', ''),
                    key=f"custom_section_name_{i}"
                )
            
            st.session_state.newsletter_structure['sections'][i]['name'] = section_name
            
            if section_name:
                # Configurar notas individuais
                st.markdown("**📝 Notas desta seção**")
                
                # Inicializar estrutura de notas se não existir
                if 'individual_notes' not in st.session_state.newsletter_structure['sections'][i]:
                    st.session_state.newsletter_structure['sections'][i]['individual_notes'] = []
                
                # Controles para adicionar/remover notas
                col1, col2, col3 = st.columns([2, 2, 2])
                
                with col1:
                    if st.button("➕ Adicionar Nota", key=f"add_note_{i}"):
                        st.session_state.newsletter_structure['sections'][i]['individual_notes'].append({
                            'links': []
                        })
                        st.rerun()
                
                with col2:
                    notes_list = st.session_state.newsletter_structure['sections'][i]['individual_notes']
                    if st.button("➖ Remover Última", key=f"remove_note_{i}") and notes_list:
                        notes_list.pop()
                        st.rerun()
                
                with col3:
                    notes_count = len(st.session_state.newsletter_structure['sections'][i]['individual_notes'])
                    st.metric("Notas", notes_count)
                
                # Formulário para cada nota individual
                for j, note in enumerate(st.session_state.newsletter_structure['sections'][i]['individual_notes']):
                    with st.container():
                        st.markdown(f"**Nota {j+1}**")
                        
                        # Links para esta nota específica
                        note_links = st.text_area(
                            f"Links para a Nota {j+1} (um por linha)",
                            value='\n'.join(note.get('links', [])),
                            height=80,
                            key=f"note_links_{i}_{j}",
                            placeholder="https://exemplo.com/link1\nhttps://exemplo.com/link2"
                        )
                        
                        # Atualizar links desta nota
                        st.session_state.newsletter_structure['sections'][i]['individual_notes'][j]['links'] = [
                            link.strip() for link in note_links.split('\n') if link.strip()
                        ]
                        
                        # Mostrar contador de links desta nota
                        links_in_note = len([l for l in note_links.split('\n') if l.strip()])
                        if links_in_note > 0:
                            st.caption(f"📎 {links_in_note} link(s) nesta nota")
                        
                        if j < len(st.session_state.newsletter_structure['sections'][i]['individual_notes']) - 1:
                            st.divider()
                
                # Atualizar estrutura legada para compatibilidade
                all_notes_links = []
                for note in st.session_state.newsletter_structure['sections'][i]['individual_notes']:
                    all_notes_links.extend(note.get('links', []))
                st.session_state.newsletter_structure['sections'][i]['notes'] = all_notes_links
                
                # Configurar manchetes
                st.markdown("**📰 Manchetes desta seção**")
                
                col1, col2 = st.columns([3, 1])
                
                with col1:
                    headlines_text = st.text_area(
                        "Links para manchetes (um por linha)",
                        value='\n'.join(section.get('headlines', [])),
                        height=80,
                        key=f"headlines_{i}",
                        placeholder="https://exemplo.com/manchete1\nhttps://exemplo.com/manchete2"
                    )
                
                with col2:
                    headlines_count = len([l for l in headlines_text.split('\n') if l.strip()])
                    st.metric("Manchetes", headlines_count)
                
                # Atualizar manchetes
                st.session_state.newsletter_structure['sections'][i]['headlines'] = [
                    link.strip() for link in headlines_text.split('\n') if link.strip()
                ]
    
    # Seção Agenda
    st.markdown("### 📅 Agenda")
    
    col1, col2 = st.columns([3, 1])
    with col1:
        agenda_links = st.text_area(
            "Links para agenda (um por linha)",
            value='\n'.join(st.session_state.newsletter_structure['agenda_links']),
            height=80,
            placeholder="https://exemplo.com/evento1"
        )
    
    with col2:
        agenda_count = len([l for l in agenda_links.split('\n') if l.strip()])
        st.metric("Eventos", agenda_count)
    
    # Atualizar agenda
    if agenda_links:
        st.session_state.newsletter_structure['agenda_links'] = [
            link.strip() for link in agenda_links.split('\n') if link.strip()
        ]
    
    # Resumo da estrutura
    if st.session_state.newsletter_structure['lead_links'] or st.session_state.newsletter_structure['sections']:
        st.markdown("### 📋 Resumo da Estrutura")
        
        total_links = len(st.session_state.newsletter_structure['lead_links'])
        
        col1, col2, col3 = st.columns(3)
        
        with col1:
            st.metric("Links de Abertura", len(st.session_state.newsletter_structure['lead_links']))
        
        with col2:
            total_sections = len([s for s in st.session_state.newsletter_structure['sections'] if s.get('name')])
            st.metric("Seções Configuradas", total_sections)
        
        for section in st.session_state.newsletter_structure['sections']:
            if section.get('name'):
                total_links += len(section.get('notes', []))
                total_links += len(section.get('headlines', []))
        
        total_links += len(st.session_state.newsletter_structure['agenda_links'])
        
        with col3:
            st.metric("Total de Links", total_links)
        
        # Detalhes por seção com notas individuais
        for section in st.session_state.newsletter_structure['sections']:
            if section.get('name'):
                individual_notes = section.get('individual_notes', [])
                total_note_links = sum(len(note.get('links', [])) for note in individual_notes)
                headlines_count = len(section.get('headlines', []))
                st.write(f"**{section['name']}**: {len(individual_notes)} notas ({total_note_links} links), {headlines_count} manchetes")

def handle_newsletter_generation(chosen_model):
    """Interface para gerar a newsletter"""
    st.subheader("🚀 Gerar Newsletter")
    
    # Verificar se há estrutura definida
    if not st.session_state.get('newsletter_structure') or not st.session_state.newsletter_structure.get('lead_links'):
        st.warning("Configure a estrutura da newsletter na aba 'Estruturar Newsletter' primeiro.")
        return
    
    # Mostrar resumo da estrutura
    structure = st.session_state.newsletter_structure
    
    st.markdown("### 📊 Estrutura Atual")
    
    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("Abertura", len(structure['lead_links']))
    with col2:
        configured_sections = len([s for s in structure['sections'] if s.get('name')])
        st.metric("Seções", configured_sections)
    with col3:
        total_links = len(structure['lead_links']) + len(structure['agenda_links'])
        for s in structure['sections']:
            total_links += len(s.get('notes', [])) + len(s.get('headlines', []))
        st.metric("Total Links", total_links)
    
    # Instruções adicionais
    additional_instructions = st.text_area(
        "Instruções adicionais (opcional)",
        placeholder="Ex: Destaque dados econômicos, evite termos técnicos, foque em tendências...",
        height=100
    )
    
    # Botão para gerar
    if st.button("🚀 Gerar Newsletter Completa"):
        
        # Converter estrutura para formato compatível
        all_links, instructions = convert_structure_to_format(structure)
        
        # === NOVO: Preview numerado dos links globais (índice → URL)
        with st.expander("🔢 Mapa de Links (índice global → URL)"):
            st.text("\n".join([f"{i+1}: {u}" for i, u in enumerate(all_links)]))
        
        # === NOVO: Seletor explícito dos índices da Matéria de Abertura (override)
        default_lead_len = len(structure['lead_links'])
        default_lead_indices = list(range(1, default_lead_len + 1)) if default_lead_len > 0 else []
        lead_indices = st.multiselect(
            "📌 Matéria de Abertura — escolha os links pelo número (override)",
            options=list(range(1, len(all_links) + 1)),
            default=default_lead_indices,
            help="Esses índices têm prioridade sobre qualquer instrução textual."
        )
        
        # Combinar com instruções adicionais + override textual da abertura
        override_line = ""
        if lead_indices:
            if len(lead_indices) == 1:
                override_line = f"A Matéria de Abertura deve OBRIGATORIAMENTE usar o link {lead_indices[0]}."
            else:
                # formatação: 1, 2 e 3
                li = list(map(int, lead_indices))
                li.sort()
                if len(li) == 2:
                    override_line = f"A Matéria de Abertura deve OBRIGATORIAMENTE usar os links {li[0]} e {li[1]}."
                else:
                    override_line = (
                        "A Matéria de Abertura deve OBRIGATORIAMENTE usar os links "
                        + ", ".join(map(str, li[:-1])) + f" e {li[-1]}."
                    )
        
        final_instructions = " ".join(
            x for x in [override_line, instructions, additional_instructions] if x and x.strip()
        ).strip()
        
        # Mostrar o que será processado
        with st.expander("🔍 Preview do que será processado"):
            st.write(f"**Total de links**: {len(all_links)}")
            if lead_indices:
                st.write(f"**Override da Abertura (índices globais)**: {lead_indices}")
                # Mostrar URLs escolhidas para abertura
                chosen_urls = []
                for pos in lead_indices:
                    if 1 <= pos <= len(all_links):
                        chosen_urls.append(all_links[pos - 1])
                if chosen_urls:
                    st.text("URLs escolhidas para a Abertura:\n" + "\n".join(chosen_urls))
            st.write(f"**Instruções geradas**: {instructions}")
            if additional_instructions:
                st.write(f"**Instruções adicionais**: {additional_instructions}")
            if override_line:
                st.write(f"**Override aplicado**: {override_line}")
        
        # Gerar newsletter
        with st.spinner("Gerando newsletter..."):
            generator = NewsletterGenerator(chosen_model)
            # Sem alterar assinatura do gerador: passamos o override via texto (final_instructions)
            result = generator.generate_newsletter(
                all_links,
                final_instructions,
                ui_lead_indices=lead_indices  # <-- NOVO: passa índices 1-based
            )
            
            if result['success']:
                st.success("Newsletter gerada com sucesso!")
                
                url = result.get('doc_url')
                if url:
                    st.link_button("📂 Abrir no Google Docs", url, help="Abre a newsletter no Google Docs")
                    
                
                # Preview da newsletter
                with st.expander("📄 Preview da Newsletter"):
                    preview_text = result['content'][:2000]
                    st.text(preview_text + "..." if len(result['content']) > 2000 else preview_text)
                    
                # Estatísticas
                col1, col2 = st.columns(2)
                with col1:
                    st.metric("Links Processados", result.get('links_processed', 0))
                with col2:
                    st.metric("Caracteres Gerados", len(result['content']))
                    
            else:
                st.error(f"Erro ao gerar newsletter: {result['error']}")

def convert_structure_to_format(structure):
    """Converte estrutura do formulário para formato compatível com notas individuais"""
    
    all_links = []
    instructions_parts = []
    
    # Lead
    lead_links = structure['lead_links']
    all_links.extend(lead_links)
    
    # Mantemos a instrução padrão (compatível com parser atual);
    # o override explícito (quando usado) vai por fora nas final_instructions.
    if len(lead_links) == 2:
        instructions_parts.append("A matéria de abertura deve usar os dois primeiros links.")
    elif len(lead_links) > 0:
        instructions_parts.append(f"A matéria de abertura deve usar os primeiros {len(lead_links)} links.")
    
    link_counter = len(lead_links) + 1
    
    # Seções com notas individuais
    for section in structure['sections']:
        if not section.get('name'):
            continue
            
        section_name = section['name']
        individual_notes = section.get('individual_notes', [])
        headlines = section.get('headlines', [])
        
        if individual_notes:
            notes_count = len(individual_notes)
            section_instruction = f"O bloco {section_name} deve ter {notes_count} notas."
            
            # Instruções para cada nota individual
            note_names = ["primeira", "segunda", "terceira", "quarta", "quinta", "sexta", "sétima", "oitava", "nona", "décima"]
            
            for i, note in enumerate(individual_notes):
                note_links = note.get('links', [])
                if note_links:
                    # Adicionar links desta nota
                    all_links.extend(note_links)
                    
                    note_name = note_names[i] if i < len(note_names) else f"{i+1}ª"
                    
                    if len(note_links) == 1:
                        section_instruction += f" A {note_name} nota deve usar o link {link_counter}."
                        link_counter += 1
                    else:
                        # Múltiplos links para uma nota
                        link_range = list(range(link_counter, link_counter + len(note_links)))
                        if len(note_links) == 2:
                            section_instruction += f" A {note_name} nota deve usar os links {link_range[0]} e {link_range[1]}."
                        else:
                            links_str = ', '.join(map(str, link_range[:-1])) + f" e {link_range[-1]}"
                            section_instruction += f" A {note_name} nota deve usar os links {links_str}."
                        link_counter += len(note_links)
            
            # Manchetes
            if headlines:
                all_links.extend(headlines)
                headlines_links = [str(link_counter + i) for i in range(len(headlines))]
                if len(headlines) == 1:
                    section_instruction += f" Ao final do bloco, escreva a manchete do link {headlines_links[0]}."
                else:
                    section_instruction += f" Ao final do bloco, escreva as manchetes dos links {', '.join(headlines_links)}."
                link_counter += len(headlines)
            
            instructions_parts.append(section_instruction)
    
    # Agenda
    agenda_links = structure['agenda_links']
    if agenda_links:
        all_links.extend(agenda_links)
        if len(agenda_links) == 1:
            instructions_parts.append(f"O bloco Agenda deve usar o link {link_counter}.")
        else:
            agenda_range = list(range(link_counter, link_counter + len(agenda_links)))
            instructions_parts.append(f"O bloco Agenda deve usar os links {', '.join(map(str, agenda_range))}.")
    
    return all_links, " ".join(instructions_parts)

if __name__ == "__main__":
    main()

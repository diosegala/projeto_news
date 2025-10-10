# src/content_mapper.py

class ContentMapper:
    """Mapper corrigido para mapeamento preciso entre instruções e conteúdo"""
    
    def __init__(self, instructions, content_items):
        self.instructions = instructions
        self.content_items = content_items
        
        # Criar mapeamento número_do_link -> conteúdo
        self.content_by_link = self._create_mapping()
        
        # Verificar integridade do mapeamento
        self._verify_mapping()
    
    def _create_mapping(self):
        """Cria mapeamento link_number -> content"""
        mapping = {}
        
        # CRÍTICO: enumerate DEVE começar em 1, não 0
        # Link 1 = primeiro item, Link 2 = segundo item, etc.
        for i, item in enumerate(self.content_items, 1):
            mapping[i] = item
            
            # Debug dos primeiros e últimos links
            if i <= 3:
                print(f"[MAPEAMENTO] Link {i} => {item.get('url', 'NO URL')[:80]}")
            if i >= len(self.content_items) - 2:
                print(f"[MAPEAMENTO] Link {i} => {item.get('url', 'NO URL')[:80]}")
        
        return mapping
    
    def _verify_mapping(self):
        """Verifica se o mapeamento está correto"""
        total_items = len(self.content_items)
        total_mapped = len(self.content_by_link)
        
        print(f"[VERIFICAÇÃO] Total de itens: {total_items}")
        print(f"[VERIFICAÇÃO] Total mapeado: {total_mapped}")
        
        # Verificar se todos os números estão corretos
        expected_keys = list(range(1, total_items + 1))
        actual_keys = sorted(self.content_by_link.keys())
        
        if expected_keys != actual_keys:
            print(f"[ERRO] Chaves esperadas: {expected_keys[:5]}...{expected_keys[-5:]}")
            print(f"[ERRO] Chaves reais: {actual_keys[:5]}...{actual_keys[-5:]}")
    
    def get_lead_content(self):
        """Conteúdo da matéria de abertura com verificação detalhada"""
        content = []
        
        print(f"\n[GET_LEAD] Instruções dizem usar links: {self.instructions.lead_links}")
        
        for link_num in self.instructions.lead_links:
            print(f"[GET_LEAD] Buscando link número {link_num}")
            
            if link_num in self.content_by_link:
                item = self.content_by_link[link_num]
                url = item.get('url', 'NO URL')
                print(f"[GET_LEAD] Link {link_num} encontrado: {url[:80]}")
                content.append(item)
            else:
                print(f"[ERRO CRÍTICO] Link {link_num} NÃO EXISTE no mapeamento!")
                print(f"[ERRO CRÍTICO] Chaves disponíveis: {sorted(self.content_by_link.keys())[:10]}")
                
                # Tentativa de recuperação por acesso direto
                if link_num <= len(self.content_items):
                    fallback_item = self.content_items[link_num - 1]  # -1 porque lista começa em 0
                    print(f"[RECUPERAÇÃO] Usando acesso direto: {fallback_item.get('url', '')[:80]}")
                    content.append(fallback_item)
        
        return content
    
    def get_structured_sections(self):
        """Retorna seções estruturadas com debug"""
        result = {}
        
        for section in self.instructions.sections:
            print(f"\n[SECTION] Processando: {section.name}")
            
            section_data = {
                'notes': [],
                'headlines': []
            }
            
            # Processar notas
            for note_num, link_numbers in section.notes:
                note_content = []
                print(f"  [NOTA {note_num}] Links: {link_numbers}")
                
                for link_num in link_numbers:
                    if link_num in self.content_by_link:
                        item = self.content_by_link[link_num]
                        print(f"    Link {link_num}: {item.get('url', '')[:60]}")
                        note_content.append(item)
                    else:
                        print(f"    [ERRO] Link {link_num} não encontrado!")
                
                if note_content:
                    section_data['notes'].append({
                        'number': note_num,
                        'content': note_content
                    })
            
            # Processar manchetes
            for link_num in section.headlines:
                if link_num in self.content_by_link:
                    item = self.content_by_link[link_num]
                    print(f"  [MANCHETE] Link {link_num}: {item.get('url', '')[:60]}")
                    section_data['headlines'].append(item)
                else:
                    print(f"  [ERRO] Manchete link {link_num} não encontrado!")
            
            result[section.name] = section_data
        
        return result
    
    def get_agenda_content(self):
        """Conteúdo da agenda com debug"""
        if self.instructions.agenda_link:
            link_num = self.instructions.agenda_link
            print(f"\n[AGENDA] Buscando link {link_num}")
            
            if link_num in self.content_by_link:
                item = self.content_by_link[link_num]
                print(f"[AGENDA] Encontrado: {item.get('url', '')[:80]}")
                return item
            else:
                print(f"[ERRO] Link de agenda {link_num} não encontrado!")
                
                # Tentativa de recuperação
                if link_num <= len(self.content_items):
                    fallback_item = self.content_items[link_num - 1]
                    print(f"[RECUPERAÇÃO] Usando: {fallback_item.get('url', '')[:80]}")
                    return fallback_item
        
        return None
    
    # Métodos de compatibilidade com versão anterior
    def get_notes_by_section(self):
        """Compatibilidade com versão anterior - retorna notas por seção"""
        sections = {}
        structured = self.get_structured_sections()
        
        for section_name, section_data in structured.items():
            sections[section_name] = []
            for note in section_data['notes']:
                # Tupla (número_da_nota, lista_de_conteúdos)
                sections[section_name].append((note['number'], note['content']))
        
        return sections
    
    def get_headlines_by_section(self):
        """Compatibilidade com versão anterior - retorna manchetes por seção"""
        sections = {}
        structured = self.get_structured_sections()
        
        for section_name, section_data in structured.items():
            if section_data['headlines']:
                sections[section_name] = section_data['headlines']
        
        return sections
    
    def debug_full_mapping(self):
        """Método para debug completo do mapeamento"""
        print("\n" + "="*60)
        print("DEBUG COMPLETO DO MAPEAMENTO")
        print("="*60)
        
        print(f"\nTotal de links recebidos: {len(self.content_items)}")
        print(f"Total de links mapeados: {len(self.content_by_link)}")
        
        print("\nPRIMEIROS 5 LINKS:")
        for i in range(1, min(6, len(self.content_items) + 1)):
            if i in self.content_by_link:
                url = self.content_by_link[i].get('url', 'NO URL')
                print(f"  Link {i}: {url[:100]}")
        
        print("\nÚLTIMOS 5 LINKS:")
        start = max(1, len(self.content_items) - 4)
        for i in range(start, len(self.content_items) + 1):
            if i in self.content_by_link:
                url = self.content_by_link[i].get('url', 'NO URL')
                print(f"  Link {i}: {url[:100]}")
        
        print("\nMAPEAMENTO PARA LEAD:")
        lead_content = self.get_lead_content()
        for i, item in enumerate(lead_content, 1):
            print(f"  Lead item {i}: {item.get('url', 'NO URL')[:100]}")
        
        print("="*60)
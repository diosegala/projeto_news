# src/instruction_parser.py
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import List, Optional

# ============================================================
# MODELOS DE SAÍDA (objetos com atributos estáveis)
# ============================================================

@dataclass
class NoteRequirement:  # [NEW]
    note_number: int
    links: List[int] = field(default_factory=list)

@dataclass
class SectionRequirement:  # [NEW]
    name: str
    notes: List[NoteRequirement] = field(default_factory=list)
    headlines: List[int] = field(default_factory=list)

@dataclass
class EnhancedInstructions:  # [NEW]
    lead_links: List[int] = field(default_factory=list)
    sections: List[SectionRequirement] = field(default_factory=list)
    agenda_links: List[int] = field(default_factory=list)


# ============================================================
# PARSER PRINCIPAL
# ============================================================

class InstructionParser:
    """
    Parser tolerante às instruções em Português geradas pela UI.
    Reconhece:
      - "A matéria de abertura deve usar os dois primeiros links."
      - "A matéria de abertura deve usar os primeiros N links."
      - "A Matéria de Abertura deve OBRIGATORIAMENTE usar o link 3."
      - "A Matéria de Abertura deve OBRIGATORIAMENTE usar os links 3 e 4."
      - "O bloco {Seção} deve ter {N} notas."
      - "A {primeira|segunda|...} nota deve usar o link X."
      - "A {primeira|...} nota deve usar os links X, Y e Z."
      - "Ao final do bloco, escreva a(s) manchete(s) do(s) link(s) X, Y e Z."
      - "O bloco Agenda deve usar o(s) link(s) X, Y, Z."
    Todas as listas de índices são 1-based, seguindo a UI.
    """

    # --------------------------------------------------------
    # Mapas auxiliares (ordinais por extenso → número)
    # --------------------------------------------------------
    ORDINAIS = {  # [NEW]
        "primeira": 1, "segunda": 2, "terceira": 3, "quarta": 4, "quinta": 5,
        "sexta": 6, "sétima": 7, "setima": 7, "oitava": 8, "nona": 9, "décima": 10, "decima": 10
    }

    # --------------------------------------------------------
    # API pública
    # --------------------------------------------------------
    def parse(self, text: str) -> EnhancedInstructions:
        if not isinstance(text, str):
            return EnhancedInstructions()

        # Normaliza espaços e caixa
        original = text
        t = " ".join(text.replace("\n", " ").split())

        # 1) Abertura (lead)
        lead = self._parse_lead(t)

        # 2) Seções (blocos), notas e manchetes
        sections = self._parse_sections_and_notes(t)

        # 3) Agenda
        agenda = self._parse_agenda(t)

        return EnhancedInstructions(lead_links=lead, sections=sections, agenda_links=agenda)

    # --------------------------------------------------------
    # LEAD
    # --------------------------------------------------------
    def _parse_lead(self, t: str) -> List[int]:
        lead: List[int] = []

        # a) Overrides explícitos da UI (mais fortes)
        #    "A Matéria de Abertura deve OBRIGATORIAMENTE usar o link 3."
        m = re.search(r"Matéria de Abertura.*?OBRIGATORIAMENTE.*?usar o link (\d+)", t, flags=re.IGNORECASE)
        if m:
            return [int(m.group(1))]

        m = re.search(r"Matéria de Abertura.*?OBRIGATORIAMENTE.*?usar os links ([\d,\se]+)\.", t, flags=re.IGNORECASE)
        if m:
            return self._parse_index_list(m.group(1))

        # b) Frases da UI base
        #    "A matéria de abertura deve usar os dois primeiros links."
        if re.search(r"matéria de abertura.*?dois primeiros links", t, flags=re.IGNORECASE):
            return [1, 2]

        #    "A matéria de abertura deve usar os primeiros N links."
        m = re.search(r"matéria de abertura.*?os primeiros (\d+) links", t, flags=re.IGNORECASE)
        if m:
            n = int(m.group(1))
            return list(range(1, n + 1))

        return lead

    # --------------------------------------------------------
    # SEÇÕES, NOTAS, MANCHETES
    # --------------------------------------------------------
    def _parse_sections_and_notes(self, t: str) -> List[SectionRequirement]:
        sections: List[SectionRequirement] = []

        # Dividimos por sentenças para acompanhar "O bloco X deve ter N notas." e suas notas subsequentes
        sentences = re.split(r"(?<=[\.\!\?])\s+", t)

        current_section: Optional[SectionRequirement] = None
        note_counter_expected: Optional[int] = None  # vindo de "deve ter N notas"

        for sent in sentences:
            s = sent.strip()
            if not s:
                continue

            # 1) Começo de uma nova seção
            m = re.search(r"O bloco\s+(.+?)\s+deve ter\s+(\d+)\s+notas", s, flags=re.IGNORECASE)
            if m:
                # Fecha seção anterior, se houver
                if current_section is not None:
                    sections.append(current_section)

                name = m.group(1).strip()
                note_counter_expected = int(m.group(2))
                current_section = SectionRequirement(name=name, notes=[], headlines=[])
                continue

            # 2) Manchetes da seção corrente
            #    "Ao final do bloco, escreva a(s) manchete(s) do(s) link(s) 10, 11, 12."
            if current_section:
                mh = re.search(r"Ao final do bloco.*?manchete[s]?\s+do[s]?\s+link[s]?\s+([^\.\!]+)", s, flags=re.IGNORECASE)
                if mh:
                    current_section.headlines = self._parse_index_list(mh.group(1))
                    continue

            # 3) Notas da seção corrente
            if current_section:
                # "A primeira nota deve usar o link X."
                m1 = re.search(r"A\s+([A-Za-zçáéíóúâêôãõàäëïöü\-]+)\s+nota\s+deve usar o link\s+(\d+)", s, flags=re.IGNORECASE)
                if m1:
                    ordinal = m1.group(1).lower()
                    nn = self.ORDINAIS.get(ordinal, None)
                    if nn is None:
                        # Se não reconhecemos o ordinal textual, inferimos por comprimento+1
                        nn = len(current_section.notes) + 1
                    idx = int(m1.group(2))
                    current_section.notes.append(NoteRequirement(note_number=nn, links=[idx]))
                    continue

                # "A segunda nota deve usar os links 5 e 6." / "... 5, 6 e 7"
                m2 = re.search(r"A\s+([A-Za-zçáéíóúâêôãõàäëïöü\-]+)\s+nota\s+deve usar os links\s+([^\.\!]+)", s, flags=re.IGNORECASE)
                if m2:
                    ordinal = m2.group(1).lower()
                    nn = self.ORDINAIS.get(ordinal, None)
                    if nn is None:
                        nn = len(current_section.notes) + 1
                    lst = self._parse_index_list(m2.group(2))
                    current_section.notes.append(NoteRequirement(note_number=nn, links=lst))
                    continue

                # fallback: "A nota 3 deve usar os links 7 e 8."
                m3 = re.search(r"A\s+nota\s+(\d+)\s+deve usar os links\s+([^\.\!]+)", s, flags=re.IGNORECASE)
                if m3:
                    nn = int(m3.group(1))
                    lst = self._parse_index_list(m3.group(2))
                    current_section.notes.append(NoteRequirement(note_number=nn, links=lst))
                    continue

                m4 = re.search(r"A\s+nota\s+(\d+)\s+deve usar o link\s+(\d+)", s, flags=re.IGNORECASE)
                if m4:
                    nn = int(m4.group(1))
                    idx = int(m4.group(2))
                    current_section.notes.append(NoteRequirement(note_number=nn, links=[idx]))
                    continue

        # Fecha última seção, se aberta
        if current_section is not None:
            sections.append(current_section)

        # Opcional: se "deve ter N notas" foi informado, podemos ordenar por note_number
        for sec in sections:
            if sec.notes:
                sec.notes.sort(key=lambda x: x.note_number)

        return sections

    # --------------------------------------------------------
    # AGENDA
    # --------------------------------------------------------
    def _parse_agenda(self, t: str) -> List[int]:
        # "O bloco Agenda deve usar o link X."
        m = re.search(r"O bloco\s+Agenda\s+deve usar o link\s+(\d+)", t, flags=re.IGNORECASE)
        if m:
            return [int(m.group(1))]

        # "O bloco Agenda deve usar os links X, Y e Z."
        m = re.search(r"O bloco\s+Agenda\s+deve usar os links\s+([^\.\!]+)", t, flags=re.IGNORECASE)
        if m:
            return self._parse_index_list(m.group(1))

        return []

    # --------------------------------------------------------
    # UTIL
    # --------------------------------------------------------
    def _parse_index_list(self, span: str) -> List[int]:
        """
        Converte "1, 2 e 3" / "5 e 6" / "10, 11" em [1,2,3] / [5,6] / [10,11].
        Remove espaços e aceita vírgula e 'e' como separadores.
        """
        if not span:
            return []
        # troca " e " por vírgula, remove duplicados preservando ordem
        s = re.sub(r"\se\s", ",", span.strip(), flags=re.IGNORECASE)
        parts = [p.strip() for p in s.split(",") if p.strip()]
        out: List[int] = []
        for p in parts:
            if p.isdigit():
                v = int(p)
                if v not in out:
                    out.append(v)
        return out

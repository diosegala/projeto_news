# src/improved_ai_service.py
from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

import textwrap

# --- HOTFIX: normalizador de nota (suporta tupla ou objeto) ---
def _note_parts(n):
    if isinstance(n, tuple):
        try:
            nn, ll = n[0], n[1]
        except Exception:
            return None, []
    else:
        nn = getattr(n, "note_number", None)
        ll = getattr(n, "links", [])
    try:
        nn = int(nn) if nn is not None else None
    except Exception:
        nn = None
    if isinstance(ll, (list, tuple)):
        ll = [int(x) for x in ll if str(x).isdigit()]
    else:
        ll = []
    return nn, ll
# --------------------------------------------------------------

# streamlit é opcional aqui (para debug); se não existir, seguimos com logging
try:
    import streamlit as st  # type: ignore
    HAS_ST = True
except Exception:
    HAS_ST = False

from .config import Config
from .instruction_parser import InstructionParser
from .content_mapper import ContentMapper  # mantemos o import para compatibilidade

logger = logging.getLogger(__name__)
if not logger.handlers:
    logging.basicConfig(level=logging.INFO)

# =============================================================================
# Helpers internos
# =============================================================================

@dataclass
class _NoteNorm:
    note_number: int
    links: List[int]

def _norm_note(n: Any) -> _NoteNorm:
    """Normaliza uma nota vinda do parser (tupla ou objeto)."""
    if isinstance(n, tuple):
        if len(n) >= 2:
            nn = int(n[0])
            ll = list(map(int, n[1] if isinstance(n[1], (list, tuple)) else []))
            return _NoteNorm(nn, ll)
        return _NoteNorm(-1, [])
    nn = getattr(n, "note_number", None)
    ll = getattr(n, "links", None)
    try:
        nn = int(nn)
    except Exception:
        nn = -1
    if isinstance(ll, (list, tuple)):
        ll = list(map(int, ll))
    else:
        ll = []
    return _NoteNorm(nn, ll)

def _safe_get(obj: Any, attr: str, default: Any = None) -> Any:
    try:
        return getattr(obj, attr, default)
    except Exception:
        return default

def _excerpt(text: Optional[str], limit: int) -> str:
    if not text:
        return ""
    t = text.strip().replace("\r", " ")
    if len(t) <= limit:
        return t
    return t[:limit] + " [...]"

def _maybe_st_text(s: str) -> None:
    if HAS_ST:
        try:
            st.text(s)
            return
        except Exception:
            pass
    logger.info(s)

# =============================================================================
# Serviço principal
# =============================================================================

class ImprovedAIService:
    def __init__(self, model_choice: str):
        self.config = Config()
        self.model_choice = model_choice
        self.parser = InstructionParser()
        # NÃO instanciar ContentMapper aqui; ele precisa de args
        self.mapper: Optional[ContentMapper] = None

        # limites de contexto
        self.MAX_CHARS_PER_SOURCE = getattr(self.config, "MAX_CHARS_PER_SOURCE", 2000)
        self.SYSTEM_TONE = getattr(self.config, "SYSTEM_TONE",
                                   """
                                   Você é editor sênior do mercado imobiliário. 
                                   Priorize indicadores e números sempre que existirem nas fontes; quantifique variações (%, valores, moeda, período) e feche cada item com (Fonte X).
                                   """)
                                #    "Você é um editor sênior e curador de notícias do mercado imobiliário." \
                                #    "Priorize indicadores e números sempre que existirem nas fontes; quantifique variações (%, valores, moeda, período) e feche cada item com (Fonte X).")

        # Clients (carregados sob demanda)
        self._openai_client = None
        self._gemini_client = None

    # -------------------------------------------------------------------------
    # API pública usada pelo NewsletterGenerator
    # -------------------------------------------------------------------------
    def generate_newsletter(
        self,
        content_items: List[Dict[str, Any]],
        user_instructions: str,
        style_guide: str,
        ui_lead_indices: Optional[List[int]] = None
    ) -> Dict[str, Any]:
        """
        Gera o texto da newsletter a partir de:
          - content_items: lista alinhada 1-based ('idx', 'url', 'title', 'text', ...)
          - user_instructions: instruções textuais com índices globais 1-based
          - style_guide: guia de estilo (pode ser string vazia)
          - ui_lead_indices: override 1-based para a matéria de abertura
        Retorna dict com 'content' (texto final).
        """
        # 1) Sanidade de índices 1-based
        idx_map = self._build_index_map(content_items)  # {1: item1, 2: item2, ...}
        urls_map = {i: it.get("url") for i, it in idx_map.items()}

        # 2) Parse das instruções
        try:
            parsed = self.parser.parse(user_instructions)
        except Exception as e:
            self._debug_parser_failure(user_instructions, e)
            parsed = None

        # 3) Constrói plano (lead/sections/headlines/agenda)
        plan = self._build_plan(parsed, ui_lead_indices)

        # 4) DEBUG do mapeamento por seção/nota → índices → URLs
        self._debug_plan_mapping(plan, urls_map)

        # 5) Monta prompt com “barreiras” por nota e com os trechos das fontes
        prompt = self._build_constrained_prompt(plan, content_items, style_guide)

        # 6) Chama o LLM escolhido
        content = self._call_llm(prompt)

        return {"content": content or ""}

    # -------------------------------------------------------------------------
    # Etapas internas
    # -------------------------------------------------------------------------
    def _build_index_map(self, items: List[Dict[str, Any]]) -> Dict[int, Dict[str, Any]]:
        out: Dict[int, Dict[str, Any]] = {}
        for it in items or []:
            try:
                pos = it.get("idx") or it.get("position") or it.get("pos")
                pos = int(pos)
                if pos >= 1:
                    out[pos] = it
            except Exception:
                continue
        return out

    def _debug_parser_failure(self, instructions: str, error: Exception) -> None:
        msg = f"[DEBUG] parser falhou: {error}"
        _maybe_st_text(msg)
        logger.debug("Instruções originais:\n%s", instructions)

    def _build_plan(self, parsed: Any, ui_lead_indices: Optional[List[int]]) -> Dict[str, Any]:
        """
        Constrói um plano tolerante:
          {
            'lead': [índices 1-based],
            'sections': [
                {'name': 'Vendas e Locação', 'notes': [ {'note_number':1, 'links':[5,6]}, ... ],
                 'headlines': [idx, idx, ...] },
                ...
            ],
            'agenda': [idx, idx, ...]
          }
        """
        # Lead
        lead = []
        if parsed is not None:
            lead = _safe_get(parsed, "lead_links", []) or []
        if ui_lead_indices:  # override da UI
            lead = list(map(int, ui_lead_indices))

        # Sections
        sections_out: List[Dict[str, Any]] = []
        if parsed is not None:
            sections = _safe_get(parsed, "sections", []) or []
            for s in sections:
                name = _safe_get(s, "name", "") or _safe_get(s, "section_name", "") or ""
                raw_notes = _safe_get(s, "notes", []) or []
                notes_norm = []
                for n in raw_notes:
                    nn = _norm_note(n)
                    if nn.note_number >= 1:
                        notes_norm.append({"note_number": nn.note_number, "links": nn.links})
                headlines = _safe_get(s, "headlines", [])
                if not isinstance(headlines, (list, tuple)):
                    headlines = []
                headlines = list(map(int, headlines))
                sections_out.append({
                    "name": name or "Sem nome",
                    "notes": notes_norm,
                    "headlines": headlines
                })

        # Agenda
        agenda = []
        if parsed is not None:
            agenda = _safe_get(parsed, "agenda_links", None)
            if agenda is None:
                agenda = _safe_get(parsed, "agenda", [])
            if not isinstance(agenda, (list, tuple)):
                agenda = []
            agenda = list(map(int, agenda))

        return {"lead": lead, "sections": sections_out, "agenda": agenda}

    def _debug_plan_mapping(self, plan: Dict[str, Any], urls_map: Dict[int, str]) -> None:
        try:
            lines: List[str] = []
            if plan.get("lead"):
                lead_idxs = plan["lead"]
                lead_urls = [urls_map.get(i, "") for i in lead_idxs]
                lines.append("=== MAPEAMENTO: ABERTURA ===")
                lines.append(f"Índices: {lead_idxs}")
                lines.append("URLs: " + "; ".join(lead_urls))
                lines.append("")

            sections = plan.get("sections", [])
            for s in sections:
                lines.append(f"=== SEÇÃO: {s.get('name','(sem nome)')} ===")
                for n in s.get("notes", []):
                    idxs = n.get("links", [])
                    urls = [urls_map.get(i, "") for i in idxs]
                    lines.append(f"Nota {n.get('note_number')}: idx {idxs} → URLs: {urls}")
                if s.get("headlines"):
                    h_idxs = s["headlines"]
                    h_urls = [urls_map.get(i, "") for i in h_idxs]
                    lines.append(f"Manchetes: idx {h_idxs} → URLs: {h_urls}")
                lines.append("")

            if plan.get("agenda"):
                a_idxs = plan["agenda"]
                a_urls = [urls_map.get(i, "") for i in a_idxs]
                lines.append("=== AGENDA ===")
                lines.append(f"Índices: {a_idxs}")
                lines.append("URLs: " + "; ".join(a_urls))

            if lines:
                _maybe_st_text("\n".join(lines))
        except Exception as e:
            logger.warning("Falha ao imprimir mapping de DEBUG: %s", e)

    def _build_constrained_prompt(
        self,
        plan: Dict[str, Any],
        items: List[Dict[str, Any]],
        style_guide: str
    ) -> str:
        """Gera prompt com “barreiras” por nota e anexos com trechos por índice (1-based)."""
        by_idx: Dict[int, Dict[str, Any]] = {int(it.get("idx")): it for it in items if it.get("idx")}

        def source_block(idx: int) -> str:
            it = by_idx.get(idx, {})
            url = it.get("url", "")
            title = it.get("title") or ""
            text = _excerpt(it.get("text"), self.MAX_CHARS_PER_SOURCE)
            pretty = f"[{idx}] {title} — {url}".strip()
            return f"{pretty}\n{text}".strip()

        header = textwrap.dedent(f"""
        SISTEMA: {self.SYSTEM_TONE}

        Você vai escrever uma newsletter **nos moldes fornecidos**, seguindo ESTRITAMENTE as fontes permitidas por bloco.
        • Nunca use conteúdo de fontes não permitidas para aquele bloco/nota.
        • Não misture fontes entre notas.
        • Cite a(s) fonte(s) no final de cada nota entre parênteses, como (Fonte X), usando o veículo/nome do site da URL correspondente.
        • Mantenha o tom e o estilo do guia de estilo (se houver).

        GUIA DE ESTILO (resumo):
        {style_guide[:1200]}
        """).strip()

        body_lines: List[str] = []

        if plan.get("lead"):
            lead_idxs: List[int] = list(map(int, plan["lead"]))
            body_lines.append("\n[ABERTURA — USE APENAS ESTES ÍNDICES] " + ", ".join(map(str, lead_idxs)))
            body_lines.append("Instrução: Escreva a matéria de abertura (tese + contexto + impactos + fechamento com fontes).")
            body_lines.append("Fontes permitidas (trechos):")
            for i in lead_idxs:
                body_lines.append(source_block(i))

        for s in plan.get("sections", []):
            sec_name = s.get("name", "Seção")
            body_lines.append(f"\n[SEÇÃO: {sec_name}]")
            for n in s.get("notes", []):
                nn = int(n.get("note_number", -1))
                idxs: List[int] = list(map(int, n.get("links", [])))
                if nn < 1 or not idxs:
                    continue
                body_lines.append(f"[NOTA {nn} — USE APENAS ESTES ÍNDICES] " + ", ".join(map(str, idxs)))
                body_lines.append("Fontes permitidas (trechos):")
                for i in idxs:
                    body_lines.append(source_block(i))
                body_lines.append("Instrução: Escreva 1–3 parágrafos (fato + implicação prática para o mercado), fechando com fontes.")

            headlines = s.get("headlines", [])
            if headlines:
                h_idxs: List[int] = list(map(int, headlines))
                body_lines.append(f"[MANCHETES — USE APENAS ESTES ÍNDICES] " + ", ".join(map(str, h_idxs)))
                body_lines.append("Instrução: Liste manchetes telegráficas (1 linha cada), fechando com fonte entre parênteses.")
                body_lines.append("Fontes permitidas (trechos):")
                for i in h_idxs:
                    body_lines.append(source_block(i))

        if plan.get("agenda"):
            a_idxs: List[int] = list(map(int, plan["agenda"]))
            body_lines.append("\n[AGENDA — USE APENAS ESTES ÍNDICES] " + ", ".join(map(str, a_idxs)))
            body_lines.append("Instrução: Escreva itens de agenda claros e objetivos, fechando com a fonte.")
            body_lines.append("Fontes permitidas (trechos):")
            for i in a_idxs:
                body_lines.append(source_block(i))

        footer = textwrap.dedent("""
        FORMATAÇÃO ESPERADA:
        • Título da ABERTURA em forma de tese.
        • ABERTURA: 4–8 parágrafos; feche com as fontes entre parênteses.
        • Para cada SEÇÃO, escreva as NOTAS como parágrafos, e liste MANCHE TES (se houver) como bullets curtos.
        • Ao final de CADA nota/manchete, inclua as fontes usadas entre parênteses (ex.: (Valor, O Globo)).
        • Não invente links. Use apenas os índices e trechos fornecidos para cada bloco.
        """).strip()

        prompt = header + "\n\n" + "\n".join(body_lines) + "\n\n" + footer
        return prompt

    # -------------------------------------------------------------------------
    # Chamada ao LLM (Gemini/OpenAI), escolhendo com base nas chaves disponíveis
    # -------------------------------------------------------------------------
    def _call_llm(self, prompt: str) -> str:
        """
        Normaliza o modelo selecionado e chama o provedor correspondente.
        Em caso de falha, retorna mensagem clara do erro (sem cair no genérico).
        """
        raw = self.model_choice or ""
        provider = ""
        model_clean = raw

        # Normalização do "provider: model"
        if ":" in raw:
            prov, mod = raw.split(":", 1)
            provider = prov.strip().lower()
            model_clean = mod.strip()
        else:
            lower = raw.lower()
            if "gemini" in lower or "google" in lower:
                provider = "gemini"
            elif "gpt" in lower or "openai" in lower:
                provider = "openai"

        # DEBUG explícito (aparece no Streamlit; se não houver Streamlit, vai para log)
        _maybe_st_text(
            f"[LLM DEBUG] provider='{provider or 'auto'}' | model='{model_clean}' | "
            f"OPENAI_KEY={'set' if bool(self.config.OPENAI_API_KEY) else 'missing'} | "
            f"GOOGLE_KEY={'set' if bool(self.config.GOOGLE_API_KEY) else 'missing'}"
        )

        # Se o provider veio explícito da UI, honrar e, se falhar, retornar o erro específico
        if provider == "gemini":
            if not self.config.GOOGLE_API_KEY:
                return "[ERRO] Google/Gemini selecionado, mas GOOGLE_API_KEY não está configurada."
            try:
                return self._call_gemini(prompt, model_name=model_clean or "gemini-1.5-pro")
            except Exception as e:
                return f"[ERRO] Falha ao chamar Gemini ({model_clean or 'gemini-1.5-pro'}): {e}"

        if provider == "openai":
            if not self.config.OPENAI_API_KEY:
                return "[ERRO] OpenAI selecionado, mas OPENAI_API_KEY não está configurada."
            try:
                return self._call_openai(prompt, model_name=model_clean or "gpt-4o-mini")
            except Exception as e:
                return f"[ERRO] Falha ao chamar OpenAI ({model_clean or 'gpt-4o-mini'}): {e}"

        # Provider não inferido: tentar os disponíveis e acumular erros
        errors = []

        # Tenta OpenAI se chave existir
        if self.config.OPENAI_API_KEY:
            try:
                return self._call_openai(
                    prompt,
                    model_name=(model_clean if "gpt" in model_clean.lower() else "gpt-4o-mini")
                )
            except Exception as e:
                errors.append(f"OpenAI({model_clean or 'gpt-4o-mini'}): {e}")

        # Tenta Gemini se chave existir
        if self.config.GOOGLE_API_KEY:
            try:
                return self._call_gemini(
                    prompt,
                    model_name=(model_clean if "gemini" in model_clean.lower() else "gemini-1.5-pro")
                )
            except Exception as e:
                errors.append(f"Gemini({model_clean or 'gemini-1.5-pro'}): {e}")

        # Se chegamos aqui e havia chaves, mas ambos falharam, exponha os erros reais
        if errors:
            return "[ERRO] Falhas ao chamar LLM: " + " | ".join(errors)

        # Sem nenhuma chave mesmo
        return ("[ERRO] Nenhum provedor de LLM disponível/configurado. "
                "Verifique GOOGLE_API_KEY/OPENAI_API_KEY no Config e o nome do modelo.")


    # ---- Provedores ----------------------------------------------------------
    def _call_gemini(self, prompt: str, model_name: str) -> str:
        """Chamada simples ao Gemini (Google Generative AI)."""
        if self._gemini_client is None:
            try:
                import google.generativeai as genai  # type: ignore
                genai.configure(api_key=self.config.GOOGLE_API_KEY)
                self._gemini_client = genai
            except Exception as e:
                raise RuntimeError(f"google-generativeai não disponível: {e}")

        genai = self._gemini_client
        model = genai.GenerativeModel(model_name)
        resp = model.generate_content(prompt)
        try:
            if hasattr(resp, "text"):
                return resp.text or ""
            if hasattr(resp, "candidates") and resp.candidates:
                return resp.candidates[0].content.parts[0].text
        except Exception:
            pass
        return str(resp or "")

    def _call_openai(self, prompt: str, model_name: str) -> str:
        """
        Chama OpenAI, suportando tanto o SDK novo (openai>=1.*) quanto o antigo.
        """
        # Tentativa com SDK novo
        try:
            from openai import OpenAI  # type: ignore
            if self._openai_client is None:
                self._openai_client = OpenAI(api_key=self.config.OPENAI_API_KEY)
            client = self._openai_client
            chat = client.chat.completions.create(
                model=model_name,
                messages=[
                    {"role": "system", "content": self.SYSTEM_TONE},
                    {"role": "user", "content": prompt}
                ],
                temperature=getattr(self.config, "TEMPERATURE", 0.3),
                max_tokens=getattr(self.config, "MAX_TOKENS", 3500),
            )
            return (chat.choices[0].message.content or "").strip()
        except Exception as e_new:
            # Fallback para SDK antigo
            try:
                import openai  # type: ignore
                openai.api_key = self.config.OPENAI_API_KEY
                chat = openai.ChatCompletion.create(
                    model=model_name,
                    messages=[
                        {"role": "system", "content": self.SYSTEM_TONE},
                        {"role": "user", "content": prompt}
                    ],
                    temperature=getattr(self.config, "TEMPERATURE", 0.3),
                    max_tokens=getattr(self.config, "MAX_TOKENS", 3500),
                )
                return (chat["choices"][0]["message"]["content"] or "").strip()
            except Exception as e_old:
                raise RuntimeError(f"SDK OpenAI falhou (novo: {e_new}) (antigo: {e_old})")

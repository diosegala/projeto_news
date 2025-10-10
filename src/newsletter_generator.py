# src/newsletter_generator.py

from typing import List, Dict, Any, Optional
from datetime import datetime
import logging

import streamlit as st

from .content_processor import ContentProcessor
from .improved_ai_service import ImprovedAIService
from .google_docs_service import GoogleDocsService
from .config import Config

logger = logging.getLogger(__name__)
if not logger.handlers:
    logging.basicConfig(level=logging.INFO)


class NewsletterGenerator:
    def __init__(self, model_choice: str):
        self.config = Config()
        self.content_processor = ContentProcessor()
        self.ai_service = ImprovedAIService(model_choice)
        self.docs_service = GoogleDocsService()

    
    def _validate_links(self, links: List[str]) -> List[str]:
        """
        Limpa e valida *sem* alterar a ordem e *sem* remover duplicados.
        >>> REGRA: NUNCA deduplicar nem “encurtar” a lista, para manter os índices 1-based.

        Retorna uma lista do MESMO tamanho, contendo strings (possivelmente vazias se a entrada for inválida).
        """
        # [CHANGED] (antes havia lógica de 'seen' com deduplicação; removido)
        cleaned: List[str] = []
        for raw in (links or []):
            if not isinstance(raw, str):
                logger.debug("Link não-string encontrado; preservando posição com string vazia.")
                cleaned.append("")  # preserva posição
                continue
            url = raw.strip()
            if not url:
                cleaned.append("")  # preserva posição vazia
                continue
            if not (url.startswith("http://") or url.startswith("https://")):
                # Mantemos mesmo assim para não deslocar índices; apenas registramos aviso.
                logger.warning("URL sem http/https; mantendo para preservar índice: %s", url)
                cleaned.append(url)
                continue
            cleaned.append(url)

        # [NEW] Aviso não-destrutivo sobre duplicados (sem remover)
        self._warn_duplicates(cleaned)

        return cleaned

    # [NEW]
    def _warn_duplicates(self, links: List[str]) -> None:
        """Loga posições duplicadas apenas para diagnóstico (não remove)."""
        seen: Dict[str, List[int]] = {}
        for i, u in enumerate(links, start=1):
            if not u:
                continue
            seen.setdefault(u, []).append(i)
        dups = {u: idxs for u, idxs in seen.items() if len(idxs) > 1}
        if dups:
            logger.warning("URLs duplicadas (posições preservadas): %s", dups)

    # [NEW]
    def _ensure_alignment(self, links: List[str], items: Optional[List[Dict[str, Any]]]) -> List[Dict[str, Any]]:
        """
        Garante que o vetor de itens tenha o mesmo comprimento de 'links'
        e que cada posição 1-based aponte para o link correspondente.

        Se o ContentProcessor tiver filtrado falhas, reconstituímos placeholders
        para NÃO deslocar índices.
        """
        n = len(links)
        aligned: List[Dict[str, Any]] = [None] * n  # type: ignore

        # Posiciona o que já veio, se houver índice informado
        for it in (items or []):
            try:
                pos = (
                    it.get("idx")
                    or it.get("position")
                    or it.get("pos")
                )
                if isinstance(pos, int) and 1 <= pos <= n:
                    aligned[pos - 1] = it
            except Exception:
                # Se não for dict, ignora silenciosamente
                continue

        # Preenche vazios e força coerência de idx/url
        for i in range(n):
            if aligned[i] is None:
                aligned[i] = {
                    "idx": i + 1,
                    "url": links[i],
                    "title": None,
                    "text": None,
                    "success": False,
                    "error": "placeholder",
                }
            else:
                # força coerência de idx/url (mesmo que o extractor tenha retornado outro valor)
                aligned[i]["idx"] = i + 1
                aligned[i]["url"] = links[i]

        return aligned

    # ---------------------------------------------------------------------
    # Geração de Newsletter
    # ---------------------------------------------------------------------
    def generate_newsletter(
        self,
        links: List[str],
        user_instructions: str,
        ui_lead_indices: Optional[List[int]] = None
    ) -> Dict[str, Any]:
        """
        Fluxo:
          1) Validar links SEM alterar ordem/comprimento
          2) Extrair conteúdo preservando posições (ou preencher placeholders)
          3) Gerar texto com IA respeitando mapeamento 1-based e override da Abertura
          4) (Opcional) Criar Google Doc

        Retorno:
          {
            "success": bool,
            "content": str,
            "doc_url": Optional[str],
            "links_processed": int,
            "debug": {...}
          }
        """
        try:
            # 1) Validação leve (sem dedup/sem filtro destrutivo)
            valid_links = self._validate_links(links)

            # 2) Extração de conteúdo
            # IMPORTANTE: o ContentProcessor atual expõe _process_batch (privado).
            # Usamos mesmo assim para manter compatibilidade com o seu código existente.
            try:
                raw_items = self.content_processor._process_batch(valid_links)  # type: ignore
            except Exception as e:
                logger.exception("Falha na extração; usando placeholders. Erro: %s", e)
                raw_items = []

            content_items = self._ensure_alignment(valid_links, raw_items)

            # 3) Geração com IA — assinatura conforme seu ImprovedAIService:
            #    generate_newsletter(content_items, user_instructions, style_guide, ui_lead_indices)
            style_guide = self._load_style_guide()
            generated = self.ai_service.generate_newsletter(
                content_items,
                user_instructions,
                style_guide,
                ui_lead_indices
            )

            # Aceita dict ou string
            if isinstance(generated, dict):
                content = generated.get("content") or generated.get("text") or ""
            else:
                content = str(generated or "")

            if not content.strip():
                return {
                    "success": False,
                    "error": "IA não retornou conteúdo.",
                    "links_processed": len(valid_links),
                    "debug": {
                        "links_count": len(valid_links),
                        "ui_lead_indices": ui_lead_indices,
                    },
                }

            # 4) (Opcional) Criação do Google Doc (usa o método público existente)
            doc_url: Optional[str] = None
            try:
                # [CHANGED] GoogleDocsService.create_newsletter_doc aceita apenas 'content'
                doc_url = self.docs_service.create_newsletter_doc(content)
            except Exception as e:
                logger.warning("Falha ao criar Google Doc (seguindo sem doc): %s", e)

            return {
                "success": True,
                "content": content,
                "doc_url": doc_url,
                "links_processed": len(valid_links),
                "debug": {
                    "links_count": len(valid_links),
                    "ui_lead_indices": ui_lead_indices,
                },
            }

        except Exception as e:
            logger.exception("Erro inesperado no generate_newsletter: %s", e)
            return {"success": False, "error": str(e)}

    # ---------------------------------------------------------------------
    # Utilidades
    # ---------------------------------------------------------------------
    def _load_style_guide(self) -> str:
        """Carrega o guia de estilo do caminho definido no Config."""
        try:
            with open(self.config.STYLE_GUIDE_PATH, "r", encoding="utf-8") as f:
                return f.read()
        except Exception:
            return ""

    def _default_doc_title(self) -> str:
        # Ex.: "NEWS - 2025-09-23"
        today = datetime.now().strftime("%Y-%m-%d")
        return f"NEWS - {today}"

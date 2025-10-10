# src/content_processor.py
import asyncio
import aiohttp
import concurrent.futures
from typing import List, Dict, Optional, Tuple  # [NEW]
from urllib.parse import urlparse
import trafilatura
from bs4 import BeautifulSoup
import io
from pdfminer.high_level import extract_text as pdf_extract_text
from .config import Config
from .session_manager import SessionManager
import streamlit as st
import logging  # [NEW]

logger = logging.getLogger(__name__)  # [NEW]
if not logger.handlers:  # [NEW]
    logging.basicConfig(level=logging.INFO)  # [NEW]


class ContentProcessor:
    def __init__(self):
        self.config = Config()
        self.session_manager = SessionManager()  # [CHANGED] explicitamente manter instância

    # ---------------------------------------------------------------------
    # Extração paralela (assíncrona) – preserva posições (1-based em 'idx')
    # ---------------------------------------------------------------------
    async def process_links_parallel(self, links):
        async def worker(idx, url):
            try:
                item = await self._fetch_and_extract(url)  # [NEW] método implementado abaixo
                if not item or not item.get("text"):
                    # NÃO remova do array: preserve a posição com placeholder
                    return idx, {
                        "idx": idx,  # [NEW]
                        "url": url,
                        "title": None,
                        "text": "",
                        "success": False,
                        "error": "extraction_failed",
                    }
                item["url"] = url
                item["idx"] = idx  # [NEW] padroniza campo de posição (1-based)
                item["success"] = True  # [NEW]
                return idx, item
            except Exception as e:
                logger.warning("Erro async ao extrair %s: %s", url, e)
                return idx, {
                    "idx": idx,  # [NEW]
                    "url": url,
                    "title": None,
                    "text": "",
                    "success": False,
                    "error": f"exception:{e}",
                }

        tasks = [worker(idx, url) for idx, url in enumerate(links, start=1)]
        results = await asyncio.gather(*tasks, return_exceptions=False)  # mantém a ordem dos tasks
        # results é uma lista de (idx, item)
        results.sort(key=lambda x: x[0])  # redundante aqui, mas seguro
        ordered_items = [item for _, item in results]
        return ordered_items

    # [NEW] ----------------------------------------------------------------
    # Helper assíncrono: baixa e extrai texto (HTML/PDF) via aiohttp
    # ---------------------------------------------------------------------
    async def _fetch_and_extract(self, url: str) -> Dict:
        timeout = aiohttp.ClientTimeout(total=self.config.REQUEST_TIMEOUT or 30)
        async with aiohttp.ClientSession(timeout=timeout) as session:
            async with session.get(url, allow_redirects=True) as resp:
                content_type = resp.headers.get("Content-Type", "").lower()
                raw = await resp.read()

        # PDF?
        if url.lower().endswith(".pdf") or "application/pdf" in content_type:
            text = self._extract_pdf_bytes(raw)
            title = None
        else:
            html = raw.decode("utf-8", errors="ignore")
            # trafilatura
            text = self._extract_html_text(html, url)
            # título básico (fallback com BeautifulSoup)
            title = None
            try:
                soup = BeautifulSoup(html, "html.parser")
                if soup.title and soup.title.string:
                    title = soup.title.string.strip()
            except Exception:
                title = None

        if text and text.strip():
            return {
                "title": title,
                "text": text.strip(),
                "source": self._get_pretty_source(url),
            }
        return {"title": title, "text": "", "source": self._get_pretty_source(url)}

    # ---------------------------------------------------------------------
    # Agrupamento por domínio (otimização de sessões)
    # ---------------------------------------------------------------------
    def _group_by_domain(self, links: List[str]) -> Dict[str, List[str]]:
        """Agrupa links por domínio para otimizar sessões"""
        groups = {}
        for link in links:
            domain = self._get_domain(link)
            if domain not in groups:
                groups[domain] = []
            groups[domain].append(link)
        return groups

    def _get_domain(self, url: str) -> str:
        """Extrai domínio da URL"""
        try:
            parsed = urlparse(url)
            domain = parsed.netloc.lower()
            if domain.startswith("www."):
                domain = domain[4:]
            return domain
        except Exception:
            return "unknown"

    # ---------------------------------------------------------------------
    # Processamento em batch (sincrono) – usa SessionManager (requests-like)
    # ---------------------------------------------------------------------
    def _process_batch(self, links: List[str]) -> List[Dict]:
        """Processa um batch de links sequencialmente, **SEM** encurtar a lista."""
        results: List[Dict] = []

        for idx, url in enumerate(links, start=1):  # [CHANGED] capturamos idx aqui
            try:
                domain = self._get_domain(url)
                session = self.session_manager.get_session(domain)

                # Faz download do conteúdo
                response = session.get(
                    url,
                    timeout=self.config.REQUEST_TIMEOUT,
                    allow_redirects=True
                )
                response.raise_for_status()

                content_type = (response.headers or {}).get("Content-Type", "").lower()
                data = response.content

                # PDF?
                if url.lower().endswith(".pdf") or "application/pdf" in content_type:
                    text = self._extract_pdf_bytes(data)  # [NEW] evita tocar disco
                    title = None
                else:
                    html = response.text
                    text = self._extract_html_text(html, url)
                    # título básico (fallback)
                    title = None
                    try:
                        soup = BeautifulSoup(html, "html.parser")
                        if soup.title and soup.title.string:
                            title = soup.title.string.strip()
                    except Exception:
                        title = None

                if not text:
                    # placeholder preservando posição
                    results.append({
                        "idx": idx,            # [NEW] 1-based
                        "url": url,
                        "title": title,
                        "text": "",
                        "success": False,
                        "error": "extraction_failed",
                        "source": self._get_pretty_source(url),
                    })
                else:
                    results.append({
                        "idx": idx,            # [NEW]
                        "url": url,
                        "title": title,
                        "text": text.strip(),
                        "success": True,
                        "source": self._get_pretty_source(url),
                    })

            except Exception as e:
                logger.warning("Falha ao processar %s: %s", url, e)
                results.append({
                    "idx": idx,                # [NEW]
                    "url": url,
                    "title": None,
                    "text": "",
                    "success": False,
                    "error": f"exception:{e}",
                    "source": self._get_pretty_source(url),
                })

        # **Nunca** encurte ou reordene a lista
        return results

    # ---------------------------------------------------------------------
    # Extrações pontuais
    # ---------------------------------------------------------------------
    def _extract_pdf_text(self, pdf_path: str) -> Optional[str]:
        """Extrai texto de um PDF em disco (compatibilidade)."""
        try:
            text = pdf_extract_text(pdf_path)
            return text.strip() if text and text.strip() else None
        except Exception as e:
            logger.debug("Erro em _extract_pdf_text(%s): %s", pdf_path, e)
            return None

    # [NEW]
    def _extract_pdf_bytes(self, pdf_bytes: bytes) -> Optional[str]:
        """Extrai texto de bytes de PDF (sem gravar em disco)."""
        try:
            with io.BytesIO(pdf_bytes) as bio:
                text = pdf_extract_text(bio)
            return text.strip() if text and text.strip() else None
        except Exception as e:
            logger.debug("Erro em _extract_pdf_bytes: %s", e)
            return None

    def _extract_html_text(self, html: str, url: str) -> Optional[str]:
        """Extrai texto de HTML usando trafilatura (com fallback simples)."""
        # Primeiro, tente trafilatura
        try:
            text = trafilatura.extract(
                html,
                include_comments=False,
                include_tables=False,
                url=url
            )
            if text and text.strip():
                return text.strip()
        except Exception as e:
            logger.debug("Trafilatura falhou em %s: %s", url, e)

        # Fallback: texto cru da página (melhor que nada)
        try:
            soup = BeautifulSoup(html, "html.parser")
            for tag in soup(["script", "style", "noscript"]):
                tag.extract()
            raw = soup.get_text(separator="\n")
            cleaned = "\n".join(line.strip() for line in raw.splitlines() if line.strip())
            return cleaned if cleaned else None
        except Exception as e:
            logger.debug("Fallback HTML falhou em %s: %s", url, e)
            return None

    def _get_pretty_source(self, url: str) -> str:
        """Converte URL em nome bonito do veículo"""
        domain = self._get_domain(url)

        known_sources = {
            "valor.globo.com": "Valor Econômico",
            "oglobo.globo.com": "O Globo",
            "g1.globo.com": "G1",
            "imobireport.com.br": "Imobi Report",
            "estadao.com.br": "Estadão",
            "folha.uol.com.br": "Folha de S.Paulo",
            "exame.com": "Exame",
            "infomoney.com.br": "InfoMoney",
            "cnnbrasil.com.br": "CNN Brasil",
        }

        if domain in known_sources:
            return known_sources[domain]

        # Fallback: primeira parte do domínio
        parts = domain.split(".")
        candidate = parts[-2] if len(parts) >= 2 else parts[0]
        return candidate.replace("-", " ").title()

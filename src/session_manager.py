import requests
from typing import Dict
from urllib.parse import urljoin
from bs4 import BeautifulSoup
from .config import Config
import streamlit as st

class SessionManager:
    def __init__(self):
        self.config = Config()
        self._session_cache: Dict[str, requests.Session] = {}
    
    def get_session(self, domain: str) -> requests.Session:
        """Retorna sessão autenticada para o domínio"""
        if domain in self._session_cache:
            return self._session_cache[domain]
        
        session = requests.Session()
        session.headers.update(self.config.HEADERS)
        
        # Tenta fazer login se configurado
        login_config = self.config.LOGINS.get(domain)
        if login_config:
            self._perform_login(session, domain, login_config)
        
        self._session_cache[domain] = session
        return session
    
    def _perform_login(self, session: requests.Session, domain: str, config: dict):
        """Executa login baseado na configuração"""
        try:
            if config.get("strategy") == "globo_id":
                self._globo_id_login(session, config)
            else:
                self._standard_login(session, config)
        except Exception as e:
            st.warning(f"Falha no login para {domain}: {str(e)}")
    
    def _standard_login(self, session: requests.Session, config: dict):
        """Login padrão com POST simples"""
        login_url = config.get("login_url")
        username = config.get("username")
        password = config.get("password")
        
        if not all([login_url, username, password]):
            return
        
        # Preparar payload
        user_field = config.get("username_field", "username")
        pass_field = config.get("password_field", "password")
        extra_fields = config.get("extra_fields", {})
        
        payload = {
            user_field: username,
            pass_field: password,
            **extra_fields
        }
        
        # Fazer login
        session.get(login_url, timeout=self.config.REQUEST_TIMEOUT)
        response = session.post(
            login_url, 
            data=payload, 
            timeout=self.config.REQUEST_TIMEOUT
        )
        response.raise_for_status()
    
    def _globo_id_login(self, session: requests.Session, config: dict):
        """Login específico para Globo ID (duas etapas)"""
        start_url = config.get("start_url")
        username = config.get("username")
        password = config.get("password")
        
        if not all([start_url, username, password]):
            return
        
        # Etapa 1: Submeter email
        r1 = session.get(start_url, timeout=self.config.REQUEST_TIMEOUT)
        r1.raise_for_status()
        
        email_form = self._find_form_with_field(r1.text, ["email", "login", "username"])
        if email_form:
            action_url = urljoin(r1.url, email_form["action"])
            payload = email_form["fields"].copy()
            
            # Preencher email
            for field in ["email", "login", "username"]:
                if field in payload:
                    payload[field] = username
                    break
            
            r2 = session.post(action_url, data=payload, timeout=self.config.REQUEST_TIMEOUT)
            r2.raise_for_status()
        else:
            r2 = r1
        
        # Etapa 2: Submeter senha
        password_form = self._find_form_with_field(r2.text, ["password", "senha"])
        if password_form:
            action_url = urljoin(r2.url, password_form["action"])
            payload = password_form["fields"].copy()
            
            # Preencher senha
            for field in ["password", "senha"]:
                if field in payload:
                    payload[field] = password
                    break
            
            r3 = session.post(action_url, data=payload, timeout=self.config.REQUEST_TIMEOUT)
            r3.raise_for_status()
    
    def _find_form_with_field(self, html: str, field_names: list) -> dict:
        """Encontra formulário contendo algum dos campos especificados"""
        try:
            soup = BeautifulSoup(html, "lxml")
            forms = soup.find_all("form")
            
            for form in forms:
                inputs = form.find_all(["input", "textarea", "select"])
                fields = {}
                found_target = False
                
                for inp in inputs:
                    name = inp.get("name")
                    if not name:
                        continue
                    
                    fields[name] = inp.get("value", "")
                    
                    if name.lower() in field_names:
                        found_target = True
                
                if found_target:
                    return {
                        "action": form.get("action", ""),
                        "method": form.get("method", "POST").upper(),
                        "fields": fields
                    }
        except Exception:
            pass
        
        return None
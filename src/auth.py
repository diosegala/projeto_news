# src/auth.py - Sistema de autenticação
import hashlib
import base64
import secrets
from datetime import datetime
from tinydb import TinyDB, Query
import streamlit as st
import os
from .config import Config

class AuthManager:
    def __init__(self):
        self.config = Config()
        self.users_db = TinyDB(self.config.USERS_DB_PATH)
        self.users_table = self.users_db.table("users")
        self.pepper = os.getenv("AUTH_PEPPER", "")
        
        # Cria usuário admin se não existir
        if not self._user_by_username("admin"):
            self.register_user("admin", "dioner.segala@cupola.com.br", "Cupola*123", role="admin")
    
    def _pbkdf2_sha256(self, password: str, salt: bytes, iterations: int = 200_000) -> str:
        """Gera hash PBKDF2"""
        material = (password + self.pepper).encode("utf-8")
        dk = hashlib.pbkdf2_hmac("sha256", material, salt, iterations)
        return base64.b64encode(dk).decode("ascii")
    
    def _hash_password(self, password: str, iterations: int = 200_000) -> dict:
        """Cria hash da senha"""
        salt = secrets.token_bytes(16)
        return {
            "algo": "pbkdf2_sha256",
            "iterations": iterations,
            "salt_b64": base64.b64encode(salt).decode("ascii"),
            "hash_b64": self._pbkdf2_sha256(password, salt, iterations),
        }
    
    def _verify_password(self, password: str, record: dict) -> bool:
        """Verifica senha"""
        try:
            salt = base64.b64decode(record["salt_b64"])
            iterations = int(record["iterations"])
            expected = record["hash_b64"]
            calculated = self._pbkdf2_sha256(password, salt, iterations)
            return secrets.compare_digest(calculated, expected)
        except Exception:
            return False
    
    def _user_by_username(self, username: str):
        """Busca usuário por nome"""
        return self.users_table.get(Query().username == username)
    
    def register_user(self, username: str, email: str, password: str, role: str = "user") -> tuple[bool, str]:
        """Registra novo usuário"""
        username = (username or "").strip().lower()
        email = (email or "").strip()
        
        if not username or not email or not password:
            return False, "Preencha usuário, e-mail e senha."
        
        if self._user_by_username(username):
            return False, "Usuário já existe."
        
        password_hash = self._hash_password(password)
        self.users_table.insert({
            "username": username,
            "email": email,
            "password": password_hash,
            "role": role,
            "created_at": datetime.utcnow().isoformat(),
            "active": True,
        })
        
        return True, "Usuário criado com sucesso."
    
    def login_user(self, username: str, password: str) -> tuple[bool, str, dict]:
        """Autentica usuário"""
        username = (username or "").strip().lower()
        user = self._user_by_username(username)
        
        if not user or not user.get("active", True):
            return False, "Usuário/senha inválidos.", {}
        
        if not self._verify_password(password, user["password"]):
            return False, "Usuário/senha inválidos.", {}
        
        profile = {
            "username": user["username"],
            "email": user["email"], 
            "role": user.get("role", "user")
        }
        
        return True, "Login ok.", profile


def require_login_ui() -> bool:
    """Interface de login/registro"""
    auth_manager = AuthManager()
    
    # Verifica se já está logado
    if st.session_state.get("user"):
        with st.sidebar.expander("Conta", expanded=True):
            user = st.session_state["user"]
            st.write(f"**{user['username']}**")
            st.caption(user.get("email", ""))
            if st.button("Sair"):
                st.session_state.pop("user", None)
                st.rerun()
        return True
    
    # Interface de login
    st.title("Acesso")
    login_tab, register_tab = st.tabs(["Entrar", "Criar conta"])
    
    with login_tab:
        with st.form("login_form"):
            username = st.text_input("Usuário")
            password = st.text_input("Senha", type="password")
            submit_login = st.form_submit_button("Entrar")
        
        if submit_login:
            success, message, profile = auth_manager.login_user(username, password)
            if success:
                st.session_state["user"] = profile
                st.success("Bem-vindo!")
                st.rerun()
            else:
                st.error(message)
    
    with register_tab:
        with st.form("register_form"):
            reg_username = st.text_input("Usuário (sem espaços)").lower()
            reg_email = st.text_input("E-mail")
            reg_password = st.text_input("Senha", type="password")
            reg_password2 = st.text_input("Confirmar senha", type="password")
            submit_register = st.form_submit_button("Criar conta")
        
        if submit_register:
            if reg_password != reg_password2:
                st.error("As senhas não conferem.")
            else:
                success, message = auth_manager.register_user(reg_username, reg_email, reg_password)
                if success:
                    st.success(message + " Agora faça login.")
                else:
                    st.error(message)
    
    return False
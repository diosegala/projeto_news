from googleapiclient.discovery import build
from google.auth.transport.requests import Request
from google_auth_oauthlib.flow import InstalledAppFlow
from google.oauth2.credentials import Credentials
from google.oauth2 import service_account
from .config import Config
from datetime import datetime
import os
from .config import Config

class GoogleDocsService:
    def __init__(self):
        self.config = Config()
        self.scopes = [
            "https://www.googleapis.com/auth/documents",
            "https://www.googleapis.com/auth/drive.file",
        ]

    def _get_services(self):
        """Cria clients do Docs e Drive usando Service Account via st.secrets."""
        info = self.config.get_service_account_info()
        if not info:
            raise RuntimeError("GOOGLE_SERVICE_ACCOUNT ausente ou inválido em st.secrets.")
        creds = service_account.Credentials.from_service_account_info(info, scopes=self.scopes)
        docs_service = build("docs", "v1", credentials=creds, cache_discovery=False)
        drive_service = build("drive", "v3", credentials=creds, cache_discovery=False)
        return docs_service, drive_service
    
    
    def create_newsletter_doc(self, content: str) -> str:
        """Cria documento no Google Docs e retorna URL"""
        try:
            docs_service, drive_service = self._get_services()
            
            # Criar documento
            timestamp = datetime.now().strftime("%Y-%m-%d %H.%M")
            title = f"{self.config.GDOC_TITLE} — {timestamp}"
            
            doc_id = self._create_document(drive_service, title)
            
            # Escrever conteúdo
            self._write_content(docs_service, doc_id, content)
            
            return f"https://docs.google.com/document/d/{doc_id}/edit"
            
        except Exception as e:
            raise Exception(f"Erro ao criar documento: {str(e)}")
    

    
    def _get_credentials(self):
        """Gerencia autenticação OAuth"""
        creds = None
        
        # Carrega credenciais existentes
        if os.path.exists(self.config.TOKEN_PATH):
            creds = Credentials.from_authorized_user_file(
                self.config.TOKEN_PATH, self.scopes
            )
        
        # Renova ou cria novas credenciais
        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                creds.refresh(Request())
            else:
                if not os.path.exists(self.config.OAUTH_CLIENT_SECRETS):
                    raise Exception("Arquivo de credenciais OAuth não encontrado")
                
                flow = InstalledAppFlow.from_client_secrets_file(
                    self.config.OAUTH_CLIENT_SECRETS, self.scopes
                )
                creds = flow.run_local_server(port=0)
            
            # Salva credenciais
            with open(self.config.TOKEN_PATH, "w") as token:
                token.write(creds.to_json())
        
        return creds
    
    def _create_document(self, drive_service, title: str) -> str:
        """Cria novo documento no Drive"""
        file_metadata = {
            "name": title,
            "mimeType": "application/vnd.google-apps.document",
        }
        
        if self.config.GDRIVE_FOLDER_ID:
            file_metadata["parents"] = [self.config.GDRIVE_FOLDER_ID]
        
        created_file = drive_service.files().create(
            body=file_metadata,
            fields="id",
            supportsAllDrives=True
        ).execute()
        
        return created_file["id"]
    
    def _write_content(self, docs_service, doc_id: str, content: str):
        """Escreve conteúdo no documento"""
        # Adiciona header com timestamp
        timestamp = datetime.now().strftime("%d/%m/%Y %H:%M")
        header = f"Gerado em: {timestamp}\n" + ("="*80) + "\n\n"
        
        full_content = header + content
        
        if not full_content.endswith("\n"):
            full_content += "\n"
        
        docs_service.documents().batchUpdate(
            documentId=doc_id,
            body={
                "requests": [{
                    "insertText": {
                        "location": {"index": 1},
                        "text": full_content
                    }
                }]
            }
        ).execute()
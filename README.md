perfeito — aqui está um **README.md completo**, já no seu contexto (Streamlit Cloud, Service Account, pasta em Drive Compartilhado, sem OAuth local). Está em **pt-BR** e pronto pra colar no repositório.

---

# README.md

```markdown
# Newsletter IA — Streamlit + Google Docs

Gere uma newsletter a partir de links de notícias. O app:
1) coleta e processa conteúdo (páginas web e PDFs),
2) usa IA para analisar e escrever,
3) publica o resultado em um **Google Doc** dentro de uma pasta de **Drive Compartilhado**.

> **Stack principal:** Streamlit • Gemini (OpenAI opcional) • Google Docs/Drive API (Service Account) • TinyDB

---

## ✨ Recursos
- **Interface** em Streamlit.
- **Processamento** de links (HTML/PDF) com fallback e robustez.
- **Geração** de textos com modelos Gemini (prioritário). OpenAI opcional.
- **Publicação**: cria e escreve no **Google Docs** direto no **Drive Compartilhado** (sem OAuth do usuário).
- **Autenticação básica** no app via TinyDB (opcional; pode ser removido depois).

---

## 🗂 Estrutura de pastas (sugerida)
```

.
├─ streamlit_app.py                 # entrypoint do Streamlit
├─ src/
│  ├─ config.py                     # configurações (lidas APENAS de st.secrets)
│  ├─ newsletter_generator.py       # orquestra a geração da newsletter
│  ├─ improved_ai_service.py        # chamadas à IA (Gemini prioritário)
│  ├─ content_processor.py          # download/parse de páginas e PDFs
│  ├─ instruction_parser.py         # parsing de instruções
│  ├─ content_mapper.py             # estrutura/normalização do conteúdo
│  ├─ session_manager.py            # sessões/autenticação dos portais (usa st.secrets)
│  ├─ google_docs_service.py        # criação/escrita no Google Docs (Service Account)
│  └─ auth.py                       # login básico do app (TinyDB)
├─ data/
│  ├─ db.json                       # base local (exemplo)
│  ├─ users.json                    # credenciais do app (exemplo)
│  └─ style_guide.md                # guia de estilo para a escrita
├─ .streamlit/
│  ├─ config.toml                   # (opcional) tema/layout
│  └─ secrets.toml                  # (NÃO versionar)
├─ requirements.txt
└─ README.md

````

> Se você tinha versões antigas (`ai_service.py`, `structured_prompt.py`, etc.), mantenha fora do repositório ou remova.

---

## 🔐 Configuração de segredos (obrigatório)

No **Streamlit Cloud**, vá em **App → Settings → Secrets** e cole seu `secrets.toml`.  
Localmente, crie um arquivo **`.streamlit/secrets.toml`** (não comite).

### Exemplo de `secrets.toml`  
> ⚠️ Exemplo didático — **não coloque chaves reais** no repositório.

```toml
# Título padrão do Google Doc
GDOC_TITLE = "Newsletter Imobi Report"

# Pasta de DESTINO: deve ser uma pasta DENTRO de um Drive Compartilhado
# (copie o ID da URL da pasta: https://drive.google.com/drive/folders/<ID_AQUI>)
GDRIVE_FOLDER_ID = "1In0t_AJ35XHmPeJ_NX6yc_Ki7LD1MrNx"

# Service Account (formato BLOCO TOML)
[GOOGLE_SERVICE_ACCOUNT]
type = "service_account"
project_id = "seu-projeto"
private_key_id = "xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx"
private_key = """-----BEGIN PRIVATE KEY-----
... (cole o PEM completo com quebras de linha reais)
-----END PRIVATE KEY-----"""
client_email = "seu-sa@seu-projeto.iam.gserviceaccount.com"
client_id = "12345678901234567890"
auth_uri = "https://accounts.google.com/o/oauth2/auth"
token_uri = "https://oauth2.googleapis.com/token"
auth_provider_x509_cert_url = "https://www.googleapis.com/oauth2/v1/certs"
client_x509_cert_url = "https://www.googleapis.com/robot/v1/metadata/x509/seu-sa%40seu-projeto.iam.gserviceaccount.com"
universe_domain = "googleapis.com"

# (opcionais) chaves de IA
GOOGLE_API_KEY = ""
OPENAI_API_KEY = ""

# (opcional) headers p/ scraping
[HEADERS]
User-Agent = "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, como Gecko) Chrome/127.0 Safari/537.36"

# (opcional) logins dos portais — se o session_manager ler direto de st.secrets["LOGINS"]
# [LOGINS.imobireport.com.br]
# login_url = "https://imobireport.com.br/entrar/"
# method = "POST"
# username_field = "log"
# password_field = "pwd"
# username = "..."
# password = "..."
# [LOGINS.imobireport.com.br.extra_fields]
# rememberme = "forever"
````

### Permissões necessárias no Google Drive

* Use um **Drive Compartilhado** (Shared Drive) com espaço disponível.
* Dê ao **Service Account** permissão de **Content manager** (ou superior) **no Drive Compartilhado**.
* Coloque o **ID da pasta** **dentro** desse Shared Drive em `GDRIVE_FOLDER_ID`.
* O app cria docs com:

  * `parents=[GDRIVE_FOLDER_ID]`
  * `supportsAllDrives=True`

> Dica: se aparecer `storageQuotaExceeded`, é porque a criação caiu no “Meu Drive” do SA. Garanta que:
>
> 1. `GDRIVE_FOLDER_ID` é mesmo **de uma pasta do Shared Drive** (não um atalho), e
> 2. o SA tem **Content manager** no Shared Drive.

---

## ▶️ Rodando localmente

```bash
# 1) Python 3.10+ recomendado
python -m venv .venv
source .venv/bin/activate         # Windows: .venv\Scripts\activate

# 2) Dependências
pip install -r requirements.txt

# 3) Streamlit
streamlit run streamlit_app.py
```

> Certifique-se de ter o `.streamlit/secrets.toml` local.


---

## 🧪 Como funciona (resumo técnico)

* `content_processor.py` baixa e extrai conteúdo (HTML/PDF).
* `instruction_parser.py` e `content_mapper.py` preparam/estruturam os dados.
* `improved_ai_service.py` envia prompts estruturados para o modelo (Gemini por padrão).
* `newsletter_generator.py` coordena o fluxo e devolve a estrutura final (lead + seções).
* `google_docs_service.py` cria o documento dentro da pasta (`parents=[GDRIVE_FOLDER_ID]`) e escreve via `documents().batchUpdate(...)`.
* `auth.py` provê login básico no app (TinyDB).
* `streamlit_app.py` orquestra a UI.

---

## 🛠 Troubleshooting

**`GOOGLE_SERVICE_ACCOUNT ausente/ inválido`**

* Use **bloco TOML** para o SA (como no exemplo).
* Verifique se `private_key` tem **quebras reais** e headers corretos.

**`storageQuotaExceeded` ao criar o Doc**

* Quase sempre é criação no **“Meu Drive”** do SA.
* Use **pasta de Shared Drive** em `GDRIVE_FOLDER_ID` e mantenha `supportsAllDrives=True`.
* Garanta permissão **Content manager** do SA no Shared Drive.

**`File not found: 0A...`**

* IDs iniciados com `0A` são de **Shared Drive (driveId)**, não de arquivo/pasta.
* Para checar o drive use `drives().get`; para `files().get`, passe o **ID de pasta** (ex.: `folders/<id>` na URL).

**Link do Doc não abre como botão**

* Use `st.link_button("📂 Abrir no Google Docs", url)` ou Markdown `[📂 Abrir no Google Docs](url)`.


---

## 📜 Licença

Defina sua licença preferida. Exemplo: [MIT](https://opensource.org/licenses/MIT).

---

## 🙌 Contribuindo

Sinta-se à vontade para abrir issues e PRs. Sugestões:

* melhorar prompts/estilo (em `style_guide.md`),
* adicionar provedores de IA,
* exportar em outros formatos (ex.: PDF/HTML),
* autenticação mais robusta (OAuth do usuário) — **opcional** para o seu caso.
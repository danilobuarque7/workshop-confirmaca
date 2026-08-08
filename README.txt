# Workshop - versão pronta para publicação

## 1. Instalar
python -m venv .venv
Windows: .venv\Scripts\activate
pip install -r requirements.txt

## 2. Rodar localmente
python app.py
Acesse http://127.0.0.1:5000

## 3. QR Code
Coloque seu arquivo em:
static/img/qrcode-pix.png

## 4. Banco
Localmente, sem DATABASE_URL, usa SQLite.
Na hospedagem, configure DATABASE_URL com PostgreSQL.

## 5. Painel
/admin

IMPORTANTE: antes de publicar, coloque autenticação no /admin. Esta versão deixa o painel sem senha para facilitar os testes locais.

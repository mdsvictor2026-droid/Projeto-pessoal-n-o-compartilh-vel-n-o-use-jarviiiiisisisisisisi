# JARVIS Cloud Edition

Versão cloud do JARVIS — disponível 24/7 via Telegram, sem depender do PC.

## Features
- Web search (DuckDuckGo)
- Clima (OpenWeatherMap)
- Lembretes via Telegram
- Gmail (ler, enviar, responder)
- Ajuda com código
- Data e hora
- Memória de conversa por sessão

## Instalação

### 1. Dependências
```bash
pip install -r requirements.txt
```

### 2. Configurar api_keys.json
```json
{
  "gemini_api_key": "SUA_CHAVE_GEMINI",
  "telegram_bot_token": "TOKEN_DO_BOT_CLOUD",
  "telegram_chat_id": "",
  "openweather_api_key": "SUA_CHAVE_OPENWEATHER"
}
```

> Crie um bot NOVO no @BotFather para o cloud — diferente do bot local.
> OpenWeather: cadastro grátis em openweathermap.org → API Keys

### 3. Gmail (opcional)
Copie os arquivos do Jarvis local:
- `config/credentials_gmail.json`
- `config/token_gmail.json` (se já autorizou antes)

### 4. Rodar localmente
```bash
python main.py
```

### 5. Rodar na Oracle Cloud (24/7)
```bash
# Instalar como serviço systemd
sudo nano /etc/systemd/system/jarvis-cloud.service
```
```ini
[Unit]
Description=JARVIS Cloud
After=network.target

[Service]
ExecStart=/usr/bin/python3 /home/ubuntu/jarvis-cloud/main.py
WorkingDirectory=/home/ubuntu/jarvis-cloud
Restart=always
User=ubuntu

[Install]
WantedBy=multi-user.target
```
```bash
sudo systemctl enable jarvis-cloud
sudo systemctl start jarvis-cloud
sudo systemctl status jarvis-cloud
```

## Uso
Mande qualquer mensagem para o bot no Telegram. Exemplos:
- "Qual o clima em São Paulo?"
- "Pesquise as últimas notícias sobre IA"
- "Leia meus emails não lidos"
- "Me lembre em 30 minutos de tomar água"
- "Escreva uma função Python que..."

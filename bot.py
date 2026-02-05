#!/usr/bin/env python3
import os
import re
import tempfile
from telegram.ext import Updater, CommandHandler, MessageHandler, filters
from google.cloud import texttospeech
import requests
from bs4 import BeautifulSoup

TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN")
GOOGLE_API_KEY = os.environ.get("GOOGLE_API_KEY")

def extract_article(url):
    try:
        r = requests.get(url, headers={'User-Agent': 'Mozilla/5.0'}, timeout=30)
        r.raise_for_status()
        soup = BeautifulSoup(r.content, 'html.parser')
        for tag in soup(["script", "style", "nav", "footer"]):
            tag.decompose()
        article = soup.find('article') or soup.find('main')
        if article:
            text = article.get_text()
        else:
            text = '\n\n'.join([p.get_text().strip() for p in soup.find_all('p') if len(p.get_text().strip()) > 50])
        text = re.sub(r'\n\s*\n', '\n\n', text).strip()
        return text if len(text) > 100 else None
    except:
        return None

def split_chunks(text, max_bytes=4500):
    chunks = []
    sentences = text.split('. ')
    current = ""
    for s in sentences:
        test = current + s + ". "
        if len(test.encode('utf-8')) > max_bytes:
            if current:
                chunks.append(current.strip())
            current = s + ". "
        else:
            current = test
    if current:
        chunks.append(current.strip())
    return chunks

def make_audio(text):
    try:
        client = texttospeech.TextToSpeechClient(client_options={"api_key": GOOGLE_API_KEY})
        chunks = split_chunks(text)
        voice = texttospeech.VoiceSelectionParams(
            language_code="en-US",
            name="en-US-Neural2-J",
            ssml_gender=texttospeech.SsmlVoiceGender.MALE
        )
        config = texttospeech.AudioConfig(
            audio_encoding=texttospeech.AudioEncoding.MP3,
            speaking_rate=1.0
        )
        audio = b""
        for chunk in chunks:
            resp = client.synthesize_speech(
                input=texttospeech.SynthesisInput(text=chunk),
                voice=voice,
                audio_config=config
            )
            audio += resp.audio_content
        return audio
    except:
        return None

def start(update, context):
    update.message.reply_text("🎧 Schick mir eine URL!")

def handle(update, context):
    url = update.message.text.strip()
    if not url.startswith('http'):
        update.message.reply_text("❌ Keine gültige URL")
        return
    
    msg = update.message.reply_text("⏳ Lade...")
    text = extract_article(url)
    
    if not text:
        msg.edit_text("❌ Kein Text gefunden")
        return
    
    words = len(text.split())
    msg.edit_text(f"✅ {words} Wörter\n🎤 Generiere Audio...")
    
    audio = make_audio(text)
    if not audio:
        msg.edit_text("❌ Audio-Fehler")
        return
    
    msg.edit_text("⬆️ Sende...")
    
    with tempfile.NamedTemporaryFile(suffix='.mp3', delete=False) as f:
        f.write(audio)
        path = f.name
    
    try:
        update.message.reply_audio(audio=open(path, 'rb'), title="Article")
        msg.delete()
    finally:
        os.unlink(path)

def main():
    print("Starting bot...")
    updater = Updater(TELEGRAM_TOKEN, use_context=True)
    dp = updater.dispatcher
    dp.add_handler(CommandHandler("start", start))
    dp.add_handler(MessageHandler(filters.text & ~filters.command, handle))
    print("Bot running!")
    updater.start_polling()
    updater.idle()

if __name__ == '__main__':
    main()

from html import parser

from aiogram.fsm.context import FSMContext
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram import Bot, Dispatcher, F
from aiogram.filters import CommandStart
from aiogram.types import Message, CallbackQuery
from aiogram.utils.callback_answer import CallbackAnswer, CallbackAnswerMiddleware
from aiogram.types import BufferedInputFile
from dotenv import load_dotenv
from parse_hitmos.entered_tracks import EnteredTrack
from States import Form

import aiohttp
import os
import asyncio
import logging
import Db as db
import hashlib

log = logging.getLogger(__name__)

load_dotenv()
bot_token = os.getenv("BOT_TOKEN")
if bot_token is None:
    raise ValueError(f"Bot token is not set: {token}")

bot = Bot(token = bot_token)
dp = Dispatcher()
dp.callback_query.middleware(CallbackAnswerMiddleware())

@dp.message(CommandStart())
async def start(message):
    builder = InlineKeyboardBuilder()
    builder.button(text='1. Найди песню', callback_data='find_song')
    builder.button(text='2. Добавь песню в плейлист', callback_data='put_song_to_playlist')
    builder.adjust(1)
    markup = builder.as_markup()
    await message.answer(f"Привет! {message.from_user.first_name}. Выбирай: ", reply_markup=markup)

@dp.callback_query(F.data)
async def callback_handler(call: CallbackQuery, callback_answer: CallbackAnswer, state: FSMContext):
    if call.data == 'find_song':
        await call.message.answer('Введи название, автора песни')
        await state.set_state(Form.waiting_query)
    elif call.data == 'put_song_to_playlist':
        await call.message.answer('Введи название, автора песни')
        await state.set_state(Form.waiting_for_playlist)

@dp.message(Form.waiting_query)
async def find_song(message: Message, state: FSMContext):
    query = message.text.lower()

    result = await asyncio.to_thread(EnteredTrack, query, 1)
    items = result.data.get('items', []) if result.data else []
    if not items:
        await message.answer("Не нашел трек, попробуй еще раз")
        await state.clear()
        return
    track = items[0]
    song_name = track['title']
    song_author = track['author']
    song_url = result.base_url.rstip('/') + track['url_down']
    song_token = make_token(song_url)
    db.add_song(song_name, song_author, song_path, song_token)

    proxy_url = f"https://song_proxy.com/download/{song_token}"
    await message.answer_audio(proxy_url, title=song_name, performer=song_author)

    await state.clear()
    log.info(f"Song found: {song_name}, {song_author}, {song_path}")

@dp.message(Form.waiting_for_playlist)
async def put_song_to_playlist(message: Message, state: FSMContext):
    pass

@dp.message()
async def info(message):
    if message.text.lower() == 'привет':
        await message.answer(f"Привет! {message.from_user.first_name}")
    elif message.text.lower() == 'id':
        await message.answer(f'id чата: {message.from_user.id}')

def make_token(url):
    return hashlib.sha256(url.encode()).hexdigest()[:16]

async def main():
    await dp.start_polling(bot)

if __name__ == '__main__':
    asyncio.run(main())
    logging.basicConfig(level=logging.INFO, stream=sys.stdout, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
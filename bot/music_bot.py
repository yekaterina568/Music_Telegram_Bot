import asyncio
import logging
import os
import sys

from aiogram import Bot, Dispatcher, F
from aiogram.filters import CommandStart, Command
from aiogram.fsm.context import FSMContext
from aiogram.types import BufferedInputFile, Message, CallbackQuery
from aiogram.utils.callback_answer import CallbackAnswer, CallbackAnswerMiddleware
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiohttp import ClientSession, ClientTimeout
from dotenv import load_dotenv
from parse_hitmos.entered_tracks import EnteredTrack

import songs_db as db

log = logging.getLogger(__name__)
load_dotenv()

bot_token = os.getenv("BOT_TOKEN")
if bot_token is None:
    raise ValueError(f"Bot token is not set")

bot = Bot(token=bot_token)
dp = Dispatcher()
dp.callback_query.middleware(CallbackAnswerMiddleware())

help_text = ('Бот может: \n'
             '1. Отправить песню (напиши автора название)')


@dp.message(CommandStart())
async def start(message):
    builder = InlineKeyboardBuilder()
    builder.button(text='1. Все не то', callback_data='helpani')
    builder.button(text='2. Добавь песню в плейлист', callback_data='put_song_to_playlist')
    builder.adjust(1)
    markup = builder.as_markup()
    await message.answer(f"Привет! {message.from_user.first_name}. Выбирай: ", reply_markup=markup)


@dp.callback_query(F.data)
async def callback_handler(call: CallbackQuery, callback_answer: CallbackAnswer, state: FSMContext):
    if call.data == 'helpani':
        await call.message.answer(help_text)
    elif call.data == 'put_song_to_playlist':
        pass


@dp.message(Command('help'))
async def help(message: Message):
    await message.answer(help_text)


@dp.message()
async def get_any(message: Message):
    await find_song(message)


async def find_song(message: Message):
    query = message.text.lower()

    result = await asyncio.to_thread(EnteredTrack, query, 10, True)
    items = result.data.get('items', []) if result.data else []
    if not items:
        await message.answer("Не нашел трек, попробуй еще раз")
        return
    track = items[0]
    song_name = track['title']
    song_author = track['author']
    song_path = result.base_url.rstrip('/') + track['url_down']
    file = await download_song(song_path, song_name)
    await message.answer_audio(audio=file, title=song_name, performer=song_author)

    await db.add_song(song_name, song_author, song_path)
    log.info(f"Song found: {song_name}, {song_author}, {song_path}")


async def download_song(url, name):
    if url.endswith('.mp3'):
        try:
            timeout = ClientTimeout(total=60)
            async with ClientSession(timeout=timeout) as session:
                async with session.get(url) as response:
                    data = await response.read()
                    return BufferedInputFile(data, f"{name}.mp3")
        except Exception as e:
            log.error(e)
            raise e
    raise ValueError(f"Invalid url for downloading the song: {url}")


async def put_song_to_playlist(message: Message, state: FSMContext):
    pass


async def main():
    await db.init_db()
    await dp.start_polling(bot, skip_updates=True)


if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO, stream=sys.stdout,
                        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    asyncio.run(main())

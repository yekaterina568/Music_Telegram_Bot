import asyncio
import logging
import os
import sys

from aiogram import Bot, Dispatcher, F
from aiogram.filters import CommandStart, Command
from aiogram.fsm.context import FSMContext
from aiogram.types import BufferedInputFile, Message, CallbackQuery
from aiogram.utils.callback_answer import CallbackAnswerMiddleware
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
             '1. Отправить песню. Для этого напиши автора название(может занять время)')


@dp.message(CommandStart())
async def start(message: Message):
    builder = InlineKeyboardBuilder()
    builder.button(text='1. Все не то', callback_data='helpani')
    builder.button(text='2. Добавь песню в плейлист', callback_data='put_song_to_playlist')
    builder.button(text='3. Моя история песен', callback_data='user_history')
    builder.adjust(1)
    markup = builder.as_markup()
    await message.answer(f"Привет! {message.from_user.first_name}. Выбирай: ", reply_markup=markup)
    await db.get_or_create_user(message.from_user.first_name, message.from_user.id)


@dp.callback_query(F.data)
async def callback_handler(call: CallbackQuery, state: FSMContext):
    if call.data == 'helpani':
        await call.message.answer(help_text)
    elif call.data == 'put_song_to_playlist':
        pass
    elif call.data == 'user_history':
        await show_history(call)
    elif call.data.startswith('!'):
        song_id = int(call.data[1:])
        await get_song(song_id, call.message)


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
    await send(song_path, song_name, song_author, message)

    user_id = await db.get_or_create_user(message.from_user.first_name, message.from_user.id)
    await db.add_song(song_name, song_author, song_path, user_id)


async def get_song(song_id, message: Message):
    song = await db.find_song_path(song_id)
    song_name, song_author, song_path = song
    await send(song_path, song_name, song_author, message)


async def send(song_path, song_name, song_author, message: Message):
    file = await(download_song(song_path))
    await message.answer_audio(audio=file, title=song_name, performer=song_author)
    log.info(f"Song was sent: {song_name}, {song_author}, {song_path}")


async def download_song(url):
    if url.endswith('.mp3'):
        try:
            timeout = ClientTimeout(total=60)
            async with ClientSession(timeout=timeout) as session:
                async with session.get(url) as response:
                    data = await response.read()
                    return BufferedInputFile(data, "song.mp3")
        except Exception as e:
            log.error(e)
            raise e
    raise ValueError(f"Invalid url for downloading the song: {url}")


async def put_song_to_playlist(message: Message, state: FSMContext):
    pass


async def show_history(call: CallbackQuery):
    history = await db.show_user_history(call.from_user.id)
    if not history:
        await call.message.answer("У тебя пока нет истории")
        return
    builder = InlineKeyboardBuilder()
    for i in range(len(history)):
        song_id, song_name, song_author = history[i]
        builder.button(text=f"{i + 1}. {song_name} {song_author}", callback_data=f"!{song_id}")
    builder.adjust(1)
    markup = builder.as_markup()
    await call.message.answer("Твоя история: ", reply_markup=markup)


async def main():
    await db.init_db()
    await dp.start_polling(bot, skip_updates=True)


if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO, stream=sys.stdout,
                        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    asyncio.run(main())

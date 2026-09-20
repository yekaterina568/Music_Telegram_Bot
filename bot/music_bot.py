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
from parse_hitmos.excepts import NoFoundTrack

import songs_db as db
from states import Form

log = logging.getLogger(__name__)
load_dotenv()

bot_token = os.getenv("BOT_TOKEN")
if bot_token is None:
    raise ValueError(f"Bot token is not set")

bot = Bot(token=bot_token)
dp = Dispatcher()
dp.callback_query.middleware(CallbackAnswerMiddleware())

songs_in_progress = set()

help_text = ('Бот может: \n'
             '1. Отправить песню. Для этого введи автора, название песни(может занять время)')


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
        await get_playlist_name(call, state)
    elif call.data == 'user_history':
        await show_history(call, state)
    elif call.data.startswith('!'):
        song_id = int(call.data[1:])
        await get_song_for_history(song_id, call.message)
    elif call.data == 'playlist_new_song':
        await call.message.answer('Введи название, автора песни')
        await state.set_state(Form.waiting_song_for_playlist)
    elif call.data.startswith('@'):
        song_id = int(call.data[1:])
        await song_to_playlist(song_id, call.message, state)


@dp.message(Command('help'))
async def help(message: Message):
    await message.answer(help_text)


@dp.message(Form.waiting_for_playlist_name)
async def put_to_playlist(message: Message, state: FSMContext):
    playlist_name = message.text
    user_id = await db.find_user(message.from_user.id)

    builder = InlineKeyboardBuilder()
    builder.button(text='1. Из истории прослушивания', callback_data='user_history')
    builder.button(text="2. Новая песня", callback_data='playlist_new_song')
    builder.adjust(1)
    markup = builder.as_markup()

    await message.answer('Выбери способ добавления в плейлист: ', reply_markup=markup)
    playlist_id = await db.add_or_get_playlist(playlist_name, user_id)
    await state.update_data(playlist_id=playlist_id)


@dp.message(Form.waiting_song_for_playlist)
async def new_song_to_playlist(message: Message, state: FSMContext):
    song_res = await find_song(message.text.rstrip())
    if song_res is None:
        await message.answer('Не нашел трек, попробуй еще раз')
        return
    song_name, song_author, song_path = song_res
    user_id = await db.find_user(message.from_user.id)
    song_id = await db.add_song(song_name, song_author, song_path, user_id)
    await song_to_playlist(song_id, message, state)


@dp.message()
async def get_any(message: Message):
    song = await find_song(message.text)
    if song is None:
        await message.answer('Не нашел трек, попробуй еще раз')
        return
    song_name, song_author, song_path = song
    await send(song_path, song_name, song_author, message)
    user_id = await db.get_or_create_user(message.from_user.first_name, message.from_user.id)
    await db.add_song(song_name, song_author, song_path, user_id)


async def find_song(request):
    query = request.lower().strip()
    try:
        result = await asyncio.to_thread(EnteredTrack, query, 10)
        items = result.data.get('items', [])
        track = items[0]
        song_name = track['title']
        song_author = track['author']
        song_path = result.base_url.rstrip('/') + track['url_down']
    except NoFoundTrack as e:
        log.error(f'Track was not found: {e}')
        return
    return song_name, song_author, song_path


async def send(song_path, song_name, song_author, message: Message):
    try:
        file = await(download_song(song_path))
        await message.answer_audio(audio=file, title=song_name, performer=song_author)
        log.info(f"Song was sent: {song_name}, {song_author}, {song_path}")
    except Exception as e:
        await message.answer('Не удалось скачать песню. Попробуй еще раз')
        log.error(f"Couldn't download song - {song_path}: {e}")


async def download_song(url):
    if url.endswith('.mp3'):
        try:
            timeout = ClientTimeout(total=60)
            async with ClientSession(timeout=timeout) as session:
                async with session.get(url) as response:
                    data = await response.read()
                    return BufferedInputFile(data, "song.mp3")
        except Exception as e:
            log.error(f"Couldn't download song by {url}: {e}")
            raise
    raise ValueError(f"Invalid url for downloading the song: {url}")


async def get_playlist_name(call: CallbackQuery, state: FSMContext):
    await call.message.answer('Введи название для плейлиста: ')
    await state.set_state(Form.waiting_for_playlist_name)


async def show_history(call: CallbackQuery, state: FSMContext):
    history = await db.show_user_history(call.from_user.id)
    if not history:
        await call.message.answer("У тебя пока нет истории")
        return
    builder = InlineKeyboardBuilder()
    state_data = await state.get_data()
    if state_data['playlist_id'] is not None:
        for i in range(len(history)):
            song_id, song_name, song_author = history[i]
            builder.button(text=f"{i + 1}. {song_name} {song_author}", callback_data=f"@{song_id}")
    else:
        for i in range(len(history)):
            song_id, song_name, song_author = history[i]
            builder.button(text=f"{i + 1}. {song_name} {song_author}", callback_data=f"!{song_id}")
    builder.adjust(1)
    markup = builder.as_markup()
    await call.message.answer("Твоя история: ", reply_markup=markup)


async def get_song_for_history(song_id, message: Message):
    if song_id in songs_in_progress:
        return
    songs_in_progress.add(song_id)
    try:
        song = await db.find_song_path(song_id)
        song_name, song_author, song_path = song
        await send(song_path, song_name, song_author, message)
    except Exception as e:
        await message.answer('Не удалось скачать песню. Попробуй еще раз')
        log.error(f"Couldn't download song - {song_id}: {e}")
    finally:
        songs_in_progress.remove(song_id)


async def song_to_playlist(song_id, message: Message, state: FSMContext):
    playlist = await state.get_data()
    playlist_id = playlist['playlist_id']
    await db.add_playlist_song(song_id, playlist_id)
    await message.answer(f'Песня успешно добавлена в плейлист')
    log.info(f'New song: {song_id} was added to playlist {playlist_id}')
    await state.clear()


async def main():
    await db.init_db()
    await dp.start_polling(bot, skip_updates=True)


if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO, stream=sys.stdout,
                        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    asyncio.run(main())

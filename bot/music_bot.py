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

how = 'Для этого отправь автора, название песни (может занять время)'
help_text = ('1. Нажми старт для начала работы бота \n'
             '2. Можешь скачать песню в любой момент: \n'
             + f'3. {how}')


@dp.message(CommandStart())
async def start(message: Message):
    builder = InlineKeyboardBuilder()
    builder.button(text='1. Скачать песню', callback_data='helpani')
    builder.button(text='2. Мои плейлисты', callback_data='user_playlists')
    builder.button(text='3. Добавь песню в плейлист', callback_data='put_song_to_playlist')
    builder.button(text='4. Моя история песен', callback_data='user_history')
    builder.adjust(1)
    markup = builder.as_markup()
    await message.answer(f"Привет! {message.from_user.first_name}. Выбирай: ", reply_markup=markup)
    await db.get_or_create_user(message.from_user.first_name, message.from_user.id)


@dp.callback_query(F.data)
async def callback_handler(call: CallbackQuery, state: FSMContext):
    if call.data == 'helpani':
        await call.message.answer(how)
    elif call.data == 'put_song_to_playlist':
        await list_user_playlists(call.message, call.from_user.id, '^В какой плейлист добавить?')
    elif call.data == 'user_history':
        await show_history(call, state)
    elif call.data.startswith('~'):
        song_id = int(call.data[1:])
        await get_song(song_id, call.message)
    elif call.data == 'playlist_new_song':
        await call.message.answer('Введи название, автора песни')
        await state.set_state(Form.waiting_song_for_playlist)
    elif call.data.startswith('@'):
        song_id = int(call.data[1:])
        await song_to_playlist(song_id, call.message, state)
    elif call.data == 'new_playlist':
        await call.message.answer('Введи название для плейлиста: ')
        await state.set_state(Form.waiting_for_playlist_name)
    elif call.data == 'show_playlists':
        await show_playlists(call.message, call.from_user.id)
    elif call.data.startswith('^'):
        playlist_id = int(call.data[1:])
        await state.update_data(playlist_id=playlist_id)
        await get_way_for_playlist(call.message)
    elif call.data == 'user_playlists':
        await resolve_playlist(call.message)
    elif call.data.startswith('&'):
        playlist_id = int(call.data[1:])
        await state.update_data(show_playlist_id=playlist_id)
        await playlist_to_song(call, state)


@dp.message(Command('help'))
async def help(message: Message):
    await message.answer(help_text)


@dp.message(Form.waiting_for_playlist_name)
async def new_playlist(message: Message, state: FSMContext):
    playlist_name = message.text.rstrip()
    if playlist_name is None:
        await message.answer('Неверное название для плейлиста. Попробуй еще раз')
        return
    telegram_id = message.from_user.id
    user_id = await db.find_user(telegram_id)
    await db.add_or_get_playlist(playlist_name, user_id)
    await show_playlists(message, telegram_id)
    await state.clear()


@dp.message(Form.waiting_song_for_playlist)
async def new_song_to_playlist(message: Message, state: FSMContext):
    song_res = await find_song(message.text.rstrip())
    if song_res is None:
        await message.answer('Не нашел трек, попробуй еще раз')
        return
    song_name, song_author, song_path = song_res
    user_id = await db.find_user(message.from_user.id)
    song_id = await db.add_or_get_song(song_name, song_author, song_path, user_id)
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
    await db.add_or_get_song(song_name, song_author, song_path, user_id)


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


async def get_way_for_playlist(message: Message):
    builder = InlineKeyboardBuilder()
    builder.button(text='1. Песня из истории прослушивания', callback_data='user_history')
    builder.button(text="2. Новая песня", callback_data='playlist_new_song')
    builder.adjust(1)
    markup = builder.as_markup()
    await message.answer('Выбери способ добавления в плейлист: ', reply_markup=markup)


async def resolve_playlist(message: Message):
    builder = InlineKeyboardBuilder()
    builder.button(text='1. Показать текущие плейлисты', callback_data='show_playlists')
    builder.button(text='2. Создать новый плейлист', callback_data='new_playlist')
    builder.adjust(1)
    markup = builder.as_markup()
    await message.answer('Выбирай: ', reply_markup=markup)


async def show_playlists(message: Message, telegram_id):
    await list_user_playlists(message, telegram_id, '&Твои плейлисты:')


async def list_user_playlists(message: Message, telegram_id, use):
    use_sign = use[0]
    use_case = use[1:]
    user_playlists = await db.find_user_playlists(telegram_id)
    if not user_playlists:
        await message.answer('У тебя пока нет плейлистов')
        return
    builder = InlineKeyboardBuilder()
    for i in range(len(user_playlists)):
        playlist_id, playlist_name = user_playlists[i]
        builder.button(text=f'{i + 1}. {playlist_name}', callback_data=f"{use_sign}{playlist_id}")
    builder.adjust(1)
    markup = builder.as_markup()
    await message.answer(use_case, reply_markup=markup)


async def show_history(call: CallbackQuery, state: FSMContext):
    history = await db.show_user_history(call.from_user.id)
    if not history:
        await call.message.answer("У тебя пока нет истории")
        return
    state_data = await state.get_data()
    playlist_id = state_data.get('playlist_id')
    if playlist_id is None:
        await list_songs(history, call.message, "~Твои песни из истории прослушивания:")
    else:
        await list_songs(history, call.message, "@Твои песни из истории прослушивания:")


async def playlist_to_song(call: CallbackQuery, state: FSMContext):
    state_data = await state.get_data()
    playlist_id = state_data.get('show_playlist_id')
    if playlist_id is None:
        await call.message.answer("Что-то пошло не так. Попробуй еще раз")
        return
    playlist_songs = await db.find_playlist_songs(playlist_id)
    if playlist_songs is []:
        await call.message.answer("В этом плейлисте нет песен")
        return
    await list_songs(playlist_songs, call.message, '~Текущие песни в плейлисте:')
    await state.clear()


async def list_songs(songs: tuple, message: Message, use):
    use_sign = use[0]
    use_case = use[1:]
    builder = InlineKeyboardBuilder()
    for i in range(len(songs)):
        song_id, song_name, song_author = songs[i]
        builder.button(text=f"{i + 1}. {song_name} {song_author}", callback_data=f"{use_sign}{song_id}")
    builder.adjust(1)
    markup = builder.as_markup()
    await message.answer(use_case, reply_markup=markup)


async def get_song(song_id, message: Message):
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
    playlist_songs = await db.find_playlist_songs(playlist_id)
    await list_songs(playlist_songs, message, '~Текущие песни в плейлисте:')
    log.info(f'New song: {song_id} was added to playlist {playlist_id}')
    await state.clear()


async def main():
    await db.init_db()
    await dp.start_polling(bot, skip_updates=True)


if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO, stream=sys.stdout,
                        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    asyncio.run(main())

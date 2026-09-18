from aiogram.fsm.state import State, StatesGroup


class Form(StatesGroup):
    waiting_for_playlist_name = State()
    waiting_song_for_playlist = State()

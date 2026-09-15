from aiogram.fsm.state import State, StatesGroup

class Form(StatesGroup):
    waiting_query = State()
    waiting_for_playlist = State()
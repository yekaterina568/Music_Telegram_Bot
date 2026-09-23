from enum import Enum


class Action(str, Enum):
    GET_SONG = '~'
    SONG_TO_PLAYLIST = '@'
    CHOOSE_PLAYLIST = '^'
    SHOW_PLAYLIST_SONGS = '&'

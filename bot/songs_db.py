from pathlib import Path

import aiosqlite

DB_PATH = Path(__file__).parent / 'bot'

async def init_db():
    async with aiosqlite.connect(DB_PATH) as db_con:
        await db_con.execute('pragma foreign_keys=on')
        await db_con.execute('''                                                                                          
                   create table if not exists user(                                                             
                   id integer primary key,                                                                      
                   name varchar(100),                                                                           
                   telegram_id integer,                                                                         
                   unique(telegram_id))''')

        await db_con.execute('''                                                                                          
                       create table if not exists song(                                                             
                       id integer primary key,                                                                      
                       name varchar(100),                                                                           
                       author varchar(100),                                                                         
                       path varchar)''')

        await db_con.execute('''                                                                                          
                       create table if not exists playlist(                                                         
                       id integer primary key,                                                                      
                       name varchar(100),                                                                           
                       user_id integer references user(id))''')

        await db_con.execute('''                                                                                          
                       create table if not exists playlist_song(                                                    
                       id integer primary key,                                                                      
                       song_id integer references song(id),                                                         
                       playlist_id integer references playlist(id))''')

        await db_con.commit()

async def add_user(name, telegram_id):
    async with aiosqlite.connect(DB_PATH) as db_con:
        cur = await db_con.execute('insert into user(name, telegram_id) values(?, ?)', (name, telegram_id))
        await db_con.commit()
        return cur.lastrowid

async def add_song(name, author, path):
    async with aiosqlite.connect(DB_PATH) as db_con:
        cur = await db_con.execute('insert into song(name, author, path) values (?, ?, ?)', (name, author, path))
        await db_con.commit()
        return cur.lastrowid

async def add_playlist(name, user_id):
    async with aiosqlite.connect(DB_PATH) as db_con:
        cur = await db_con.execute('insert into playlist(name, user_id) values(?, ?)', (name, user_id))
        await db_con.commit()
        return cur.lastrowid

async def add_playlist_song(song_id, playlist_id):
    async with aiosqlite.connect(DB_PATH) as db_con:
        cur = await db_con.execute('insert into playlist_song(song_id, playlist_id) values(?, ?)', (song_id, playlist_id))
        await db_con.commit()
        return cur.lastrowid
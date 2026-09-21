from pathlib import Path

import aiosqlite

DB_PATH = Path(__file__).parent / 'bot'

async def init_db():
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute('pragma foreign_keys=on')
        await db.execute('''                                                                                          
                       create table if not exists user(                                                             
                       id integer primary key,                                                                      
                       name varchar(100),                                                                           
                       telegram_id integer,                                                                         
                       unique(telegram_id))''')

        await db.execute('''                                                                                          
                       create table if not exists song(                                                             
                       id integer primary key,                                                                      
                       name varchar(100),                                                                           
                       author varchar(100),                                                                         
                       path varchar,
                       user_id integer references user(id),
                       unique(path, user_id))''')

        await db.execute('''                                                                                          
                       create table if not exists playlist(                                                         
                       id integer primary key,                                                                      
                       name varchar(100),                                                                           
                       user_id integer references user(id),
                       unique(name, user_id))''')

        await db.execute('''                                                                                          
                       create table if not exists playlist_song(                                                    
                       id integer primary key,                                                                      
                       song_id integer references song(id),                                                         
                       playlist_id integer references playlist(id),
                       unique(song_id, playlist_id))''')

        await db.commit()

async def get_or_create_user(name, telegram_id):
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute('insert or ignore into user(name, telegram_id) values(?, ?)', (name, telegram_id))
        await db.commit()
        return await find_user(telegram_id)

async def add_or_get_song(name, author, path, user_id):
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute('insert or ignore into song(name, author, path, user_id) values (?, ?, ?, ?)', (name, author, path, user_id))
        await db.commit()
        return await find_song(path, user_id)

async def add_or_get_playlist(name, user_id):
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute('insert or ignore into playlist(name, user_id) values(?, ?)', (name, user_id))
        await db.commit()
        return await find_playlist(name, user_id)

async def add_playlist_song(song_id, playlist_id):
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute('insert or ignore into playlist_song(song_id, playlist_id) values(?, ?)', (song_id, playlist_id))
        await db.commit()

async def show_user_history(telegram_id):
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute('''
        select s.id, s.name, author
        from song s
        join user u 
        on u.id = s.user_id
        where u.telegram_id = ?        
        ''', (telegram_id, ))
        rows = await cur.fetchall()
        return rows

async def find_song_path(song_id):
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute('select name, author, path from song where id = ?', (song_id, ))
        res = await cur.fetchone()
        return res

async def find_user(telegram_id):
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute('select id from user where telegram_id = ?', (telegram_id,))
        res = await cur.fetchone()
        return res[0]

async def find_playlist(name, user_id):
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute('select id from playlist where name = ? and user_id = ?', (name, user_id))
        res = await cur.fetchone()
        return res[0]

async def find_song(path, user_id):
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute('select id from song where path = ? and user_id = ?', (path, user_id))
        res = await cur.fetchone()
        return res[0]

async def find_user_playlists(telegram_id):
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute('''
        select p.id, p.name
        from playlist p 
        join user u 
        on u.id = p.user_id
        where u.telegram_id = ?
        ''', (telegram_id, ))
        res = await cur.fetchall()
        return res

async def find_playlist_songs(playlist_id):
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute('''
        select s.id, s.name, s.author
        from song s 
        join playlist_song p 
        on p.song_id = s.id
        where p.playlist_id = ?
        ''', (playlist_id, ))
        res = await cur.fetchall()
        return res
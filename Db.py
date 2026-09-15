import sqlite3

db_con = sqlite3.connect("db")
db_cur = db_con.cursor()
db_cur.execute('pragma foreign_keys=ON')

db_cur.execute('''
               create table if not exists user(
               id integer primary key, 
               name varchar(100), 
               telegram_id integer,
               unique(telegram_id))''')

db_cur.execute('''
               create table if not exists song(
               id integer primary key, 
               name varchar(100), 
               author varchar(100), 
               path varchar,
               token varchar(16),
               unique(name, author, path, token))''')

db_cur.execute('''
               create table if not exists playlist(
               id integer primary key, 
               name varchar(100),
               user_id integer references user(id))''')

db_cur.execute('''
               create table if not exists playlist_song(
               id integer primary key, 
               song_id integer references song(id), 
               playlist_id integer references playlist(id))''')

db_con.commit()

def add_user(name, telegram_id):
    db_cur.execute('insert into user(name, telegram_id) values(?, ?)', (name, telegram_id))
    db_con.commit()
    return db_cur.lastrowid

def add_song(name, author, path, token):
    db_cur.execute('insert into song(name, author, path, token) values (?, ?, ?, ?)', (name, author, path, token))
    db_con.commit()
    return db_cur.lastrowid

def add_playlist(name, user_id):
    db_cur.execute('insert into playlist(name, user_id) values(?, ?)', (name, user_id))
    db_con.commit()
    return db_cur.lastrowid

def add_playlist_song(song_id, playlist_id):
    db_cur.execute('insert into playlist_song(song_id, playlist_id) values(?, ?)', (song_id, playlist_id))
    db_con.commit()
    return db_cur.lastrowid

def get_song_path(token):
    db_cur.execute('select path from song where token = ?', (token,))
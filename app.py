import eventlet
eventlet.monkey_patch()

from flask import Flask, render_template, request, redirect, url_for, session
from flask_socketio import SocketIO, emit
from werkzeug.security import generate_password_hash, check_password_hash
from pymongo import MongoClient
import random
import os

app = Flask(__name__)
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'dev-secret-change-me')
socketio = SocketIO(app, cors_allowed_origins="*", ping_timeout=10, ping_interval=5)

# MongoDB
MONGO_URI = os.environ.get('MONGO_URI', 'mongodb://localhost:27017/diep_game')
mongo = MongoClient(MONGO_URI)
db = mongo.get_default_database()
users_collection = db['users']

# Game state
players = {}
items = {}
item_counter = 0
COLORS = ['#4488cc', '#cc4444', '#44cc44', '#cc8844', '#8844cc', '#44cccc']
START_HP = 100
START_MAX_HP = 100
BULLET_DAMAGE = 100

# Class stats - each class has its own balance
CLASS_STATS = {
    'scout': {
        'hp': 70,
        'max_hp': 70,
        'speed': 300,
        'bullet_damage': 45,
        'fire_rate': 10,
        'bullet_speed': 700,
    },
    'assault': {
        'hp': 100,
        'max_hp': 100,
        'speed': 200,
        'bullet_damage': 10,
        'fire_rate': 400,
        'bullet_speed': 600,
    },
    'support': {
        'hp': 170,
        'max_hp': 170,
        'speed': 50,
        'bullet_damage': 20,
        'fire_rate': 220,
        'bullet_speed': 400,
    },
    'medic': {
        'hp': 120,
        'max_hp': 120,
        'speed': 140,
        'bullet_damage': 15,
        'fire_rate': 400,
        'bullet_speed': 350,
    },
}

def adjust_max_hp(sid, reason, **kwargs):
    p = players.get(sid)
    if not p:
        return
    if reason == 'powerup':
        p['max_hp'] = 300
        p['hp'] = min(p['hp'] + 200, p['max_hp'])

    socketio.emit('hp_update', {
        'id': sid,
        'hp': p['hp'],
        'max_hp': p['max_hp'],
    })

def spawn_item():
    global item_counter
    item_counter += 1
    item_id = f'item_{item_counter}'
    items[item_id] = {
        'x': random.randint(60, 1900),
        'y': random.randint(60, 1900),
    }
    return item_id

for _ in range(3):
    spawn_item()


# =============================================
#  AUTH ROUTES
# =============================================
@app.route('/')
def index():
    if 'username' in session:
        return redirect(url_for('homePage'))
    return redirect(url_for('login'))


@app.route('/login', methods=['GET', 'POST'])
def login():
    error = None
    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '')
        user = users_collection.find_one({'username': username})
        if user and check_password_hash(user['password_hash'], password):
            session['username'] = username
            return redirect(url_for('homePage'))
        else:
            error = 'Invalid username or password'
    return render_template('login.html', error=error)


@app.route('/signup', methods=['GET', 'POST'])
def signup():
    error = None
    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '')
        if len(username) < 3:
            error = 'Username must be at least 3 characters'
        elif len(password) < 4:
            error = 'Password must be at least 4 characters'
        elif users_collection.find_one({'username': username}):
            error = 'Username already taken'
        else:
            users_collection.insert_one({
                'username': username,
                'password_hash': generate_password_hash(password),
                'high_score': 0,
                'kills': 0,
            })
            session['username'] = username
            return redirect(url_for('homePage'))
    return render_template('signup.html', error=error)


@app.route('/logout')
def logout():
    session.pop('username', None)
    return redirect(url_for('login'))

@app.route('/homePage')
def homePage():
    if 'username' not in session:
        return redirect(url_for('login'))
    return render_template('homePage.html', username=session['username'])

# Class selection screen
@app.route('/class-select')
def classSelect():
    if 'username' not in session:
        return redirect(url_for('login'))
    return render_template('classSelect.html', username=session['username'])

# Placeholder for achievements 
@app.route('/achievements')
def achievements():
    if 'username' not in session:
        return redirect(url_for('login'))
    return redirect(url_for('homePage'))

@app.route('/game')
def game():
    if 'username' not in session:
        return redirect(url_for('login'))
    tank_class = request.args.get('tank_class', 'assault')
    if tank_class not in CLASS_STATS:
        tank_class = 'assault'
    class_stats = CLASS_STATS[tank_class]
    return render_template('game.html',
        username=session['username'],
        tank_class=tank_class,
        class_stats=class_stats,
    )


# =============================================
#  SOCKET EVENTS
# =============================================
@socketio.on('connect')
def on_connect():
    username = request.args.get('username', session.get('username', 'Guest'))
    tank_class = request.args.get('tank_class', 'assault')
    if tank_class not in CLASS_STATS:
        tank_class = 'assault'
    stats = CLASS_STATS[tank_class]
    players[request.sid] = {
        'x': random.randint(100, 1900),
        'y': random.randint(100, 1900),
        'angle': 0,
        'color': random.choice(COLORS),
        'scale': 1,
        'hp': stats['hp'],
        'max_hp': stats['max_hp'],
        'alive': True,
        'username': username,
        'tank_class': tank_class,
        'bullet_damage': stats['bullet_damage'],
    }
    emit('init', {'id': request.sid, 'players': players, 'items': items})
    emit('player_joined', {'id': request.sid, 'data': players[request.sid]}, broadcast=True, include_self=False)
    print(f'[+] {username} ({tank_class}) connected — {len(players)} players')


@socketio.on('disconnect')
def on_disconnect():
    who = players.get(request.sid, {}).get('username', '?')
    players.pop(request.sid, None)
    emit('player_left', {'id': request.sid}, broadcast=True)
    print(f'[-] {who} disconnected — {len(players)} players')


@socketio.on('move')
def on_move(data):
    if request.sid in players and players[request.sid]['alive']:
        players[request.sid]['x'] = data['x']
        players[request.sid]['y'] = data['y']
        players[request.sid]['angle'] = data['angle']
        emit('player_moved', {'id': request.sid, 'data': data}, broadcast=True, include_self=False)


@socketio.on('shoot')
def on_shoot(data):
    if request.sid in players and players[request.sid]['alive']:
        emit('player_shot', {'id': request.sid, 'data': data}, broadcast=True, include_self=False)



@socketio.on('hit')
def on_hit(data):
    target_id = data.get('target_id')
    if target_id not in players or not players[target_id]['alive']:
        return

    # Use the attacker's class-specific bullet damage
    attacker = players.get(request.sid, {})
    damage = attacker.get('bullet_damage', BULLET_DAMAGE)
    players[target_id]['hp'] -= damage
    print(f'[HIT] {attacker.get("username","?")} ({attacker.get("tank_class","?")}) dealt {damage} dmg to {players[target_id].get("username","?")} — HP: {players[target_id]["hp"]}/{players[target_id]["max_hp"]}')

    if players[target_id]['hp'] <= 0:
        players[target_id]['hp'] = 0
        players[target_id]['alive'] = False
        killer_name = players.get(request.sid, {}).get('username', '?')
        victim_name = players.get(target_id, {}).get('username', '?')

        users_collection.update_one(
            {'username': killer_name},
            {'$inc': {'kills': 1}}
        )

        socketio.emit('player_died', {
            'id': target_id,
            'killer_id': request.sid,
            'killer_name': killer_name,
            'victim_name': victim_name,
        })

        def make_respawn(tid):
            def do_respawn():
                socketio.sleep(3)
                if tid in players:
                    # Respawn with class-specific HP
                    p_class = players[tid].get('tank_class', 'assault')
                    p_stats = CLASS_STATS.get(p_class, CLASS_STATS['assault'])
                    players[tid]['hp'] = p_stats['hp']
                    players[tid]['max_hp'] = p_stats['max_hp']
                    players[tid]['alive'] = True
                    players[tid]['x'] = random.randint(100, 1900)
                    players[tid]['y'] = random.randint(100, 1900)
                    players[tid]['scale'] = 1
                    socketio.emit('player_respawned', {'id': tid, 'data': players[tid]})
            return do_respawn
        socketio.start_background_task(make_respawn(target_id))
    else:
        socketio.emit('player_damaged', {'id': target_id, 'hp': players[target_id]['hp']})


@socketio.on('pickup')
def on_pickup(data):
    item_id = data.get('item_id')
    if item_id in items:
        del items[item_id]
        if request.sid in players:
            players[request.sid]['scale'] = 3
            adjust_max_hp(request.sid, 'powerup')
        socketio.emit('item_picked', {'item_id': item_id, 'player_id': request.sid, 'scale': 3})

        def respawn():
            socketio.sleep(5)
            new_id = spawn_item()
            socketio.emit('item_spawned', {'item_id': new_id, 'data': items[new_id]})
        socketio.start_background_task(respawn)


if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    socketio.run(app, host='0.0.0.0', port=port, debug=False)
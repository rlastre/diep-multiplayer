from flask import Flask, render_template
from flask_socketio import SocketIO, emit
import random
import os

app = Flask(__name__)
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'dev-secret-change-me')
socketio = SocketIO(app, cors_allowed_origins="*", ping_timeout=10, ping_interval=5)

players = {}
items = {}
item_counter = 0

COLORS = ['#4488cc', '#cc4444', '#44cc44', '#cc8844', '#8844cc', '#44cccc']
START_HP = 100
BULLET_DAMAGE = 25


def spawn_item():
    global item_counter
    item_counter += 1
    item_id = f'item_{item_counter}'
    items[item_id] = {
        'x': random.randint(60, 740),
        'y': random.randint(60, 540),
    }
    return item_id


for _ in range(3):
    spawn_item()


@app.route('/')
def index():
    return render_template('game.html')


@socketio.on('connect')
def on_connect():
    color = random.choice(COLORS)
    players[sid()] = {
        'x': random.randint(100, 700),
        'y': random.randint(100, 500),
        'angle': 0,
        'color': color,
        'scale': 1,
        'hp': START_HP,
        'alive': True,
    }
    emit('init', {'id': sid(), 'players': players, 'items': items})
    emit('player_joined', {'id': sid(), 'data': players[sid()]}, broadcast=True, include_self=False)
    print(f'[+] {sid()} connected — {len(players)} players')


@socketio.on('disconnect')
def on_disconnect():
    players.pop(sid(), None)
    emit('player_left', {'id': sid()}, broadcast=True)
    print(f'[-] {sid()} disconnected — {len(players)} players')


@socketio.on('move')
def on_move(data):
    if sid() in players and players[sid()]['alive']:
        players[sid()]['x'] = data['x']
        players[sid()]['y'] = data['y']
        players[sid()]['angle'] = data['angle']
        emit('player_moved', {'id': sid(), 'data': data}, broadcast=True, include_self=False)


@socketio.on('shoot')
def on_shoot(data):
    if sid() in players and players[sid()]['alive']:
        emit('player_shot', {'id': sid(), 'data': data}, broadcast=True, include_self=False)


@socketio.on('hit')
def on_hit(data):
    """A player reports their bullet hit another player."""
    target_id = data.get('target_id')
    if target_id not in players:
        return
    if not players[target_id]['alive']:
        return

    players[target_id]['hp'] -= BULLET_DAMAGE

    if players[target_id]['hp'] <= 0:
        players[target_id]['hp'] = 0
        players[target_id]['alive'] = False
        # Tell everyone this player died and who killed them
        socketio.emit('player_died', {'id': target_id, 'killer_id': sid()})

        # Respawn after 3 seconds
        def respawn():
            socketio.sleep(3)
            if target_id in players:
                players[target_id]['hp'] = START_HP
                players[target_id]['alive'] = True
                players[target_id]['x'] = random.randint(100, 700)
                players[target_id]['y'] = random.randint(100, 500)
                players[target_id]['scale'] = 1
                socketio.emit('player_respawned', {'id': target_id, 'data': players[target_id]})
        socketio.start_background_task(respawn)
    else:
        # Just damage, tell everyone the new hp
        socketio.emit('player_damaged', {'id': target_id, 'hp': players[target_id]['hp']})


@socketio.on('pickup')
def on_pickup(data):
    item_id = data.get('item_id')
    if item_id in items:
        del items[item_id]
        if sid() in players:
            players[sid()]['scale'] = 3
        socketio.emit('item_picked', {'item_id': item_id, 'player_id': sid(), 'scale': 3})

        def respawn():
            socketio.sleep(5)
            new_id = spawn_item()
            socketio.emit('item_spawned', {'item_id': new_id, 'data': items[new_id]})
        socketio.start_background_task(respawn)


def sid():
    from flask import request
    return request.sid


if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    socketio.run(app, host='0.0.0.0', port=port, debug=False)
from flask import Flask, render_template
from flask_socketio import SocketIO, emit
import random

app = Flask(__name__)
app.config['SECRET_KEY'] = 'dev-secret'
socketio = SocketIO(app, cors_allowed_origins="*")

# All connected players: { sid: { x, y, angle, color } }
players = {}

# Random color for each player
COLORS = ['#4488cc', '#cc4444', '#44cc44', '#cc8844', '#8844cc', '#44cccc']


@app.route('/')
def index():
    return render_template('game.html')


@socketio.on('connect')
def on_connect():
    """New player joins — give them a spawn position and color."""
    color = random.choice(COLORS)
    players[sid()] = {
        'x': random.randint(100, 700),
        'y': random.randint(100, 500),
        'angle': 0,
        'color': color,
    }
    # Tell the new player their own info + all existing players
    emit('init', {'id': sid(), 'players': players})
    # Tell everyone else this player joined
    emit('player_joined', {'id': sid(), 'data': players[sid()]}, broadcast=True, include_self=False)
    print(f'[+] {sid()} connected — {len(players)} players')


@socketio.on('disconnect')
def on_disconnect():
    """Player leaves — remove them and tell everyone."""
    players.pop(sid(), None)
    emit('player_left', {'id': sid()}, broadcast=True)
    print(f'[-] {sid()} disconnected — {len(players)} players')


@socketio.on('move')
def on_move(data):
    """Player sends their updated position and barrel angle."""
    if sid() in players:
        players[sid()]['x'] = data['x']
        players[sid()]['y'] = data['y']
        players[sid()]['angle'] = data['angle']
        # Broadcast to everyone else
        emit('player_moved', {'id': sid(), 'data': data}, broadcast=True, include_self=False)


@socketio.on('shoot')
def on_shoot(data):
    """Player fired a bullet — relay it to everyone else."""
    emit('player_shot', {'id': sid(), 'data': data}, broadcast=True, include_self=False)


def sid():
    """Shortcut for current session id."""
    from flask import request
    return request.sid


if __name__ == '__main__':
    print('Starting server on http://localhost:5000')
    socketio.run(app, host='0.0.0.0', port=5000, debug=True)

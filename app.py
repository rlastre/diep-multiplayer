from flask import Flask, render_template
from flask_socketio import SocketIO, emit
import random
import os

app = Flask(__name__)
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'dev-secret-change-me')
socketio = SocketIO(app, cors_allowed_origins="*")

# All connected players: { sid: { x, y, angle, color } }
players = {}

COLORS = ['#4488cc', '#cc4444', '#44cc44', '#cc8844', '#8844cc', '#44cccc']


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
    }
    emit('init', {'id': sid(), 'players': players})
    emit('player_joined', {'id': sid(), 'data': players[sid()]}, broadcast=True, include_self=False)
    print(f'[+] {sid()} connected — {len(players)} players')


@socketio.on('disconnect')
def on_disconnect():
    players.pop(sid(), None)
    emit('player_left', {'id': sid()}, broadcast=True)
    print(f'[-] {sid()} disconnected — {len(players)} players')


@socketio.on('move')
def on_move(data):
    if sid() in players:
        players[sid()]['x'] = data['x']
        players[sid()]['y'] = data['y']
        players[sid()]['angle'] = data['angle']
        emit('player_moved', {'id': sid(), 'data': data}, broadcast=True, include_self=False)


@socketio.on('shoot')
def on_shoot(data):
    emit('player_shot', {'id': sid(), 'data': data}, broadcast=True, include_self=False)


def sid():
    from flask import request
    return request.sid


if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    socketio.run(app, host='0.0.0.0', port=port, debug=False)

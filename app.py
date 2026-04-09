from flask import Flask, render_template, request
from flask_socketio import SocketIO, emit
import random
import math

app = Flask(__name__)
app.config['SECRET_KEY'] = 'kmeans-edu-secret!'
socketio = SocketIO(app)

game_state = {
    'round': 1,
    'max_rounds': 8,
    'status': 'waiting',
    'data': [],
    'submissions': {}
}
users = {}

def get_distance(p1, p2):
    dist_sq = (p1['x'] - p2['x'])**2 + (p1['y'] - p2['y'])**2
    if 'z' in p1 and 'z' in p2:
        dist_sq += (p1['z'] - p2['z'])**2
    return math.sqrt(dist_sq)

def generate_fixed_data(round_num):
    data = []
    if round_num == 1:
        # 1라운드: 매우 명확한 3개 군집 (시각=3, 수학=3)
        centers = [{'x': 20, 'y': 20}, {'x': 80, 'y': 20}, {'x': 50, 'y': 80}]
        spread = 5
        for c in centers:
            for _ in range(40):
                pt = {
                    'x': c['x'] + (random.random() + random.random() - 1) * spread,
                    'y': c['y'] + (random.random() + random.random() - 1) * spread
                }
                data.append(pt)
                
    elif round_num == 2:
        # 2라운드: 시각적 직관과 알고리즘의 괴리 (시각=2, 수학=3)
        # 인간은 좌측 원 1개, 우측 길쭉한 타원 1개로 총 2개라 인식하지만,
        # 우측 타원의 Y축 분산이 극단적으로 커서 K-means는 이를 위아래 2개로 쪼갬
        
        # 1. 좌측 작고 밀집된 군집 (원형)
        for _ in range(50):
            data.append({
                'x': 35 + random.uniform(-5, 5),
                'y': 50 + random.uniform(-5, 5)
            })
            
        # 2. 우측 위아래로 매우 길게 퍼진 군집 (막대형)
        for _ in range(150):
            data.append({
                'x': 65 + random.uniform(-5, 5),
                'y': 50 + random.uniform(-35, 35) # Y축으로 길게 늘임
            })
            
    return data




def generate_random_data(round_num):
    is_3d = round_num >= 5
    diff_level = round_num - 2 if round_num <= 4 else round_num - 4
    
    configs = {
        1: {'spread': 8, 'min_dist': 45 if not is_3d else 50},
        2: {'spread': 12, 'min_dist': 30 if not is_3d else 35},
        3: {'spread': 18, 'min_dist': 18 if not is_3d else 25},
        4: {'spread': 25, 'min_dist': 10 if not is_3d else 15}
    }
    conf = configs.get(diff_level, configs[4])
    k = random.randint(3, 6)
    centers = []
    
    for _ in range(k):
        placed, retries, cur_dist = False, 0, conf['min_dist']
        while not placed and retries < 100:
            candidate = {'x': random.uniform(15, 85), 'y': random.uniform(15, 85)}
            if is_3d: candidate['z'] = random.uniform(15, 85)
            if not any(get_distance(candidate, c) < cur_dist for c in centers):
                centers.append(candidate); placed = True
            else:
                retries += 1
                if retries % 20 == 0: cur_dist *= 0.8

    data = []
    for c in centers:
        for _ in range(random.randint(30, 45)):
            pt = {'x': c['x'] + (random.random() + random.random() - 1) * conf['spread'],
                  'y': c['y'] + (random.random() + random.random() - 1) * conf['spread']}
            if is_3d: pt['z'] = c['z'] + (random.random() + random.random() - 1) * conf['spread']
            data.append(pt)
    return data

@app.route('/')
def index():
    return render_template('index.html')

@socketio.on('join')
def handle_join(data):
    nickname = data.get('nickname', '').strip()[:10]
    users[request.sid] = nickname
    emit('join_success', {'nickname': nickname, 'state': game_state})

@socketio.on('start_round')
def handle_start():
    if users.get(request.sid) != 'teacher': return
    
    if game_state['round'] <= 2:
        game_state['data'] = generate_fixed_data(game_state['round'])
    else:
        game_state['data'] = generate_random_data(game_state['round'])
        
    game_state['submissions'] = {}
    game_state['status'] = 'playing'
    emit('round_started', {'round': game_state['round'], 'data': game_state['data']}, broadcast=True)
    socketio.start_background_task(run_timer, game_state['round'])

def run_timer(round_num):
    socketio.sleep(10)
    if game_state['round'] == round_num and game_state['status'] == 'playing':
        game_state['status'] = 'result'
        socketio.emit('round_ended', {'submissions': game_state['submissions']})

@socketio.on('submit_guess')
def handle_guess(data):
    nickname = users.get(request.sid)
    if nickname and nickname != 'teacher' and game_state['status'] == 'playing':
        game_state['submissions'][nickname] = data['guess']

@socketio.on('next_round')
def handle_next():
    if users.get(request.sid) != 'teacher': return
    if game_state['round'] < game_state['max_rounds']:
        game_state['round'] += 1
        game_state['status'] = 'waiting'
        emit('prepare_next', {'round': game_state['round']}, broadcast=True)

if __name__ == '__main__':
    socketio.run(app, debug=True, host='0.0.0.0', port=5000)
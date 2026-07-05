import socket
import time
import math
import random
import pygame
import json

# ----------------------------------------------------------------------
# CONFIGURAÇÃO
# ----------------------------------------------------------------------
HOST = "0.0.0.0"
PORT = 5555

ARENA_W, ARENA_H = 900, 600
GOAL_MOUTH = 160          # altura da boca do gol (em pixels), centralizada
GOAL_DEPTH = 20

PLAYER_RADIUS = 16
BALL_RADIUS = 9

PLAYER_SPEED = 180.0      # pixels/seg quando comandado pelo joystick
WANDER_SPEED = 40.0       # pixels/seg quando "sem comando"
WANDER_RADIUS = 45.0      # raio ao redor do ponto de origem
BALL_KICK_SPEED = 420.0   # pixels/seg ao chutar
BALL_FRICTION = 0.985     # perda de velocidade por frame
BALL_MIN_SPEED = 15.0     # abaixo disso, bola para

TICK_RATE = 30
DT = 1.0 / TICK_RATE

MAX_PLAYERS = 4
CLIENT_TIMEOUT = 8.0      # segundos sem pacote -> desconecta

JOYSTICK_DEADZONE = 0.15

TEAM_COLORS = {"A": (220, 60, 60), "B": (60, 110, 220)}
TEAM_ORDER = ["A", "B", "A", "B"]  # ordem de entrada -> time

# ----------------------------------------------------------------------
# ESTADO DO JOGO
# ----------------------------------------------------------------------

class Player:
    def __init__(self, pid, team, addr, home):
        self.id = pid
        self.team = team
        self.addr = addr
        self.home = home
        self.x, self.y = home
        self.facing = (1.0, 0.0) if team == "A" else (-1.0, 0.0)
        self.has_ball = False
        self.last_seen = time.time()
        self.last_kick = 0            # pra detectar borda de subida do botão
        self.wander_target = home

    def touch(self):
        self.last_seen = time.time()


class Ball:
    def __init__(self):
        self.reset()

    def reset(self):
        self.x, self.y = ARENA_W / 2, ARENA_H / 2
        self.vx, self.vy = 0.0, 0.0
        self.owner = None


class GameState:
    def __init__(self):
        self.players = {}       # id -> Player
        self.next_id = 1
        self.ball = Ball()
        self.score = {"A": 0, "B": 0}
        self.match_active = True
        self.winner = None

    def spawn_point(self, team, index):
        """Posições iniciais espalhadas verticalmente por time."""
        slots_a = [ARENA_H * 0.3, ARENA_H * 0.7]
        slots_b = [ARENA_H * 0.3, ARENA_H * 0.7]
        x = ARENA_W * 0.22 if team == "A" else ARENA_W * 0.78
        slots = slots_a if team == "A" else slots_b
        used = [p.home[1] for p in self.players.values() if p.team == team]
        for y in slots:
            if y not in used:
                return (x, y)
        return (x, ARENA_H / 2)

    def add_player(self, addr):
        if len(self.players) >= MAX_PLAYERS:
            return None
        pid = self.next_id
        self.next_id += 1
        team = TEAM_ORDER[(pid - 1) % 4]
        home = self.spawn_point(team, pid)
        p = Player(pid, team, addr, home)
        self.players[pid] = p
        return p

    def remove_timed_out(self):
        now = time.time()
        dead = [pid for pid, p in self.players.items()
                if now - p.last_seen > CLIENT_TIMEOUT]
        for pid in dead:
            if self.ball.owner == pid:
                self.ball.owner = None
            del self.players[pid]

    def reset_match(self):
        self.ball.reset()
        self.score = {"A": 0, "B": 0}
        self.match_active = True
        self.winner = None
        for p in self.players.values():
            p.x, p.y = p.home
            p.has_ball = False


STATE = GameState()

# ----------------------------------------------------------------------
# REDE (UDP)
# ----------------------------------------------------------------------

sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
sock.bind((HOST, PORT))
sock.setblocking(False)


def send(addr, msg):
    try:
        sock.sendto(msg.encode("utf-8"), addr)
    except OSError:
        pass


def broadcast(msg):
    for p in STATE.players.values():
        send(p.addr, msg)


def poll_network():
    while True:
        try:
            data, addr = sock.recvfrom(1024)
        except BlockingIOError:
            break
        except OSError:
            break
        handle_packet(data.decode("utf-8", errors="ignore"), addr)


def handle_packet(msg, addr):
    line = msg.strip()
    if not line:
        return
    
    try:
        data = json.loads(line)
        cmd = str(data.get("cmd", "")).upper()

        if cmd == "HELLO":
            p = STATE.add_player(addr)
            if p is None:
                send(addr, json.dumps({"cmd": "FULL"}))
            else:
                send(addr, json.dumps({
                    "cmd": "WELCOME",
                    "pid": p.id,
                    "team": p.team,
                    "x": int(p.x),
                    "y": int(p.y)
                }))
        elif cmd == "INPUT":
            pid = int(data.get("pid"))
            jx = float(data.get("jx"))
            jy = float(data.get("jy"))
            kick = int(data.get("kick"))
            p = STATE.players.get(pid)
            if not p:
                return
            p.addr = addr  # atualiza endereço, caso tenha mudado
            p.touch()
            apply_input(p, jx, jy, kick)

        elif cmd == "BYE":
            try:
                pid = int(data.get("pid"))
            except (IndexError, ValueError):
                return
            if pid in STATE.players:
                if STATE.ball.owner == pid:
                    STATE.ball.owner = None
                del STATE.players[pid]
    except (json.JSONDecodeError, KeyError, TypeError, ValueError):
        pass  # ignora mensagens malformadas


def apply_input(p, jx, jy, kick):
    mag = math.hypot(jx, jy)
    if mag > JOYSTICK_DEADZONE:
        nx, ny = jx / mag, jy / mag
        p.facing = (nx, ny)
        p.x += nx * PLAYER_SPEED * DT
        p.y += ny * PLAYER_SPEED * DT
        p.wander_target = (p.x, p.y)
    else:
        wander(p)

    # chute: só dispara na borda de subida (0 -> 1) pra não ficar
    # recarregando o chute enquanto o botão fica pressionado
    if kick == 1 and p.last_kick == 0 and p.has_ball and STATE.match_active:
        STATE.ball.vx = p.facing[0] * BALL_KICK_SPEED
        STATE.ball.vy = p.facing[1] * BALL_KICK_SPEED
        STATE.ball.owner = None
        p.has_ball = False
    p.last_kick = kick

    clamp_player(p)


def wander(p):
    dx = p.wander_target[0] - p.x
    dy = p.wander_target[1] - p.y
    dist = math.hypot(dx, dy)
    if dist < 3:
        angle = random.uniform(0, 2 * math.pi)
        r = random.uniform(0, WANDER_RADIUS)
        p.wander_target = (p.home[0] + math.cos(angle) * r,
                            p.home[1] + math.sin(angle) * r)
        return
    nx, ny = dx / dist, dy / dist
    p.x += nx * WANDER_SPEED * DT
    p.y += ny * WANDER_SPEED * DT


def clamp_player(p):
    p.x = max(PLAYER_RADIUS, min(ARENA_W - PLAYER_RADIUS, p.x))
    p.y = max(PLAYER_RADIUS, min(ARENA_H - PLAYER_RADIUS, p.y))


# ----------------------------------------------------------------------
# FÍSICA DA BOLA / COLISÕES / GOL
# ----------------------------------------------------------------------

# --- Funções auxiliares para colisão contínua ---

def point_segment_distance(px, py, x1, y1, x2, y2):
    """Distância do ponto (px,py) ao segmento (x1,y1)-(x2,y2)."""
    dx = x2 - x1
    dy = y2 - y1
    if dx == 0 and dy == 0:
        return math.hypot(px - x1, py - y1)
    t = ((px - x1) * dx + (py - y1) * dy) / (dx*dx + dy*dy)
    t = max(0, min(1, t))
    proj_x = x1 + t * dx
    proj_y = y1 + t * dy
    return math.hypot(px - proj_x, py - proj_y)

def circle_segment_intersection(px, py, r, x1, y1, x2, y2):
    """
    Retorna (True, tx, ty) se o segmento intersecta o círculo,
    onde (tx, ty) é o ponto de interseção mais próximo de (x1,y1).
    Caso contrário, retorna (False, None, None).
    """
    dist = point_segment_distance(px, py, x1, y1, x2, y2)
    if dist > r:
        return False, None, None
    # Encontra o ponto de projeção
    dx = x2 - x1
    dy = y2 - y1
    if dx == 0 and dy == 0:
        return True, x1, y1
    t = ((px - x1) * dx + (py - y1) * dy) / (dx*dx + dy*dy)
    t = max(0, min(1, t))
    proj_x = x1 + t * dx
    proj_y = y1 + t * dy
    # Ponto de interseção na borda do círculo, na direção do centro
    cx, cy = px, py
    vx = proj_x - cx
    vy = proj_y - cy
    mag = math.hypot(vx, vy)
    if mag == 0:
        return True, cx + r, cy
    nx = vx / mag
    ny = vy / mag
    tx = cx + nx * r
    ty = cy + ny * r
    return True, tx, ty

# --- Atualização da bola (com colisão contínua) ---

def update_ball():
    ball = STATE.ball

    if ball.owner is not None:
        owner = STATE.players.get(ball.owner)
        if owner is None:
            ball.owner = None
        else:
            offset = PLAYER_RADIUS + BALL_RADIUS + 2
            ball.x = owner.x + owner.facing[0] * offset
            ball.y = owner.y + owner.facing[1] * offset
        return

    # Bola em trânsito
    old_x, old_y = ball.x, ball.y

    # Aplica velocidade com subpassos para precisão
    vx, vy = ball.vx, ball.vy
    speed = math.hypot(vx, vy)
    max_step = 20.0  # distância máxima por subpasso (pixels)
    steps = max(1, int(speed * DT / max_step) + 1)
    for _ in range(steps):
        sub_dt = DT / steps
        ball.x += vx * sub_dt
        ball.y += vy * sub_dt

        # Verifica colisão com jogadores usando swept collision
        collided = False
        for p in STATE.players.values():
            hit, tx, ty = circle_segment_intersection(
                p.x, p.y, PLAYER_RADIUS + BALL_RADIUS,
                old_x, old_y, ball.x, ball.y
            )
            if hit:
                ball.x, ball.y = tx, ty
                ball.vx = ball.vy = 0.0
                ball.owner = p.id
                p.has_ball = True
                for other in STATE.players.values():
                    if other.id != p.id:
                        other.has_ball = False
                collided = True
                break
        if collided:
            break
        old_x, old_y = ball.x, ball.y

    # Aplica fricção e verifica velocidade mínima
    ball.vx *= BALL_FRICTION
    ball.vy *= BALL_FRICTION
    if math.hypot(ball.vx, ball.vy) < BALL_MIN_SPEED:
        ball.vx = ball.vy = 0.0

    # Colisão com paredes e gol
    goal_top = ARENA_H / 2 - GOAL_MOUTH / 2
    goal_bottom = ARENA_H / 2 + GOAL_MOUTH / 2
    in_goal_y = goal_top <= ball.y <= goal_bottom

    if ball.y - BALL_RADIUS < 0:
        ball.y = BALL_RADIUS
        ball.vy *= -1
    elif ball.y + BALL_RADIUS > ARENA_H:
        ball.y = ARENA_H - BALL_RADIUS
        ball.vy *= -1

    if ball.x - BALL_RADIUS < 0:
        if in_goal_y:
            score_goal("B")
        else:
            ball.x = BALL_RADIUS
            ball.vx *= -1
    elif ball.x + BALL_RADIUS > ARENA_W:
        if in_goal_y:
            score_goal("A")
        else:
            ball.x = ARENA_W - BALL_RADIUS
            ball.vx *= -1

    # Verificação final (ponto) para evitar sobreposição
    if ball.owner is None:
        for p in STATE.players.values():
            dist = math.hypot(ball.x - p.x, ball.y - p.y)
            if dist < PLAYER_RADIUS + BALL_RADIUS:
                ball.owner = p.id
                ball.vx = ball.vy = 0.0
                p.has_ball = True
                for other in STATE.players.values():
                    if other.id != p.id:
                        other.has_ball = False
                break

# --- Colisão entre jogadores com transferência de posse ---

def handle_player_collisions():
    """Resolve colisões entre jogadores e transfere posse da bola se necessário."""
    players = list(STATE.players.values())
    for i in range(len(players)):
        for j in range(i+1, len(players)):
            p1 = players[i]
            p2 = players[j]
            dx = p2.x - p1.x
            dy = p2.y - p1.y
            dist = math.hypot(dx, dy)
            min_dist = PLAYER_RADIUS * 2
            if dist < min_dist and dist > 0:
                # Separar os jogadores para evitar sobreposição
                overlap = (min_dist - dist) / 2
                nx = dx / dist
                ny = dy / dist
                p1.x -= nx * overlap
                p1.y -= ny * overlap
                p2.x += nx * overlap
                p2.y += ny * overlap
                # Garantir que não saiam da arena
                clamp_player(p1)
                clamp_player(p2)

                # Transferência de posse: se um tem bola e o outro não
                if p1.has_ball and not p2.has_ball:
                    STATE.ball.owner = p2.id
                    p1.has_ball = False
                    p2.has_ball = True
                elif p2.has_ball and not p1.has_ball:
                    STATE.ball.owner = p1.id
                    p2.has_ball = False
                    p1.has_ball = True
                # Se ambos têm ou ambos não têm, não transfere

# --- Gol ---

def score_goal(team):
    STATE.score[team] += 1
    STATE.match_active = False
    STATE.winner = team
    broadcast(json.dumps({"cmd": "GOAL", "team": team}))


# ----------------------------------------------------------------------
# ENVIO DE ESTADO
# ----------------------------------------------------------------------

def build_state_message():
    ball = STATE.ball
    owner = ball.owner if ball.owner is not None else -1
    players = [
        {
            "id": p.id,
            "team": p.team,
            "x": int(p.x),
            "y": int(p.y),
            "has_ball": 1 if p.has_ball else 0,
        }
        for p in STATE.players.values()
    ]
    return json.dumps({
        "cmd": "STATE",
        "n_jogadores": len(STATE.players),
        "players": players,
        "ball": {
            "x": int(ball.x),
            "y": int(ball.y),
            "owner": owner,
        },
        "score": {
            "A": STATE.score["A"],
            "B": STATE.score["B"],
        },
        "active": 1 if STATE.match_active else 0,
    })


def broadcast_state():
    msg = build_state_message()
    broadcast(msg)


# ----------------------------------------------------------------------
# VISUAL (PYGAME)
# ----------------------------------------------------------------------

def run():
    pygame.init()
    screen = pygame.display.set_mode((ARENA_W, ARENA_H))
    pygame.display.set_caption("Servidor - Futebol ESP32")
    clock = pygame.time.Clock()
    font = pygame.font.SysFont("consolas", 22)
    small_font = pygame.font.SysFont("consolas", 16)

    running = True
    while running:
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False
            elif event.type == pygame.KEYDOWN:
                if event.key == pygame.K_r:
                    STATE.reset_match()

        poll_network()
        STATE.remove_timed_out()

        if STATE.match_active:
            update_ball()
            handle_player_collisions()   # <-- NOVO: colisão entre jogadores

        broadcast_state()
        draw(screen, font, small_font)

        clock.tick(TICK_RATE)

    pygame.quit()


def draw(screen, font, small_font):
    screen.fill((30, 120, 40))  # campo verde

    # linha central
    pygame.draw.line(screen, (255, 255, 255),
                      (ARENA_W // 2, 0), (ARENA_W // 2, ARENA_H), 2)
    pygame.draw.circle(screen, (255, 255, 255),
                        (ARENA_W // 2, ARENA_H // 2), 60, 2)

    goal_top = ARENA_H / 2 - GOAL_MOUTH / 2
    goal_bottom = ARENA_H / 2 + GOAL_MOUTH / 2

    # gols
    pygame.draw.rect(screen, (255, 255, 255),
                      (0, goal_top, GOAL_DEPTH, GOAL_MOUTH), 3)
    pygame.draw.rect(screen, (255, 255, 255),
                      (ARENA_W - GOAL_DEPTH, goal_top, GOAL_DEPTH, GOAL_MOUTH), 3)

    # jogadores
    for p in STATE.players.values():
        color = TEAM_COLORS[p.team]
        pygame.draw.circle(screen, color, (int(p.x), int(p.y)), PLAYER_RADIUS)
        if p.has_ball:
            pygame.draw.circle(screen, (255, 255, 0),
                                (int(p.x), int(p.y)), PLAYER_RADIUS + 4, 2)
        # direção que o jogador está olhando
        end = (p.x + p.facing[0] * 22, p.y + p.facing[1] * 22)
        pygame.draw.line(screen, (0, 0, 0), (p.x, p.y), end, 2)
        label = small_font.render(f"#{p.id}", True, (255, 255, 255))
        screen.blit(label, (p.x - 10, p.y - PLAYER_RADIUS - 18))

    # bola
    ball = STATE.ball
    pygame.draw.circle(screen, (255, 255, 255),
                        (int(ball.x), int(ball.y)), BALL_RADIUS)

    # placar
    score_text = font.render(
        f"Time A {STATE.score['A']}  x  {STATE.score['B']} Time B",
        True, (255, 255, 255))
    screen.blit(score_text, (ARENA_W // 2 - score_text.get_width() // 2, 10))

    conn_text = small_font.render(
        f"Jogadores conectados: {len(STATE.players)}/{MAX_PLAYERS}  "
        f"(porta UDP {PORT})", True, (230, 230, 230))
    screen.blit(conn_text, (10, ARENA_H - 24))

    if not STATE.match_active:
        msg = f"FIM DE JOGO! TIME {STATE.winner} MARCOU O GOL"
        sub = "Pressione R para reiniciar a partida"
        t1 = font.render(msg, True, (255, 230, 0))
        t2 = small_font.render(sub, True, (255, 255, 255))
        screen.blit(t1, (ARENA_W // 2 - t1.get_width() // 2, ARENA_H // 2 - 30))
        screen.blit(t2, (ARENA_W // 2 - t2.get_width() // 2, ARENA_H // 2 + 10))

    pygame.display.flip()


if __name__ == "__main__":
    print(f"Servidor escutando em UDP {HOST}:{PORT}")
    run()
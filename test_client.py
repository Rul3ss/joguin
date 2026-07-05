"""
Cliente de teste - simula um ESP32 usando o teclado.
Use as setas (ou WASD) para mover e ESPAÇO para chutar.

Rode várias instâncias (em terminais diferentes) para simular
vários jogadores conectando ao mesmo servidor.

    python test_client.py            # conecta em 127.0.0.1:5555
    python test_client.py 192.168.0.10 5555   # conecta em outro IP/porta
"""

import socket
import sys
import time
import pygame
import json

SERVER_IP = sys.argv[1] if len(sys.argv) > 1 else "127.0.0.1"
SERVER_PORT = int(sys.argv[2]) if len(sys.argv) > 2 else 5555

sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
sock.setblocking(False)
sock.settimeout(2)

sock.sendto(json.dumps({"cmd": "HELLO"}).encode(), (SERVER_IP, SERVER_PORT))
try:
    data, _ = sock.recvfrom(1024)
except socket.timeout:
    print("Servidor não respondeu. Verifique IP/porta e se o server.py está rodando.")
    sys.exit(1)

msg = data.decode()
print("Servidor respondeu:", msg)
data = json.loads(msg)
if data.get("cmd") != "WELCOME":
    print("Não foi possível entrar (talvez a partida esteja cheia).")
    sys.exit(1)

my_id = data.get("pid")
my_team = data.get("team")
print(f"Conectado! ID={my_id} Time={my_team}")

sock.setblocking(False)

pygame.init()
screen = pygame.display.set_mode((300, 150))
pygame.display.set_caption(f"Cliente de teste - jogador {my_id} (Time {my_team})")
font = pygame.font.SysFont("consolas", 18)
clock = pygame.time.Clock()
state_text = "Aguardando STATE..."

running = True
while running:
    for event in pygame.event.get():
        if event.type == pygame.QUIT:
            running = False

    try:
        while True:
            msg, _ = sock.recvfrom(2048)
            data = json.loads(msg.decode())
            cmd = str(data.get("cmd", "")).upper()
            if cmd == "STATE":
                state_text = (
                    f"STATE: {data.get('n_jogadores', 0)} jogadores | "
                    f"Bola=({data.get('ball', {}).get('x', 0)}, {data.get('ball', {}).get('y', 0)}) | "
                    f"Placar {data.get('score', {}).get('A', 0)} x {data.get('score', {}).get('B', 0)}"
                )
            elif cmd == "GOAL":
                state_text = f"GOAL: time {data.get('team')} marcou"
            else:
                state_text = state_text
    except BlockingIOError:
        pass
    except (json.JSONDecodeError, UnicodeDecodeError):
        pass

    keys = pygame.key.get_pressed()
    jx = 0.0
    jy = 0.0
    if keys[pygame.K_LEFT] or keys[pygame.K_a]:
        jx -= 1.0
    if keys[pygame.K_RIGHT] or keys[pygame.K_d]:
        jx += 1.0
    if keys[pygame.K_UP] or keys[pygame.K_w]:
        jy -= 1.0
    if keys[pygame.K_DOWN] or keys[pygame.K_s]:
        jy += 1.0
    kick = 1 if keys[pygame.K_SPACE] else 0

    packet = json.dumps({
        "cmd": "INPUT",
        "pid": my_id,
        "jx": jx,
        "jy": jy,
        "kick": kick
    })
    sock.sendto(packet.encode(), (SERVER_IP, SERVER_PORT))

    screen.fill((20, 20, 20))
    lines = [
        f"Jogador #{my_id}  Time {my_team}",
        f"Setas/WASD = mover | ESPAÇO = chutar",
        f"jx={jx:.1f} jy={jy:.1f} kick={kick}",
        state_text,
    ]
    for i, line in enumerate(lines):
        screen.blit(font.render(line, True, (255, 255, 255)), (10, 10 + i * 25))
    pygame.display.flip()

    clock.tick(30)

sock.sendto(json.dumps({"cmd": "BYE", "pid": my_id}).encode(), (SERVER_IP, SERVER_PORT))
pygame.quit()

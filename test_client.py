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

SERVER_IP = sys.argv[1] if len(sys.argv) > 1 else "127.0.0.1"
SERVER_PORT = int(sys.argv[2]) if len(sys.argv) > 2 else 5555

sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
sock.setblocking(False)
sock.settimeout(2)

sock.sendto(b"HELLO", (SERVER_IP, SERVER_PORT))
try:
    data, _ = sock.recvfrom(1024)
except socket.timeout:
    print("Servidor não respondeu. Verifique IP/porta e se o server.py está rodando.")
    sys.exit(1)

msg = data.decode()
print("Servidor respondeu:", msg)
parts = msg.split(",")
if parts[0] != "WELCOME":
    print("Não foi possível entrar (talvez a partida esteja cheia).")
    sys.exit(1)

my_id = int(parts[1])
my_team = parts[2]
print(f"Conectado! ID={my_id} Time={my_team}")

sock.setblocking(False)

pygame.init()
screen = pygame.display.set_mode((300, 150))
pygame.display.set_caption(f"Cliente de teste - jogador {my_id} (Time {my_team})")
font = pygame.font.SysFont("consolas", 18)
clock = pygame.time.Clock()

running = True
while running:
    for event in pygame.event.get():
        if event.type == pygame.QUIT:
            running = False

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

    packet = f"INPUT,{my_id},{jx},{jy},{kick}"
    sock.sendto(packet.encode(), (SERVER_IP, SERVER_PORT))

    screen.fill((20, 20, 20))
    lines = [
        f"Jogador #{my_id}  Time {my_team}",
        f"Setas/WASD = mover | ESPAÇO = chutar",
        f"jx={jx:.1f} jy={jy:.1f} kick={kick}",
    ]
    for i, line in enumerate(lines):
        screen.blit(font.render(line, True, (255, 255, 255)), (10, 10 + i * 25))
    pygame.display.flip()

    clock.tick(30)

sock.sendto(f"BYE,{my_id}".encode(), (SERVER_IP, SERVER_PORT))
pygame.quit()

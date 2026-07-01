# Servidor de Futebol ESP32 — Como rodar

## 1. Instalar e rodar

```bash
cd futebol-server
pip install -r requirements.txt
python server.py
```

Abre uma janela mostrando a arena (campo, gols, placar). O servidor fica
escutando UDP na porta **5555** em todas as interfaces de rede (`0.0.0.0`).

Pressione **R** na janela para reiniciar a partida (útil pra testar
várias vezes sem reabrir o programa).

## 2. Testar sem hardware (antes de mexer no ESP32)

Em outro terminal:
```bash
python test_client.py
```
Use as setas/WASD para mover e ESPAÇO pra chutar. Você pode abrir várias
janelas desse cliente de teste (até 4) pra simular vários jogadores
entrando e ver a distribuição automática de times funcionando.

Se o servidor estiver rodando em outra máquina/IP:
```bash
python test_client.py 192.168.0.42 5555
```

## 3. Como deixar acessível para os ESP32

O ESP32 só precisa conseguir mandar pacotes UDP para `IP_DO_SERVIDOR:5555`.
Existem 3 níveis, do mais simples ao mais "de verdade online":

### Opção A — Mesma rede Wi-Fi (recomendado para a apresentação)
A forma mais simples e mais confiável para demonstração em sala:
1. Ligue um notebook/PC (rodando `server.py`) e os ESP32 na **mesma rede
   Wi-Fi** (pode ser o hotspot do celular, por exemplo).
2. Descubra o IP local da máquina do servidor:
   - Windows: `ipconfig` (campo "Endereço IPv4")
   - Linux/Mac: `ip addr` ou `ifconfig`
3. No firmware do ESP32, aponte para esse IP (ex.: `192.168.1.23`) na
   porta `5555`.

Isso já é "rede", não precisa de internet de verdade — e evita qualquer
problema de firewall/roteador. Pra maioria dos projetos de curso é o
suficiente e o mais estável no dia da apresentação.

### Opção B — Internet de verdade, sem VPS (túnel temporário)
Se quiser que o servidor rodando no seu notebook seja alcançável de fora
da sua rede local sem mexer no roteador, dá pra usar um túnel UDP
temporário, por exemplo com **ngrok** (`ngrok udp 5555`) ou **Tailscale**
(cria uma rede virtual privada entre suas máquinas e os ESP32, se eles
também rodarem um cliente — mais indicado se você tiver outro
computador/roteador Tailscale fazendo de intermediário, já que ESP32 puro
não roda o cliente Tailscale).

### Opção C — VPS na nuvem (hospedagem "de verdade")
Para o servidor ficar disponível 24/7 num IP público fixo:
1. Suba uma VPS pequena (Oracle Cloud Free Tier, AWS EC2 free tier, ou
   qualquer provedor barato).
2. Copie os arquivos do servidor pra lá e rode `python server.py`.
3. Libere a porta UDP 5555 no firewall da VPS (ex.: `ufw allow 5555/udp`
   no Ubuntu) e no security group, se for AWS/Oracle.
4. No firmware do ESP32, aponte para o **IP público** da VPS.

**Atenção:** a maioria das VPS não tem monitor/tela conectado (é
"headless"). O jeito atual do `server.py` usa Pygame pra abrir uma janela,
o que **não funciona direto numa VPS sem interface gráfica**. Duas saídas
se você for por esse caminho:
- Rodar a lógica do servidor na VPS *sem* a parte visual (dá pra separar
  fácil — a física e o protocolo já estão isolados das funções `run()`/
  `draw()`), e abrir a visualização só localmente no seu notebook
  enquanto testa.
- Ou trocar o Pygame por uma visualização web (uma paginazinha HTML com
  `<canvas>` atualizada via WebSocket) que qualquer navegador acessa
  remotamente — se quiser, eu monto essa versão depois.

Para o projeto da faculdade, a **Opção A** costuma ser a mais tranquila:
zero configuração de rede, zero dependência de internet, e o Pygame
mostra tudo em tempo real durante a apresentação.

## 4. Arquivos do projeto

- `server.py` — servidor completo (física, times, colisões, gol, rede, visual).
- `test_client.py` — cliente de teste com teclado, pra validar sem ESP32.
- `protocolo.md` — especificação do protocolo de comunicação (pra colar
  no relatório coletivo da turma).
- `requirements.txt` — dependência (`pygame`).

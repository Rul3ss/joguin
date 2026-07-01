# Protocolo de Comunicação — Servidor ↔ ESP32

Transporte: **UDP**, mensagens em texto puro (sem JSON), campos separados por vírgula.
Isso deixa o parsing trivial no ESP32 com `sscanf`/`sprintf`, sem precisar de nenhuma
biblioteca extra.

Porta padrão do servidor: **5555**

## 1. Conexão

**ESP32 → Servidor**
```
HELLO
```

**Servidor → ESP32** (sucesso)
```
WELCOME,<id>,<time>,<x>,<y>
```
Exemplo: `WELCOME,1,A,198,180`
- `id`: identificador único do jogador, atribuído pelo servidor (o ESP32 deve
  guardar esse valor e usá-lo em todas as mensagens seguintes).
- `time`: `"A"` ou `"B"`.
- `x,y`: posição inicial na arena.

**Servidor → ESP32** (partida cheia)
```
FULL
```

## 2. Envio de comandos (joystick + botão)

**ESP32 → Servidor**, enviado continuamente (ex.: a cada 30–50 ms):
```
INPUT,<id>,<jx>,<jy>,<kick>
```
- `id`: id recebido no `WELCOME`.
- `jx`, `jy`: eixos do joystick normalizados entre **-1.0 e 1.0**
  (0,0 = joystick centralizado/parado).
- `kick`: `1` se o botão de chute está pressionado, `0` caso contrário.

Exemplo: `INPUT,1,0.80,-0.20,0`

> O servidor detecta a *borda de subida* do botão (0→1) para disparar o chute
> apenas uma vez por toque, então o ESP32 pode simplesmente mandar o estado
> atual do botão a cada pacote, sem se preocupar em "debounciar" o chute.

## 3. Estado da partida (broadcast)

**Servidor → todos os ESP32 conectados**, a cada tick (~30 vezes/seg):
```
STATE,<n_jogadores>;<id>,<time>,<x>,<y>,<com_bola>;...;BALL,<bx>,<by>,<owner>;SCORE,<a>,<b>;ACTIVE,<0ou1>
```
Exemplo com 2 jogadores:
```
STATE,2;1,A,220,180,1;2,B,700,300,0;BALL,236,180,1;SCORE,0,0;ACTIVE,1
```
- Lista de jogadores separada por `;`, cada um no formato
  `id,time,x,y,com_bola` (`com_bola` = 1 ou 0).
- `BALL,x,y,owner`: posição da bola e id do dono (`-1` se estiver livre).
- `SCORE,a,b`: placar atual.
- `ACTIVE`: `1` enquanto a partida está rolando, `0` depois do gol.

O ESP32 não *precisa* processar essa mensagem para jogar (o servidor é
autoritativo), mas é útil se quiser, por exemplo, acender um LED quando
está com a posse de bola.

## 4. Fim de partida

**Servidor → todos**, no momento do gol:
```
GOAL,<time_que_marcou>
```
Exemplo: `GOAL,A`

## 5. Desconexão

**ESP32 → Servidor**, ao desligar/reiniciar de forma limpa:
```
BYE,<id>
```

O servidor também remove automaticamente jogadores que ficarem **8 segundos
sem enviar `INPUT`** (timeout), tratando como desconexão.

## Resumo dos tipos de mensagem

| Direção            | Mensagem                          | Quando                      |
|--------------------|------------------------------------|------------------------------|
| ESP32 → Servidor    | `HELLO`                           | ao iniciar/conectar          |
| Servidor → ESP32    | `WELCOME,id,time,x,y` ou `FULL`   | resposta ao HELLO             |
| ESP32 → Servidor    | `INPUT,id,jx,jy,kick`             | continuamente (loop)          |
| Servidor → todos    | `STATE,...`                       | a cada tick (~30/s)           |
| Servidor → todos    | `GOAL,time`                       | quando sai um gol             |
| ESP32 → Servidor    | `BYE,id`                          | ao desconectar de propósito   |

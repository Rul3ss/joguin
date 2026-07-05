# Protocolo de Comunicação — Servidor ↔ ESP32

Transporte: **UDP**, mensagens em **JSON**.
Cada pacote contém um objeto JSON serializado em UTF-8, com o campo `cmd`
indicando o tipo da mensagem.

Porta padrão do servidor: **5555**

## 1. Conexão

**ESP32 → Servidor**
```json
{"cmd": "HELLO"}
```

**Servidor → ESP32** (sucesso)
```json
{"cmd": "WELCOME", "pid": 1, "team": "A", "x": 198, "y": 180}
```
- `pid`: identificador único do jogador, atribuído pelo servidor.
- `team`: time do jogador, `"A"` ou `"B"`.
- `x`, `y`: posição inicial na arena.

**Servidor → ESP32** (partida cheia)
```json
{"cmd": "FULL"}
```

## 2. Envio de comandos (joystick + botão)

**ESP32 → Servidor**, enviado continuamente (ex.: a cada 30–50 ms):
```json
{"cmd": "INPUT", "pid": 1, "jx": 0.8, "jy": -0.2, "kick": 0}
```
- `pid`: id recebido no `WELCOME`.
- `jx`, `jy`: eixos do joystick normalizados entre `-1.0` e `1.0`
  (`0,0` = joystick centralizado/parado).
- `kick`: `1` se o botão de chute está pressionado, `0` caso contrário.

Exemplo: `{"cmd": "INPUT", "pid": 1, "jx": 0.8, "jy": -0.2, "kick": 0}`

> O servidor detecta a borda de subida do botão (`0 -> 1`) para disparar o chute
> apenas uma vez por toque, então o ESP32 pode simplesmente mandar o estado
> atual do botão a cada pacote, sem se preocupar em debounciar o chute.

## 3. Estado da partida (broadcast)

**Servidor → todos os ESP32 conectados**, a cada tick (~30 vezes/seg):
```json
{
  "cmd": "STATE",
  "n_jogadores": 2,
  "players": [
    {"id": 1, "team": "A", "x": 220, "y": 180, "has_ball": 1},
    {"id": 2, "team": "B", "x": 700, "y": 300, "has_ball": 0}
  ],
  "ball": {"x": 236, "y": 180, "owner": 1},
  "score": {"A": 0, "B": 0},
  "active": 1
}
```
- `n_jogadores`: quantidade de jogadores conectados.
- `players`: lista com `id`, `team`, `x`, `y` e `has_ball`.
- `ball`: posição da bola e `owner` (`-1` se estiver livre).
- `score`: objeto com os placares de `A` e `B`.
- `active`: `1` enquanto a partida está rolando, `0` após o gol.

O ESP32 não *precisa* processar essa mensagem para jogar (o servidor é
autoritativo), mas é útil se quiser, por exemplo, acender um LED quando
está com a posse de bola.

## 4. Fim de partida

**Servidor → todos**, no momento do gol:
```json
{"cmd": "GOAL", "team": "A"}
```

Exemplo: `{"cmd": "GOAL", "team": "A"}`

## 5. Desconexão

**ESP32 → Servidor**, ao desligar/reiniciar de forma limpa:
```json
{"cmd": "BYE", "pid": 1}
```

O servidor também remove automaticamente jogadores que ficarem **8 segundos
sem enviar `INPUT`** (timeout), tratando como desconexão.

## Resumo dos tipos de mensagem

| Direção            | Mensagem JSON                                      | Quando                    |
|--------------------|-----------------------------------------------------|---------------------------|
| ESP32 → Servidor   | `{"cmd": "HELLO"}`                               | ao iniciar/conectar       |
| Servidor → ESP32   | `{"cmd": "WELCOME", ...}` ou `{"cmd": "FULL"}` | resposta ao `HELLO`       |
| ESP32 → Servidor   | `{"cmd": "INPUT", ...}`                          | continuamente (loop)      |
| Servidor → todos   | `{"cmd": "STATE", ...}`                          | a cada tick (~30/s)       |
| Servidor → todos   | `{"cmd": "GOAL", "team": "A"}`                | quando sai um gol         |
| ESP32 → Servidor   | `{"cmd": "BYE", "pid": 1}`                      | ao desconectar de propósito |

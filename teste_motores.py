#!/usr/bin/env python3
"""
teste_motores.py - bancada de teste: 4x JGB37-520 (encoder Hall) + 2x MD10C
                   no Raspberry Pi 3.

RODE SEMPRE COM AS RODAS NO AR.

Antes:  sudo apt install pigpio python3-pigpio
        sudo systemctl enable --now pigpiod
        (nao use a saida de audio analogica do Pi: ela divide o periferico
         de PWM com GPIO12/13)

Uso:
    python3 teste_motores.py encoder    # 1. gira a roda a mao: mede contagens/volta
    python3 teste_motores.py direcao    # 2. cada lado sozinho, frente e re
    python3 teste_motores.py varredura  # 3. duty de 0 ao teto: zona morta e rpm max
    python3 teste_motores.py degrau     # 4. resposta ao degrau: constante de tempo
    python3 teste_motores.py tudo       # 1 a 4 em sequencia + resumo
    python3 teste_motores.py girar      # liga os 4 motores por 3 s (30% de duty)
        opcoes: --duty 40  --tempo 5  --re
    python3 teste_motores.py parar      # emergencia: zera o PWM dos dois lados

O PWM por hardware e gerado pelo pigpiod, nao por este script. Se o script
morrer sem passar pelo 'finally' (kill -9, travamento), os motores CONTINUAM
girando. Para parar na mao:
    python3 teste_motores.py parar        ou        pigs hp 12 0 0; pigs hp 13 0 0
"""

import argparse
import csv
import os
import signal
import sys
import threading
import time

import pigpio

# ============================ configuracao =================================

# --- pinos (numeracao BCM) ---
MOTOR = {
    "esq": {"pwm": 12, "dir": 17},   # pinos fisicos 32 e 11
    "dir": {"pwm": 13, "dir": 22},   # pinos fisicos 33 e 15
}
ENCODER = {
    "esq": {"a": 23, "b": 24},       # verde e amarelo, pinos fisicos 16 e 18
    "dir": {"a": 25, "b": 5},        # verde e amarelo, pinos fisicos 22 e 29
}

# --- inversoes: o teste te diz quais trocar ---
INVERTER_MOTOR = {"esq": False, "dir": False}
INVERTER_ENCODER = {"esq": False, "dir": False}

# --- eletrica ---
PWM_HZ = 10000
V_MOTOR_NOMINAL = 12.0
V_BATERIA_MAX = 16.8          # 4S cheia. Se trocar para 3S, use 12.6
DUTY_TETO = min(1.0, V_MOTOR_NOMINAL / V_BATERIA_MAX)   # 0,714 com 4S

# --- encoder ---
PPR_MOTOR = 11                # datasheet: pulsos por volta do EIXO DO MOTOR, por canal
CPR_SAIDA = None              # contagens (x4) por volta da RODA. None = medir no teste 1
GLITCH_US = 0                 # filtro do pigpio; o encoder ja entrega sinal tratado

# --- tempos e niveis dos testes ---
T_RAMPA = 0.4
FRACAO_DIRECAO = 0.4          # teste 2 roda a 40% do teto
T_SEGURA_DIRECAO = 1.5
DUTY_PASSO = 0.05             # teste 3 sobe de 5 em 5 %
T_ASSENTA = 1.0
T_JANELA = 0.5
FRACAO_DEGRAU = 0.6           # teste 4: degrau de 0 a 60% do teto
T_DEGRAU = 2.0

# --- protecao contra motor travado ---
PROTECAO_TRAVAMENTO = True
TRAVAMENTO_DUTY = 0.5 * DUTY_TETO   # acima disso o motor TEM que girar
TRAVAMENTO_T = 1.0                  # parado por mais que isso = aborta tudo
TRAVAMENTO_MIN_CONTAGENS = 5

PASTA_RESULTADOS = "resultados"
LADOS = ("esq", "dir")
NOME = {"esq": "ESQUERDO", "dir": "DIREITO"}

# ===========================================================================


def _outro(lado):
    return "dir" if lado == "esq" else "esq"


# Decodificacao de quadratura x4. Estado = (A << 1) | B.
# Sentido positivo (A adiantado de B): 00 -> 10 -> 11 -> 01 -> 00
# Indice = (estado_anterior << 2) | estado_novo ; None = pulou um estado.
_TRANSICAO = (
    0, -1, +1, None,
    +1, 0, None, -1,
    -1, None, 0, +1,
    None, +1, -1, 0,
)


class EncoderQuadratura:
    """Conta as 4 bordas por ciclo dos canais A e B (resolucao x4)."""

    def __init__(self, pi, a, b, inverter=False):
        self.pi = pi
        self.a, self.b = a, b
        self.sinal = -1 if inverter else 1
        for g in (a, b):
            pi.set_mode(g, pigpio.INPUT)
            pi.set_pull_up_down(g, pigpio.PUD_OFF)   # pull-up ja existe na placa
            if GLITCH_US:
                pi.set_glitch_filter(g, GLITCH_US)
        self._nivel_a = pi.read(a)
        self._nivel_b = pi.read(b)
        self._estado = (self._nivel_a << 1) | self._nivel_b
        self._contagem = 0
        self.invalidas = 0
        self.eventos = 0
        self._cbs = [
            pi.callback(a, pigpio.EITHER_EDGE, self._borda),
            pi.callback(b, pigpio.EITHER_EDGE, self._borda),
        ]

    # roda na thread de callbacks do pigpio (uma so, em ordem)
    def _borda(self, gpio, nivel, tick):
        if nivel > 1:                       # 2 = timeout de watchdog
            return
        if gpio == self.a:
            self._nivel_a = nivel
        else:
            self._nivel_b = nivel
        novo = (self._nivel_a << 1) | self._nivel_b
        passo = _TRANSICAO[(self._estado << 2) | novo]
        self._estado = novo
        self.eventos += 1
        if passo is None:
            self.invalidas += 1
        else:
            self._contagem += passo

    @property
    def posicao(self):
        return self.sinal * self._contagem

    def leitura(self):
        return self.posicao, self.invalidas, self.eventos

    def fechar(self):
        for cb in self._cbs:
            cb.cancel()
        if GLITCH_US:
            for g in (self.a, self.b):
                self.pi.set_glitch_filter(g, 0)


class MotorMD10C:
    """Um MD10C: DIR define o sentido, PWM por hardware define a tensao media."""

    def __init__(self, pi, pwm, dir_, inverter=False):
        self.pi = pi
        self.pino_pwm, self.pino_dir = pwm, dir_
        self.inverter = inverter
        self.duty = 0.0
        pi.set_mode(dir_, pigpio.OUTPUT)
        pi.write(dir_, 0)
        self._pwm(0.0)

    def _pwm(self, fracao):
        self.pi.hardware_PWM(self.pino_pwm, PWM_HZ, int(round(fracao * 1_000_000)))

    def aplicar(self, duty):
        """duty = fracao da tensao da bateria, com sinal. SEMPRE limitado ao teto."""
        duty = max(-DUTY_TETO, min(DUTY_TETO, float(duty)))
        frente = duty >= 0
        if self.inverter:
            frente = not frente
        self.pi.write(self.pino_dir, 1 if frente else 0)
        self._pwm(abs(duty))
        self.duty = duty

    def parar(self):
        self._pwm(0.0)
        self.duty = 0.0

    def desligar(self):
        self.parar()
        self.pi.hardware_PWM(self.pino_pwm, 0, 0)
        self.pi.write(self.pino_dir, 0)


class Travamento(Exception):
    pass


class Bancada:
    def __init__(self):
        self.pi = pigpio.pi()
        if not self.pi.connected:
            raise SystemExit("pigpiod nao esta rodando: sudo systemctl start pigpiod")
        self.motor, self.enc = {}, {}
        try:
            for lado in LADOS:
                self.motor[lado] = MotorMD10C(self.pi, MOTOR[lado]["pwm"],
                                              MOTOR[lado]["dir"], INVERTER_MOTOR[lado])
            for lado in LADOS:
                self.enc[lado] = EncoderQuadratura(self.pi, ENCODER[lado]["a"],
                                                   ENCODER[lado]["b"], INVERTER_ENCODER[lado])
        except Exception:
            self.fechar()
            raise
        self.cpr = {lado: CPR_SAIDA for lado in LADOS}
        self.inv_motor = dict(INVERTER_MOTOR)
        self.inv_enc = dict(INVERTER_ENCODER)
        self.resultados = {}
        self.falhas = []
        agora = time.monotonic()
        self._ref = {l: (self.enc[l].posicao, agora) for l in LADOS}

    # ---------------- controle ----------------

    def parar_tudo(self):
        for m in self.motor.values():
            m.parar()

    def fechar(self):
        for m in self.motor.values():
            try:
                m.desligar()
            except Exception:
                pass
        for e in self.enc.values():
            try:
                e.fechar()
            except Exception:
                pass
        try:
            self.pi.stop()
        except Exception:
            pass

    def inverter_motor(self, lado):
        self.motor[lado].inverter = not self.motor[lado].inverter
        self.inv_motor[lado] = self.motor[lado].inverter

    def inverter_encoder(self, lado):
        self.enc[lado].sinal *= -1
        self.inv_enc[lado] = not self.inv_enc[lado]

    def rampa(self, alvos, segundos=T_RAMPA):
        """Leva os lados em 'alvos' (lado -> duty) ate o alvo, linearmente.
        Se algum lado troca de sentido, passa por zero antes."""
        if any(self.motor[l].duty * alvos[l] < 0 for l in alvos):
            self.rampa({l: 0.0 for l in alvos}, segundos / 2)
            time.sleep(0.2)
        inicio = {l: self.motor[l].duty for l in alvos}
        n = max(1, int(segundos / 0.02))
        for i in range(1, n + 1):
            for l in alvos:
                self.motor[l].aplicar(inicio[l] + (alvos[l] - inicio[l]) * i / n)
            time.sleep(segundos / n)

    def vigiar(self):
        """Aborta se algum motor com duty alto nao se mexe ha TRAVAMENTO_T s."""
        if not PROTECAO_TRAVAMENTO:
            return
        agora = time.monotonic()
        for l in LADOS:
            pos = self.enc[l].posicao
            p0, t0 = self._ref[l]
            if (abs(self.motor[l].duty) < TRAVAMENTO_DUTY
                    or abs(pos - p0) >= TRAVAMENTO_MIN_CONTAGENS):
                self._ref[l] = (pos, agora)
            elif agora - t0 > TRAVAMENTO_T:
                self.parar_tudo()
                raise Travamento(l)

    def segurar(self, segundos):
        fim = time.monotonic() + segundos
        while True:
            restante = fim - time.monotonic()
            if restante <= 0:
                return
            time.sleep(min(0.05, restante))
            self.vigiar()

    def medir(self, janela=T_JANELA):
        """Mede os dois lados ao mesmo tempo durante 'janela' segundos."""
        a = {l: self.enc[l].leitura() for l in LADOS}
        t0 = time.monotonic()
        self.segurar(janela)
        d = {l: self.enc[l].leitura() for l in LADOS}
        dt = time.monotonic() - t0
        out = {}
        for l in LADOS:
            cont = d[l][0] - a[l][0]
            cpr = self.cpr[l]
            out[l] = {
                "contagens": cont,
                "rpm": cont / cpr / dt * 60.0 if cpr else None,
                "invalidas": d[l][1] - a[l][1],
                "eventos_s": (d[l][2] - a[l][2]) / dt,
            }
        return out


# ---------------- entrada/saida ----------------

def titulo(texto):
    print("\n" + "=" * 64 + "\n" + texto + "\n" + "=" * 64)


def perguntar(prompt, opcoes, padrao=None):
    while True:
        r = input(prompt).strip().lower()
        if not r and padrao:
            return padrao
        if r and r[0] in opcoes:
            return r[0]
        print(f"   responda com: {'/'.join(opcoes)}")


def perguntar_inteiro(prompt, padrao):
    r = input(prompt).strip()
    try:
        v = int(r)
        return v if v > 0 else padrao
    except ValueError:
        return padrao


def esperar_enter_mostrando(b, mensagem):
    """Mostra as contagens ao vivo enquanto espera o Enter."""
    print(mensagem)
    parar = threading.Event()

    def mostra():
        while not parar.is_set():
            sys.stdout.write(f"\r    contagem  esq: {b.enc['esq'].posicao:+9d}"
                             f"   dir: {b.enc['dir'].posicao:+9d}   (Enter quando terminar) ")
            sys.stdout.flush()
            parar.wait(0.1)

    th = threading.Thread(target=mostra, daemon=True)
    th.start()
    try:
        input()
    finally:
        parar.set()
        th.join()
        print()


def salvar_csv(nome, cabecalho, linhas):
    os.makedirs(PASTA_RESULTADOS, exist_ok=True)
    caminho = os.path.join(PASTA_RESULTADOS, f"{nome}_{time.strftime('%Y%m%d_%H%M%S')}.csv")
    with open(caminho, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(cabecalho)
        w.writerows(linhas)
    print(f"\n  dados salvos em {caminho}")


def exigir_cpr(b):
    if not all(b.cpr[l] for l in LADOS):
        raise SystemExit("\nSem contagens por volta: rode o teste 'encoder' antes "
                         "ou preencha CPR_SAIDA na configuracao.")


# ---------------- TESTE 1: encoder ----------------

def teste_encoder(b):
    titulo("TESTE 1/4 - ENCODER  (motores desligados, roda girada a mao)")
    b.parar_tudo()
    print("Mede quantas contagens o encoder da por volta da RODA e confere\n"
          "se a contagem SOBE quando a roda gira no sentido de andar para frente.")
    voltas = perguntar_inteiro(
        "Quantas voltas voce vai girar cada roda? (3 ou mais = mais preciso) [3]: ", 3)
    medidas = {}
    for lado in LADOS:
        outro = _outro(lado)
        print(f"\nLado {NOME[lado]}: use a roda cujo encoder esta ligado. "
              "Faca uma marca de fita na roda e outra no chassi.")
        antes = {l: b.enc[l].leitura() for l in LADOS}
        esperar_enter_mostrando(
            b, f"Gire a roda do lado {NOME[lado]} exatamente {voltas} volta(s) PARA FRENTE.")
        depois = {l: b.enc[l].leitura() for l in LADOS}
        d = depois[lado][0] - antes[lado][0]
        cruz = depois[outro][0] - antes[outro][0]
        inval = depois[lado][1] - antes[lado][1]
        ev = depois[lado][2] - antes[lado][2]
        print(f"  contagens: {d:+d}  ({abs(d) / voltas:.1f} por volta)   "
              f"transicoes invalidas: {inval}")

        if abs(d) < 20 * voltas:
            print("  ERRO: o encoder quase nao contou. Confira: azul no 3V3, preto no GND,\n"
                  f"  verde no GPIO{ENCODER[lado]['a']} e amarelo no GPIO{ENCODER[lado]['b']}.")
            b.falhas.append(f"encoder {lado} nao conta")
            continue
        if abs(cruz) > 0.1 * abs(d):
            print(f"  AVISO: o encoder do lado {NOME[outro]} tambem contou ({cruz:+d}).\n"
                  "  Os fios de encoder dos dois lados provavelmente estao trocados.")
            b.falhas.append(f"encoder {lado}: fios trocados com o outro lado")
        if d < 0:
            b.inverter_encoder(lado)
            print("  Contagem NEGATIVA girando para frente: encoder deste lado invertido.\n"
                  f"  -> INVERTER_ENCODER['{lado}'] = {b.inv_enc[lado]}  "
                  "(ou troque verde <-> amarelo). Ja corrigido nesta execucao.")
        if ev and inval > 0.005 * ev:
            print("  AVISO: muitas transicoes invalidas: ruido no sinal. Afaste os fios\n"
                  "  do encoder dos fios de motor e confira os 100 nF nos motores.")
        medidas[lado] = abs(d) / voltas

    if not medidas:
        return
    vals = list(medidas.values())
    cpr = sum(vals) / len(vals)
    if len(vals) == 2 and abs(vals[0] - vals[1]) / cpr > 0.03:
        print(f"\n  AVISO: os lados diferem {abs(vals[0] - vals[1]) / cpr * 100:.1f}%. "
              "Como os motores sao iguais,\n  a volta a mao nao foi exata: "
              "repita com mais voltas.")
    for l in LADOS:
        b.cpr[l] = cpr
    b.resultados["CPR_SAIDA"] = round(cpr)
    print(f"\n  CPR medido: {cpr:.0f} contagens por volta da roda"
          f"  ->  reducao implicita ~1:{cpr / (4 * PPR_MOTOR):.1f}")


# ---------------- TESTE 2: sentido ----------------

def teste_direcao(b):
    titulo("TESTE 2/4 - SENTIDO DE GIRO  (um lado por vez, frente e re)")
    duty = FRACAO_DIRECAO * DUTY_TETO
    print(f"Duty de teste: {duty * 100:.0f}%  (~{duty * V_BATERIA_MAX:.1f} V medios com bateria cheia)")

    for lado in LADOS:
        outro = _outro(lado)
        falhas_antes = len(b.falhas)
        # 1) roda FRENTE e RE sem corrigir nada no meio, anotando o que aconteceu
        fases = []
        for sentido in (+1, -1):
            nome = "FRENTE" if sentido > 0 else "RE"
            print(f"\n  {NOME[lado]}: comandando {nome} por {T_SEGURA_DIRECAO:.1f} s ...")
            antes = {l: b.enc[l].posicao for l in LADOS}
            b.rampa({lado: sentido * duty})
            b.segurar(T_SEGURA_DIRECAO)
            b.rampa({lado: 0.0})
            time.sleep(0.5)
            d = b.enc[lado].posicao - antes[lado]
            cruz = b.enc[outro].posicao - antes[outro]
            print(f"  encoder {lado}: {d:+d}   encoder {outro}: {cruz:+d}")
            r = perguntar(f"  As rodas do lado {NOME[lado]} giraram para "
                          "[f]rente, [r]e, ou [n]ao giraram? ", "frn")
            if r == "n":
                if abs(d) > 50:
                    print("  Estranho: o encoder contou mas voce nao viu girar. "
                          "Confira se olhou o lado certo.")
                else:
                    m = MOTOR[lado]
                    print(f"  ERRO: o motor nao girou. Confira a bateria no POWER+/- do MD10C {lado},\n"
                          f"  o fio PWM no GPIO{m['pwm']} e o GND de sinal do MD10C.")
                b.falhas.append(f"motor {lado} nao girou no comando {nome}")
                break
            if sentido > 0:
                mesma = perguntar("  As DUAS rodas desse lado giraram no mesmo sentido? [s/n] ", "sn")
                if mesma == "n":
                    print("  -> Um dos dois motores deste lado esta com vermelho/branco invertido\n"
                          "     na saida do MD10C. Inverta so o que girou errado.")
                    b.falhas.append(f"motores do lado {lado} brigando entre si")
            fases.append({"fisico": +1 if r == "f" else -1, "d": d, "cruz": cruz})
        if len(fases) < 2:
            continue
        fr, re = fases

        # 2) so agora analisa
        if fr["fisico"] == re["fisico"]:
            print(f"\n  ERRO: FRENTE e RE giraram para o mesmo lado: o sinal DIR nao esta chegando\n"
                  f"  no MD10C {lado}. Confira o fio do GPIO{MOTOR[lado]['dir']}.")
            b.falhas.append(f"DIR do lado {lado} nao funciona")
            continue
        if fr["fisico"] < 0:
            b.inverter_motor(lado)
            print(f"\n  O lado {NOME[lado]} gira ao contrario do comando.\n"
                  f"  -> INVERTER_MOTOR['{lado}'] = {b.inv_motor[lado]}  (ou inverta vermelho/branco "
                  "dos DOIS motores deste lado). Ja corrigido nesta execucao.")

        if min(abs(f["d"]) for f in fases) < 50:
            print("  ERRO: a roda girou mas o encoder quase nao contou. Confira se o encoder\n"
                  "  ligado e o de uma roda DESTE lado e se o conector esta firme.")
            b.falhas.append(f"encoder {lado} nao conta com o motor girando")
        else:
            concorda = [f["d"] * f["fisico"] > 0 for f in fases]
            if not any(concorda):
                b.inverter_encoder(lado)
                print("  O encoder conta ao contrario do giro real.\n"
                      f"  -> INVERTER_ENCODER['{lado}'] = {b.inv_enc[lado]}. Ja corrigido nesta execucao.")
            elif not all(concorda):
                print("  ERRO: o sinal do encoder concorda com o giro num sentido e no outro nao.")
                b.falhas.append(f"encoder {lado} inconsistente")
            simetria = abs(re["d"]) / abs(fr["d"])
            if not 0.8 < simetria < 1.25:
                print(f"  AVISO: re andou {simetria * 100:.0f}% do que a frente andou com o mesmo duty.")
        if any(abs(f["cruz"]) > 50 and abs(f["cruz"]) > 0.2 * abs(f["d"]) for f in fases):
            print(f"  AVISO: o encoder do lado {NOME[outro]} contou junto. Fios de motor ou de\n"
                  "  encoder trocados entre os lados?")
            b.falhas.append(f"lados {lado}/{outro} cruzados")
        if len(b.falhas) == falhas_antes:
            print(f"  {NOME[lado]}: OK")


# ---------------- TESTE 3: varredura ----------------

def _ajuste_linear(xs, ys):
    n = len(xs)
    mx, my = sum(xs) / n, sum(ys) / n
    sxx = sum((x - mx) ** 2 for x in xs)
    if sxx == 0:
        return None, None
    a = sum((x - mx) * (y - my) for x, y in zip(xs, ys)) / sxx
    return a, my - a * mx


def teste_varredura(b):
    exigir_cpr(b)
    titulo("TESTE 3/4 - VARREDURA DE DUTY  (os dois lados juntos, para frente)")
    duties = []
    d = DUTY_PASSO
    while d < DUTY_TETO - 1e-6:
        duties.append(round(d, 4))
        d += DUTY_PASSO
    duties.append(DUTY_TETO)

    print(f"{'duty':>6} {'V med':>6} | {'rpm esq':>8} {'rpm dir':>8} {'dif %':>6} | "
          f"{'eventos/s':>9} {'invalidas':>9}")
    linhas = []
    pico_eventos, invalidas_total, eventos_total = 0.0, 0, 0.0
    for duty in duties:
        b.rampa({l: duty for l in LADOS}, segundos=0.15)
        b.segurar(T_ASSENTA)
        m = b.medir()
        re, rd = m["esq"]["rpm"], m["dir"]["rpm"]
        media = (re + rd) / 2
        dif = f"{(re - rd) / media * 100:+6.1f}" if min(re, rd) > 10 else f"{'--':>6}"
        ev = m["esq"]["eventos_s"] + m["dir"]["eventos_s"]
        inv = m["esq"]["invalidas"] + m["dir"]["invalidas"]
        pico_eventos = max(pico_eventos, ev)
        invalidas_total += inv
        eventos_total += ev * T_JANELA
        print(f"{duty * 100:5.0f}% {duty * V_BATERIA_MAX:5.1f}V | {re:8.1f} {rd:8.1f} {dif} | "
              f"{ev:9.0f} {inv:9d}")
        linhas.append([duty, round(duty * V_BATERIA_MAX, 2), round(re, 2), round(rd, 2), inv, round(ev)])
    b.rampa({l: 0.0 for l in LADOS})

    rpm = {"esq": [r[2] for r in linhas], "dir": [r[3] for r in linhas]}
    duty_min, rpm_max, inclinacao, duty_zero = {}, {}, {}, {}
    for l in LADOS:
        rpm_max[l] = rpm[l][-1]
        limiar = max(5.0, 0.03 * rpm_max[l])
        idx = next((i for i, r in enumerate(rpm[l]) if r > limiar), None)
        if idx is None:
            b.falhas.append(f"motor {l} nao arrancou na varredura")
            continue
        duty_min[l] = duties[idx]
        xs, ys = duties[idx:], rpm[l][idx:]
        if len(xs) >= 2:
            a, c = _ajuste_linear(xs, ys)
            inclinacao[l] = a
            duty_zero[l] = -c / a if a else None

    print()
    for l in LADOS:
        if l not in duty_min:
            print(f"  {NOME[l]}: nao arrancou em nenhum duty.")
            continue
        extra = ""
        if l in inclinacao and duty_zero.get(l) is not None:
            extra = (f"  |  modelo: rpm ~ {inclinacao[l]:.0f} x (duty - {duty_zero[l]:.3f})")
        print(f"  {NOME[l]}: arranca em {duty_min[l] * 100:.0f}%  |  "
              f"{rpm_max[l]:.0f} rpm no teto{extra}")
    if all(l in duty_min for l in LADOS):
        # so a metade de cima: perto da zona morta a diferenca e grande e nao significa nada
        com = [(e, d) for du, e, d in zip(duties, rpm["esq"], rpm["dir"])
               if du >= 0.5 * DUTY_TETO and min(e, d) > 10]
        if com:
            dif = sum((e - d) / ((e + d) / 2) for e, d in com) / len(com) * 100
            print(f"  diferenca esq - dir (metade de cima da faixa): {dif:+.1f}%"
                  "  -> o PID de cada lado compensa isso")
    print(f"  pico de eventos de encoder: {pico_eventos:.0f}/s  |  transicoes invalidas: {invalidas_total}")
    if eventos_total and invalidas_total > 0.001 * eventos_total:
        print("  AVISO: transicoes invalidas acima de 0,1%: o Pi pode estar perdendo bordas\n"
              "  ou ha ruido. Isso estraga a medida de velocidade em rpm alto.")
        b.falhas.append("transicoes invalidas no encoder")

    b.resultados.update(DUTY_MIN=duty_min, RPM_MAX=rpm_max,
                        RPM_POR_DUTY=inclinacao, DUTY_ZERO=duty_zero,
                        EVENTOS_PICO=round(pico_eventos))
    salvar_csv("varredura", ["duty", "v_medio", "rpm_esq", "rpm_dir", "invalidas", "eventos_s"], linhas)


# ---------------- TESTE 4: degrau ----------------

def teste_degrau(b):
    exigir_cpr(b)
    titulo("TESTE 4/4 - RESPOSTA AO DEGRAU  (os dois lados juntos)")
    duty = FRACAO_DEGRAU * DUTY_TETO
    print(f"Degrau de 0 para {duty * 100:.0f}%, amostrando a 100 Hz por {T_DEGRAU:.1f} s ...")
    b.parar_tudo()
    time.sleep(1.0)

    amostras = []
    t0 = time.monotonic()
    for l in LADOS:
        b.motor[l].aplicar(duty)                    # degrau de verdade, sem rampa
    proximo = t0
    while True:
        agora = time.monotonic()
        t = agora - t0
        amostras.append((t, b.enc["esq"].posicao, b.enc["dir"].posicao))
        b.vigiar()
        if t >= T_DEGRAU:
            break
        proximo += 0.01
        time.sleep(max(0.0, proximo - time.monotonic()))
    b.rampa({l: 0.0 for l in LADOS})

    # rpm por diferenca centrada (nao atrasa o sinal)
    k = 3
    serie = {"esq": [], "dir": []}
    tempos = []
    for i in range(k, len(amostras) - k):
        dt = amostras[i + k][0] - amostras[i - k][0]
        tempos.append(amostras[i][0])
        for j, l in ((1, "esq"), (2, "dir")):
            dpos = amostras[i + k][j] - amostras[i - k][j]
            serie[l].append(dpos / b.cpr[l] / dt * 60.0)

    tau = {}
    for l in LADOS:
        final = [r for t, r in zip(tempos, serie[l]) if T_DEGRAU - 0.6 <= t <= T_DEGRAU - 0.1]
        if not final:
            continue
        regime = sum(final) / len(final)
        if regime < 5:
            print(f"  {NOME[l]}: nao girou no degrau.")
            b.falhas.append(f"motor {l} nao respondeu ao degrau")
            continue
        alvo63, alvo90 = 0.632 * regime, 0.9 * regime
        t63 = next((t for t, r in zip(tempos, serie[l]) if r >= alvo63), None)
        t90 = next((t for t, r in zip(tempos, serie[l]) if r >= alvo90), None)
        tau[l] = t63
        print(f"  {NOME[l]}: regime {regime:.0f} rpm  |  tau (63%) = {t63 * 1000:.0f} ms"
              f"  |  90% em {t90 * 1000:.0f} ms")
    b.resultados["TAU_S"] = {l: round(v, 3) for l, v in tau.items()}
    if tau:
        print("  Use ~5 x tau como duracao minima de cada tentativa do enxame: "
              "antes disso a roda nem chegou na velocidade.")

    linhas = [[round(t, 4), round(re, 2), round(rd, 2)]
              for t, re, rd in zip(tempos, serie["esq"], serie["dir"])]
    salvar_csv("degrau", ["t", "rpm_esq", "rpm_dir"], linhas)


# ---------------- acionamento simples ----------------

def girar(b, duty_pct, segundos, re):
    duty = min(duty_pct / 100.0, DUTY_TETO)
    if duty_pct / 100.0 > DUTY_TETO:
        print(f"Duty pedido ({duty_pct:.0f}%) acima do teto: usando {DUTY_TETO * 100:.0f}%.")
    sentido = -1 if re else +1
    titulo(f"GIRAR - os 4 motores, {'RE' if re else 'FRENTE'}, "
           f"{duty * 100:.0f}% (~{duty * V_BATERIA_MAX:.1f} V medios), {segundos:.1f} s")
    antes = {l: b.enc[l].posicao for l in LADOS}
    b.rampa({l: sentido * duty for l in LADOS})
    t0 = time.monotonic()
    while True:
        passou = time.monotonic() - t0
        if passou >= segundos:
            break
        b.segurar(min(0.5, segundos - passou))
        print(f"  {time.monotonic() - t0:4.1f} s   encoder esq: {b.enc['esq'].posicao - antes['esq']:+8d}"
              f"   dir: {b.enc['dir'].posicao - antes['dir']:+8d}")
    dt = time.monotonic() - t0
    b.rampa({l: 0.0 for l in LADOS})
    print("  parado.")
    for l in LADOS:
        d = b.enc[l].posicao - antes[l]
        rpm = f"  (~{d / b.cpr[l] / dt * 60:.0f} rpm medio)" if b.cpr[l] else ""
        print(f"  {NOME[l]}: {d:+d} contagens{rpm}")
    if not CPR_SAIDA:
        print("  (para ver rpm, rode o teste 'encoder' e preencha CPR_SAIDA)")


# ---------------- resumo / emergencia ----------------

def resumo(b):
    titulo("RESUMO")
    if b.falhas:
        print("PROBLEMAS ENCONTRADOS:")
        for f in b.falhas:
            print(f"  - {f}")
        print()
    r = b.resultados

    def fmt(d):
        return "{" + ", ".join(f'"{k}": {round(v, 3) if isinstance(v, float) else v}'
                               for k, v in d.items()) + "}"

    print("# --- copie para a configuracao (medido por teste_motores.py) ---")
    print(f"INVERTER_MOTOR = {fmt(b.inv_motor)}")
    print(f"INVERTER_ENCODER = {fmt(b.inv_enc)}")
    if "CPR_SAIDA" in r:
        print(f"CPR_SAIDA = {r['CPR_SAIDA']}   # contagens x4 por volta da roda")
    for chave in ("DUTY_MIN", "DUTY_ZERO", "RPM_POR_DUTY", "RPM_MAX", "TAU_S"):
        if r.get(chave):
            print(f"{chave} = {fmt(r[chave])}")
    if r.get("RPM_MAX"):
        print(f"# RPM_MAX medido no teto de duty ({DUTY_TETO * 100:.0f}%), com a bateria de agora")


def parar_emergencia():
    pi = pigpio.pi()
    if not pi.connected:
        raise SystemExit("pigpiod nao esta rodando.")
    for lado in LADOS:
        pi.hardware_PWM(MOTOR[lado]["pwm"], 0, 0)
        pi.write(MOTOR[lado]["dir"], 0)
    pi.stop()
    print("PWM zerado nos dois lados.")


def _sigterm(signum, frame):
    raise SystemExit("\nSIGTERM recebido.")


def main():
    ap = argparse.ArgumentParser(description="Bancada de teste dos motores do robo 4WD.")
    ap.add_argument("teste", choices=["encoder", "direcao", "varredura", "degrau", "tudo",
                                      "girar", "parar"])
    ap.add_argument("--duty", type=float, default=30.0,
                    help="so para 'girar': duty em %% da tensao da bateria (limitado ao teto)")
    ap.add_argument("--tempo", type=float, default=3.0, help="so para 'girar': segundos")
    ap.add_argument("--re", action="store_true", help="so para 'girar': gira para tras")
    args = ap.parse_args()

    if args.teste == "parar":
        parar_emergencia()
        return

    signal.signal(signal.SIGTERM, _sigterm)
    print(f"Teto de duty: {DUTY_TETO * 100:.0f}%  (motor {V_MOTOR_NOMINAL:.0f} V, "
          f"bateria ate {V_BATERIA_MAX:.1f} V)")
    if args.teste != "encoder":
        if perguntar("As rodas estao NO AR e o robo esta apoiado? [s/N] ", "sn", "n") != "s":
            raise SystemExit("Abortado. Suspenda o robo antes de ligar os motores.")

    b = Bancada()
    try:
        if args.teste == "encoder":
            teste_encoder(b)
        elif args.teste == "direcao":
            teste_direcao(b)
        elif args.teste == "varredura":
            teste_varredura(b)
        elif args.teste == "degrau":
            teste_degrau(b)
        elif args.teste == "girar":
            girar(b, args.duty, args.tempo, args.re)
            return
        else:
            for teste in (teste_encoder, teste_direcao, teste_varredura, teste_degrau):
                teste(b)
                if b.falhas:
                    print("\nParando a sequencia: resolva os problemas acima antes de seguir.")
                    break
        resumo(b)
    except Travamento as e:
        lado = e.args[0]
        print(f"\n\nABORTADO: o motor {NOME[lado]} recebeu duty alto e nao girou por "
              f"{TRAVAMENTO_T:.1f} s.\nRoda presa, motor sem energia ou encoder desligado. "
              "Motores parados.")
    except KeyboardInterrupt:
        print("\n\nInterrompido. Motores parados.")
    finally:
        b.fechar()


if __name__ == "__main__":
    main()

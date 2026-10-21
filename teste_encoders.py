#!/usr/bin/env python3
"""
teste_encoders.py - verificacao simples dos encoders Hall (motores desligados).

Gire cada roda DIANTEIRA a mao e olhe a tela:
  - nivel A/B: tem que alternar entre 0 e 1 enquanto a roda gira
  - bordas A/B: tem que subir nos DOIS canais
  - posicao:   sobe num sentido, desce no outro

Diagnostico rapido:
  nivel parado e 0 bordas nos dois canais -> sem sinal: alimentacao (azul/preto)
                                             no conector, fio solto ou encoder ruim
  bordas so em A ou so em B               -> o fio do canal parado esta solto
  posicao oscilando +1/-1 sem sair do lugar -> so um canal funciona
  muitas invalidas                        -> ruido ou bordas perdidas

Antes:  sudo systemctl start pigpiod
Uso:    python3 teste_encoders.py            (sem pull-up interno, como na placa)
        python3 teste_encoders.py --pullup   (liga o pull-up interno de 3,3 V)
Sair:   Ctrl+C
"""

import argparse
import sys
import time

import pigpio

# numeracao BCM, igual ao teste_motores.py
ENCODER = {
    "esq": {"a": 23, "b": 24},       # pinos fisicos 16 e 18
    "dir": {"a": 25, "b": 5},        # pinos fisicos 22 e 29
}

# Indice = (estado_anterior << 2) | estado_novo ; estado = (A << 1) | B
_TRANSICAO = (
    0, -1, +1, None,
    +1, 0, None, -1,
    -1, None, 0, +1,
    None, +1, -1, 0,
)


class Encoder:
    def __init__(self, pi, a, b, pull):
        self.a, self.b = a, b
        for g in (a, b):
            pi.set_mode(g, pigpio.INPUT)
            pi.set_pull_up_down(g, pull)
        self.nivel = {a: pi.read(a), b: pi.read(b)}
        self.bordas = {a: 0, b: 0}
        self.posicao = 0
        self.invalidas = 0
        self._estado = self._calc_estado()
        self._cbs = [pi.callback(g, pigpio.EITHER_EDGE, self._borda) for g in (a, b)]

    def _calc_estado(self):
        return (self.nivel[self.a] << 1) | self.nivel[self.b]

    def _borda(self, gpio, nivel, tick):
        if nivel > 1:
            return
        self.nivel[gpio] = nivel
        self.bordas[gpio] += 1
        novo = self._calc_estado()
        passo = _TRANSICAO[(self._estado << 2) | novo]
        self._estado = novo
        if passo is None:
            self.invalidas += 1
        else:
            self.posicao += passo

    def linha(self, nome):
        a, b = self.a, self.b
        return (f"{nome}  nivel A={self.nivel[a]} B={self.nivel[b]}  "
                f"bordas A={self.bordas[a]:6d} B={self.bordas[b]:6d}  "
                f"posicao={self.posicao:+8d}  invalidas={self.invalidas:4d}")

    def fechar(self):
        for cb in self._cbs:
            cb.cancel()


def main():
    ap = argparse.ArgumentParser(description="Verificacao simples dos encoders.")
    ap.add_argument("--pullup", action="store_true", help="liga o pull-up interno")
    args = ap.parse_args()

    pi = pigpio.pi()
    if not pi.connected:
        raise SystemExit("pigpiod nao esta rodando: sudo systemctl start pigpiod")

    pull = pigpio.PUD_UP if args.pullup else pigpio.PUD_OFF
    enc = {lado: Encoder(pi, p["a"], p["b"], pull) for lado, p in ENCODER.items()}

    print(f"pull-up interno: {'LIGADO' if args.pullup else 'desligado'}")
    for lado, p in ENCODER.items():
        print(f"  {lado}: A=GPIO{p['a']}  B=GPIO{p['b']}")
    print("Gire as rodas dianteiras a mao. Ctrl+C para sair.\n\n")
    try:
        while True:
            sys.stdout.write("\033[2A\r" + enc["esq"].linha("ESQ") + "\033[K\n"
                             + enc["dir"].linha("DIR") + "\033[K\n")
            sys.stdout.flush()
            time.sleep(0.1)
    except KeyboardInterrupt:
        print("\nfim.")
    finally:
        for e in enc.values():
            e.fechar()
        pi.stop()


if __name__ == "__main__":
    main()

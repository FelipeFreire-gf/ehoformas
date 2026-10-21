#!/usr/bin/env python3
"""
lidar.py - le o RPLIDAR C1 pela serial (adaptador CP210x na USB do Pi).

Antes (no Pi):
    sudo apt install -y python3-serial
    sudo usermod -aG dialout $USER     # depois saia e entre de novo no SSH

Uso:
    python3 lidar.py info              # modelo, firmware e saude do sensor
    python3 lidar.py texto             # obstaculo mais proximo em 8 direcoes, ao vivo
    python3 lidar.py stream            # uma volta por linha (JSON), para o ver_lidar.py

Ver o desenho no notebook:
    ssh dasneves@10.74.1.113 "python3 lidar.py stream" | python3 ver_lidar.py

Opcoes: --porta /dev/ttyUSB0   --frente 0   (angulo, em graus, que aponta
para a frente do robo; ajuste olhando o modo 'texto')
"""

import argparse
import json
import signal
import struct
import sys
import time

import serial

PORTA = "/dev/ttyUSB0"
BAUD = 460800                 # RPLIDAR C1
DIST_MIN_MM = 50              # abaixo disso e reflexo do proprio robo / lixo

CMD_SCAN, CMD_STOP, CMD_INFO, CMD_SAUDE = 0x20, 0x25, 0x50, 0x52
SAUDE_TXT = {0: "OK", 1: "AVISO", 2: "ERRO"}


class Lidar:
    def __init__(self, porta=PORTA, baud=BAUD):
        try:
            self.s = serial.Serial(porta, baud, timeout=1)
        except serial.SerialException as e:
            raise SystemExit(
                f"Nao abri {porta}: {e}\n"
                "Confira com 'ls /dev/ttyUSB*' se o LiDAR aparece, e se seu usuario\n"
                "esta no grupo dialout ('groups'; se nao, sudo usermod -aG dialout $USER).")
        self.s.dtr = False    # nos RPLIDAR A1 isso liga o motor; no C1 nao atrapalha

    def _cmd(self, c):
        self.s.write(bytes([0xA5, c]))

    def _descritor(self):
        d = self.s.read(7)
        if len(d) != 7 or d[0] != 0xA5 or d[1] != 0x5A:
            raise RuntimeError(
                f"resposta inesperada do LiDAR ({d.hex() or 'nada'}). Confira a porta "
                f"e o baud ({self.s.baudrate}).")
        tamanho = struct.unpack("<I", d[2:6])[0] & 0x3FFFFFFF
        return tamanho, d[6]

    def parar(self):
        self._cmd(CMD_STOP)
        time.sleep(0.05)
        self.s.reset_input_buffer()

    def info(self):
        self.parar()
        self._cmd(CMD_INFO)
        n, _ = self._descritor()
        d = self.s.read(n)
        return {"modelo": f"0x{d[0]:02X}", "firmware": f"{d[2]}.{d[1]:02d}",
                "hardware": d[3], "serie": d[4:20].hex().upper()}

    def saude(self):
        self.parar()
        self._cmd(CMD_SAUDE)
        n, _ = self._descritor()
        d = self.s.read(n)
        return SAUDE_TXT.get(d[0], str(d[0])), struct.unpack("<H", d[1:3])[0]

    def voltas(self):
        """Gera uma lista [(angulo_graus, distancia_mm, qualidade), ...] por volta."""
        self.parar()
        self._cmd(CMD_SCAN)
        n, _ = self._descritor()
        if n != 5:
            raise RuntimeError(f"tamanho de amostra inesperado: {n}")
        volta, buf, ang_ant = [], b"", 0.0
        while True:
            buf += self.s.read(max(5, self.s.in_waiting))
            i = 0
            while len(buf) - i >= 5:
                b0, b1 = buf[i], buf[i + 1]
                inicio, inicio_inv, checa = b0 & 1, (b0 >> 1) & 1, b1 & 1
                ang = ((b1 >> 1) | (buf[i + 2] << 7)) / 64.0
                if inicio == inicio_inv or checa != 1 or ang >= 360.0:
                    i += 1                         # fora de sincronia: anda 1 byte
                    continue
                dist = (buf[i + 3] | (buf[i + 4] << 8)) / 4.0
                q = b0 >> 2
                i += 5
                # volta nova: bit de inicio E o angulo dando a volta (lixo raramente acerta os dois)
                if inicio and ang < ang_ant - 180.0 and len(volta) > 10:
                    yield volta
                    volta = []
                ang_ant = ang
                if dist >= DIST_MIN_MM and q > 0:
                    volta.append((ang, dist, q))
            buf = buf[i:]

    def fechar(self):
        try:
            self.parar()
        finally:
            self.s.close()


# ---------------- modos ----------------

SETORES = [("F", 0), ("FD", 45), ("D", 90), ("TD", 135),
           ("T", 180), ("TE", 225), ("E", 270), ("FE", 315)]


def mais_proximo_por_setor(volta, frente, ignorar=2):
    """Distancia mais proxima de cada setor de 45 graus. Descarta os 'ignorar'
    pontos mais proximos de cada setor: um ponto isolado e quase sempre ruido."""
    dists = {nome: [] for nome, _ in SETORES}
    for ang, dist, _ in volta:
        a = (ang - frente) % 360
        dists[SETORES[int(((a + 22.5) % 360) // 45)][0]].append(dist)
    perto = {}
    for nome, ds in dists.items():
        ds.sort()
        perto[nome] = ds[ignorar] if len(ds) > ignorar else None
    return perto


def modo_texto(lidar, frente):
    def m(v):
        return "  --  " if v is None else f"{v / 1000:5.2f}m"
    print("Obstaculo mais proximo em cada direcao (angulos crescem no sentido horario).")
    print("Ponha a mao na frente do robo: se reagir outro setor, ajuste --frente.\n\n\n\n")
    t_ant = time.monotonic()
    for volta in lidar.voltas():
        agora = time.monotonic()
        hz = 1.0 / max(agora - t_ant, 1e-3)
        t_ant = agora
        p = mais_proximo_por_setor(volta, frente)
        sys.stdout.write("\x1b[4A")
        sys.stdout.write(f"\r\x1b[K   FE {m(p['FE'])}    F  {m(p['F'])}    FD {m(p['FD'])}\n")
        sys.stdout.write(f"\r\x1b[K   E  {m(p['E'])}      [robo]      D  {m(p['D'])}\n")
        sys.stdout.write(f"\r\x1b[K   TE {m(p['TE'])}    T  {m(p['T'])}    TD {m(p['TD'])}\n")
        sys.stdout.write(f"\r\x1b[K   {len(volta)} pontos por volta, {hz:4.1f} voltas/s\n")
        sys.stdout.flush()


def modo_stream(lidar, frente):
    for volta in lidar.voltas():
        pts = [[round((a - frente) % 360, 1), int(d)] for a, d, _ in volta]
        sys.stdout.write(json.dumps({"t": round(time.time(), 3), "p": pts}, separators=(",", ":")) + "\n")
        sys.stdout.flush()


def main():
    ap = argparse.ArgumentParser(description="RPLIDAR C1 no Raspberry Pi.")
    ap.add_argument("modo", choices=["info", "texto", "stream"])
    ap.add_argument("--porta", default=PORTA)
    ap.add_argument("--baud", type=int, default=BAUD)
    ap.add_argument("--frente", type=float, default=0.0,
                    help="angulo do LiDAR que aponta para a frente do robo")
    args = ap.parse_args()

    def _sair(signum, frame):          # SSH caiu / processo morto: para o motor do LiDAR
        raise SystemExit
    signal.signal(signal.SIGHUP, _sair)
    signal.signal(signal.SIGTERM, _sair)

    lidar = Lidar(args.porta, args.baud)
    try:
        if args.modo == "info":
            for k, v in lidar.info().items():
                print(f"{k:>9}: {v}")
            estado, codigo = lidar.saude()
            print(f"{'saude':>9}: {estado}" + (f" (codigo {codigo})" if codigo else ""))
        elif args.modo == "texto":
            modo_texto(lidar, args.frente)
        else:
            modo_stream(lidar, args.frente)
    except KeyboardInterrupt:
        pass
    except BrokenPipeError:
        pass                      # o visualizador do outro lado foi fechado
    finally:
        try:
            lidar.fechar()
        except Exception:
            pass


if __name__ == "__main__":
    main()

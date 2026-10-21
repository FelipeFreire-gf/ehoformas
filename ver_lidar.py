#!/usr/bin/env python3
"""
ver_lidar.py - desenha ao vivo, NO SEU NOTEBOOK, o que o lidar.py manda do Pi.

Arch:   sudo pacman -S python-matplotlib
Uso:    ssh dasneves@10.74.1.113 "python3 lidar.py stream" | python3 ver_lidar.py
        ... | python3 ver_lidar.py --alcance 6          # raio do grafico em metros
        ... | python3 ver_lidar.py --png volta.png      # salva uma volta e sai (bom pro TCC)

Frente do robo para cima; angulos crescem no sentido horario, como no LiDAR.
"""

import argparse
import json
import math
import sys
import threading
import time

ultima = {"volta": None, "t": 0.0, "voltas": 0}
trava = threading.Lock()


def ler_stdin():
    for linha in sys.stdin:
        try:
            dado = json.loads(linha)
        except ValueError:
            continue                    # mensagem de erro ou lixo: ignora
        with trava:
            ultima["volta"] = dado["p"]
            ultima["t"] = time.monotonic()
            ultima["voltas"] += 1


def preparar(ax, alcance):
    ax.set_theta_zero_location("N")     # 0 grau = frente do robo, para cima
    ax.set_theta_direction(-1)          # horario
    ax.set_rlim(0, alcance)
    ax.set_rlabel_position(135)
    ax.grid(True, alpha=0.35)
    ax.set_title("RPLIDAR C1 — vista de cima", pad=18)
    ax.plot([0], [0], marker="^", markersize=12, color="#C0392B")   # o robo


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--alcance", type=float, default=4.0, help="raio do grafico, em metros")
    ap.add_argument("--png", help="salva a primeira volta neste arquivo e sai")
    args = ap.parse_args()

    if args.png:
        import matplotlib
        matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.animation import FuncAnimation

    threading.Thread(target=ler_stdin, daemon=True).start()

    fig = plt.figure(figsize=(7, 7))
    ax = fig.add_subplot(projection="polar")
    preparar(ax, args.alcance)
    pontos = ax.scatter([], [], s=4, c="#1F5FA8")
    info = fig.text(0.02, 0.02, "esperando dados do Pi...", fontsize=10, color="#555")

    def desenhar(volta, n):
        th = [math.radians(a) for a, d in volta]
        r = [d / 1000.0 for a, d in volta]
        pontos.set_offsets(list(zip(th, r)) or [[0, 0]])
        info.set_text(f"{len(volta)} pontos nesta volta  ·  {n} voltas recebidas")

    if args.png:
        t0 = time.monotonic()
        while ultima["volta"] is None:
            if time.monotonic() - t0 > 15:
                raise SystemExit("Nenhum dado chegou em 15 s.")
            time.sleep(0.05)
        with trava:
            desenhar(ultima["volta"], ultima["voltas"])
        fig.savefig(args.png, dpi=150, bbox_inches="tight")
        print(f"salvo em {args.png}")
        return

    def atualizar(_):
        with trava:
            volta, t, n = ultima["volta"], ultima["t"], ultima["voltas"]
        if volta is not None:
            desenhar(volta, n)
            if time.monotonic() - t > 2:
                info.set_text("sem dados ha mais de 2 s: o Pi parou de mandar?")
        return pontos, info

    anim = FuncAnimation(fig, atualizar, interval=100, cache_frame_data=False)  # noqa: F841
    plt.show()


if __name__ == "__main__":
    main()

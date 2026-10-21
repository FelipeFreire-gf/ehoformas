#!/usr/bin/env python3
"""
profundidade.py - le a profundidade da Orbbec Astra Pro no Pi (SDK OpenNI2 da Orbbec).

Antes (no Pi, uma vez):
    sudo apt install -y python3-numpy python3-opencv
    pip3 install --break-system-packages openni

Uso:
    python3 profundidade.py centro      # distancia no centro e o ponto mais perto, no terminal
    python3 profundidade.py stream      # video colorido (MJPEG) na saida, para o notebook

Ver no notebook (Arch: sudo pacman -S ffmpeg):
    ssh dasneves@10.74.1.113 "python3 profundidade.py stream" | ffplay -loglevel error -fflags nobuffer -flags low_delay -f mjpeg -

Opcoes: --res 640 (padrao 320x240, mais leve pro Pi 3)  --alcance 4000 (mm, cor maxima)
        --fps 15 (quadros enviados por segundo)  --sdk <pasta com libOpenNI2.so>
Cores: perto = vermelho, longe = azul, preto = sem medida (mais perto que ~0,6 m,
       longe demais, ou superficie que nao reflete o infravermelho).
"""

import argparse
import glob
import os
import signal
import sys
import time

import numpy as np

SDK_PADRAO = os.path.expanduser("~/orbbec/arm64/OpenNI_*_a311d/sdk/libs")


def achar_sdk(caminho):
    candidatos = glob.glob(caminho)
    for c in candidatos:
        if os.path.isfile(os.path.join(c, "libOpenNI2.so")):
            return c
    raise SystemExit(f"Nao achei libOpenNI2.so em {caminho}. Passe a pasta certa com --sdk.")


class Profundidade:
    def __init__(self, sdk, largura):
        try:
            from openni import openni2
            from openni import _openni2 as c_api
        except ImportError:
            raise SystemExit("Falta o modulo openni: pip3 install --break-system-packages openni")
        self.openni2 = openni2
        # o driver da Orbbec e procurado em ./OpenNI2/Drivers relativo a biblioteca
        os.chdir(sdk)
        openni2.initialize(sdk)
        try:
            self.dev = openni2.Device.open_any()
        except Exception as e:
            openni2.unload()
            raise SystemExit(f"Nao abri a camera: {e}\nReconecte a USB e confira a regra do udev.")
        self.stream = self.dev.create_depth_stream()

        modos = [m for m in self.stream.get_sensor_info().videoModes
                 if m.pixelFormat == c_api.OniPixelFormat.ONI_PIXEL_FORMAT_DEPTH_1_MM]
        escolhido = next((m for m in modos if m.resolutionX == largura and m.fps == 30), None)
        if escolhido is None and modos:
            escolhido = min(modos, key=lambda m: abs(m.resolutionX - largura))
        if escolhido is not None:
            self.stream.set_video_mode(escolhido)
        try:
            self.stream.set_mirroring_enabled(False)
        except Exception:
            pass
        self.stream.start()
        m = self.stream.get_video_mode()
        self.largura, self.altura, self.fps = m.resolutionX, m.resolutionY, m.fps

    def ler(self):
        """Retorna uma matriz altura x largura de distancias em mm (0 = sem medida)."""
        f = self.stream.read_frame()
        return np.frombuffer(f.get_buffer_as_uint16(), dtype=np.uint16).reshape(f.height, f.width).copy()

    def fechar(self):
        try:
            self.stream.stop()
        finally:
            self.openni2.unload()


def resumo(d):
    h, w = d.shape
    centro = int(d[h // 2, w // 2])
    janela = d[h // 4: 3 * h // 4, w // 4: 3 * w // 4]
    validos = janela[janela > 0]
    mais_perto = int(np.percentile(validos, 1)) if validos.size else 0   # 1% ignora ruido
    cobertura = (d > 0).mean() * 100
    return centro, mais_perto, cobertura


def colorir(d, alcance):
    import cv2
    validos = d > 0
    norm = np.clip(d.astype(np.float32) / alcance, 0, 1)
    img = cv2.applyColorMap((255 * (1 - norm)).astype(np.uint8), cv2.COLORMAP_JET)
    img[~validos] = 0
    return img


def modo_centro(cam):
    print(f"{cam.largura}x{cam.altura} a {cam.fps} fps. Ctrl+C para sair.\n")
    while True:
        centro, perto, cob = resumo(cam.ler())
        c = f"{centro / 1000:5.2f} m" if centro else " --   "
        p = f"{perto / 1000:5.2f} m" if perto else " --   "
        sys.stdout.write(f"\r\x1b[K centro {c}   |   mais perto (meio da imagem) {p}   |   "
                         f"{cob:3.0f}% da imagem com medida")
        sys.stdout.flush()


def modo_stream(cam, alcance, fps_envio):
    import cv2
    saida = sys.stdout.buffer
    intervalo = 1.0 / fps_envio
    proximo = 0.0
    while True:
        d = cam.ler()
        agora = time.monotonic()
        if agora < proximo:
            continue                       # le todo quadro (nao acumula fila), envia so alguns
        proximo = agora + intervalo
        img = colorir(d, alcance)
        escala = max(1, 640 // img.shape[1])
        if escala > 1:
            img = cv2.resize(img, None, fx=escala, fy=escala, interpolation=cv2.INTER_NEAREST)
        h, w = img.shape[:2]
        centro, perto, _ = resumo(d)
        cv2.drawMarker(img, (w // 2, h // 2), (255, 255, 255), cv2.MARKER_CROSS, 22, 2)
        txt = f"centro {centro / 1000:.2f} m" if centro else "centro --"
        txt += f"   mais perto {perto / 1000:.2f} m" if perto else ""
        cv2.rectangle(img, (0, h - 30), (w, h), (0, 0, 0), -1)
        cv2.putText(img, txt, (10, h - 9), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 1, cv2.LINE_AA)
        ok, jpg = cv2.imencode(".jpg", img, [cv2.IMWRITE_JPEG_QUALITY, 80])
        if ok:
            saida.write(jpg.tobytes())
            saida.flush()


def main():
    ap = argparse.ArgumentParser(description="Profundidade da Orbbec Astra Pro no Raspberry Pi.")
    ap.add_argument("modo", choices=["centro", "stream"])
    ap.add_argument("--sdk", default=SDK_PADRAO)
    ap.add_argument("--res", type=int, default=320, choices=[320, 640])
    ap.add_argument("--alcance", type=int, default=4000, help="mm que viram a cor mais fria")
    ap.add_argument("--fps", type=float, default=15.0, help="quadros por segundo enviados no stream")
    args = ap.parse_args()

    def _sair(signum, frame):
        raise SystemExit
    signal.signal(signal.SIGHUP, _sair)
    signal.signal(signal.SIGTERM, _sair)

    cam = Profundidade(achar_sdk(args.sdk), args.res)
    try:
        if args.modo == "centro":
            modo_centro(cam)
        else:
            modo_stream(cam, args.alcance, args.fps)
    except (KeyboardInterrupt, BrokenPipeError):
        pass
    finally:
        cam.fechar()
        if args.modo == "centro":
            print()


if __name__ == "__main__":
    main()

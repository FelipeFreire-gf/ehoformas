# TCC — Robô 4WD: registro de atualizações

**Autor:** Felipe das Neves Freire — Engenharia de Software, UnB (FGA)
**Atualizado em:** 28/10/2026

---

## 1. Objetivo

Robô 4WD que **mapeia uma área com o LiDAR e a câmera de profundidade** e depois **vai sozinho até um ponto escolhido no mapa**, usando **ROS 2**.

- **Etapa 1 (atual):** mapeamento 2D com `slam_toolbox`.
- **Etapa 2:** navegação autônoma até um ponto, com Nav2.
- **Depois:** câmera de profundidade nos obstáculos.
- **Plataforma de controle:** comparar vários algoritmos no mesmo robô e nas mesmas condições: PID clássico (referência), MPC, bioinspirados (PSO e outros) e outros (LQR, fuzzy, adaptativo...). Em dois níveis: velocidade das rodas (nó da base, no Pi, algoritmo escolhido por parâmetro) e seguimento de trajetória (controlador do Nav2, no notebook). No TCC: seção "Plataforma para comparação de algoritmos de controle" de `editaveis/software.tex`.

---

## 2. Hardware

| Item | Modelo / detalhe |
|---|---|
| Computador | Raspberry Pi 3 (1 GB), Raspberry Pi OS **Trixie 64-bit** (aarch64), Python 3.13, usuário `dasneves` |
| Chassi | Kit 4WD, 20 cm de largura × 21 cm de comprimento |
| Motores | 4× JGB37-520 12 V, 333 rpm, com encoder Hall em quadratura (11 PPR no eixo do motor) |
| Rodas | 8 cm de diâmetro, por dentro do chassi |
| Drivers | 2× Cytron **MD10C** R3 (PWM + DIR), um por lado, dois motores em paralelo em cada |
| IMU | Bosch **BNO055**, em UART |
| LiDAR | Slamtec **RPLIDAR C1**, adaptador CP210x, 460800 baud |
| Câmera | Orbbec **Astra Pro**: RGB por UVC (`2bc5:0501`) + profundidade (`2bc5:0403`) |
| Wi-Fi | Adaptador USB Realtek RTL8188EU |
| Outros | Buzzer (GPIO18 → 1 kΩ → BC548), cooler 5 V |
| Notebook | Arch Linux (`snow@archlinux`) |

**Cores do conector do motor:** vermelho M−, branco M+, preto GND, azul Vcc (3,3 V), verde A, amarelo B.

---

## 3. Pinagem (BCM / pino físico)

Esquemático no Proteus: `tcc1.pdsprj`, revisão 1.1. A imagem está em `pinagem_robo4wd.png`.

| Função | GPIO (BCM) | Pino físico |
|---|---|---|
| MD10C esquerdo — PWM | 12 | 32 |
| MD10C esquerdo — DIR | 17 | 11 |
| MD10C direito — PWM | 13 | 33 |
| MD10C direito — DIR | 22 | 15 |
| Encoder dianteiro esquerdo A / B | 23 / 24 | 16 / 18 |
| Encoder dianteiro direito A / B | 25 / 5 | 22 / 29 |
| BNO055 TX / RX (UART, cruzado) | 14 / 15 | 8 / 10 |
| Buzzer | 18 | 12 |
| Cooler 5 V | — | 4 (5 V) / 6 (GND) |
| Vcc dos encoders e do BNO055 | 3,3 V | 1 / 17 |

**Observações:**

- Só os encoders dos **motores dianteiros** são lidos.
- O BNO055 está em modo UART: PS1 em nível alto, PS0 em nível baixo.
- O GPIO18 divide o mesmo canal de PWM (PWM0) com o GPIO12. Não use a saída de áudio analógico do Pi.

---

## 4. Alimentação

- **Bateria:** LiPo 4S de drone (16,8 V carregada), com BMS.
- **Motores:** um buck de 12 V alimenta o VIN dos dois MD10C (chave SW1). Por isso o `DUTY_TETO = 100%`.
- **Raspberry Pi:** um buck de 5 V / 5 A (saída fixa) alimenta o Pi pelo micro-USB (chave SW2, com voltímetro).
- **Cooler:** ligado direto no 5 V. Continua girando com o Pi desligado pelo sistema e só para quando a SW2 é desligada.

### 4.1 Problema encontrado: tensão baixa no Pi

- `vcgencmd get_throttled` → `0x70005`: tensão baixa naquele momento, processador sendo reduzido, e as duas coisas já tinham acontecido antes.
- O `dmesg` mostra "Undervoltage detected!" logo na inicialização, além de desconexões USB do hub interno da Astra e do Wi-Fi USB.
- **Efeitos:** a câmera reconecta com outro nome (`/dev/video0` vira `/dev/video1`), o Wi-Fi cai e o ROS fica lento.
- **Causa provável:** queda de tensão no cabo micro-USB e no fusível de entrada do Pi 3. O voltímetro do buck mostra 5 V, mas o Pi recebe menos quando a corrente sobe (LiDAR + Astra + Wi-Fi + processador).

### 4.2 Correção (pendente)

1. Medir a tensão **no próprio Pi**, entre os **pinos 2 (5 V) e 14 (GND)**, com tudo ligado.
2. Alimentar **pelos pinos 2 e 14**, com fio curto e grosso (20–22 AWG), no lugar do micro-USB.
   - Por esse caminho não há proteção: confira a polaridade e a tensão antes de ligar.
3. Se ainda ficar abaixo de ~4,8 V: trocar por um buck **ajustável de 5 A** (XL4015 ou XL4016) e regular em **5,15–5,2 V** (máximo 5,25 V). O LM2596 **não é recomendado**: aguenta só uns 2 A reais.
4. Se cair quando a câmera e o LiDAR ligarem: usar um hub USB com alimentação própria.
5. Teste final: `vcgencmd get_throttled` tem que dar `throttled=0x0` com tudo ligado.

### 4.3 Avaliação da bateria de nobreak (chumbo-ácido 12 V 7 Ah)

Conclusão: **não compensa**.

- **Peso:** ~2,1 kg, contra ~0,3–0,5 kg da LiPo.
- **Tensão:** 11,5–12,8 V. É baixa demais para o buck de 12 V funcionar direito.
- **Energia útil:** ~42 Wh, porque só dá para usar ~50% dela. A LiPo 4S de 2200 mAh tem ~26 Wh úteis.

**Alternativa melhor:** pack Li-ion 18650 **4S com BMS** (por exemplo, 4S2P ~5 Ah, ~400 g).

**Cuidados com a LiPo:**

- Não descarregar abaixo de ~3,5 V por célula (14 V no total).
- Carregar com balanceador.
- Guardar em ~3,8 V por célula.
- Carregar dentro de um saco antichamas.

---

## 5. Software base no Pi

- **pigpio:** compilado do código-fonte, porque o Trixie não tem o pacote `pigpio` no apt. Não existe serviço instalado; inicie com `sudo pigpiod`.
  - Para iniciar a cada boot, crie o serviço `/etc/systemd/system/pigpiod.service` (`ExecStart=/usr/local/bin/pigpiod`, `Type=forking`) e rode `sudo systemctl enable --now pigpiod`.
- **Interface gráfica desligada** para liberar RAM: `sudo systemctl set-default multi-user.target`.
- **Pacotes:** `python3-serial`, `python3-numpy`, `python3-opencv`, `build-essential`, `git`.

---

## 6. Scripts desenvolvidos

| Arquivo | Onde roda | Para que serve |
|---|---|---|
| `teste_motores.py` | Pi | Bancada de teste dos motores e encoders. Modos: `encoder`, `direcao`, `varredura`, `degrau`, `tudo`, `girar` (`--duty`, `--tempo`, `--re`), `parar`. Inclui proteção contra motor travado e rampa. |
| `controle_wasd.py` | Pi (via SSH) | Dirige o robô pelo teclado: WASD/setas, Q/E para curvas abertas, 1–9/0 para velocidade, espaço para parar, X para sair. Para sozinho se as teclas param de chegar, se o SSH cai (SIGHUP) e se um motor trava (só volta depois de soltar a tecla). |
| `lidar.py` | Pi | Leitor do RPLIDAR C1 em Python. Modos `info`, `texto`, `stream` (JSON por volta). Opções `--frente`, `--porta`. |
| `ver_lidar.py` | Notebook | Mostra ao vivo, em gráfico polar, o que o `lidar.py stream` manda. `--png` salva uma volta. Precisa de `sudo pacman -S python-matplotlib tk`. |
| `profundidade.py` | Pi | Profundidade da Astra. Modos `centro` (distância no terminal) e `stream` (vídeo colorido em MJPEG para o notebook). |
| `astra_depth.c` + `compilar_astra.sh` | Pi | Programa em C (compilado como C++) contra o SDK OpenNI2 da Orbbec. Lê os quadros de profundidade e repassa para o `profundidade.py`. |
| `gerar_pinagem.py` | — | Gera `pinagem_robo4wd.png` e `.svg`. |
| `corrigir_openni.py` | Pi | Remendo do pacote `openni` do pip. **Ficou obsoleto** (ver 7.1). |

**Comandos de visualização no notebook:**
```bash
# LiDAR (sem ROS)
ssh dasneves@10.74.1.113 "python3 lidar.py stream" | python3 ver_lidar.py
# Profundidade (sem ROS)
ssh dasneves@10.74.1.113 "python3 profundidade.py stream" | ffplay -loglevel error -fflags nobuffer -flags low_delay -f mjpeg -
# Câmera RGB (use /dev/video1 se a câmera reconectou)
ssh dasneves@10.74.1.113 "ffmpeg -loglevel error -f v4l2 -input_format mjpeg -video_size 640x480 -i /dev/video0 -c copy -f mjpeg -" | ffplay -loglevel error -f mjpeg -
```

> ⚠️ A cópia do `teste_motores.py` que está no Pi é a **versão antiga**: ela mostra "Teto de duty: 71% … 16,8 V". Copie a atual de novo:
> `scp teste_motores.py controle_wasd.py dasneves@10.74.1.113:~/`

---

## 7. Câmera de profundidade (Orbbec Astra Pro)

- **SDK:** OpenNI2 da Orbbec, v2.3.0.86, build arm64, em `~/orbbec/arm64/OpenNI_2.3.0.86_..._a311d`.
- **Validação:** o `SimpleRead` do SDK funcionou no Pi: ~30 fps, ~1044 mm no centro, e **0 mm (sem medida) abaixo de ~0,6 m**, que é o alcance mínimo.

### 7.1 Problemas e solução

1. **Pacote `openni` do pip:** quebrado no Python 3.12+ ("abstract class"). Foi corrigido com o `corrigir_openni.py`.
2. **Segundo erro, sem saída:** "malloc(): invalid size". As estruturas do pacote Python não batem com a biblioteca da Orbbec, e isso corrompe a memória.
3. **Solução:** abandonar o pacote Python e escrever um programa em C (`astra_depth.c`), compilado contra os cabeçalhos do próprio SDK.
   - Os cabeçalhos do OpenNI2 usam sintaxe de C++, então ele compila com `g++ -x c++`.
   - Se o cabeçalho não reconhecer o aarch64, o script tenta de novo com `-D__arm__`.
   - Foi testado com uma câmera simulada.

**Na ROS, a câmera vai usar o driver próprio** (OrbbecSDK_ROS2 ou ros2_astra_camera). Assim, o `astra_depth` só fica como ferramenta de teste.

---

## 8. ROS 2

### 8.1 Arquitetura decidida

O Pi 3 não aguenta SLAM e navegação. Por isso:

- **Raspberry Pi**, só os drivers:
  - LiDAR → `/scan`
  - **Nó da base** (a escrever): `/cmd_vel` → PID por lado → MD10C; encoders → `/odom` e TF `odom → base_link`
  - BNO055 → `/imu`
  - Câmera de profundidade, mais tarde
- **Notebook:** `slam_toolbox`, `robot_localization` (EKF), Nav2, RViz, teleop e os comandos de diagnóstico.
- **Distribuição:** **Jazzy** nos dois lados.

### 8.2 Instalação no Pi (feita)

O ROS não tem pacote oficial para o Trixie. Foi usado o repositório da comunidade **rospian** (Jazzy para Trixie arm64):
```bash
curl -fsSL https://raw.githubusercontent.com/rospian/rospian-repo/HEAD/public/rospian-archive-keyring.asc | gpg --dearmor | sudo tee /usr/share/keyrings/rospian-archive-keyring.gpg >/dev/null
echo "deb [arch=arm64 signed-by=/usr/share/keyrings/rospian-archive-keyring.gpg] https://rospian.github.io/rospian-repo trixie-jazzy main" | sudo tee /etc/apt/sources.list.d/rospian.list
sudo apt update && sudo apt install -y ros-jazzy-ros-base
```

**Notas:**

- O link da chave que está no README do rospian dá 404. A chave certa fica em `public/`, com impressão digital `1DA7 7376 628C 1D73 C385 0854 EFDD 7DE4 DE41 1677`.
- Pacotes disponíveis no rospian: só o `ros-jazzy-depthimage-to-laserscan`. Não há driver do LiDAR, nem `robot_localization`, nem driver da Astra.
- O `colcon` foi instalado pelo pip, porque o apt não tem: `pip install --break-system-packages colcon-common-extensions`. É preciso pôr `~/.local/bin` no PATH.

`~/.bashrc` do Pi:
```bash
source /opt/ros/jazzy/setup.bash
source ~/ros2_ws/install/setup.bash
export PATH="$HOME/.local/bin:$PATH"
```

### 8.3 Driver do LiDAR (feito)

```bash
mkdir -p ~/ros2_ws/src && cd ~/ros2_ws/src
git clone --depth 1 https://github.com/Slamtec/sllidar_ros2.git
cd ~/ros2_ws && MAKEFLAGS=-j2 colcon build --symlink-install --parallel-workers 1   # ~5 min no Pi 3
ros2 launch sllidar_ros2 sllidar_c1_launch.py serial_port:=/dev/ttyUSB0
```

**Resultado:** o driver achou o C1 (firmware 1.02, hardware rev 18), com saúde OK, modo Standard, 5 kHz, 10 Hz e alcance de 16 m.

Use o `sllidar_c1_launch.py`, sem `view_` no nome. Os `view_*` tentam abrir o RViz, que fica no notebook.

### 8.4 Diagnóstico em andamento

- `ros2 topic hz /scan` **trava** no Pi.
- Com `ros2 daemon stop` + `ros2 topic list --no-daemon`, o `/scan` e o `/sllidar_node` **aparecem**. Ou seja, os processos se encontram; o processo de fundo do `ros2` (daemon) é que trava.
- **Ainda não confirmado** se os dados chegam:
  ```bash
  ros2 daemon stop
  ros2 topic echo /scan --once --no-daemon | head -30
  ```
- Se esse teste também travar com o LiDAR girando, force a troca de dados pela rede local: `export FASTDDS_BUILTIN_TRANSPORTS=UDPv4` nos dois terminais.
- **Provavelmente agravado pela tensão baixa**, que reduz o processador. Refazer depois de corrigir a alimentação.

### 8.5 Notebook (pendente)

O Arch não tem ROS oficial. A solução é uma caixa Ubuntu 24.04 com distrobox:
```bash
sudo pacman -S distrobox podman
distrobox create -n ros -i ubuntu:24.04 && distrobox enter ros
# dentro da caixa:
sudo apt update && sudo apt install -y curl software-properties-common
sudo add-apt-repository -y universe
export ROS_APT_SOURCE_VERSION=$(curl -s https://api.github.com/repos/ros-infrastructure/ros-apt-source/releases/latest | grep -F "tag_name" | awk -F\" '{print $4}')
curl -L -o /tmp/ros2-apt-source.deb "https://github.com/ros-infrastructure/ros-apt-source/releases/download/${ROS_APT_SOURCE_VERSION}/ros2-apt-source_${ROS_APT_SOURCE_VERSION}.noble_all.deb"
sudo dpkg -i /tmp/ros2-apt-source.deb
sudo apt update && sudo apt install -y ros-jazzy-desktop ros-jazzy-slam-toolbox ros-jazzy-navigation2 ros-jazzy-nav2-bringup ros-jazzy-robot-localization ros-jazzy-teleop-twist-keyboard
echo '[ -f /opt/ros/jazzy/setup.bash ] && source /opt/ros/jazzy/setup.bash' >> ~/.bashrc
```

**Teste:** `ros2 topic list` tem que mostrar o `/scan`. Depois, no `rviz2`:

1. Em **Fixed Frame**, coloque `laser`.
2. Adicione **/scan → LaserScan**.
3. Se não aparecer nada, mude **Reliability** para **Best Effort**.

**Rede:** a rede da UnB pode bloquear o multicast que o ROS usa para descobrir os outros computadores. Se o notebook não enxergar o Pi, use um roteador ou hotspot próprio, ou um Discovery Server.

### 8.6 Referência estudada: HelMoRo (Helbling Technik)

O HelMoRo tem sensores parecidos com os seus (LiDAR Slamtec, Astra Pro, BNO055, 4 rodas) e confirma a arquitetura:

- **Motores:** um nó de motores converte `cmd_vel` → velocidade de cada lado, usando o mesmo cálculo de um robô de 2 rodas: v ± ω·L/2.
- **Odometria:** o EKF (`robot_localization`) usa só a **velocidade para frente das rodas** e a **velocidade de giro do giroscópio**. O ângulo calculado pelas rodas é ignorado, por causa da derrapagem.
- **Mapa:** `slam_toolbox` em mapeamento, resolução de 5 cm.
- **Navegação:** Nav2, com o destino escolhido pelo "2D Goal Pose" no RViz.
- **Comandos:** `twist_mux` dá prioridade ao joystick sobre o Nav2, com tempo de expiração de 0,12 s.
- **Diferenças para o seu robô:**
  - Eles usam controladoras RoboClaw, que fazem o PID na própria placa. Com o MD10C, o **PID tem que rodar no nó da base**, no Pi.
  - O computador deles (Pi 5 ou Jetson) roda tudo a bordo. Aqui, o SLAM e o Nav2 vão para o notebook.
- **Para reaproveitar:** a configuração do EKF, o `twist_mux` e o driver `bno055` (flynneva), que aceita UART.
- Fontes: https://helbling-technik.github.io/HelMoRo/ e https://github.com/Helbling-Technik/HelMoRo-software-ROS2

### 8.7 Mapa esperado

- `slam_toolbox` gera um **mapa 2D de ocupação**, como uma planta baixa: cinza é desconhecido, branco é livre e preto é parede.
- Para salvar: `ros2 run nav2_map_server map_saver_cli -f mapa`. Isso gera `mapa.pgm` e `mapa.yaml`.
- Um mapa **3D colorido** seria com o RTAB-Map e a Astra. Fica para depois, rodando no notebook.
- **Para o mapa sair bom:** dirigir devagar, fazer curvas suaves e voltar a passar por lugares já mapeados.

---

## 9. Medidas do robô (para a descrição do robô e a odometria)

| Medida | Valor | Situação |
|---|---|---|
| Chassi | 20 cm (largura) × 21 cm (comprimento) | ok |
| Diâmetro da roda | 8 cm | ok |
| Rodas para fora do chassi | não (por enquanto) | ok |
| Distância entre o centro da roda esquerda e o da direita | ? | **falta esclarecer** o valor de "11,5 cm": é entre esquerda e direita, ou entre frente e trás? |
| Posição do LiDAR | ~centro do chassi (8 cm até a frente, 7,5 cm até trás; ~0,25 cm à frente do centro), 10 cm do chão, lado do cabo para trás | conferir no RViz se a frente está certa (talvez seja preciso girar 180°) |
| Contagens do encoder por volta da roda | ? | **medir**: `sudo pigpiod && python3 teste_motores.py encoder` |

---

## 10. Pendências / próximos passos

- [ ] Corrigir a alimentação do Pi (ver 4.2) e confirmar `throttled=0x0`.
- [ ] Atualizar o `teste_motores.py` e o `controle_wasd.py` no Pi.
- [ ] Criar o serviço do `pigpiod` para iniciar no boot.
- [ ] Medir o `CPR_SAIDA` (`teste_motores.py encoder`).
- [ ] Esclarecer a distância entre as rodas esquerda e direita.
- [ ] Confirmar que o `/scan` tem dados (`echo --no-daemon`).
- [ ] Instalar o ROS Jazzy no notebook (distrobox) e ver o `/scan` no RViz.
- [ ] Escrever o **nó da base** (Python): `cmd_vel` → PID por lado → MD10C, encoders → `/odom`, parada automática se o comando parar de chegar, ganhos prontos para o PSO.
- [ ] Driver do BNO055 (`bno055` flynneva, UART) → `/imu`.
- [ ] Descrição do robô (URDF / TF estáticos `base_link → laser`, `base_link → imu`).
- [ ] EKF (`robot_localization`) no notebook.
- [ ] Primeiro mapa com o `slam_toolbox`.
- [ ] Nav2: ir até um ponto do mapa.
- [ ] Câmera de profundidade na ROS (320×240, 15 fps, só profundidade).
- [ ] Ajustar o PID por PSO no robô físico.

---

## 11. Escrita do TCC (LaTeX)

Os comandos de instalação, compilação e correção do LaTeX estão em `comandosLatex.md`.

- Arquivo principal: `main.tex`. Capítulos escritos: `editaveis/hardware.tex` e `editaveis/software.tex`.

---

## 12. Comandos úteis no Pi

```bash
free -h                      # memória (olhe a coluna "available")
watch -n 1 free -h           # memória ao vivo
htop                         # processos (F6 → PERCENT_MEM)
vcgencmd get_throttled       # 0x0 = alimentação ok
dmesg -w | grep -i voltage   # avisos de tensão baixa ao vivo
dmesg | grep -iE "mmc|I/O error|EXT4-fs error"   # saúde do cartão microSD
lsusb; ls /dev/video* /dev/ttyUSB*               # dispositivos USB
sudo shutdown now            # desligar (depois desligue a SW2)
```

Acesso: `ssh dasneves@10.74.1.113`. Para copiar arquivos: `scp arquivo dasneves@10.74.1.113:~/` (não esqueça o `:`).

# ARENA

**Plataforma robótica móvel com ROS 2 para mapeamento, navegação autônoma e comparação de algoritmos de controle**

Trabalho de Conclusão de Curso em Engenharia de Software, Faculdade UnB Gama (FGA), Universidade de Brasília.

- **Autor:** Felipe das Neves Freire
- **Orientador:** Prof. Dr. Renato Coral Sampaio

---

## Sobre o projeto

O ARENA é um robô de tração nas quatro rodas (4WD), montado com componentes de custo acessível, que:

1. **mapeia** um ambiente com um LiDAR e uma câmera de profundidade;
2. **navega sozinho** até um ponto escolhido no mapa, usando ROS 2;
3. serve de **bancada para comparar algoritmos de controle** no mesmo hardware, com os mesmos ensaios e as mesmas métricas.

A maioria das comparações entre controladores é feita em simulação, que não reproduz bem a zona morta e a saturação dos motores, o escorregamento das rodas, o ruído dos sensores e o limite de processamento do computador embarcado. No ARENA, os drivers de motor não fazem controle próprio. Por isso o algoritmo de controle fica todo no software e pode ser trocado sem mudar o resto do sistema.

### Questões de pesquisa

1. É possível construir, com componentes de baixo custo e ROS 2, um robô 4WD capaz de mapear e navegar de forma autônoma?
2. Como estruturar o software para que diferentes algoritmos de controle possam ser trocados e comparados nas mesmas condições?
3. Como o PID clássico, o MPC e os algoritmos bioinspirados se comparam, em um robô real, quanto ao erro de seguimento, ao esforço de controle e ao custo computacional?
4. Quais desses algoritmos podem rodar no computador embarcado e quais precisam rodar na estação de base?

---

## Hardware

| Função | Componente |
|---|---|
| Computador embarcado | Raspberry Pi 3 (1 GB), Raspberry Pi OS Trixie 64-bit |
| Chassi | Kit 4WD, 20 cm × 21 cm, rodas de 8 cm |
| Motores | 4× JGB37-520 12 V, 333 rpm, com encoder Hall em quadratura (11 PPR) |
| Drivers | 2× Cytron MD10C R3 (PWM + DIR), um por lado |
| IMU | Bosch BNO055 (UART) |
| LiDAR | Slamtec RPLIDAR C1 (USB, 460800 baud) |
| Câmera de profundidade | Orbbec Astra Pro |
| Alimentação | LiPo 4S com BMS, *buck* de 12 V para os motores e *buck* de 5 V / 5 A para o Pi |

A pinagem completa está no capítulo de hardware do TCC (branch `latex`).

---

## Arquitetura de software

O Raspberry Pi 3 não tem capacidade para rodar SLAM e navegação. Por isso o processamento é dividido entre o robô e um notebook, que se comunicam por Wi-Fi com ROS 2 Jazzy:

```
 Raspberry Pi (robô)                        Notebook (estação de base)
 ─────────────────────                      ──────────────────────────
 sllidar_ros2 ─────────── /scan ──────────▶ slam_toolbox ── /map ──▶ Nav2
 nó da base ───────────── /odom ──────────▶ robot_localization (EKF)  │
 bno055 ───────────────── /imu ───────────▶        │                  │
 nó da base ◀──────────── /cmd_vel ─────────────────────────────────┘
   (PID / MPC / ... por lado → MD10C)                     RViz, teleoperação
```

- **No robô:** os drivers dos sensores e o **nó da base**, que converte `/cmd_vel` na velocidade de cada lado, roda o controlador de velocidade das rodas e publica a odometria.
- **No notebook:** fusão de sensores (EKF: velocidade linear das rodas + velocidade angular do giroscópio), mapeamento com `slam_toolbox`, navegação com Nav2 e visualização no RViz.

### Algoritmos de controle

Os algoritmos são comparados em dois níveis:

- **Velocidade das rodas**, no nó da base. O algoritmo é escolhido por um parâmetro do ROS 2.
- **Seguimento de trajetória**, como controlador (*plugin*) do Nav2.

| Família | Algoritmos |
|---|---|
| Clássico | PID (referência), com *anti-windup* |
| Preditivo | MPC, baseado no modelo de primeira ordem identificado na bancada |
| Bioinspirado | PSO (enxame de partículas) para sintonia, e outros |
| Outros | LQR, fuzzy, adaptativo... (a definir) |

Todos passam pelos mesmos ensaios (degraus, rampas e trajetórias, com repetição). Eles são comparados por IAE, sobressinal, tempo de acomodação, esforço de controle e tempo de cálculo, com os dados gravados com `ros2 bag`.

---

## Organização do repositório

Cada parte do projeto fica em uma branch:

| Branch | Conteúdo |
|---|---|
| `main` | Este README e a licença |
| `latex` | Texto do TCC (template da FGA com abnTeX2), `agent.md` (registro do projeto), `comandosLatex.md` e `diretrizesTCC.md` |
| `motorEncoders` | `teste_motores.py` (bancada dos motores e encoders) e `teste_encoders.py` (diagnóstico dos encoders) |
| `lidar` | `lidar.py` (leitor do RPLIDAR C1), `ver_lidar.py` (visualização no notebook) e `profundidade.py` (câmera Astra) |

```bash
git clone git@github.com:FelipeFreire-gf/ehoformas.git
cd ehoformas
git switch motorEncoders   # ou: latex, lidar
```

---

## Primeiros passos

### Testes dos motores e encoders (no Raspberry Pi)

Rode sempre com as rodas no ar.

```bash
sudo pigpiod                          # serviço de GPIO (pigpio)
python3 teste_encoders.py             # gire as rodas dianteiras à mão
python3 teste_motores.py encoder      # mede as contagens por volta da roda
python3 teste_motores.py direcao      # confere o sentido de cada lado
python3 teste_motores.py varredura    # zona morta e curva de velocidade
python3 teste_motores.py degrau       # constante de tempo
python3 teste_motores.py parar        # emergência: zera o PWM
```

### LiDAR (sem ROS)

```bash
ssh <usuario>@<ip-do-pi> "python3 lidar.py stream" | python3 ver_lidar.py
```

### Compilar o TCC

Na branch `latex`, abra o `main.tex` no TeXstudio ou rode:

```bash
latexmk -pdf main.tex
```

As dependências e os erros comuns estão em `comandosLatex.md`.

---

## Situação atual

- [x] Montagem do hardware e esquemático (Proteus, rev. 1.1)
- [x] Scripts de bancada dos motores, encoders, LiDAR e câmera
- [x] ROS 2 Jazzy no Pi e driver do LiDAR (`sllidar_ros2`) compilado e detectando o sensor
- [ ] Confirmar a chegada dos dados no `/scan` e ver o tópico no RViz do notebook
- [ ] Correção da alimentação do Pi (subtensão)
- [ ] Nó da base (controle de velocidade intercambiável + odometria)
- [ ] Driver da IMU, descrição do robô (URDF) e EKF
- [ ] Primeiro mapa com o `slam_toolbox`
- [ ] Navegação autônoma com o Nav2
- [ ] Implementação e comparação dos controladores

---

## Licença

Este projeto é distribuído sob a **GNU General Public License v3.0**. Veja o arquivo [LICENSE](LICENSE).

Você pode usar, estudar, modificar e redistribuir o código. Versões modificadas que forem distribuídas também precisam ser GPL v3 e ter o código-fonte disponível.

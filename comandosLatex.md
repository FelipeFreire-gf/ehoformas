# TCC — Comandos do LaTeX

Comandos para instalar, compilar e corrigir o texto do TCC no notebook (Arch Linux).
O texto usa o **template da FGA** (https://github.com/fga-unb/template-latex-tcc) com a classe abnTeX2.

---

## 1. Instalação (Arch)

```bash
sudo pacman -Syu
sudo pacman -S texstudio texlive-basic texlive-latex texlive-latexrecommended texlive-latexextra \
  texlive-fontsrecommended texlive-langportuguese texlive-publishers texlive-bibtexextra \
  texlive-pictures texlive-mathscience biber
```

Pacotes que faltaram na primeira compilação:

```bash
sudo pacman -S texlive-langfrench texlive-langspanish   # idiomas que o abnTeX2 carrega
sudo pacman -S ghostscript texlive-fontutils            # conversão .eps -> .pdf (epstopdf/repstopdf)
which repstopdf                                         # tem que mostrar /usr/bin/repstopdf
```

Se `which repstopdf` não mostrar nada, descubra qual pacote tem o programa:

```bash
sudo pacman -Fy && pacman -F epstopdf
```

Se der erro 404 de servidor, atualize os mirrors:

```bash
sudo reflector --country Brazil --protocol https --age 12 --sort rate --save /etc/pacman.d/mirrorlist
sudo pacman -Syyu
```

---

## 2. Template

O Docker do README do template não é necessário.

```bash
git clone https://github.com/fga-unb/template-latex-tcc.git tcc && cd tcc/latex
```

- Arquivo principal: **`main.tex`**.
- Edite só a pasta `editaveis/`. Os dados do trabalho (autor, título, orientador) ficam em `editaveis/informacoes.tex`.
- Capítulos escritos: `editaveis/hardware.tex` e `editaveis/software.tex`, incluídos no `main.tex` logo depois da introdução.
- Referências: `bibliografia.bib`.

---

## 3. Compilar

**No TeXstudio:**

1. Abra `main.tex`.
2. Em Opções → Configurar TeXstudio → Compilar, escolha **PdfLaTeX** como compilador e **BibTeX** como bibliografia.
   Outra opção é escolher **Latexmk** como compilador padrão, que já roda tudo quantas vezes for preciso.
3. Compile com **F5**. Se as referências aparecerem como **?**, rode **F8** (BibTeX) e depois F5 de novo.

**Pelo terminal** (mesma sequência do TeXstudio):

```bash
pdflatex main.tex && bibtex main && pdflatex main.tex && pdflatex main.tex
# ou, de uma vez:
latexmk -pdf main.tex
```

---

## 4. Figuras EPS

O `pdflatex` não lê `.eps` direto. Com o `repstopdf` instalado, ele converte sozinho e gera `figuras/<nome>-eps-converted-to.pdf`.

Conversão manual com o Ghostscript (dentro de `figuras/`):

```bash
gs -q -dSAFER -dEPSCrop -sDEVICE=pdfwrite -o nome-eps-converted-to.pdf nome.eps
```

Outra opção é converter uma vez e usar o PDF no `.tex`:

```bash
cd figuras && for f in *.eps; do epstopdf "$f"; done
# ou: ps2pdf -dEPSCrop figuras/capa.eps figuras/capa.pdf
```

Depois troque `figuras/capa.eps` por `figuras/capa.pdf` em `fixos/novoscomandos.tex`, e `figuras/fig01.eps` por `figuras/fig01.pdf` em `editaveis/elementosdotexto.tex`.

Com o pdflatex, figuras PNG e JPG funcionam direto no `\includegraphics`.

---

## 5. Erros e avisos já vistos

| Mensagem | O que fazer |
|---|---|
| `babel Error: Unknown option 'french'` / `'spanish'` | Instalar `texlive-langfrench texlive-langspanish`, ou tirar `french,spanish` do `\documentclass` |
| `File 'figuras/...-eps-converted-to.pdf' not found` | Instalar o `epstopdf` (seção 1) ou converter na mão (seção 4) |
| `Citation ... undefined`, `No file main.aux/.lof/.lot`, `LastPage undefined` | Normal na 1ª compilação: rodar BibTeX e compilar de novo (ou usar Latexmk) |
| `Name 'brazil' is deprecated` | Só um aviso. Pode trocar `brazil` por `brazilian` no `\documentclass` |
| `\settocpreprocessor is marked deprecated` | Vem de dentro da classe abntex2. Ignorar |
| `destination with the same identifier (page.1)` | Comum no abnTeX2 (páginas sem número). Inofensivo |
| *Bad box* na `fichacatalografica.tex` | Espaçamento do modelo de ficha. Ignorar |

---

## 6. Git

```bash
git switch latex                     # mudar para a branch do texto
git switch -c nova-branch            # criar e mudar
git branch -m nome-antigo novo-nome  # renomear
git push origin -u novo-nome         # enviar com o nome novo
git push origin --delete nome-antigo # apagar a antiga no remoto
```

Arquivos gerados pela compilação (`*.aux`, `*.log`, `*.toc`, `*.bbl`, `*.blg`, `*.synctex.gz`, `*-eps-converted-to.pdf`) podem ir para o `.gitignore`.

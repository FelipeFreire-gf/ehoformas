# TCC — Diretrizes de formatação da FGA

Resumo das instruções que vinham como capítulos de exemplo no template da FGA ("Aspectos Gerais", "Considerações sobre os Elementos Textuais", "Elementos do Texto" e "Elementos do Pós-Texto"). Esses capítulos foram tirados do `main.tex`; este arquivo guarda o conteúdo para consulta.

O modelo LaTeX já aplica sozinho a formatação básica (papel, fonte, margens, numeração e espaçamento). Ela fica aqui só como referência.

---

## 1. Aspectos gerais

- As instruções são o mínimo exigido para uniformizar os relatórios de TCC da FGA. Estilo, concisão e clareza são responsabilidade do autor.
- TCC 1 e TCC 2 seguem um **regulamento próprio** aprovado pelo Colegiado da FGA, e o aluno deve conhecê-lo.

### 1.1 Estrutura do trabalho

Os itens marcados com *(opcional)* podem ser omitidos. Os marcados com **(essencial)** são obrigatórios.

**Pré-textuais**
- Capa
- Folha de rosto
- Dedicatória *(opcional — removida deste trabalho)*
- Agradecimentos *(opcional)*
- Epígrafe *(opcional)*
- Resumo
- Abstract
- Lista de figuras
- Lista de tabelas
- Lista de símbolos
- Sumário

**Textuais**
- Introdução **(essencial)**
- Desenvolvimento **(essencial)**
- Conclusões **(essencial)**

**Pós-textuais**
- Referências bibliográficas
- Bibliografia *(opcional)*
- Anexos
- Contracapa

No modelo, os arquivos que se editam ficam em `editaveis/`. Os de `fixos/` normalmente não precisam ser mexidos.

### 1.2 Formatação básica (já configurada no modelo)

**Papel:** A4 (21 cm × 29,7 cm), branco, de 75 a 90 g/m².

**Fonte**
- Arial ou Times New Roman tamanho 12 no corpo do texto.
- Tamanho 10 para paginação, legendas e notas de rodapé.
- Citações diretas com mais de três linhas: tamanho 10, sem itálico, negrito ou aspas.
- Itálico para nomes científicos e expressões estrangeiras, exceto as latinas.

**Margens**
- Esquerda: 3 cm
- Direita: 2 cm
- Superior: 3 cm
- Inferior: 2 cm

**Numeração de páginas**
- A contagem começa na folha de rosto, mas o número só aparece a partir da Introdução, a primeira página textual.
- Algarismos arábicos, tamanho 10, no canto superior direito, a 2 cm da borda superior, sem traços, pontos ou parênteses.
- Apêndices e anexos continuam a numeração do texto.

**Espaçamento e alinhamento**
- Entrelinhas de 1,5 no corpo do texto.
- Espaçamento simples no resumo, nas citações com mais de três linhas, nas notas de rodapé, nas legendas e nas referências.
- Recuo de 1,25 cm na primeira linha de cada parágrafo.
- Títulos de seção começam no alto da folha, separados do texto por um espaço de 1,5.
- Texto justificado. As exceções são as citações longas, com recuo de 4 cm da margem esquerda, e as referências, alinhadas só à esquerda.

**Quebra de capítulos e aproveitamento de páginas**
- Cada capítulo começa em página nova.
- Evite uma última página de capítulo com só 2 ou 3 linhas. Se acontecer, ajuste o texto.
- Evite espaços vazios. Se uma figura ou tabela não couber no fim da página, reposicione o texto para preencher o vazio.
- Sempre que possível, não quebre uma figura ou tabela entre páginas.

### 1.3 Cópias

- **Revisão da banca (TCC 1 e TCC 2):** uma cópia para cada membro da banca, entregue na Secretaria da FGA.
- **Depois da aprovação em TCC 2:**
  - 1 cópia encadernada;
  - 1 cópia não encadernada (folhas avulsas);
  - 1 cópia em mídia digital com todos os arquivos do trabalho: o texto, os arquivos de origem dos gráficos e das figuras e o código-fonte desenvolvido. O autor deve garantir que a mídia não tenha vírus.

Confira com a coordenação se essas regras de entrega ainda valem, porque o texto do template é de 2013.

---

## 2. Elementos textuais

### 2.1 Introdução

- Não deve ter agradecimentos nem comentários pessoais sobre a escolha ou a relevância do tema.
- Já no primeiro parágrafo deve deixar claro o que o trabalho pretende.
- Vale reescrevê-la no final, quando se tem a visão do trabalho inteiro.
- Sempre que fizer sentido, deve conter:
  - a contextualização do tema;
  - a justificativa ou relevância;
  - o problema de pesquisa;
  - os objetivos geral e específicos;
  - um resumo da metodologia;
  - a organização do trabalho.

### 2.2 Desenvolvimento

- Dividido em seções. As seções primárias, normalmente os capítulos, são numeradas a partir de 1. As secundárias, terciárias e seguintes saem da divisão de cada uma delas.
- É a parte mais importante, e exige organização, objetividade e clareza.
- Convém dividir em pelo menos três partes:
  1. **Referencial teórico:** análise dos trabalhos relevantes encontrados na pesquisa bibliográfica.
  2. **Metodologia:** todos os passos usados, com ênfase em (1) a população ou os sujeitos da pesquisa, (2) os materiais e equipamentos e (3) os procedimentos de coleta de dados.
  3. **Resultados, discussão e conclusões:** os dados obtidos, a análise à luz do referencial teórico e as conclusões.

### 2.3 Editor de texto

O programa usado para escrever é escolha do autor.

---

## 3. Elementos do texto

### 3.1 Corpo do texto

- Use linguagem técnica. Para a terminologia de metrologia, siga o Vocabulário Internacional de Metrologia (INMETRO).
- Use unidades do SI. Outras unidades podem vir entre parênteses, como unidade secundária. Exceção: unidades que fazem parte de nomes comerciais (ex.: "disquete de 3½ polegadas").
- Use vírgula como separador decimal.
- Apresente resultados experimentais com a incerteza de medição.

### 3.2 Títulos de seções

| Nível | Exemplo | Formato |
|---|---|---|
| Primária | **1 SEÇÃO PRIMÁRIA** | maiúsculas, negrito, tamanho 12 |
| Secundária | 1.1 SEÇÃO SECUNDÁRIA | maiúsculas, normal, tamanho 12 |
| Terciária | **1.1.1 Seção terciária** | só a primeira letra maiúscula, negrito, tamanho 12 |
| Quaternária | 1.1.1.1 Seção quaternária | só a primeira letra maiúscula, normal, tamanho 12 |
| Quinária | *1.1.1.1.1 Seção quinária* | só a primeira letra maiúscula, itálico, tamanho 12 |

No LaTeX, esses níveis correspondem a `\chapter`, `\section`, `\subsection`, `\subsubsection` e `\paragraph`.

### 3.3 Notas de rodapé

Numeradas em sequência (1, 2, 3...) ao longo do texto, no rodapé da página em que aparecem. No LaTeX: `\footnote{...}`.

### 3.4 Equações

- Numeradas em sequência, com algarismos arábicos entre parênteses, alinhados à direita.
- No meio da frase, cite como "Eq. (1)". No início da frase, como "Equação (1)".
- Use parênteses para evitar ambiguidade nos denominadores.
- Todo símbolo deve estar na lista de símbolos. Ele também pode ser explicado logo depois da equação.
- Os símbolos citados no texto devem ter a mesma formatação usada na equação.

```latex
\begin{equation}
	\label{eq:nome}
	v = \frac{v_d + v_e}{2}
\end{equation}
... como mostra a Eq.~(\ref{eq:nome}).
```

### 3.5 Figuras e gráficos

- Centralizadas, com legenda.
- Rótulos e anotações em português, com as grandezas em unidades do SI e fonte compatível com a do texto.
- Os eixos dos gráficos têm título em português e a unidade entre colchetes. Exemplo: "Velocidade [m/s]".
- Numeradas em sequência e todas citadas no texto, com qualidade para impressão em cores e em preto e branco.
- **Citação:** "Fig. (1)" no meio da frase, "Figura (1)" no início, e "(Fig. 1)" quando a referência é implícita. Use o plural para mais de uma figura.
- Posicione cada figura o mais perto possível da primeira citação, de preferência logo depois do parágrafo que a cita.

### 3.6 Tabelas

- Centralizadas, com a legenda **acima** da tabela.
- Rótulos em português e unidades do SI, mostradas só na primeira linha ou coluna, entre colchetes.
- **Citação:** "Tab. (1)" no meio da frase, "Tabela (1)" no início, e "(Tab. 1)" quando a referência é implícita.
- Posicione cada tabela o mais perto possível da primeira citação.

Modelo usado nos capítulos deste trabalho:

```latex
\begin{table}[htb]
	\centering
	\caption{Título da tabela}
	\label{tab:nome}
	\begin{tabular}{|l|c|}
		\hline
		\textbf{Coluna} & \textbf{Valor [unidade]} \\ \hline
		... & ... \\ \hline
	\end{tabular}
	\legend{Fonte: Autor.}
\end{table}
```

### 3.7 Citação de referências

- Siga a norma ABNT NBR 6023 (referências) e a NBR 10520 (citações).
- Em trabalhos com até dois autores, cite os dois nomes.
- No modelo (`abntex2cite` com a opção `alf`):
  - `\cite{chave}` gera "(AUTOR, ano)", para usar no fim da frase;
  - `\citeonline{chave}` gera "Autor (ano)", para usar dentro da frase. Ex.: "\citeonline{siegwart2011} mostram que...".

---

## 4. Elementos do pós-texto

### 4.1 Referências bibliográficas

- Começam em página nova, logo depois do último capítulo.
- Primeira linha de cada referência alinhada à esquerda e as demais com recuo de 0,5 cm. Não precisa de linha em branco entre elas.
- **Toda referência da lista deve ser citada no texto, e toda citação deve estar na lista.** O BibTeX já garante a primeira parte: só aparecem na lista as entradas do `bibliografia.bib` que forem citadas.
- Ordem alfabética pelo sobrenome do primeiro autor. O estilo `abntex2-alf` faz isso sozinho.
- Não cite artigos ainda não publicados. Artigos aceitos mas ainda não publicados são citados como "no prelo" (*in press*).
- Siga rigorosamente a norma ABNT NBR 6023. Um guia útil é "Como fazer referências: bibliográficas, eletrônicas e demais formas de documentos", de M. B. B. Arruda.

### 4.2 Anexos

- Ficam numa seção separada, depois das referências.
- Numerados em algarismos romanos maiúsculos (I, II, III...).
- A primeira página dos anexos tem um índice com o título e a página inicial de cada anexo.
- **Citação:** "Anexo I" no texto ou "(Anexo I)" quando a referência é implícita. Use o plural para mais de um anexo.
- Apêndices são textos do próprio autor. Anexos são documentos de terceiros (por exemplo, datasheets). No modelo, eles ficam em `editaveis/apendices.tex` e `editaveis/anexos.tex`.

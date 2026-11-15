# Especificação do Experimento

**Versão 1.0 — 15/11/2026.** Este documento fixa o objeto de estudo, os fatores, os cenários, o oráculo e as hipóteses **antes** de qualquer medição. Alterações posteriores devem gerar nova versão, com a mudança e o motivo registrados no histórico ao final. Recomenda-se marcar este arquivo com uma *tag* no repositório antes de executar o experimento, para que a ordem "especificar, depois medir" seja verificável.

## 1. Objetivo e Questões de Pesquisa

Investigar quais práticas associadas à programação funcional contribuem para a idempotência e a testabilidade de pipelines de dados em lote, separando-as de práticas de engenharia independentes de paradigma.

- **QP1 (reexecução):** quais fatores, isoladamente e em combinação, determinam se um pipeline produz o resultado correto após reexecuções, *backfills*, falhas parciais e chegadas irregulares de dados?
- **QP2 (testabilidade):** o protocolo da QP2 será especificado na versão 1.1 deste documento, antes da escrita das suítes de teste.

## 2. Objeto de Estudo

Um pipeline em lote, em Python (≥ 3.10), que processa eventos de pedidos de uma data lógica *D* e grava uma partição de saída para *D*. As etapas são:

1. **Leitura:** eventos cuja data de ocorrência é *D* e que já chegaram à origem no instante da execução.
2. **Normalização:** os eventos existem em dois formatos (v1 plano e v2 aninhado). Registros que não se encaixam em nenhum formato, ou com valor ilegível, são descartados.
3. **Validação:** mantém apenas eventos com status `confirmado` e valor não negativo.
4. **Deduplicação:** quando ativa, mantém um registro por `id_evento`.
5. **Enriquecimento:** associa a cada evento o nível do cliente (`bronze`, `prata`, `ouro`) a partir de uma tabela de referência estática.
6. **Agregação:** por (data, nível), conta pedidos e soma a receita em centavos (inteiros, sem ponto flutuante).
7. **Escrita:** grava as linhas agregadas na partição `data=D` do destino.

O código fica em `src/pipeline/`. A divisão entre núcleo (`nucleo.py`: etapas 2 a 6) e casca (`casca.py`: relógio, origem, destino, etapas 1 e 7) segue o padrão *functional core, imperative shell*.

## 3. Fatores

Quatro fatores binários, cada um com uma variante que segue o princípio (1) e outra que o viola (0). A combinação completa gera 2⁴ = 16 configurações, rotuladas pela sequência T W P D (ex.: `1111` segue todos; `0111` usa o relógio do sistema).

| Fator | Variante 1 (segue) | Variante 0 (viola) | Classificação |
|---|---|---|---|
| **T** Tempo injetado | a data a processar é parâmetro recebido do orquestrador | a data é derivada do relógio do sistema ("ontem") | Funcional |
| **W** Escrita por sobrescrita | a partição *D* é substituída integralmente | as linhas são anexadas à partição *D* | Independente de paradigma |
| **P** Transformações puras | cada etapa devolve dados novos, sem estado entre chamadas | a normalização altera o registro recebido e a agregação usa um acumulador mutável que persiste entre chamadas no mesmo processo | Funcional |
| **D** Deduplicação por chave | um registro por `id_evento`, escolhido de forma determinística | sem deduplicação | Independente de paradigma |

**Critério de classificação.** Um fator é classificado como *funcional* quando sua variante 1 decorre de transparência referencial: a saída da etapa depende apenas de seus argumentos explícitos. T torna explícita uma entrada antes oculta (o relógio). P elimina efeitos colaterais e estado compartilhado. W e D tratam da interação com o armazenamento e da semântica dos dados, e podem ser adotados em código imperativo sem qualquer mudança de estilo.

Essa classificação é discutível. Por exemplo, a sobrescrita de partição é apresentada por Beauchemin (2018) como parte da "engenharia de dados funcional". O artigo deve registrar a classificação como decisão de projeto e discuti-la nas ameaças à validade.

## 4. Modelo de Processo

Parte das falhas depende de o estado em memória sobreviver entre execuções. Por isso, cada cenário declara se as execuções ocorrem:

- **em processo novo**, como uma tarefa reexecutada por um orquestrador: estado de módulo zerado e cache da origem vazio; ou
- **no mesmo processo**, como uma célula reexecutada num *notebook* ou um laço de *backfill* num único *script*: estado de módulo e cache da origem preservados.

A origem mantém em cache, por processo, os registros já desserializados, à semelhança de um *DataFrame* em cache numa sessão. Assim, uma alteração feita num registro lido fica visível numa nova leitura no mesmo processo.

## 5. Dados

Gerados sinteticamente por `src/pipeline/dados.py`, com os parâmetros fixos abaixo.

| Parâmetro | Valor |
|---|---|
| Dias | 5 (a partir de 02/03/2026) |
| Eventos por dia | 150 |
| Clientes | 40, com nível sorteado |
| Formatos | v1 ou v2, 50% cada |
| Defeitos | 85% sem defeito; 4% sem cliente; 4% valor negativo; 4% sem valor; 3% valor ilegível |
| Status | 5% `cancelado`, demais `confirmado` |
| Chegada normal | 1 a 30 min após o evento |
| Duplicatas (quando ativas) | 10% dos eventos reentregues 1 a 20 min depois, com conteúdo idêntico |
| Atrasos (quando ativos) | 10% dos eventos chegam em D+1, entre 10h e 20h |
| Sementes | 0 a 29 (30 conjuntos de dados) |

A verdade (o conjunto de eventos únicos com seus atributos) é gerada por um gerador pseudoaleatório; as duplicatas e os atrasos, por outro. Assim, a mesma semente produz a mesma verdade em todos os cenários.

## 6. Oráculo e Métrica

- **Gabarito:** calculado em `dados.py` diretamente a partir da verdade gerada, por código independente do pipeline. Não é a saída de nenhuma configuração.
- **Comparação:** ao fim de cada cenário, o conteúdo completo do destino (todas as partições, como multiconjunto de linhas) é serializado de forma canônica e comparado ao gabarito. Partições escritas em datas erradas ou linhas duplicadas tornam o resultado incorreto.
- **Métrica primária:** para cada configuração e cenário, a proporção das 30 sementes em que o destino coincide com o gabarito.

## 7. Cenários

A execução agendada da data *D* ocorre em D+1 às 02:00.

| Cenário | Dados | Execuções | Processo |
|---|---|---|---|
| **C0** Controle | limpos | cada dia uma vez, no horário agendado | novo |
| **C1** Execução duplicada | limpos | cada dia no horário agendado e de novo às 02:05 | mesmo |
| **C2** *Backfill* | limpos | pipeline implantado depois: em (último dia + 5) às 09:00, os 5 dias são executados em sequência | mesmo |
| **C3** Falha parcial e nova tentativa | limpos | execução agendada; num dia sorteado, a escrita falha após *k* linhas (*k* sorteado entre 1 e o número de linhas − 1) e a tarefa é reexecutada às 02:10 | novo |
| **C4** Entrega duplicada | com duplicatas | cada dia uma vez, no horário agendado | novo |
| **C5** Dados atrasados | com atrasos | execução agendada; em (último dia + 2) às 09:00, todos os dias são reprocessados | novo |

**C0 é condição de validade:** todas as 16 configurações devem passar nele. Uma falha em C0 indicaria erro de implementação, e não efeito de reexecução.

**Excluído:** *backfill* fora de ordem. O pipeline não tem dependência entre partições, então a ordem dos dias não altera o resultado por construção. O cenário apenas duplicaria C2.

## 8. Hipóteses (Registradas Antes da Execução)

Previsão analítica, para cada fator violado isoladamente (os demais na variante 1), de quais cenários falham:

| Configuração | C0 | C1 | C2 | C3 | C4 | C5 | Mecanismo previsto |
|---|---|---|---|---|---|---|---|
| `1111` | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | — |
| `0111` (sem T) | ✓ | ✓ | ✗ | ✓ | ✓ | ✗ | execução tardia processa a data errada |
| `1011` (sem W) | ✓ | ✗ | ✓ | ✗ | ✓ | ✗ | anexação duplica linhas já escritas |
| `1101` (sem P) | ✓ | ✗ | ✗ | ✓ | ✓ | ✓ | registro em cache convertido duas vezes; acumulador carrega totais de execuções anteriores |
| `1110` (sem D) | ✓ | ✓ | ✓ | ✓ | ✗ | ✓ | duplicatas contadas duas vezes |

As 11 configurações restantes são combinações; a previsão é que um cenário falhe sempre que algum fator violado falharia nele isoladamente. Divergências entre previsão e observação serão relatadas e discutidas.

**Natureza do resultado.** Como o pipeline e os cenários são construídos pelo autor, a maior parte do resultado é previsível por análise. A contribuição do experimento não é descobrir falhas inesperadas, e sim: (i) verificar executavelmente o mapeamento entre práticas e cenários de falha; (ii) testar a hipótese de aditividade nas combinações; e (iii) separar as práticas funcionais das independentes de paradigma de forma reproduzível.

## 9. Ameaças à Validade Conhecidas

- **Construção:** o autor escreve todas as variantes; a variante 0 de cada fator pode não representar o código encontrado na prática. Mitigação: cada variante 0 reproduz um defeito documentado na literatura técnica (uso de `now()`, `INSERT` em vez de sobrescrita, mutação *in place*, argumento padrão mutável, ausência de deduplicação), e as escolhas ficam registradas aqui antes das medições.
- **Interna:** os efeitos de P dependem do modelo de processo (Seção 4). Isso é declarado por cenário, não omitido.
- **Externa:** um único pipeline, pequeno, sem paralelismo, em Python puro. Os resultados não se generalizam diretamente para motores distribuídos como o Spark.
- **Classificação dos fatores:** ver Seção 3.

## Histórico

| Versão | Data | Alteração |
|---|---|---|
| 1.0 | 15/11/2026 | Versão inicial. |

![NetTRAC Rastreadores](assets/logo.png)

# Pipeline de Notas Fiscais (NFS-e) — NetTRAC

## O problema

A NetTRAC é especializada em rastreadores veiculares de médio e grande porte. Como qualquer contribuinte no Portal Nacional da NFS-e (nfse.gov.br), a empresa esbarra numa limitação do próprio portal: não existe relatório consolidado nem exportação em lote das notas emitidas. Cada nota só dá pra consultar uma por uma, o que torna inviável qualquer análise de faturamento por cliente, por período ou por tipo de serviço direto pelo site.

Tive acesso autorizado às notas fiscais da empresa e parti daí pra construir uma solução.

## A solução

O projeto prioriza os XMLs das notas por serem documentos estruturados, mas também suporta os DANFSe em PDF. O parser de PDF extrai os mesmos campos do XML e converte ambos para o mesmo modelo de dados. Isso permite trabalhar com notas quando só o PDF está disponível. Os dados são então organizados em duas tabelas num banco Postgres (Supabase): uma de clientes (`tomadores`) e uma de notas (`notas`), relacionadas entre si. Isso resolve o problema de origem: dá pra consultar faturamento por cliente, sazonalidade, ISS apurado, tudo isso sem depender do portal.

```
Portal nfse.gov.br  →  XML/PDF  →  parser Python  →  Postgres (Supabase)  →  Power BI / análise
```

Um detalhe de modelagem que importou: a chave de deduplicação é a `chave_acesso` da nota (identificador único nacional), não o número dela. Isso torna a importação idempotente — rodar o mesmo XML duas vezes nunca duplica registro — o que é essencial num pipeline que vai ser alimentado aos poucos, nota por nota, ao longo do tempo.

## Dois jeitos de alimentar o pipeline

O projeto evoluiu em duas etapas. A primeira versão (`scripts/importar_notas.py`) lê XMLs baixados manualmente do portal — simples, funciona sem certificado digital, mas depende de alguém lembrar de baixar as notas.

A segunda versão (`scripts/sincronizar_api.py`) elimina essa dependência: busca as notas direto na API de Distribuição do ADN (Ambiente de Dados Nacional), autenticando via mTLS com o certificado digital e-CNPJ da empresa. O cursor de sincronização (NSU) fica salvo no próprio banco, então cada execução processa só o que é novo — dá pra rodar num agendador e esquecer que existe.

Os dois fluxos compartilham o mesmo parser (`scripts/parser_nfse.py`), garantindo que o dado final é idêntico não importa por qual caminho ele entrou.

Um ponto de honestidade técnica: os nomes exatos dos campos no JSON de resposta da API foram inferidos a partir da documentação pública do governo, não confirmados ao vivo (o Swagger interativo bloqueia acesso automatizado de ferramentas). O script de sincronização foi construído já prevendo isso — se algum nome de campo não bater, ele avisa claramente e mostra o JSON recebido, em vez de falhar silenciosamente.

## Stack

- Python (`lxml` pra parsing do XML, `PyMuPDF` pra extração dos PDFs, `requests-pkcs12` pra autenticação mTLS com certificado, `watchdog` pra monitoramento de pasta em tempo real)
- PostgreSQL via Supabase
- `python-dotenv` pra gerenciar credenciais

## Três jeitos de alimentar o pipeline

O projeto evoluiu em três etapas.

**Fluxo manual batch** (`scripts/importar_notas.py`): lê todos os XMLs e PDFs presentes nas pastas de uma vez. Simples, funciona sem nada extra, mas depende de alguém rodar o script.

**Fluxo automático via watcher** (`scripts/watcher.py`): monitora as pastas `pdfs/` e `xmls/` em tempo real. Basta salvar o arquivo — o resto acontece sozinho em menos de 2 segundos. Inicia automaticamente com o Windows após rodar `instalar_servico.bat` uma vez. É o fluxo recomendado para uso no dia a dia.

**Fluxo via API** (`scripts/sincronizar_api.py`): busca as notas direto na API de Distribuição do ADN (Ambiente de Dados Nacional), autenticando via mTLS com o certificado digital e-CNPJ da empresa. O cursor de sincronização (NSU) fica salvo no próprio banco, então cada execução processa só o que é novo.

Os três fluxos compartilham o mesmo parser (`scripts/parser_nfse.py`), garantindo que o dado final é idêntico não importa por qual caminho ele entrou.

## Estrutura do repositório

```
notas-fiscais-etl/
├── assets/
│   └── logo.png                       # logo da NetTRAC
├── scripts/
│   ├── parser_nfse.py                 # parser do XML
│   ├── parser_nfse_pdf.py             # parser do DANFSe em PDF
│   ├── watcher.py                     # monitora pdfs/ e xmls/ em tempo real
│   ├── processar_arquivo.py           # processa um único arquivo (usado pelo watcher)
│   ├── importar_notas.py              # fluxo batch manual: lê XMLs e PDFs de uma vez
│   └── sincronizar_api.py             # fluxo automático: busca via API + certificado
├── sql/
│   ├── schema.sql                     # criação das tabelas no banco
│   └── queries.sql                    # consultas de análise prontas pra rodar no Supabase
├── xmls/                              # XMLs baixados (não versionado)
│   ├── processados/                   # XMLs processados com sucesso
│   └── erros/                         # XMLs que falharam no processamento
├── pdfs/                              # DANFSe em PDF (não versionado)
│   ├── processados/                   # PDFs processados com sucesso
│   └── erros/                         # PDFs que falharam no processamento
├── logs/
│   └── watcher.log                    # histórico completo de processamentos
├── docs/
│   └── exemplo-nota-anonimizada.xml   # estrutura do XML, com dados fictícios
├── instalar_servico.bat               # instalador: roda uma vez, configura tudo
├── iniciar_watcher.bat                # inicia o watcher manualmente
├── requirements.txt
├── .env.example
└── .gitignore
```

## Queries SQL disponíveis

O arquivo `sql/queries.sql` contém 8 consultas prontas pra rodar no SQL Editor do Supabase:

| # | Query | O que mostra |
|---|---|---|
| 1 | Faturamento mensal | Receita total por mês |
| 2 | Faturamento anual | Receita total por ano |
| 3 | Ranking de clientes | Clientes que mais geraram receita |
| 4 | Clientes por mês | Série histórica por cliente |
| 5 | Por categoria de serviço | GPS/Antena, Sensor, Instalação etc. com % do total |
| 6 | ISS apurado por mês | Estimativa de ISS a recolher (alíquota 5%) |
| 7 | Notas pendentes | Notas ainda não pagas, com dias em aberto |
| 8 | Painel resumo | Totais gerais: notas, clientes, faturamento, a receber |

## Sobre os dados

Esse repositório não contém nenhuma nota fiscal real da NetTRAC. A pasta `xmls/`, `pdfs/` e o CSV gerado pelo script estão no `.gitignore` porque contêm CNPJ, nome de cliente e valores reais da empresa. O arquivo em `docs/exemplo-nota-anonimizada.xml` documenta a estrutura do XML com dados fictícios. Como é dado de empresa e não projeto pessoal, o acesso e a permissão pra usar essas informações, inclusive pra fins de portfólio, já estavam alinhados antes de qualquer coisa ir pro repositório.

## Próximos passos

Conectar o banco a um dashboard (Power BI ou Metabase) pra visualizar faturamento por cliente e sazonalidade é a evolução natural — as queries em `sql/queries.sql` já estão prontas pra isso. Validar o fluxo automático via API contra o ambiente de produção restrito, confirmando os nomes de campo reais, é o próximo passo técnico imediato.

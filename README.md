# Prática 1 — Extração de Dados dos Artigos do STIL 2019

Este projeto extrai informações estruturadas de artigos em PDF do STIL 2019/ASSIN 2 para formar um corpus em JSON.

Nesta etapa, o projeto realiza:

- leitura automática dos PDFs;
- extração de título, autoria, afiliações, ORCIDs, palavras-chave, resumo e referências;
- separação entre corpo do artigo e referências;
- remoção de autoria e afiliações do texto que será processado;
- geração de um corpus JSON.

> O processamento linguístico — tokenização, POS tagging, lematização, estatísticas e nuvem de palavras — ainda será implementado nas próximas etapas.

## Estrutura do projeto

```text
.
├── source/                         # Coloque aqui os PDFs dos artigos
├── src/
│   └── extract_stil.py             # Script principal de extração
├── config/
│   └── metadata_stil2019.json      # Metadados gerados automaticamente
└── output/
    └── corpus_stil2019.json        # Corpus JSON final da etapa atual
```

## Pré-requisito

O projeto utiliza Python e a biblioteca `pdfplumber`.

```bash
pip install pdfplumber
```

## Como executar

1. Adicione os PDFs dos artigos na pasta `source/`.

2. Na raiz do projeto, execute:

```bash
python src/extract_stil.py
```

Não é necessário informar nomes de arquivos, caminhos, metadata ou nome de saída.

## O que acontece na execução

O script identifica todos os arquivos PDF presentes em `source/` e:

1. Gera ou atualiza `config/metadata_stil2019.json`.
2. Extrai o conteúdo dos artigos.
3. Separa as referências do conteúdo principal.
4. Gera `output/corpus_stil2019.json`.

## Metadados

O arquivo `config/metadata_stil2019.json` é criado automaticamente a partir da primeira página de cada artigo.

Ele inclui, quando disponível:

- título;
- URL oficial do artigo;
- idioma;
- chave de armazenamento;
- autores;
- afiliações;
- ORCIDs;
- data de publicação;
- palavras-chave.

Como alguns PDFs usam fontes antigas ou codificações tipográficas particulares, recomenda-se revisar principalmente nomes próprios e afiliações após a geração automática.

Ao executar novamente o script, correções manuais já existentes no metadata são preservadas. Apenas PDFs novos recebem metadados automáticos.

Para recriar todos os metadados, ignorando revisões anteriores:

```bash
python src/extract_stil.py --regenerar-metadata
```

## Estrutura do corpus gerado

Cada artigo é salvo como um objeto JSON semelhante ao seguinte:

```json
{
  "titulo": "Título do artigo",
  "informacoes_url": "https://...",
  "idioma": "Inglês",
  "storage_key": "files/artigo.pdf",
  "autores": [],
  "data_publicacao": "26/03/2020",
  "resumo": "Resumo extraído do artigo.",
  "keywords": [],
  "referencias": [],
  "artigo_completo": "Texto do artigo sem autoria e referências.",
  "artigo_tokenizado": [],
  "pos_tagger": [],
  "lema": []
}
```

Os campos `artigo_tokenizado`, `pos_tagger` e `lema` permanecem vazios nesta versão. Eles serão preenchidos na etapa de processamento linguístico.

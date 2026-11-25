# Contexto para o Claude Code — Prospecção MEI

PWA estática (sem build, sem backend) para um agente de crédito encontrar MEIs ativos de uma cidade e registrar os contatos. Mesmo estilo do app "Cobrança do dia".

## Partes
- `preparar_dados.py` — Python 3.9+, **só biblioteca padrão**. Lê os .zip dos Dados Abertos de CNPJ da Receita (CSV `;`, latin-1, entre aspas) e gera `app/dados/`.
  - Passo 1: `Estabelecimentos*.zip` → filtra `uf` (col 19) nos estados pedidos e `situacao_cadastral` (col 5) = `02`.
  - Passo 2: `Simples.zip` → mantém quem tem `opcao_mei` (col 4) = `S` e sem `data_exclusao_mei` (col 6).
  - Passo 3: `Empresas*.zip` → razão social, limpando CNPJ do início e CPF do fim (`limpar_razao`).
  - Saída por cidade: `app/dados/<UF>/<codigo_municipio_receita>.json` com `campos` + `linhas` (arrays). O código de município é o da tabela da Receita, **não** o do IBGE.
- `app/index.html` — app inteiro (HTML + CSS + JS inline, sem framework).
  - Dados da cidade: `fetch('dados/...')`, com cópia no IndexedDB (`prospeccao-mei` / `cidades`) para funcionar sem internet.
  - Contatos: `localStorage['pm:contatos']` = `{ cnpj14: { s: ''|'contatado'|'interessado'|'naoquer', n: nota, h: [[timestamp, texto]] } }`.
  - Outras chaves: `pm:filtros`, `pm:cidade`, `pm:recentes`, `pm:msg`, `pm:indice`, `pm:cnaes`.
  - Layout: até 1023 px é o celular (lista → detalhe); a partir de 1024 px é o PC (filtros na lateral, tabela e detalhe lado a lado).
  - Tipo de negócio: calculado pelo CNAE em `tipoDoCnae()`.
- `app/sw.js` — cache do app. **Toda alteração no app precisa aumentar `CACHE`.**

## Regras
- Contatos e anotações **nunca** saem do aparelho. Não adicione backend, analytics nem chamadas de rede com esses dados.
- Não faça commit de `receita/` (os .zip da Receita). O `.gitignore` já cobre isso.
- O design aprovado está no canvas "Prospecção MEI — Design". Siga as cores e os componentes dele:
  - verde-petróleo `#0F766E` como cor principal;
  - verde `#15803D` só para o WhatsApp;
  - fontes Inter e Space Grotesk;
  - toques com pelo menos 44 px.

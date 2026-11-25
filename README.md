# Prospecção MEI

App para encontrar **MEIs ativos** de uma cidade e oferecer crédito a eles. Funciona no celular e no PC, e pode ser instalado como app.

Os dados vêm dos **Dados Abertos de CNPJ da Receita Federal**, que são públicos e atualizados todo mês.

## Como funciona

```
Receita Federal (arquivos .zip, ~7 GB)
        │   python preparar_dados.py --uf MA
        ▼
app/dados/indice.json        ← lista de cidades de cada estado
app/dados/cnaes.json         ← nomes das atividades
app/dados/MA/<codigo>.json   ← MEIs ativos de cada cidade
        │   publicar a pasta app/ (Netlify ou GitHub Pages)
        ▼
App no celular e no PC → você escolhe o estado e a cidade dentro do app
```

O script roda no seu PC porque a base da Receita é grande. O app só baixa o arquivo da cidade escolhida.

## 1. Preparar os dados (uma vez por mês)

Você precisa do **Python 3.9 ou mais novo** (em python.org) e de uns **10 GB livres** no disco.

Dentro desta pasta, rode:

```bash
python preparar_dados.py --uf MA
```

- Para mais estados, use `--uf MA PI`. A cidade você escolhe depois, no próprio app, entre todas as cidades desses estados.
- O script baixa os arquivos do mês mais recente para a pasta `receita/`. Na primeira vez demora, porque é bastante coisa. Se você rodar de novo, ele não baixa de novo o que já está completo.
- Se o download automático falhar (a Receita às vezes muda o endereço), baixe os arquivos à mão em
  https://arquivos.receitafederal.gov.br/index.php/s/YggdBLfdninEJX9 (pasta do mês mais recente), que são `Estabelecimentos0-9.zip`, `Empresas0-9.zip`, `Simples.zip`, `Municipios.zip` e `Cnaes.zip`. Coloque tudo em `receita/` e rode:
  ```bash
  python preparar_dados.py --uf MA --sem-baixar --mes 2026-11
  ```

Ao terminar, a pasta `app/dados/` está pronta. Os dados de demonstração que vêm no projeto são apagados.

**O que o script filtra:** só entra a empresa que está **ativa** na Receita, é **optante pelo MEI** hoje e fica nos estados escolhidos. Ele também tira da razão social os números do CNPJ e do CPF que a Receita coloca no nome do MEI.

## 2. Publicar o app

O app precisa de um endereço https para ser instalado.

**Netlify Drop (mais rápido):** acesse https://app.netlify.com/drop e arraste a pasta **`app`**. Quando os dados do mês seguinte chegarem, arraste a pasta de novo no mesmo site (em Deploys).

**GitHub Pages:** envie a pasta `app/` para um repositório e ative Settings → Pages.

Depois:
- **No celular:** abra o link no Chrome e toque em ⋮ → **Instalar app**.
- **No PC:** abra o link no Chrome ou no Edge e clique no ícone de instalar, na barra de endereço.

> Quem tiver o link consegue abrir os arquivos de `app/dados/`. São dados que a Receita já publica, mas não divulgue o link à toa.

## 3. Usar no dia a dia

1. **Escolha o estado e a cidade.** As últimas cidades usadas ficam salvas para trocar rápido.
2. **Lista:** tem as abas **Novos, Contatados, Interessados, Não quer e Todos**. Por padrão aparecem os mais antigos primeiro, porque empresas com mais tempo costumam ser clientes mais seguros.
3. **Filtros:** tempo de empresa (+6 meses, +1 ano, +3 anos), tipo de negócio, bairro, só com telefone e ordem da lista.
4. **WhatsApp e Ligar:** quando você toca, a empresa passa sozinha para **Contatado** e o contato fica registrado no histórico. O WhatsApp só aparece quando o número é de celular.
5. **Detalhe da empresa:** tem a situação do contato, anotações rápidas como "Não atendeu" e "Voltar depois", os dados da Receita e o botão de mapa.
6. ⚙ **Configurações:**
   - **Mensagem do WhatsApp**, que você pode editar. Aceita `{nome}`, `{empresa}` e `{cidade}`.
   - **Exportar/Importar contatos**, para passar suas marcações do celular para o PC e vice-versa.
   - **Atualizar dados da cidade.**

Seus contatos e anotações ficam **só no aparelho**. Nada vai para servidor.

## Limitações

- **Telefones desatualizados:** muitos MEIs nunca atualizam o número no cadastro.
- **Sincronização:** celular e PC não sincronizam sozinhos. Use Exportar/Importar.
- **Endereço:** o bairro vem como o MEI cadastrou, então pode ter grafias diferentes para o mesmo bairro.
- **LGPD:** confirme com o banco se essa forma de abordagem é aprovada, e respeite quem pedir para não ser contatado (marque como "Não quer").

## Arquivos

| Arquivo | O que é |
|---|---|
| `preparar_dados.py` | Baixa a base da Receita e gera `app/dados/`. Só usa a biblioteca padrão do Python. |
| `app/index.html` | O app inteiro: tela, estilo e lógica. |
| `app/sw.js` | Faz o app funcionar sem internet. **Ao alterar o app, aumente `CACHE`.** |
| `app/manifest.webmanifest`, `app/icon-*.png` | Arquivos para instalar como app. |
| `app/dados/` | Dados gerados pelo script. Vêm com uma **demonstração fictícia** que é substituída na primeira execução. |

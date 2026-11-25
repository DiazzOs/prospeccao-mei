#!/usr/bin/env python3
"""
Prepara os dados do app Prospecção MEI a partir dos Dados Abertos de CNPJ da Receita Federal.

O que ele faz:
  1. Baixa os arquivos da Receita do mês mais recente (ou usa os que já estão na pasta).
  2. Separa só os MEIs ATIVOS dos estados escolhidos.
  3. Gera um arquivo por cidade em app/dados/<UF>/<codigo>.json e a lista de cidades em app/dados/indice.json.

Uso (no terminal, dentro da pasta do projeto):
  python preparar_dados.py --uf MA
  python preparar_dados.py --uf MA PI          # vários estados
  python preparar_dados.py --uf MA --sem-baixar  # usa os .zip que já estão em ./receita

Só usa a biblioteca padrão do Python 3.9+. Não precisa instalar nada.
"""
import argparse
import base64
import csv
import io
import json
import os
import re
import sys
import time
import urllib.request
import zipfile
from datetime import datetime

SITE = "https://arquivos.receitafederal.gov.br"
TOKEN_PADRAO = "YggdBLfdninEJX9"  # compartilhamento público (Nextcloud) dos dados abertos de CNPJ
UA = {"User-Agent": "Mozilla/5.0 (prospeccao-mei)"}
ARQUIVOS = (
    [f"Estabelecimentos{i}.zip" for i in range(10)]
    + [f"Empresas{i}.zip" for i in range(10)]
    + ["Simples.zip", "Municipios.zip", "Cnaes.zip"]
)
UFS_VALIDAS = set("AC AL AM AP BA CE DF ES GO MA MG MS MT PA PB PE PI PR RJ RN RO RR RS SC SE SP TO".split())


def log(msg):
    print(time.strftime("%H:%M:%S"), msg, flush=True)


# ---------------------------------------------------------------- download

def descobrir_token():
    """A Receita publica os dados num compartilhamento do Nextcloud; o código dele pode mudar."""
    try:
        html = urllib.request.urlopen(urllib.request.Request(SITE + "/", headers=UA), timeout=30).read().decode("utf-8", "replace")
        m = re.search(r"/index\.php/s/([A-Za-z0-9]{8,})", html)
        if m:
            return m.group(1)
    except Exception:  # noqa: BLE001
        pass
    return TOKEN_PADRAO


def _req(caminho, token, metodo="GET", timeout=120, headers=None):
    auth = base64.b64encode(f"{token}:".encode()).decode()
    h = {**UA, "Authorization": "Basic " + auth, **(headers or {})}
    url = f"{SITE}/public.php/webdav/{caminho}"
    return urllib.request.urlopen(urllib.request.Request(url, headers=h, method=metodo), timeout=timeout)


def mes_mais_recente(token):
    corpo = ""
    try:
        resp = _req("", token, "PROPFIND", 60, {"Depth": "1"})
        corpo = resp.read().decode("utf-8", "replace")
        meses = sorted(set(re.findall(r"(\d{4}-\d{2})/?</d:href>", corpo)))
        if meses:
            return meses[-1]
    except Exception as e:  # noqa: BLE001
        corpo = f"{type(e).__name__}: {e}"
    log(f"listagem não funcionou ({corpo[:200]!r}); procurando o mês direto...")
    # plano B: testa o mês atual e os anteriores
    hoje = datetime.now()
    a, m = hoje.year, hoje.month
    for _ in range(4):
        mes = f"{a}-{m:02d}"
        try:
            r = _req(f"{mes}/Cnaes.zip", token, "HEAD", 60)
            r.close()
            return mes
        except Exception:  # noqa: BLE001
            pass
        a, m = (a - 1, 12) if m == 1 else (a, m - 1)
    raise RuntimeError("não encontrei pastas de mês no compartilhamento da Receita")


def baixar(pasta, mes, token):
    os.makedirs(pasta, exist_ok=True)
    for nome in ARQUIVOS:
        destino = os.path.join(pasta, nome)
        for tentativa in range(1, 4):
            try:
                resp = _req(f"{mes}/{nome}", token, timeout=180)
                total = int(resp.headers.get("Content-Length") or 0)
                if os.path.exists(destino) and total and os.path.getsize(destino) == total:
                    log(f"{nome}: já baixado")
                    resp.close()
                    break
                log(f"baixando {nome} ({total / 1e6:.0f} MB)...")
                parcial = destino + ".parcial"
                feito, ultimo = 0, time.time()
                with open(parcial, "wb") as f:
                    while True:
                        bloco = resp.read(1 << 20)
                        if not bloco:
                            break
                        f.write(bloco)
                        feito += len(bloco)
                        if time.time() - ultimo > 15 and total:
                            log(f"  {nome}: {100 * feito / total:.0f}%")
                            ultimo = time.time()
                resp.close()
                if total and feito != total:
                    raise IOError(f"veio {feito} de {total} bytes")
                os.replace(parcial, destino)
                break
            except Exception as e:  # noqa: BLE001
                if tentativa == 3:
                    raise RuntimeError(f"falha ao baixar {nome}: {e}")
                log(f"  erro em {nome} ({e}); tentando de novo...")
                time.sleep(10 * tentativa)
    with open(os.path.join(pasta, "MES.txt"), "w") as f:
        f.write(mes)


# ---------------------------------------------------------------- leitura

def linhas_zip(caminho):
    """Lê todas as linhas (texto latin-1) de todos os arquivos dentro de um .zip."""
    with zipfile.ZipFile(caminho) as z:
        for membro in z.infolist():
            if membro.is_dir():
                continue
            with z.open(membro) as bruto:
                for linha in io.TextIOWrapper(bruto, encoding="latin-1", newline=""):
                    yield linha


def campos(linha):
    return next(csv.reader([linha], delimiter=";", quotechar='"'))


def tabela_codigos(caminho):
    t = {}
    for linha in linhas_zip(caminho):
        r = campos(linha)
        if len(r) >= 2:
            t[r[0].strip()] = r[1].strip()
    return t


def arquivos(pasta, prefixo):
    lista = sorted(f for f in os.listdir(pasta) if f.startswith(prefixo) and f.lower().endswith(".zip"))
    if not lista:
        raise RuntimeError(f"nenhum arquivo {prefixo}*.zip em {pasta}")
    return [os.path.join(pasta, f) for f in lista]


# ---------------------------------------------------------------- limpeza

RE_INICIO = re.compile(r"^\s*\d{2}\.?\d{3}\.?\d{3}\s+")
RE_FIM = re.compile(r"\s*\d{8,}\s*$")


def limpar_razao(razao):
    """Tira o CNPJ do início e o CPF do fim da razão social do MEI (proteção de dados)."""
    return RE_FIM.sub("", RE_INICIO.sub("", razao or "")).strip()


def telefone(ddd, num):
    d = re.sub(r"\D", "", ddd or "")
    n = re.sub(r"\D", "", num or "")
    if not n or set(n) == {"0"}:
        return ""
    return (d[-2:] if len(d) >= 2 else d) + n


def data_ok(d):
    d = (d or "").strip()
    return d if re.fullmatch(r"\d{8}", d) and d != "00000000" else ""


# ---------------------------------------------------------------- principal

def main():
    ap = argparse.ArgumentParser(description="Prepara os dados de MEIs para o app Prospecção MEI.")
    ap.add_argument("--uf", nargs="+", default=["MA"], help="estados (ex.: MA PI)")
    ap.add_argument("--pasta", default="receita", help="pasta dos .zip da Receita (padrão: ./receita)")
    ap.add_argument("--saida", default=os.path.join("app", "dados"), help="pasta de saída (padrão: ./app/dados)")
    ap.add_argument("--mes", help="mês da base, ex.: 2026-11 (padrão: o mais recente)")
    ap.add_argument("--sem-baixar", action="store_true", help="não baixa nada, usa os .zip da pasta")
    a = ap.parse_args()

    ufs = {u.upper() for u in a.uf}
    erradas = ufs - UFS_VALIDAS
    if erradas:
        sys.exit(f"UF inválida: {', '.join(sorted(erradas))}")

    mes = a.mes
    if not a.sem_baixar:
        try:
            token = TOKEN_PADRAO
            try:
                ultimo = mes_mais_recente(token)
            except Exception:  # noqa: BLE001  (o código do compartilhamento pode ter mudado)
                token = descobrir_token()
                ultimo = mes_mais_recente(token)
            mes = mes or ultimo
            log(f"base da Receita: {mes}")
            baixar(a.pasta, mes, token)
        except Exception as e:  # noqa: BLE001
            sys.exit(
                f"\nNão consegui baixar automaticamente: {e}\n"
                f"Baixe manualmente em {SITE}/index.php/s/{TOKEN_PADRAO} (pasta do mês mais recente) os arquivos:\n  "
                + ", ".join(ARQUIVOS)
                + f"\ncoloque-os em ./{a.pasta}/ e rode de novo com --sem-baixar --mes AAAA-MM"
            )
    if not mes:
        arq_mes = os.path.join(a.pasta, "MES.txt")
        mes = open(arq_mes).read().strip() if os.path.exists(arq_mes) else datetime.now().strftime("%Y-%m")

    inicio = time.time()
    log("lendo tabelas de municípios e atividades...")
    municipios = tabela_codigos(os.path.join(a.pasta, "Municipios.zip"))
    cnaes = tabela_codigos(os.path.join(a.pasta, "Cnaes.zip"))

    # 1) estabelecimentos ativos dos estados escolhidos
    marcas = [f'"{u}";"' for u in ufs]
    ativos = {}  # cnpj_basico -> lista de registros
    for caminho in arquivos(a.pasta, "Estabelecimentos"):
        log(f"lendo {os.path.basename(caminho)}...")
        for linha in linhas_zip(caminho):
            if not any(m in linha for m in marcas):
                continue
            r = campos(linha)
            if len(r) < 28 or r[19] not in ufs or r[5].strip() not in ("02", "2"):
                continue
            ativos.setdefault(r[0], []).append((
                r[0] + r[1] + r[2],                       # cnpj
                r[4].strip(),                             # nome fantasia
                r[11].strip(),                            # cnae principal
                data_ok(r[10]),                           # início atividade
                f"{r[13].strip()} {r[14].strip()}".strip(),  # logradouro
                r[15].strip(), r[16].strip(), r[17].strip(),  # número, complemento, bairro
                r[18].strip(), r[19], r[20].strip(),       # cep, uf, município
                telefone(r[21], r[22]), telefone(r[23], r[24]),
                r[27].strip().lower(),                    # e-mail
            ))
    log(f"{len(ativos)} empresas ativas em {', '.join(sorted(ufs))}")

    # 2) quem é MEI hoje
    mei = {}
    for linha in linhas_zip(os.path.join(a.pasta, "Simples.zip")):
        if linha[1:9] not in ativos:
            continue
        r = campos(linha)
        if len(r) >= 7 and r[4].strip().upper() == "S" and not data_ok(r[6]):
            mei[r[0]] = data_ok(r[5])
    log(f"{len(mei)} são MEI")

    # 3) razão social
    razao = {}
    for caminho in arquivos(a.pasta, "Empresas"):
        log(f"lendo {os.path.basename(caminho)}...")
        for linha in linhas_zip(caminho):
            if linha[1:9] not in mei:
                continue
            r = campos(linha)
            if len(r) >= 2:
                razao[r[0]] = limpar_razao(r[1])

    # 4) arquivos por cidade
    cidades = {}
    usados = set()
    for basico, desde in mei.items():
        for e in ativos[basico]:
            cnpj, fant, cnae, ini, lograd, num, compl, bairro, cep, uf, mun, t1, t2, email = e
            usados.add(cnae)
            cidades.setdefault((uf, mun), []).append(
                [cnpj, fant, razao.get(basico, ""), cnae, ini, lograd, num, compl, bairro, cep, t1, t2, email, desde]
            )

    os.makedirs(a.saida, exist_ok=True)
    # apaga os arquivos antigos (inclusive os de demonstração) antes de gravar os novos
    for nome in os.listdir(a.saida):
        sub = os.path.join(a.saida, nome)
        if os.path.isdir(sub) and re.fullmatch(r"[A-Z]{2}", nome):
            for f in os.listdir(sub):
                if f.endswith(".json"):
                    os.remove(os.path.join(sub, f))
    gerado = datetime.now().strftime("%Y-%m-%d %H:%M")
    indice = {"base": mes, "gerado": gerado, "ufs": {}}
    for (uf, mun), linhas in sorted(cidades.items()):
        linhas.sort(key=lambda l: (l[4] or "99999999"))
        pasta_uf = os.path.join(a.saida, uf)
        os.makedirs(pasta_uf, exist_ok=True)
        nome = municipios.get(mun, mun)
        with open(os.path.join(pasta_uf, f"{mun}.json"), "w", encoding="utf-8") as f:
            json.dump({
                "uf": uf, "codigo": mun, "cidade": nome, "base": mes,
                "campos": ["cnpj", "fantasia", "razao", "cnae", "abertura", "logradouro", "numero",
                           "complemento", "bairro", "cep", "tel1", "tel2", "email", "mei_desde"],
                "linhas": linhas,
            }, f, ensure_ascii=False, separators=(",", ":"))
        indice["ufs"].setdefault(uf, []).append({"c": mun, "n": nome, "q": len(linhas)})
    for uf in indice["ufs"]:
        indice["ufs"][uf].sort(key=lambda c: c["n"])

    with open(os.path.join(a.saida, "cnaes.json"), "w", encoding="utf-8") as f:
        json.dump({c: cnaes.get(c, "") for c in sorted(usados)}, f, ensure_ascii=False, separators=(",", ":"))
    with open(os.path.join(a.saida, "indice.json"), "w", encoding="utf-8") as f:
        json.dump(indice, f, ensure_ascii=False, separators=(",", ":"))

    total = sum(len(v) for v in cidades.values())
    log(f"pronto: {total} MEIs em {len(cidades)} cidades → {a.saida}  ({time.time() - inicio:.0f}s)")
    log("agora publique a pasta app/ de novo (Netlify ou GitHub Pages) para o app pegar os dados novos.")


if __name__ == "__main__":
    main()

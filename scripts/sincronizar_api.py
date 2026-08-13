"""
Busca notas novas direto da API de Distribuicao do ADN (Ambiente de Dados
Nacional), autenticando com o certificado digital e-CNPJ da empresa via mTLS.

O cursor (ultimo NSU processado) fica salvo na tabela sync_estado do
Supabase, entao cada execucao so processa o que e novo.

ATENCAO - antes de usar em producao:
Os nomes exatos das chaves no JSON de resposta (marcados com TODO abaixo)
foram inferidos a partir da documentacao publica do governo, mas o Swagger
interativo (https://adn.producaorestrita.nfse.gov.br/contribuintes/docs/
index.html) bloqueia acesso automatizado, entao nao consegui confirmar ao
vivo. Rode primeiro contra o ambiente de PRODUCAO RESTRITA (sandbox oficial
pra teste de contribuinte), veja o JSON impresso na tela, e ajuste as
constantes CHAVES_LISTA_DOCUMENTOS e CHAVES_CONTEUDO_XML se necessario.

Seguranca:
- O arquivo .pfx do certificado NUNCA deve ser commitado nem colado em chat
  nenhum. Só fica no seu computador, referenciado pelo .env.
- Rode "python scripts/sincronizar_api.py" manualmente algumas vezes contra
  a producao restrita antes de apontar pra producao de verdade (AMBIENTE=
  producao no .env).

Uso:
    python scripts/sincronizar_api.py
"""

import os
import base64
import gzip
import json
import time

import requests_pkcs12
from dotenv import load_dotenv
from supabase import create_client

from parser_nfse import parse_nota_from_string

load_dotenv()

CERT_PATH = os.getenv("CERT_PATH")
CERT_PASSWORD = os.getenv("CERT_PASSWORD")
AMBIENTE = os.getenv("AMBIENTE", "restrita")  # "restrita" ou "producao"

BASE_URLS = {
    "restrita": "https://adn.producaorestrita.nfse.gov.br/contribuintes",
    "producao": "https://adn.nfse.gov.br/contribuintes",
}

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")

# TODO: confirmar contra o JSON real (ver aviso no topo do arquivo)
CHAVES_LISTA_DOCUMENTOS = ["LoteDFe", "loteDFe", "documentos", "DFe", "dfe"]
CHAVES_CONTEUDO_XML = ["ArquivoXml", "arquivo", "documento", "conteudo", "docZip"]
CHAVES_NSU = ["NSU", "nsu"]


def get_supabase():
    if not SUPABASE_URL or not SUPABASE_KEY:
        raise RuntimeError("Configure SUPABASE_URL e SUPABASE_KEY no .env")
    return create_client(SUPABASE_URL, SUPABASE_KEY)


def obter_ultimo_nsu(supabase):
    resp = (
        supabase.table("sync_estado")
        .select("valor")
        .eq("chave", "ultimo_nsu")
        .execute()
    )
    if resp.data:
        return int(resp.data[0]["valor"])
    return 0


def salvar_ultimo_nsu(supabase, nsu):
    supabase.table("sync_estado").upsert({"chave": "ultimo_nsu", "valor": str(nsu)}).execute()


def buscar_lote(nsu):
    if not CERT_PATH or not CERT_PASSWORD:
        raise RuntimeError("Configure CERT_PATH e CERT_PASSWORD no .env")

    url = f"{BASE_URLS[AMBIENTE]}/DFe/{nsu}"
    resposta = requests_pkcs12.get(
        url,
        pkcs12_filename=CERT_PATH,
        pkcs12_password=CERT_PASSWORD,
        headers={"Accept": "application/json"},
        timeout=30,
    )

    if resposta.status_code == 403:
        raise RuntimeError(
            "403: geralmente é problema de mTLS. Confira se CERT_PATH "
            "aponta pro .pfx certo, a senha está correta, e se o CNPJ do "
            "certificado é o da NetTRAC."
        )
    if resposta.status_code == 429:
        print("429 (limite de requisições), aguardando 10s e tentando de novo...")
        time.sleep(10)
        return buscar_lote(nsu)

    resposta.raise_for_status()
    return resposta.json()


def descompactar_xml(base64_gzip):
    """Cada documento vem GZip + Base64, padrão da API NFSe Nacional."""
    bruto = base64.b64decode(base64_gzip)
    return gzip.decompress(bruto).decode("utf-8")


def extrair_documentos(lote_json):
    for chave in CHAVES_LISTA_DOCUMENTOS:
        if chave in lote_json:
            return lote_json[chave]

    print("Não encontrei a lista de documentos nas chaves esperadas.")
    print("JSON recebido (primeiros 2000 caracteres):")
    print(json.dumps(lote_json, indent=2, ensure_ascii=False)[:2000])
    raise RuntimeError(
        "Ajuste CHAVES_LISTA_DOCUMENTOS no topo do arquivo com a chave certa."
    )


def extrair_campo(doc, candidatos):
    for chave in candidatos:
        if chave in doc and doc[chave]:
            return doc[chave]
    return None


def processar_lote(supabase, lote_json):
    documentos = extrair_documentos(lote_json)
    maior_nsu = None

    for doc in documentos:
        nsu = extrair_campo(doc, CHAVES_NSU)
        conteudo_b64 = extrair_campo(doc, CHAVES_CONTEUDO_XML)

        if not conteudo_b64:
            print(f"NSU {nsu}: não achei o campo com o XML. Chaves disponíveis: {list(doc.keys())}")
            continue

        xml_str = descompactar_xml(conteudo_b64)
        nota = parse_nota_from_string(xml_str)

        supabase.table("tomadores").upsert(
            {"cpf_cnpj": nota["cnpj_tomador"], "razao_social": nota["nome_tomador"]},
            on_conflict="cpf_cnpj",
        ).execute()

        tomador = (
            supabase.table("tomadores")
            .select("id")
            .eq("cpf_cnpj", nota["cnpj_tomador"])
            .single()
            .execute()
        )

        supabase.table("notas").upsert(
            {
                "numero": nota["numero"],
                "chave_acesso": nota["chave_acesso"],
                "data_emissao": nota["data_emissao"],
                "competencia": nota["competencia"],
                "tomador_id": tomador.data["id"],
                "codigo_servico": nota["codigo_servico"],
                "descricao": nota["descricao"],
                "categoria_servico": nota["categoria_servico"],
                "valor_servico": nota["valor_servico"],
                "status": nota["status"],
            },
            on_conflict="chave_acesso",
        ).execute()

        print(f"  NSU {nsu}: nota #{nota['numero']} - {nota['nome_tomador']} - R$ {nota['valor_servico']}")

        if nsu is not None:
            maior_nsu = max(maior_nsu or 0, int(nsu))

    return maior_nsu, len(documentos)


def main():
    supabase = get_supabase()
    ultimo_nsu = obter_ultimo_nsu(supabase)
    print(f"Ambiente: {AMBIENTE}")
    print(f"Buscando a partir do NSU {ultimo_nsu}...")

    total_processado = 0
    while True:
        lote = buscar_lote(ultimo_nsu)
        maior_nsu, qtd = processar_lote(supabase, lote)
        total_processado += qtd

        # lote com menos de 50 documentos = chegamos no fim do disponível
        if maior_nsu is None or qtd < 50:
            if maior_nsu is not None:
                salvar_ultimo_nsu(supabase, maior_nsu)
            break

        ultimo_nsu = maior_nsu
        salvar_ultimo_nsu(supabase, ultimo_nsu)

    print(f"Concluído. {total_processado} documento(s) processado(s) nesta execução.")


if __name__ == "__main__":
    main()

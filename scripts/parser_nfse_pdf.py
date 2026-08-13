"""Parser de DANFSe (PDF) da NFS-e padrão nacional.

Suporta:
- DANFSe v1.0
- DANFSe v2.0

Produz o mesmo modelo de dados usado pelo parser XML.
"""

from datetime import datetime
from pathlib import Path
import re

import fitz  # PyMuPDF

try:
    from parser_nfse import categorizar_servico
except ImportError:
    from scripts.parser_nfse import categorizar_servico


CAMPOS = [
    "numero",
    "chave_acesso",
    "data_emissao",
    "competencia",
    "cnpj_tomador",
    "nome_tomador",
    "codigo_servico",
    "descricao",
    "categoria_servico",
    "valor_servico",
    "status",
]


def _texto_pdf(caminho_pdf):
    """Extrai o texto de todas as páginas do PDF."""
    with fitz.open(caminho_pdf) as doc:
        return "\n".join(page.get_text("text") for page in doc)


def _linhas(texto):
    return [linha.strip() for linha in texto.splitlines() if linha.strip()]


def _linha_depois(texto, rotulo):
    """Retorna a primeira linha não vazia depois de um rótulo exato."""
    linhas = _linhas(texto)

    for i, linha in enumerate(linhas):
        if linha == rotulo:
            if i + 1 < len(linhas):
                return linhas[i + 1]

    return None


def _linha_depois_prefixo(texto, prefixo):
    """Procura uma linha que começa com o prefixo e retorna a próxima linha."""
    linhas = _linhas(texto)

    for i, linha in enumerate(linhas):
        if linha.startswith(prefixo):
            if i + 1 < len(linhas):
                return linhas[i + 1]

    return None


def _bloco_entre(texto, inicio, fim):
    """Retorna o texto entre dois títulos."""
    padrao = rf"{re.escape(inicio)}\s*\n(?P<bloco>.*?)(?=\n{re.escape(fim)}(?:\s*\n|$))"

    match = re.search(
        padrao,
        texto,
        flags=re.S | re.I,
    )

    return match.group("bloco") if match else ""


def _cnpj(valor):
    if not valor:
        return None

    somente_digitos = re.sub(r"\D", "", valor)

    return somente_digitos or None


def _valor_brl(valor):
    if not valor:
        return None

    numero = valor.replace("R$", "").strip()
    numero = numero.replace(".", "").replace(",", ".")

    try:
        return float(numero)
    except ValueError:
        return None


def _data_iso(data_br):
    if not data_br:
        return None

    try:
        return datetime.strptime(data_br, "%d/%m/%Y").date().isoformat()
    except ValueError:
        return None


def _datetime_iso(data_br):
    if not data_br:
        return None

    try:
        return datetime.strptime(
            data_br,
            "%d/%m/%Y %H:%M:%S"
        ).isoformat()
    except ValueError:
        return None


def _detectar_versao(texto):
    """Identifica se o PDF é DANFSe v1.0 ou v2.0."""

    if "DANFSe v2.0" in texto:
        return "v2"

    if "DANFSe v1.0" in texto:
        return "v1"

    # Fallback caso a versão não apareça claramente.
    if "TOMADOR / ADQUIRENTE" in texto:
        return "v2"

    if "TOMADOR DO SERVIÇO" in texto:
        return "v1"

    return None


# ============================================================
# DANFSe v1.0
# ============================================================

def _parse_v1(texto):
    """Extrai campos do layout DANFSe v1.0."""

    chave = _linha_depois(texto, "Chave de Acesso da NFS-e")

    numero = _linha_depois(texto, "Número da NFS-e")

    competencia_br = _linha_depois(
        texto,
        "Competência da NFS-e"
    )

    emissao_br = _linha_depois(
        texto,
        "Data e Hora da emissão da NFS-e"
    )

    bloco_tomador = _bloco_entre(
        texto,
        "TOMADOR DO SERVIÇO",
        "INTERMEDIÁRIO DO SERVIÇO NÃO IDENTIFICADO NA NFS-e",
    )

    cnpj_tomador = _cnpj(
        _linha_depois(
            bloco_tomador,
            "CNPJ / CPF / NIF"
        )
    )

    nome_tomador = _linha_depois(
        bloco_tomador,
        "Nome / Nome Empresarial"
    )

    bloco_servico = _bloco_entre(
        texto,
        "SERVIÇO PRESTADO",
        "TRIBUTAÇÃO MUNICIPAL",
    )

    codigo = _linha_depois(
        bloco_servico,
        "Código de Tributação Nacional"
    )

    codigo_servico = None

    if codigo:
        match = re.search(
            r"\d{2}\.\d{2}\.\d{2}",
            codigo
        )

        if match:
            codigo_servico = match.group(0).replace(".", "")

    descricao = _linha_depois(
        bloco_servico,
        "Descrição do Serviço"
    )

    bloco_tributacao = _bloco_entre(
        texto,
        "TRIBUTAÇÃO MUNICIPAL",
        "TRIBUTAÇÃO FEDERAL",
    )

    valor_servico = _valor_brl(
        _linha_depois(
            bloco_tributacao,
            "Valor do Serviço"
        )
    )

    return {
        "numero": numero,
        "chave_acesso": chave,
        "data_emissao": _datetime_iso(emissao_br),
        "competencia": _data_iso(competencia_br),
        "cnpj_tomador": cnpj_tomador,
        "nome_tomador": nome_tomador,
        "codigo_servico": codigo_servico,
        "descricao": descricao,
        "categoria_servico": categorizar_servico(descricao),
        "valor_servico": valor_servico,
        "status": "ativa",
    }


# ============================================================
# DANFSe v2.0
# ============================================================

def _parse_v2(texto):
    """Extrai campos do layout DANFSe v2.0."""

    chave = _linha_depois(
        texto,
        "CHAVE DE ACESSO DA NFS-e"
    )

    numero = _linha_depois(
        texto,
        "NÚMERO DA NFS-e"
    )

    competencia_br = _linha_depois(
        texto,
        "COMPETÊNCIA DA NFS-e"
    )

    emissao_br = _linha_depois(
        texto,
        "DATA E HORA DA EMISSÃO DA NFS-e"
    )

    bloco_tomador = _bloco_entre(
        texto,
        "TOMADOR / ADQUIRENTE",
        "DESTINATÁRIO DA OPERAÇÃO NÃO IDENTIFICADO NA NFS-e",
    )

    cnpj_tomador = _cnpj(
        _linha_depois(
            bloco_tomador,
            "CNPJ / CPF / NIF"
        )
    )

    nome_tomador = _linha_depois(
        bloco_tomador,
        "Nome / Nome Empresarial"
    )

    bloco_servico = _bloco_entre(
        texto,
        "SERVIÇO PRESTADO",
        "TRIBUTAÇÃO MUNICIPAL (ISSQN)",
    )

    codigo = _linha_depois(
        bloco_servico,
        "Código de Tributação Nacional/Municipal"
    )

    codigo_servico = None

    if codigo:
        match = re.search(
            r"\d{2}\.\d{2}\.\d{2}",
            codigo
        )

        if match:
            codigo_servico = match.group(0).replace(".", "")

    descricao = _linha_depois(
        bloco_servico,
        "Descrição do Serviço"
    )

    # No v2.0 o valor principal fica na seção
    # VALOR TOTAL DA NFS-e.
    bloco_valor = _bloco_entre(
        texto,
        "VALOR TOTAL DA NFS-e",
        "INFORMAÇÕES COMPLEMENTARES",
    )

    valor_servico = _valor_brl(
        _linha_depois(
            bloco_valor,
            "VALOR DA OPERAÇÃO / SERVIÇO"
        )
    )

    # Fallback caso o texto do PDF use "Valor do Serviço".
    if valor_servico is None:
        valor_servico = _valor_brl(
            _linha_depois(
                bloco_valor,
                "Valor do Serviço"
            )
        )

    return {
        "numero": numero,
        "chave_acesso": chave,
        "data_emissao": _datetime_iso(emissao_br),
        "competencia": _data_iso(competencia_br),
        "cnpj_tomador": cnpj_tomador,
        "nome_tomador": nome_tomador,
        "codigo_servico": codigo_servico,
        "descricao": descricao,
        "categoria_servico": categorizar_servico(descricao),
        "valor_servico": valor_servico,
        "status": "ativa",
    }


# ============================================================
# PARSER PRINCIPAL
# ============================================================

def parse_nota_from_text(texto, nome_arquivo=None):
    """Detecta automaticamente v1.0/v2.0 e extrai a NFS-e."""

    versao = _detectar_versao(texto)

    if versao == "v1":
        nota = _parse_v1(texto)

    elif versao == "v2":
        nota = _parse_v2(texto)

    else:
        raise ValueError(
            "Não foi possível identificar o layout do DANFSe "
            "(v1.0 ou v2.0)."
        )

    # Se por algum motivo a chave não estiver no texto,
    # usa o nome do arquivo como fallback.
    if not nota.get("chave_acesso") and nome_arquivo:
        nota["chave_acesso"] = Path(nome_arquivo).stem

    return nota


def parse_nota_from_file(caminho_pdf):
    """Lê um PDF e retorna um registro compatível com o XML."""

    texto = _texto_pdf(caminho_pdf)

    return parse_nota_from_text(
        texto,
        caminho_pdf
    )


if __name__ == "__main__":
    import argparse
    import json

    parser = argparse.ArgumentParser(
        description="Extrai dados de um DANFSe PDF"
    )

    parser.add_argument(
        "pdf",
        help="Caminho do PDF"
    )

    args = parser.parse_args()

    resultado = parse_nota_from_file(args.pdf)

    print(
        json.dumps(
            resultado,
            ensure_ascii=False,
            indent=2
        )
    )
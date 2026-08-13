"""
Parser do XML de NFS-e (padrao nacional). Usado tanto pelo fluxo manual
(importar_notas.py, le arquivo do disco) quanto pelo automatico
(sincronizar_api.py, le XML que vem em string da API do ADN).
"""

from lxml import etree

NS = {"nfse": "http://www.sped.fazenda.gov.br/nfse"}

# Ordem importa: a primeira palavra-chave que bater na descricao decide a
# categoria. Substantivos especificos (o que foi mexido) vem antes de verbos
# genericos (instalação/reparo/manutenção), porque esses verbos aparecem
# espalhados em varios tipos de servico diferentes e nao diferenciam nada
# sozinhos. Ajuste essa lista conforme aparecerem novos tipos de servico.
REGRAS_CATEGORIA = [
    ("GPS / Antena", ["gps", "antena"]),
    ("Sensor", ["sensor"]),
    ("Tela", ["tela"]),
    ("Trava", ["trava", "destravamento", "desbloqueio"]),
    ("Teclado", ["teclado"]),
    ("Periférico", ["periféric", "perifric"]),
    ("Baú", ["baú", "bau "]),
    ("Instalação", ["instalaç"]),  # fallback: instalação de algo sem categoria propria (ex: "Tampa Chinelo")
    ("Manutenção", ["manutenç"]),
    ("Reparo", ["reparo"]),
]


def categorizar_servico(descricao):
    """
    Classifica a descricao livre da nota numa categoria padronizada,
    procurando palavras-chave (sem acento nem case sensitivity).
    Retorna "Outros" se nada bater.
    """
    if not descricao:
        return "Outros"

    texto_normalizado = descricao.lower()

    for categoria, palavras_chave in REGRAS_CATEGORIA:
        for palavra in palavras_chave:
            if palavra in texto_normalizado:
                return categoria

    return "Outros"


def texto(elem, caminho):
    """Pega o texto de uma tag, ou None se ela nao existir."""
    node = elem.find(caminho, NS)
    return node.text.strip() if node is not None and node.text else None


def parse_nota_from_tree(root):
    inf_nfse = root.find(".//nfse:infNFSe", NS)
    dps = root.find(".//nfse:DPS/nfse:infDPS", NS)

    chave_acesso = inf_nfse.get("Id", "").replace("NFS", "")
    descricao = texto(dps, "nfse:serv/nfse:cServ/nfse:xDescServ")

    return {
        "numero": texto(inf_nfse, "nfse:nNFSe"),
        "chave_acesso": chave_acesso,
        "data_emissao": texto(dps, "nfse:dhEmi"),
        "competencia": texto(dps, "nfse:dCompet"),
        "cnpj_tomador": texto(dps, "nfse:toma/nfse:CNPJ"),
        "nome_tomador": texto(dps, "nfse:toma/nfse:xNome"),
        "codigo_servico": texto(dps, "nfse:serv/nfse:cServ/nfse:cTribNac"),
        "descricao": descricao,
        "categoria_servico": categorizar_servico(descricao),
        "valor_servico": texto(dps, "nfse:valores/nfse:vServPrest/nfse:vServ"),
        "status": "ativa",  # cancelamento vem por evento separado, nao por este XML
    }


def parse_nota_from_file(caminho_xml):
    tree = etree.parse(caminho_xml)
    return parse_nota_from_tree(tree.getroot())


def parse_nota_from_string(xml_string):
    conteudo = xml_string.encode("utf-8") if isinstance(xml_string, str) else xml_string
    root = etree.fromstring(conteudo)
    return parse_nota_from_tree(root)


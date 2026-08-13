"""
Le notas fiscais de NFS-e salvas em xmls/ e/ou pdfs/, extrai os campos
relevantes e gera um CSV. Se SUPABASE_URL e SUPABASE_KEY estiverem
configuradas no .env, tambem envia os dados pro banco.

O parser de XML continua sendo usado para XMLs e o parser de PDF para DANFSe.
Ambos produzem exatamente o mesmo formato de registro.

Uso:
    python scripts/importar_notas.py
"""

import os
import glob
import csv

from dotenv import load_dotenv

from parser_nfse import parse_nota_from_file as parse_xml
from parser_nfse_pdf import parse_nota_from_file as parse_pdf


load_dotenv()


PASTA_XMLS = "xmls"
PASTA_PDFS = "pdfs"
ARQUIVO_SAIDA = "notas_extraidas.csv"


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


def ler_notas():
    """Lê todos os XMLs e PDFs disponíveis."""

    notas = []

    arquivos_xml = glob.glob(
        os.path.join(PASTA_XMLS, "*.xml")
    )

    arquivos_pdf = glob.glob(
        os.path.join(PASTA_PDFS, "*.pdf")
    )

    if not arquivos_xml and not arquivos_pdf:
        print(
            f"Nenhum XML encontrado em {PASTA_XMLS}/ "
            f"nem PDF em {PASTA_PDFS}/"
        )
        return []

    # XMLs
    for caminho in arquivos_xml:
        try:
            notas.append(parse_xml(caminho))
        except Exception as e:
            print(f"Erro lendo XML {caminho}: {e}")

    # PDFs
    for caminho in arquivos_pdf:
        try:
            notas.append(parse_pdf(caminho))
        except Exception as e:
            print(f"Erro lendo PDF {caminho}: {e}")

    # Evita duplicidade caso a mesma nota exista em XML e PDF.
    unicas = {}

    for nota in notas:
        chave = nota.get("chave_acesso")

        if chave:
            unicas[chave] = nota

    return list(unicas.values())


def salvar_csv(notas):
    with open(
        ARQUIVO_SAIDA,
        "w",
        newline="",
        encoding="utf-8"
    ) as f:

        writer = csv.DictWriter(
            f,
            fieldnames=CAMPOS
        )

        writer.writeheader()
        writer.writerows(notas)

    print(
        f"{len(notas)} nota(s) exportada(s) "
        f"para {ARQUIVO_SAIDA}"
    )


def enviar_supabase(notas):

    url = os.getenv("SUPABASE_URL")
    key = os.getenv("SUPABASE_KEY")

    if not url or not key:
        print(
            "SUPABASE_URL/SUPABASE_KEY nao configurados, "
            "pulando envio ao banco."
        )

        print(
            "(configure o .env se quiser subir direto pro Supabase)"
        )

        return

    from supabase import create_client

    supabase = create_client(url, key)

    enviadas = 0
    erros = 0

    for n in notas:

        try:

            # =====================================================
            # 1. CRIA / ATUALIZA O TOMADOR
            # =====================================================

            supabase.table("tomadores").upsert(
                {
                    "cpf_cnpj": n["cnpj_tomador"],
                    "razao_social": n["nome_tomador"],
                },
                on_conflict="cpf_cnpj",
            ).execute()


            # =====================================================
            # 2. BUSCA O ID DO TOMADOR
            # =====================================================

            resultado_tomador = (
                supabase
                .table("tomadores")
                .select("id")
                .eq(
                    "cpf_cnpj",
                    n["cnpj_tomador"]
                )
                .limit(1)
                .execute()
            )

            if not resultado_tomador.data:
                raise Exception(
                    "Tomador não encontrado após upsert."
                )

            tomador_id = resultado_tomador.data[0]["id"]


            # =====================================================
            # 3. VERIFICA SE A NOTA JÁ EXISTE
            # =====================================================

            resultado_nota = (
                supabase
                .table("notas")
                .select(
                    "id, status_pagamento, data_pagamento"
                )
                .eq(
                    "chave_acesso",
                    n["chave_acesso"]
                )
                .limit(1)
                .execute()
            )


            # =====================================================
            # 4. DADOS DA NFS-e
            # =====================================================

            dados_nota = {
                "numero": n["numero"],
                "chave_acesso": n["chave_acesso"],
                "data_emissao": n["data_emissao"],
                "competencia": n["competencia"],
                "tomador_id": tomador_id,
                "codigo_servico": n["codigo_servico"],
                "descricao": n["descricao"],
                "valor_servico": n["valor_servico"],
                "status": n["status"],
            }


            # =====================================================
            # 5. NOTA JÁ EXISTE
            # =====================================================

            if resultado_nota.data:

                supabase.table("notas").update(
                    dados_nota
                ).eq(
                    "chave_acesso",
                    n["chave_acesso"]
                ).execute()

                print(
                    f"  ✓ Nota #{n['numero']} atualizada"
                )


            # =====================================================
            # 6. NOTA NOVA
            # =====================================================

            else:

                dados_nota["status_pagamento"] = "Pendente"
                dados_nota["data_pagamento"] = None

                supabase.table("notas").insert(
                    dados_nota
                ).execute()

                print(
                    f"  ✓ Nota #{n['numero']} inserida"
                )


            enviadas += 1


        except Exception as e:

            erros += 1

            print(
                f"  ✗ Erro na nota #{n.get('numero')}: {e}"
            )


    print()
    print(
        f"{enviadas} nota(s) processada(s) no Supabase."
    )

    if erros:
        print(
            f"{erros} nota(s) apresentaram erro."
        )


def main():

    notas = ler_notas()

    if not notas:
        return

    salvar_csv(notas)

    for n in notas:
        print(
            f"  #{n['numero']} - "
            f"{n['nome_tomador']} - "
            f"R$ {n['valor_servico']}"
        )

    print()
    print("Enviando para o Supabase...")

    enviar_supabase(notas)


if __name__ == "__main__":
    main()
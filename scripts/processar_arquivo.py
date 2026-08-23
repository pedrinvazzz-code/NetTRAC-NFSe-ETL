"""
Processa um único arquivo de NF (XML ou PDF):
  - detecta o tipo pela extensão
  - chama o parser correto
  - envia pro Supabase
  - move o arquivo para processados/ ou erros/
  - exibe notificação nativa do Windows

Pode ser chamado diretamente (python processar_arquivo.py caminho.pdf)
ou importado pelo watcher.
"""

import os
import sys
import shutil
import logging
from pathlib import Path

from dotenv import load_dotenv

# Garante que a pasta scripts/ está no path para os imports dos parsers
BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR / "scripts"))

load_dotenv(BASE_DIR / ".env")

from parser_nfse import parse_nota_from_file as parse_xml
from parser_nfse_pdf import parse_nota_from_file as parse_pdf

logger = logging.getLogger(__name__)


# ============================================================
# NOTIFICAÇÃO DO WINDOWS
# ============================================================

def _notificar(titulo: str, mensagem: str) -> None:
    """Exibe notificação nativa do Windows via plyer. Falha silenciosamente."""
    try:
        from plyer import notification
        notification.notify(
            title=titulo,
            message=mensagem,
            app_name="NetTRAC NF Watcher",
            timeout=8,
        )
    except Exception:
        pass


# ============================================================
# MOVIMENTAÇÃO DE ARQUIVOS
# ============================================================

def _mover(caminho: Path, destino_subdir: str) -> None:
    """Move o arquivo para subpasta dentro do mesmo diretório pai."""
    destino = caminho.parent / destino_subdir
    destino.mkdir(parents=True, exist_ok=True)
    destino_final = destino / caminho.name

    # Se já existir um arquivo com mesmo nome no destino, adiciona sufixo
    if destino_final.exists():
        destino_final = destino / f"{caminho.stem}_dup{caminho.suffix}"

    shutil.move(str(caminho), str(destino_final))
    logger.info(f"Arquivo movido para: {destino_final.relative_to(BASE_DIR)}")


# ============================================================
# ENVIO AO SUPABASE
# ============================================================

def _enviar_supabase(nota: dict) -> None:
    """Envia (upsert) a nota e o tomador no Supabase."""
    url = os.getenv("SUPABASE_URL")
    key = os.getenv("SUPABASE_KEY")

    if not url or not key:
        logger.warning(
            "SUPABASE_URL/SUPABASE_KEY não configurados — "
            "pulando envio ao banco. Configure o .env para ativar."
        )
        return

    from supabase import create_client

    supabase = create_client(url, key)

    # ----------------------------------------------------------
    # 1. Cria / atualiza o tomador
    # ----------------------------------------------------------
    supabase.table("tomadores").upsert(
        {
            "cpf_cnpj": nota["cnpj_tomador"],
            "razao_social": nota["nome_tomador"],
        },
        on_conflict="cpf_cnpj",
    ).execute()

    # ----------------------------------------------------------
    # 2. Busca o ID do tomador
    # ----------------------------------------------------------
    resultado_tomador = (
        supabase.table("tomadores")
        .select("id")
        .eq("cpf_cnpj", nota["cnpj_tomador"])
        .limit(1)
        .execute()
    )

    if not resultado_tomador.data:
        raise RuntimeError("Tomador não encontrado após upsert.")

    tomador_id = resultado_tomador.data[0]["id"]

    # ----------------------------------------------------------
    # 3. Verifica se a nota já existe
    # ----------------------------------------------------------
    existente = (
        supabase.table("notas")
        .select("id")
        .eq("chave_acesso", nota["chave_acesso"])
        .limit(1)
        .execute()
    )

    dados_nota = {
        "numero": nota["numero"],
        "chave_acesso": nota["chave_acesso"],
        "data_emissao": nota["data_emissao"],
        "competencia": nota["competencia"],
        "tomador_id": tomador_id,
        "codigo_servico": nota["codigo_servico"],
        "descricao": nota["descricao"],
        "valor_servico": nota["valor_servico"],
        "status": nota["status"],
    }

    # ----------------------------------------------------------
    # 4. Atualiza ou insere
    # ----------------------------------------------------------
    if existente.data:
        supabase.table("notas").update(dados_nota).eq(
            "chave_acesso", nota["chave_acesso"]
        ).execute()
        logger.info(f"Nota #{nota['numero']} atualizada no Supabase.")
    else:
        dados_nota["status_pagamento"] = "Pendente"
        dados_nota["data_pagamento"] = None
        supabase.table("notas").insert(dados_nota).execute()
        logger.info(f"Nota #{nota['numero']} inserida no Supabase.")


# ============================================================
# FUNÇÃO PRINCIPAL
# ============================================================

def processar(caminho_str: str) -> bool:
    """
    Processa um único arquivo de NF (PDF ou XML).

    Fluxo:
      1. Detecta extensão
      2. Parseia com o parser correto
      3. Envia pro Supabase
      4. Move pra processados/ (sucesso) ou erros/ (falha)
      5. Exibe notificação do Windows

    Retorna True se bem-sucedido, False caso contrário.
    """
    caminho = Path(caminho_str)

    if not caminho.exists():
        logger.error(f"Arquivo não encontrado: {caminho}")
        return False

    ext = caminho.suffix.lower()

    if ext not in (".xml", ".pdf"):
        logger.warning(f"Extensão não suportada, ignorando: {caminho.name}")
        return False

    logger.info(f"⏳ Processando: {caminho.name}")

    try:
        # --- Parse ---
        if ext == ".xml":
            nota = parse_xml(str(caminho))
        else:
            nota = parse_pdf(str(caminho))

        # --- Supabase ---
        _enviar_supabase(nota)

        # --- Sucesso ---
        _mover(caminho, "processados")

        resumo = (
            f"NF #{nota['numero']} — "
            f"{nota['nome_tomador']} — "
            f"R$ {nota['valor_servico']}"
        )
        logger.info(f"✅ {resumo}")
        _notificar("✅ NF processada!", resumo)

        return True

    except Exception as exc:
        logger.error(
            f"❌ Erro ao processar {caminho.name}: {exc}",
            exc_info=True,
        )
        _mover(caminho, "erros")
        _notificar(
            "❌ Erro ao processar NF",
            f"Arquivo: {caminho.name}\nErro: {exc}",
        )
        return False


# ============================================================
# USO DIRETO VIA LINHA DE COMANDO
# ============================================================

if __name__ == "__main__":
    import argparse

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s  %(levelname)-8s  %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    ap = argparse.ArgumentParser(
        description="Processa um arquivo de NF (PDF ou XML) manualmente."
    )
    ap.add_argument("arquivo", help="Caminho do PDF ou XML")
    args = ap.parse_args()

    ok = processar(args.arquivo)
    sys.exit(0 if ok else 1)

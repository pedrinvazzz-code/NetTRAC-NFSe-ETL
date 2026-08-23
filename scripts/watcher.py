"""
Watcher de pasta para NFS-e — NetTRAC.

Monitora pdfs/ e xmls/ em tempo real. Qualquer arquivo PDF ou XML
jogado nessas pastas é detectado automaticamente, processado
(parse + Supabase) e movido para processados/ ou erros/.

Início automático: registrado pelo instalar_servico.bat no
Agendador de Tarefas do Windows para rodar ao login do usuário,
sem janela visível (pythonw).
"""

import sys
import time
import logging
from pathlib import Path

# ============================================================
# CAMINHOS
# ============================================================

BASE_DIR = Path(__file__).resolve().parent.parent
PASTA_PDFS = BASE_DIR / "pdfs"
PASTA_XMLS = BASE_DIR / "xmls"
PASTA_LOGS = BASE_DIR / "logs"

# Garante que scripts/ está no path para importar processar_arquivo e parsers
sys.path.insert(0, str(BASE_DIR / "scripts"))

# ============================================================
# LOGGING
# ============================================================

PASTA_LOGS.mkdir(parents=True, exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
    handlers=[
        logging.FileHandler(
            PASTA_LOGS / "watcher.log",
            encoding="utf-8",
        ),
        logging.StreamHandler(sys.stdout),
    ],
)

logger = logging.getLogger(__name__)

# ============================================================
# HANDLER DO WATCHDOG
# ============================================================

from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler
from processar_arquivo import processar

EXTENSOES_SUPORTADAS = {".pdf", ".xml"}

# Segundos de espera após detectar o arquivo.
# Evita ler um PDF que ainda está sendo salvo (cópia lenta, rede, etc.)
DELAY_LEITURA = 1.5


class NFeHandler(FileSystemEventHandler):
    """Reage a arquivos novos ou movidos para as pastas monitoradas."""

    def on_created(self, event):
        if not event.is_directory:
            self._tratar(event.src_path)

    # Cobre o caso de "Salvar Como" de alguns programas (move temp → final)
    def on_moved(self, event):
        if not event.is_directory:
            self._tratar(event.dest_path)

    def _tratar(self, caminho: str) -> None:
        p = Path(caminho)

        # Ignora arquivos dentro das subpastas processados/ e erros/
        if p.parent.name in ("processados", "erros"):
            return

        if p.suffix.lower() not in EXTENSOES_SUPORTADAS:
            return

        logger.info(f"📄 Arquivo detectado: {p.name}")

        # Pequena pausa para garantir que o arquivo foi gravado por completo
        time.sleep(DELAY_LEITURA)

        processar(caminho)


# ============================================================
# MAIN
# ============================================================

def main():
    # Garante que as pastas monitoradas existem
    for pasta in (PASTA_PDFS, PASTA_XMLS):
        pasta.mkdir(parents=True, exist_ok=True)

    handler = NFeHandler()
    observer = Observer()
    observer.schedule(handler, str(PASTA_PDFS), recursive=False)
    observer.schedule(handler, str(PASTA_XMLS), recursive=False)
    observer.start()

    logger.info("=" * 60)
    logger.info("🟢 NetTRAC NF Watcher iniciado.")
    logger.info(f"   Monitorando PDFs : {PASTA_PDFS}")
    logger.info(f"   Monitorando XMLs : {PASTA_XMLS}")
    logger.info(f"   Log              : {PASTA_LOGS / 'watcher.log'}")
    logger.info("   Pressione Ctrl+C para encerrar.")
    logger.info("=" * 60)

    # Notificação de inicialização
    try:
        from plyer import notification
        notification.notify(
            title="NetTRAC NF Watcher",
            message="Monitoramento ativo. Pode jogar as NFs na pasta! 📂",
            app_name="NetTRAC NF Watcher",
            timeout=6,
        )
    except Exception:
        pass

    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        logger.info("Encerrando watcher...")
        observer.stop()

    observer.join()
    logger.info("🔴 Watcher encerrado.")


if __name__ == "__main__":
    main()

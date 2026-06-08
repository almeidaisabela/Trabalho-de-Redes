import logging
import time
from p2p_client import P2PClient

def configure_logs():
    """
    Configura o sistema de logs padrão para toda a aplicação.
    Todos os módulos poderão usar logging.getLogger("NomeDoModulo").
    """
    logging.basicConfig(
        level=logging.DEBUG, # Pode ser alterado para INFO posteriormente
        format='%(asctime)s [%(name)s] %(levelname)s: %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )

def main():
    configure_logs()
    logger = logging.getLogger("Main")
    logger.info("Iniciando a aplicação Chat P2P...")

    # Instancia e inicia o cliente P2P escutando na porta 4000
    client = P2PClient(host='0.0.0.0', port=4000)
    client.start_server()

    try:
        # Loop principal provisório para manter o programa rodando.
        # No futuro, aqui entrará o loop do CLI (Interface de Usuário).
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        logger.info("Encerrando aplicação via teclado (Ctrl+C)...")
        client.stop_server()

if __name__ == "__main__":
    main()
import logging
import time
from p2p_client import P2PClient
from rendezvous_connection import RendezvousClient  # Importando a nova classe

def configure_logs():
    logging.basicConfig(
        level=logging.DEBUG, 
        format='%(asctime)s [%(name)s] %(levelname)s: %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )

def main():
    configure_logs()
    logger = logging.getLogger("Main")
    logger.info("Iniciando a aplicação Chat P2P...")

    # --- Configurações de Identidade do Peer ---
    meu_namespace = "RedesUnB"
    meu_nome = "kallebe"
    minha_porta = 4000

    # 1. Inicia o Servidor TCP local para escutar conexões
    client = P2PClient(host='0.0.0.0', port=minha_porta)
    client.start_server()

    # 2. Conecta no servidor Rendezvous e registra presença
    rdv = RendezvousClient()
    registro = rdv.register(namespace=meu_namespace, name=meu_nome, port=minha_porta)
    
    if registro.get("status") != "OK":
        logger.error("Falha ao registrar no Rendezvous. Encerrando...")
        client.stop_server()
        return

    # 3. Busca a lista de peers que já estão na rede
    peers_ativos = rdv.discover(namespace=meu_namespace)
    logger.info(f"Peers atualmente no Rendezvous: {peers_ativos}")

    try:
        # Loop principal provisório
        while True:
            time.sleep(1)
            
    except KeyboardInterrupt:
        logger.info("Encerrando aplicação via teclado (Ctrl+C)...")
        # Boa prática: Remover o registro do Rendezvous ao sair
        rdv.unregister(namespace=meu_namespace, name=meu_nome, port=minha_porta)
        client.stop_server()

if __name__ == "__main__":
    main()
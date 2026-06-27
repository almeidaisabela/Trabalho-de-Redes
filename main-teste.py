import logging
import time
from p2p_client import P2PClient
from rendezvous_connection import RendezvousClient
from peer_table import PeerTable
from keep_alive import KeepAliveManager
from message_router import MessageRouter
import json
import os

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

    max_reconnect = 5
    ping_interval = 30

    if os.path.exists("config.json"):
        try:
            with open("config.json", "r") as f:
                config = json.load(f)
                max_reconnect = config.get(
                    "max_reconnect_attempts",
                    max_reconnect
                )
                ping_interval = config.get(
                    "ping_interval",
                    ping_interval
                )

            logger.info(
                "Configuração carregada: "
                f"max_reconnect_attempts = {max_reconnect}, "
                f"ping_interval = {ping_interval}"
            )

        except Exception as e:
            logger.warning(
                f"Erro ao ler config.json ({e}). "
                "Usando valores padrão."
            )


    # --- Configurações de Identidade do Peer ---
    meu_namespace = "RedesUnB"
    meu_nome = "isa"
    minha_porta = 4002
    peer_table = PeerTable()

    # 1. Inicia o Servidor TCP local para escutar conexões
    client = P2PClient(
        host='0.0.0.0',
        port=minha_porta,
        my_peer_id=f"{meu_nome}@{meu_namespace}",
        peer_table=peer_table
    )
    client.start_server()

    # 2. Conecta no servidor Rendezvous e registra presença
    rdv = RendezvousClient()
    registro = rdv.register(namespace=meu_namespace, name=meu_nome, port=minha_porta)
    
    if registro.get("status") != "OK":
        logger.error("Falha ao registrar no Rendezvous. Encerrando...")
        client.stop_server()
        return

    # 3. Busca a lista de peers que já estão na rede
    peer_table = PeerTable()
    peers_ativos = rdv.discover(namespace=meu_namespace)
    peer_table.update(peers_ativos)
    logger.info(peer_table.get_all())
    logger.info(f"Peers atualmente no Rendezvous: {peers_ativos}")

    # Cria o roteador de mensagens
    router = MessageRouter(
        peer_table,
        client.connections,
        f"{meu_nome}@{meu_namespace}"
    )

    # --- INÍCIO DO KEEP-ALIVE ---
    def envia_ping(peer_id, mensagem):
        conn = client.connections.get(peer_id)
        if conn:
            return conn.send_message(mensagem)
        return False

    kam = KeepAliveManager(
        peer_table=peer_table,
        send_function=envia_ping,
        my_peer_id=f"{meu_nome}@{meu_namespace}",
        ping_interval=ping_interval
    )
    kam.start()
    client.pending_pings = kam.pending_pings
    # --- FIM DO KEEP-ALIVE ---

    for peer in peers_ativos:
        # evita conectar em si mesmo
        if peer["name"] == meu_nome:
            continue

        peer_id = f"{peer['name']}@{peer['namespace']}"
        logger.info(f"Conectando em {peer_id}")

        peer_conn = client.connect_to_peer(peer_id, "127.0.0.1", peer["port"])

        if peer_conn:
            logger.info(f"Conexão iniciada com {peer_id}. Aguardando handshake...")
        else:
            logger.warning(f"Falha ao conectar em {peer_id}.")
    
    time.sleep(2)

    router.publish_global(
        "Mensagem para todos!"
    )

    router.send_direct(
        "kallebe@RedesUnB",
        "Olá Kallebe! Teste SEND."
    )

    logger.info("Enviando mensagem de teste...")

    try:
        # Loop principal provisório
        while True:
            time.sleep(1)
            
    except KeyboardInterrupt:
        logger.info("Encerrando aplicação via teclado (Ctrl+C)...")
        rdv.unregister(namespace=meu_namespace, name=meu_nome, port=minha_porta)
        kam.stop() # É uma boa prática parar a thread do Keep-Alive também
        client.stop_server()

if __name__ == "__main__":
    main()


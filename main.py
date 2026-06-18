import logging
import time
from p2p_client import P2PClient
from rendezvous_connection import RendezvousClient
from peer_table import PeerTable

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
    peer_table = PeerTable()
    peers_ativos = rdv.discover(namespace=meu_namespace)
    peer_table.update(peers_ativos)
    logger.info(peer_table.get_all())
    logger.info(f"Peers atualmente no Rendezvous: {peers_ativos}")

    # --- INÍCIO DO KEEP-ALIVE ---
    from keep_alive import KeepAliveManager

    def envia_ping(ip_destino, porta_destino, mensagem):
        for conn in client.connections.values():
            if conn.addr == (ip_destino, porta_destino):
                return conn.send_message(mensagem)
        return False

    kam = KeepAliveManager(peer_table=peer_table, send_function=envia_ping)
    kam.start()
    # --- FIM DO KEEP-ALIVE ---

    for peer in peers_ativos:
        # evita conectar em si mesmo
        if peer["name"] == meu_nome:
            logger.info(f"Ignorando meu próprio registro: {peer['name']}")
            continue

        peer_id = f"{peer['name']}@{peer['namespace']}"
        sock = client.connect_to_peer(
            peer_id,
            peer["ip"],
            peer["port"]
        )

        if sock:
            client.connections[peer_id] = sock

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
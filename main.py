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

    max_reconnect = 5 # Valor por omissão caso o ficheiro não exista
    if os.path.exists("config.json"):
        try:
            with open("config.json", "r") as f:
                config = json.load(f)
                max_reconnect = config.get("max_reconnect_attempts", 5)
            logger.info(f"Configuração carregada: max_reconnect_attempts = {max_reconnect}")
        except Exception as e:
            logger.warning(f"Erro ao ler config.json. A usar limite por omissão (5): {e}")
    else:
        logger.warning("Ficheiro config.json não encontrado. A usar limite por omissão (5).")

    # --- Configurações de Identidade do Peer ---
    meu_namespace = "RedesUnB"
    meu_nome = "kallebe"
    minha_porta = 4000
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
    peers_ativos = rdv.discover(namespace=meu_namespace)
    peer_table.update(peers_ativos)
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
        my_peer_id=f"{meu_nome}@{meu_namespace}"
        )
    
    kam.start()
    client.pending_pings = kam.pending_pings
    # --- FIM DO KEEP-ALIVE ---

    # --- INÍCIO DA CLI ---
    from cli import CLI
    interface = CLI(peer_table=peer_table, router=router, client=client)
    interface.start()
    # --- FIM DA CLI ---

    for peer in peers_ativos:
        # evita conectar em si mesmo
        logger.info(f"Peer encontrado: {peer}")

    for peer in peers_ativos:
        # evita conectar em si mesmo
        logger.info(f"Peer encontrado: {peer}")
        if peer["name"] == meu_nome:
            continue

        peer_id = f"{peer['name']}@{peer['namespace']}"

        logger.info(
            f"Tentando conectar em {peer_id} "
            f"({peer['ip']}:{peer['port']})"
        )
        
        sock = client.connect_to_peer(
            peer_id,
            peer["ip"],
            peer["port"]
        )

    ultimo_discover = time.time()
    intervalo_discover = 60 # Faz discover a cada 60 segundos

    try:
        # Loop principal provisório (agora com manutenção de rede)
        while True:
            agora = time.time()
            
            # 1. DISCOVER Periódico
            if agora - ultimo_discover > intervalo_discover:
                logger.info("Executando DISCOVER periódico...")
                novos_peers = rdv.discover(namespace=meu_namespace)
                peer_table.update(novos_peers)
                ultimo_discover = agora
                
                # Tenta conectar com quem for novo e ainda não estiver conectado
                for peer_id, dados in peer_table.get_all().items():
                    if peer_id != f"{meu_nome}@{meu_namespace}" and dados["status"] == "KNOWN":
                        if peer_id not in client.connections:
                            client.connect_to_peer(peer_id, dados["ip"], dados["port"])

            # 2. Reconexão Exponencial (Peers STALE)
            for peer_id, dados in peer_table.get_all().items():
                if dados["status"] == "STALE":
                    tentativas = dados.get("reconnect_attempts", 0)
                    proxima_tentativa = dados.get("next_reconnect", 0)
                    limite_tentativas = max_reconnect
                    
                    if tentativas < limite_tentativas:
                        if agora >= proxima_tentativa:
                            tentativas += 1
                            dados["reconnect_attempts"] = tentativas
                            
                            # Calcula o backoff: 1s, 2s, 4s, 8s, 16s...
                            espera = 2 ** (tentativas - 1)
                            dados["next_reconnect"] = agora + espera
                            
                            logger.info(
                                f"Tentando reconectar a {peer_id} "
                                f"(Tentativa {tentativas}/{limite_tentativas}). "
                                f"Próxima em {espera}s caso falhe."
                            )
                            # Chama a função de conexão do seu cliente TCP
                            client.connect_to_peer(peer_id, dados["ip"], dados["port"])
                    
                    elif dados["status"] != "DEAD":
                        # Desiste após o limite de tentativas para não ficar travando o loop
                        logger.warning(f"Desistindo de reconectar a {peer_id}. Marcando como DEAD.")
                        peer_table.update_status(peer_id, "DEAD")

            time.sleep(1) # Pausa de 1 segundo para não fritar o processador
            
    except KeyboardInterrupt:
        logger.info("Encerrando aplicação via teclado (Ctrl+C)...")

        # Encerramento gracioso: avisa cada peer antes de fechar
        for peer_id, conn in list(client.connections.items()):
            logger.info(f"Enviando BYE para {peer_id}...")
            conn.send_bye()

        time.sleep(0.5)  # Dá tempo para os BYEs saírem antes de fechar os sockets

        rdv.unregister(namespace=meu_namespace, name=meu_nome, port=minha_porta)
        kam.stop()
        client.stop_server()

if __name__ == "__main__":
    main()


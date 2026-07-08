# ==============================================================================
# Trabalho Final - Chat P2P
# Disciplina: Redes de Computadores - T02
# Grupo: 07
# Membros da Equipe:
# - Arthur Martins Pereira de Souza - Matrícula: 241004499
# - Isabela de Almeida Pantaleão - Matrícula: 242040346
# - Rian Kallebe da Silva Lisboa - Matrícula: 242012000
# ==============================================================================

import sys
import logging
import time
from p2p_client import P2PClient
from rendezvous_connection import RendezvousClient
from peer_table import PeerTable
from keep_alive import KeepAliveManager
from message_router import MessageRouter
import json  
import os
from cli import CLI

def configure_logs(log_level_str):
    # Converte a string do JSON para o nível real do logging (ex: CRITICAL, INFO, DEBUG)
    numeric_level = getattr(logging, log_level_str.upper(), logging.INFO)
    logging.basicConfig(
        level=numeric_level, 
        format='%(asctime)s [%(name)s] %(levelname)s: %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )

def main():
    # --- 1. CARREGAMENTO DO CONFIG.JSON ---
    config = {}
    if os.path.exists("config.json"):
        try:
            with open("config.json", "r") as f:
                config = json.load(f)
        except Exception as e:
            print(f"Erro ao ler config.json. Usando padrões. Erro: {e}")
    else:
        print("Ficheiro config.json não encontrado. Usando padrões.")

    # --- 2. EXTRAÇÃO DAS VARIÁVEIS ---
    log_level = config.get("log_level", "INFO")
    meu_nome = config.get("name", "Grupo7")
    meu_namespace = config.get("namespace", "CIC")
    meu_host = config.get("local_ip", "0.0.0.0")
    minha_porta = config.get("local_port", 4000)
    
    rdv_ip = config.get("rendezvous_ip", "10.42.0.1")
    rdv_port = config.get("rendezvous_port", 8080)
    rdv_ttl = config.get("ttl", 300)
    
    ping_interval = config.get("keep_alive_interval", 5.0)
    max_reconnect = config.get("max_reconnect_attempts", 5)
    intervalo_discover = config.get("discovery_delay", 5)

    # === VALIDAÇÃO DE TIPOS E FORMATOS ===
    if not isinstance(meu_namespace, str) or len(meu_namespace) > 64:
        print("ERRO FATAL: O namespace deve ser uma string com até 64 caracteres.")
        sys.exit(1)
        
    if not isinstance(meu_nome, str) or len(meu_nome) > 64:
        print("ERRO FATAL: O nome deve ser uma string com até 64 caracteres.")
        sys.exit(1)
        
    if not isinstance(minha_porta, int) or not (1 <= minha_porta <= 65535):
        print("ERRO FATAL: A porta deve ser um número inteiro entre 1 e 65535.")
        sys.exit(1)
        
    if not isinstance(rdv_ttl, int) or not (1 <= rdv_ttl <= 86400):
        print("ERRO FATAL: O TTL deve ser um inteiro entre 1 e 86400 segundos.")
        sys.exit(1)
    
    # --- 3. INICIALIZAÇÃO DA APLICAÇÃO ---
    configure_logs(log_level)
    logger = logging.getLogger("Main")
    logger.info("Iniciando a aplicação Chat P2P...")
    logger.info(f"Identidade carregada: {meu_nome}@{meu_namespace} na porta {minha_porta}")

    peer_table = PeerTable()

    # Inicia o Servidor TCP local para escutar conexões
    client = P2PClient(
        host=meu_host,
        port=minha_porta,
        my_peer_id=f"{meu_nome}@{meu_namespace}",
        peer_table=peer_table
    )
    client.start_server()

    # Conecta no servidor Rendezvous e registra presença
    rdv = RendezvousClient(server_ip=rdv_ip, server_port=rdv_port)
    registro = rdv.register(namespace=meu_namespace, name=meu_nome, port=minha_porta, ttl=rdv_ttl)
    
    if registro.get("status") != "OK":
        logger.error("Falha ao registrar no Rendezvous. Encerrando...")
        client.stop_server()
        return

    # Busca a lista de peers que já estão na rede
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
        my_peer_id=f"{meu_nome}@{meu_namespace}",
        ping_interval=ping_interval 
    )
    
    kam.start()
    client.pending_pings = kam.pending_pings
    # --- FIM DO KEEP-ALIVE ---

    # --- INÍCIO DA CLI ---
    interface = CLI(peer_table=peer_table, router=router, client=client)
    interface.start()
    # --- FIM DA CLI ---

    ultimo_discover = time.time()
    ultimo_register = time.time()   

    try:
        # Loop principal
        while True:
            agora = time.time()

            # === RENOVAÇÃO RECORRENTE DO REGISTER ===
            # Renova o registro quando chegar a 90% do tempo de vida (TTL)
            tempo_limite_renovacao = rdv_ttl * 0.90 
            if agora - ultimo_register > tempo_limite_renovacao:
                logger.info(f"Renovando registro no Rendezvous (TTL: {rdv_ttl}s)...")
                rdv.register(namespace=meu_namespace, name=meu_nome, port=minha_porta, ttl=rdv_ttl)
                ultimo_register = agora
            
            # 1. DISCOVER Periódico usando a variável do JSON
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
                    
                    if tentativas < max_reconnect:
                        if agora >= proxima_tentativa:
                            tentativas += 1
                            dados["reconnect_attempts"] = tentativas
                            
                            # Calcula o backoff: 1s, 2s, 4s, 8s, 16s...
                            espera = 2 ** (tentativas - 1)
                            dados["next_reconnect"] = agora + espera
                            
                            logger.info(
                                f"Tentando reconectar a {peer_id} "
                                f"(Tentativa {tentativas}/{max_reconnect}). "
                                f"Próxima em {espera}s caso falhe."
                            )
                            client.connect_to_peer(peer_id, dados["ip"], dados["port"])
                    
                    elif dados["status"] != "DEAD":
                        logger.warning(f"Desistindo de reconectar a {peer_id}. Marcando como DEAD.")
                        peer_table.update_status(peer_id, "DEAD")

            time.sleep(1) 
            
    except KeyboardInterrupt:
        logger.info("Encerrando aplicação via teclado (Ctrl+C)...")

        for peer_id, conn in list(client.connections.items()):
            logger.info(f"Enviando BYE para {peer_id}...")
            conn.send_bye()

        time.sleep(0.5) 

        rdv.unregister(namespace=meu_namespace, name=meu_nome, port=minha_porta)
        kam.stop()
        client.stop_server()

if __name__ == "__main__":
    main()
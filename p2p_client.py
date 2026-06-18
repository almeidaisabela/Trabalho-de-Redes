import socket
import threading
import logging
import json
from peer_connection import PeerConnection

class P2PClient:
    def __init__(
            self, 
            host, 
            port, 
            my_peer_id,
            peer_table
    ):
        self.host = host
        self.port = port
        self.my_peer_id = my_peer_id
        self.peer_table = peer_table

        self.logger = logging.getLogger("PeerServer")
        
        # Criação do Socket TCP (IPv4, Stream)
        self.server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        
        # Permite reutilizar a porta imediatamente se o programa for reiniciado
        self.server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        
        self.running = False

        self.connections = {}

    def start_server(self):
        """Faz o bind da porta e inicia a thread que escuta conexões."""
        try:
            self.server_socket.bind((self.host, self.port))
            self.server_socket.listen(5) # Enfileira até 5 conexões simultâneas
            self.running = True
            
            self.logger.info(f"Servidor TCP P2P escutando em {self.host}:{self.port}")

            # Inicia uma Thread separada para não travar o programa principal
            accept_thread = threading.Thread(target=self._accept_connections, daemon=True)
            accept_thread.start()
            
        except Exception as e:
            self.logger.error(f"Erro ao iniciar servidor TCP: {e}")

    def _accept_connections(self):
        """Loop infinito para aceitar novas conexões de entrada (Inbound)."""
        while self.running:
            try:
                # Atualize dentro do _accept_connections (quando recebemos uma ligação Inbound)
                conn, addr = self.server_socket.accept()
                self.logger.info(f"Inbound connected: {addr[0]}:{addr[1]}")

                peer_conn = PeerConnection(
                    sock=conn,
                    addr=addr,
                    my_peer_id=self.my_peer_id,
                    is_inbound=True,
                    connections=self.connections,
                    peer_table=self.peer_table,
                    pending_pings=getattr(self, 'pending_pings', {})
                )
                peer_conn.start() # A classe do Arthur agora trata de tudo!
                
            except OSError:
                if self.running:
                    self.logger.error("Erro no socket ao aceitar conexão.")
                break

    def stop_server(self):
        """Encerra o servidor de forma limpa."""
        self.running = False
        self.server_socket.close()
        self.logger.info("Servidor TCP fechado com sucesso.")

    def connect_to_peer(self, peer_id, ip, port):
        try:
            # Atualize no final do seu connect_to_peer (quando nos ligamos a alguém Outbound)
            sock = socket.create_connection((ip, port), timeout=60)
            sock.settimeout(None)
            self.logger.info(f"Outbound connected para o IP: {ip}:{port}")

            peer_conn = PeerConnection(
                sock=sock,
                addr=(ip, port),
                my_peer_id=self.my_peer_id,
                is_inbound=False,
                connections=self.connections,
                peer_table=self.peer_table,
                pending_pings=getattr(self, 'pending_pings', {})
            )
            peer_conn.remote_peer_id = peer_id

            peer_conn.start() # Como é is_inbound=False, isto vai disparar o _send_hello() automaticamente!

            return peer_conn

        except Exception as e:
            self.logger.error(
                f"Falha ao conectar em {peer_id}: {e}"
            )
            return None
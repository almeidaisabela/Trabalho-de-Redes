import socket
import threading
import logging
import json

class P2PClient:
    def __init__(self, host: str, port: int):
        self.host = host
        self.port = port
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
                # O código pausa aqui até que um novo peer tente se conectar
                conn, addr = self.server_socket.accept()
                self.logger.info(f"Inbound connected: {addr[0]}:{addr[1]}")
                
                # Para cada nova conexão, abrimos uma Thread dedicada
                client_thread = threading.Thread(target=self._handle_client, args=(conn, addr), daemon=True)
                client_thread.start()
                
            except OSError:
                if self.running:
                    self.logger.error("Erro no socket ao aceitar conexão.")
                break

    def _handle_client(self, conn, addr):
        """Lida com as mensagens de uma conexão TCP específica."""
        with conn:
            try:
                # Recebe os dados. O limite do protocolo é 32 KiB por linha
                data = conn.recv(32768) 
                if data:
                    texto = data.decode('utf-8').strip()
                    self.logger.debug(f"Dado recebido de {addr}: {texto}")
            except Exception as e:
                self.logger.error(f"Erro de comunicação com {addr}: {e}")
            finally:
                self.logger.info(f"Conexão encerrada com {addr}")

    def stop_server(self):
        """Encerra o servidor de forma limpa."""
        self.running = False
        self.server_socket.close()
        self.logger.info("Servidor TCP fechado com sucesso.")

    def connect_to_peer(self, peer_id, ip, port):
        try:
            sock = socket.create_connection(
                (ip, port),
                timeout=5
            )
            self.logger.info(
                f"Outbound connected: {peer_id}"
            )
            return sock

        except Exception as e:
            self.logger.error(
                f"Falha ao conectar em {peer_id}: {e}"
            )
            return None
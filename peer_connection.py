import socket
import threading
import logging
import json
import uuid

class PeerConnection:
    def __init__(self, sock: socket.socket, addr, my_peer_id: str, is_inbound: bool = False):
        """
        Gere uma ligação TCP individual com um peer.
        is_inbound = True significa que eles se ligaram a nós (somos o servidor).
        is_inbound = False significa que nós iniciámos a ligação (somos o cliente).
        """
        self.sock = sock
        self.addr = addr
        self.my_peer_id = my_peer_id
        self.is_inbound = is_inbound
        self.remote_peer_id = None
        self.logger = logging.getLogger(f"PeerConn-{addr[1]}")
        self.running = False
        self.connected = False

    def start(self):
        """Inicia a thread de escuta contínua desta ligação."""
        self.running = True
        thread = threading.Thread(target=self._listen_loop, daemon=True)
        thread.start()
        
        # Se nós fomos o cliente que iniciou a ligação, temos de dizer HELLO primeiro!
        if not self.is_inbound:
            self._send_hello()

    def send_message(self, msg_dict: dict) -> bool:
        """Converte um dicionário para JSON (com quebra de linha) e envia."""
        try:
            data = json.dumps(msg_dict) + "\n"
            self.sock.sendall(data.encode('utf-8'))
            self.logger.debug(f"Enviado para {self.remote_peer_id or self.addr}: {data.strip()}")
            return True
        except Exception as e:
            self.logger.error(f"Erro ao enviar mensagem para {self.remote_peer_id or self.addr}: {e}")
            self.stop()
            return False

    def _listen_loop(self):
        """Loop infinito para ler dados do socket linha a linha."""
        buffer = ""
        while self.running:
            try:
                # Recebe até 4096 bytes de cada vez e descodifica
                chunk = self.sock.recv(4096).decode('utf-8')
                if not chunk:
                    self.logger.info(f"A ligação foi fechada remotamente por {self.remote_peer_id or self.addr}.")
                    self.stop()
                    break
                
                buffer += chunk
                
                # O protocolo exige que cada JSON acabe com \n
                while "\n" in buffer:
                    line, buffer = buffer.split("\n", 1)
                    if line.strip():
                        self._process_message(line.strip())
                        
            except Exception as e:
                if self.running:
                    self.logger.error(f"Erro de leitura na ligação: {e}")
                self.stop()
                break

    def _process_message(self, raw_json: str):
        """Faz o parsing do JSON e roteia para a ação correta."""
        try:
            msg = json.loads(raw_json)
            msg_type = msg.get("type")
            
            # --- Handshake ---
            if msg_type == "HELLO":
                self.remote_peer_id = msg.get("peer_id")
                self.logger.info(f"Recebido HELLO de {self.remote_peer_id}. A enviar HELLO_OK...")
                self._send_hello_ok()
                self.connected = True
                
            elif msg_type == "HELLO_OK":
                self.remote_peer_id = msg.get("peer_id")
                self.logger.info(f"Handshake concluído com {self.remote_peer_id} (HELLO_OK recebido).")
                self.connected = True
                
            # --- Encerramento ---
            elif msg_type == "BYE":
                self.logger.info(f"Recebido pedido de encerramento (BYE) de {self.remote_peer_id}.")
                self._send_bye_ok(msg)
                self.stop()
                
            elif msg_type == "BYE_OK":
                self.logger.info(f"Despedida confirmada (BYE_OK) por {self.remote_peer_id}. A fechar ligação.")
                self.stop()
                
            # --- Futuro (Mensagens da Isabela e o seu PING) ---
            else:
                self.logger.debug(f"Recebida mensagem do tipo {msg_type} de {self.remote_peer_id}")
                # Aqui o sistema vai processar PING, PONG, SEND, ACK e PUB posteriormente
                
        except json.JSONDecodeError:
            self.logger.error(f"Recebido JSON inválido ou corrompido: {raw_json}")

    def _send_hello(self):
        hello_msg = {
            "type": "HELLO",
            "peer_id": self.my_peer_id,
            "version": "1.0",
            "features": ["ack", "metrics"],
            "ttl": 1
        }
        self.send_message(hello_msg)

    def _send_hello_ok(self):
        ok_msg = {
            "type": "HELLO_OK",
            "peer_id": self.my_peer_id,
            "version": "1.0",
            "features": ["ack", "metrics"],
            "ttl": 1
        }
        self.send_message(ok_msg)

    def send_bye(self):
        """Função para ser chamada quando quisermos desligar a chamada voluntariamente."""
        bye_msg = {
            "type": "BYE",
            "msg_id": str(uuid.uuid4()),
            "src": self.my_peer_id,
            "dst": self.remote_peer_id,
            "reason": "O utilizador encerrou a ligação",
            "ttl": 1
        }
        self.send_message(bye_msg)

    def _send_bye_ok(self, bye_msg):
        bye_ok = {
            "type": "BYE_OK",
            "msg_id": bye_msg.get("msg_id", str(uuid.uuid4())),
            "src": self.my_peer_id,
            "dst": self.remote_peer_id,
            "ttl": 1
        }
        self.send_message(bye_ok)
        
    def stop(self):
        """Encerra a thread e fecha o socket."""
        self.running = False
        self.connected = False
        try:
            self.sock.close()
        except:
            pass
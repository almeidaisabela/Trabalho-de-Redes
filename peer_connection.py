
import socket
import threading
import logging
import json
import uuid
from datetime import datetime, timezone
import time

class PeerConnection:
    def __init__(
            self, 
            sock: socket.socket, 
            addr, 
            my_peer_id: str, 
            is_inbound: bool = False, 
            connections=None,
            peer_table=None,
            pending_pings=None
    ):
        """
        Gere uma ligação TCP individual com um peer.
        is_inbound = True significa que eles se ligaram a nós (somos o servidor).
        is_inbound = False significa que nós iniciámos a ligação (somos o cliente).
        """
        # Guarda a ponte de comunicação (socket) e o endereço (IP/Porta)
        self.sock = sock
        self.addr = addr
        self.my_peer_id = my_peer_id
        self.is_inbound = is_inbound
        self.connections = connections
        self.peer_table = peer_table
        self.pending_pings = pending_pings if pending_pings is not None else {}

        # Identidade de quem está do outro lado da linha (preenchido no Handshake)
        self.remote_peer_id = None

        self.logger = logging.getLogger(f"PeerConn-{addr[1]}")
        self.running = False
        self.connected = False
        
        # Dicionário para rastrear mensagens enviadas que aguardam recibo de leitura (ACK)
        self.pending_acks = {}

    def start(self):
        """Inicia a thread de escuta contínua desta ligação."""
        self.running = True
        
        # Inicia duas threads separadas para essa conexão:
        # 1. Fica ouvindo o que chega pela rede.
        threading.Thread(target=self._listen_loop, daemon=True).start()
        # 2. Fica checando de 1 em 1 segundo se alguma mensagem deu timeout.
        threading.Thread(target=self._check_ack_timeouts, daemon=True).start()
        
        # Se nós fomos o cliente que iniciou a ligação, temos de dizer HELLO primeiro!
        if not self.is_inbound:
            self._send_hello()

    def send_message(self, msg_dict: dict) -> bool:
        """Converte um dicionário para JSON (com quebra de linha) e envia."""
        try:
            # Transforma o dicionário em texto e adiciona o '\n' (Delimitador do protocolo)
            data = json.dumps(msg_dict) + "\n"
            # sendall garante que o pacote inteiro seja enviado via TCP
            self.sock.sendall(data.encode('utf-8'))
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
                # O TCP é um fluxo contínuo. Ele pode entregar a mensagem pela metade 
                # ou duas mensagens grudadas. O recv pega o que estiver lá.
                chunk = self.sock.recv(4096).decode('utf-8')
                
                # Se recv retornar vazio, significa que o peer fechou o programa.
                if not chunk:
                    self.logger.info(f"A ligação foi fechada remotamente por {self.remote_peer_id or self.addr}.")
                    self.stop()
                    break
                
                buffer += chunk
                
                # O protocolo exige que cada JSON acabe com \n
                # Esse while recorta as mensagens exatamente onde elas terminam,
                # garantindo que o JSON não seja processado quebrado.
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
            
            # --- Handshake (Aperto de mão inicial) ---
            # Troca de IDs antes de permitir a comunicação real
            if msg_type == "HELLO":
                self.remote_peer_id = msg.get("peer_id")
                if self.connections is not None:
                    self.connections[self.remote_peer_id] = self
                self.logger.info(
                    f"Recebido HELLO de {self.remote_peer_id}. A enviar HELLO_OK..."
                )
                self._send_hello_ok()
                self.connected = True
                if self.peer_table:
                    self.peer_table.update_status(
                        self.remote_peer_id,
                        "CONNECTED"
                    )
                
            elif msg_type == "HELLO_OK":
                self.remote_peer_id = msg.get("peer_id")
                if self.connections is not None:
                    self.connections[self.remote_peer_id] = self
                self.logger.info(
                    f"Handshake concluído com {self.remote_peer_id} (HELLO_OK recebido)."
                )
                self.connected = True
                if self.peer_table:
                    self.peer_table.update_status(
                        self.remote_peer_id,
                        "CONNECTED"
                    )
                
            # --- Encerramento Limpo (Graceful Shutdown) ---
            elif msg_type == "BYE":
                self.logger.info(f"Recebido pedido de encerramento (BYE) de {self.remote_peer_id}.")
                self._send_bye_ok(msg)
                self.stop()
                
            elif msg_type == "BYE_OK":
                self.logger.info(f"Despedida confirmada (BYE_OK) por {self.remote_peer_id}. A fechar ligação.")
                self.stop()

            # --- Troca de Mensagens Diretas ---
            elif msg_type == "SEND":
                self.logger.info(
                    f"[SEND] {msg['src']} -> {self.my_peer_id}: "
                    f"{msg['payload']}"
                )
                # Se a mensagem exige recibo, envia um ACK de volta
                if msg.get("require_ack"):
                    ack = {
                        "type": "ACK",
                        "msg_id": msg["msg_id"],
                        "timestamp": datetime.now(timezone.utc).isoformat(),
                        "ttl": 1
                    }
                    self.send_message(ack)

            # --- Recibo de Leitura (ACK) ---
            elif msg_type == "ACK":
                msg_id = msg["msg_id"]
                sent_at = self.pending_acks.pop(msg_id, None) # Remove da lista de pendentes
                if sent_at:
                    # Calcula o RTT (Round Trip Time): o tempo que a mensagem levou para ir e voltar
                    rtt = (datetime.now(timezone.utc) - sent_at).total_seconds() * 1000
                    self.logger.info(f"ACK recebido para msg_id={msg_id} | RTT={rtt:.1f}ms")
                    
                    if self.peer_table:
                        self.peer_table.add_rtt(self.remote_peer_id, rtt)
                        
                else:
                    self.logger.warning(f"ACK recebido para msg_id desconhecido={msg_id}")

            # --- Mensagens para Todos (Broadcast/Multicast) ---
            elif msg_type == "PUB":
                dst = msg.get("dst", "")

                # O asterisco significa mensagem para a rede inteira
                if dst == "*":
                    self.logger.info(
                        f"[PUB-GLOBAL] {msg['src']}: {msg['payload']}"
                    )

                # Hashtag significa mensagem para um grupo específico (namespace)
                elif dst.startswith("#"):
                    meu_namespace = self.my_peer_id.split("@")[1]
                    namespace_destino = dst[1:]

                    if meu_namespace == namespace_destino:
                        self.logger.info(
                            f"[PUB-{namespace_destino}] "
                            f"{msg['src']}: {msg['payload']}"
                        )
            
            # --- Checagem de Latência e Vida útil (Ping/Pong) ---
            elif msg_type == "PING":
                self.logger.info(
                    f"PING recebido de {self.remote_peer_id}"
                )
                # Rebate o Ping imediatamente com um Pong
                pong = {
                    "type": "PONG",
                    "msg_id": msg["msg_id"],
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                    "ttl": 1
                }
                self.send_message(pong)
            
            elif msg_type == "PONG":
                msg_id = msg["msg_id"]
                sent_at = self.pending_pings.pop(msg_id, None)
                if sent_at:
                    rtt = (datetime.now(timezone.utc) - sent_at).total_seconds() * 1000
                    self.logger.info(f"PONG recebido de {self.remote_peer_id} | RTT={rtt:.1f}ms")
                    
                    if self.peer_table:
                        self.peer_table.add_rtt(self.remote_peer_id, rtt)
                        
                else:
                    self.logger.info(f"PONG recebido de {self.remote_peer_id} (sem RTT — ping não registrado)")
                
                if self.peer_table:
                    self.peer_table.update_status(self.remote_peer_id, "CONNECTED")
                
        except json.JSONDecodeError:
            self.logger.error(f"Recebido JSON inválido ou corrompido: {raw_json}")

    # --- Funções Auxiliares para montar o JSON correto de cada tipo ---
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
        """Encerra as threads (running = False) e limpa a conexão do dicionário."""
        self.running = False
        self.connected = False
        if self.connections is not None and self.remote_peer_id in self.connections:
            del self.connections[self.remote_peer_id]
        try:
            self.sock.close()
        except:
            pass

    def _check_ack_timeouts(self):
        """
        Thread de faxina: Fica rodando no fundo e verifica se passou de 5 segundos
        sem receber o ACK de uma mensagem enviada.
        """
        while self.running:
            time.sleep(1)
            now = datetime.now(timezone.utc)
            # Transforma em lista para não dar erro de mudar o dicionário enquanto lê
            for msg_id, sent_at in list(self.pending_acks.items()):
                elapsed = (now - sent_at).total_seconds()
                if elapsed > 5:
                    self.logger.warning(
                        f"Timeout: ACK não recebido para msg_id={msg_id} "
                        f"após {elapsed:.1f}s"
                    )
                    self.pending_acks.pop(msg_id, None)
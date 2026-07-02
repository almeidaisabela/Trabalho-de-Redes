import threading
import time
import uuid
import logging
from datetime import datetime, timezone

class KeepAliveManager:
    """
    Gerenciador de 'Batimentos Cardíacos' (Heartbeat).
    Sua única função é garantir que a lista de peers ativos não contenha "fantasmas" 
    (pessoas que já caíram, mas não avisaram).
    """
    def __init__(self, peer_table, send_function, my_peer_id, ping_interval=30):
        """
        Recebe a instância de PeerTable (da Isabela) e uma função genérica 
        para enviar mensagens TCP.
        """
        # Recebe a tabela de contatos (para saber quem pingar)
        self.peer_table = peer_table
        
        # Recebe a função de enviar mensagens de fora (Injeção de Dependência).
        # Assim, essa classe não precisa saber COMO o socket funciona.
        self.send_function = send_function 
        
        self.logger = logging.getLogger("KeepAlive")
        self.running = False
        self.my_peer_id = my_peer_id
        self.ping_interval = ping_interval
        
        # Guarda o horário exato que enviamos o PING para calcular a latência (RTT) depois
        self.pending_pings = {}

    def start(self):
        """Inicia a thread de monitorização em segundo plano."""
        self.running = True
        
        # Cria uma Thread dedicada só para isso. 
        # Se rodasse na principal, o programa iria congelar esperando os 30 segundos!
        thread = threading.Thread(target=self._ping_loop, daemon=True)
        thread.start()
        self.logger.info(f"Serviço Keep-Alive iniciado (PING a cada {self.ping_interval}s).")

    def stop(self):
        """Para o loop de verificação de forma segura."""
        self.running = False

    def _ping_loop(self):
        """Loop infinito que roda a cada 30 segundos."""
        # Enquanto o programa estiver vivo, ele dorme 30s, acorda, manda PING para todos, e dorme de novo.
        while self.running:
            time.sleep(self.ping_interval)
            self._send_pings()

    def _send_pings(self):
        """
        Varre a tabela de peers e dispara o PING para quem estiver listado como ativo.
        """
        # Pega a lista de todo mundo que conhecemos
        peers_ativos = self.peer_table.get_all()
    
        for peer_id, dados in peers_ativos.items():
            # Não faz sentido eu mandar um PING para mim mesmo
            if peer_id == self.my_peer_id:
                continue
                
            # Só manda PING se o status do peer for 'CONHECIDO' ou 'CONECTADO'
            if dados.get("status") in ("KNOWN", "CONNECTED"):
                
                # Monta a mensagem no padrão exigido pelo protocolo
                ping_msg = {
                    "type": "PING",
                    "msg_id": str(uuid.uuid4()), # ID único para rastrear a resposta (PONG)
                    "timestamp": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
                    "ttl": 1
                }
                
                # Registra a hora exata do disparo para calcular o RTT quando o PONG voltar
                self.pending_pings[ping_msg["msg_id"]] = datetime.now(timezone.utc)  # <-- novo
                
                # Tenta enviar a mensagem usando a função que recebemos lá no __init__
                sucesso = self.send_function(peer_id, ping_msg)
                
                # Se a função retornar falso (ex: erro no socket, conexão quebrou)...
                if not sucesso:
                    self.logger.warning(f"Falha ao alcançar {peer_id}. A marcar como STALE.")
                    # ...marca o peer como 'STALE' (Obsoleto/Inativo) para ninguém mais tentar falar com ele.
                    self.peer_table.mark_stale(peer_id)
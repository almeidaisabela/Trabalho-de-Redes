import threading
import time
import uuid
import logging
from datetime import datetime, timezone

class KeepAliveManager:
    def __init__(self, peer_table, send_function, my_peer_id):
        """
        Recebe a instância de PeerTable (da Isabela) e uma função genérica 
        para enviar mensagens TCP.
        """
        self.peer_table = peer_table
        # Função que o roteador vai fornecer
        self.send_function = send_function 
        self.logger = logging.getLogger("KeepAlive")
        self.running = False
        self.my_peer_id = my_peer_id
        self.pending_pings = {}

    def start(self):
        """Inicia a thread de monitorização em segundo plano."""
        self.running = True
        thread = threading.Thread(target=self._ping_loop, daemon=True)
        thread.start()
        self.logger.info("Serviço Keep-Alive iniciado (PING a cada 30s).")

    def stop(self):
        """Para o loop de verificação de forma segura."""
        self.running = False

    def _ping_loop(self):
        """Loop infinito que roda a cada 30 segundos."""
        while self.running:
            time.sleep(30)
            self._send_pings()

    def _send_pings(self):
        peers_ativos = self.peer_table.get_all()
    
        for peer_id, dados in peers_ativos.items():
            if peer_id == self.my_peer_id:
                continue
            if dados.get("status") in ("KNOWN", "CONNECTED"):
                ping_msg = {
                    "type": "PING",
                    "msg_id": str(uuid.uuid4()),
                    "timestamp": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
                    "ttl": 1
                }
                
                self.pending_pings[ping_msg["msg_id"]] = datetime.now(timezone.utc)  # <-- novo
                
                sucesso = self.send_function(peer_id, ping_msg)
                if not sucesso:
                    self.logger.warning(f"Falha ao alcançar {peer_id}. A marcar como STALE.")
                    self.peer_table.mark_stale(peer_id)
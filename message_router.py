import uuid
from datetime import datetime, timezone

class MessageRouter:
    """
    O 'MessageRouter' atua como o carteiro da aplicação. 
    Ele formata as mensagens no padrão do protocolo e decide para quais conexões enviá-las.
    """
    def __init__(self, peer_table, connections, my_peer_id):
        # Tabela com informações de todos os peers conhecidos
        self.peer_table = peer_table
        # Dicionário com as conexões TCP ativas (sockets abertos)
        self.connections = connections
        # A nossa identidade (ex: kallebe@RedesUnB) para colocar como remetente
        self.my_peer_id = my_peer_id

    def send_direct(self, dst_peer_id, texto):
        """
        Envia uma mensagem direta para um único peer (Unicast).
        """
        msg = {
            "type": "SEND", # Indica que é uma mensagem direta
            "msg_id": str(uuid.uuid4()), # Gera um ID único e aleatório para a mensagem
            "src": self.my_peer_id, # Remetente (eu)
            "dst": dst_peer_id, # Destinatário (quem vai receber)
            "payload": texto, # O texto digitado no chat
            "require_ack": True, # Exige uma confirmação de recebimento (Recibo de leitura)
            "ttl": 1 # Time-to-Live: impede que a mensagem fique circulando na rede para sempre
        }
        
        # Busca se já temos uma conexão aberta com esse destinatário
        conn = self.connections.get(dst_peer_id)
        if conn:
            # Como exige confirmação (ACK), anotamos a hora exata que enviamos
            # para depois checar se demorou muito ou se deu timeout.
            conn.pending_acks[msg["msg_id"]] = datetime.now(timezone.utc)
            
            # Envia a mensagem de fato
            conn.send_message(msg)
            return True
        
        # Retorna falso se tentou enviar para alguém que não está conectado
        return False
    
    def publish_global(self, texto):
        """
        Envia a mensagem para TODOS os peers conectados (Broadcast).
        """
        msg = {
            "type": "PUB", # PUB vem de Publish (Publicação para muitos)
            "msg_id": str(uuid.uuid4()),
            "src": self.my_peer_id,
            "dst": "*", # O asterisco é o curinga universal para "todos"
            "payload": texto,
            "require_ack": False, # Broadcast não exige recibo (geraria muito tráfego na rede)
            "ttl": 1
        }
        
        # Pega a lista de todas as conexões ativas e envia a mesma mensagem para cada uma
        for conn in self.connections.values():
            conn.send_message(msg)

    def publish_namespace(self, namespace, texto):
        """
        Envia a mensagem apenas para os peers de um grupo/sala específico (Multicast).
        """
        msg = {
            "type": "PUB",
            "msg_id": str(uuid.uuid4()),
            "src": self.my_peer_id,
            "dst": f"#{namespace}", # A hashtag indica que o destino é um grupo (ex: #RedesUnB)
            "payload": texto,
            "require_ack": False, 
            "ttl": 1
        }

        # Passa por todas as conexões abertas...
        for peer_id, conn in self.connections.items():
            # ...mas SÓ envia se o nome do peer terminar com "@NomeDoGrupo"
            if peer_id.endswith(f"@{namespace}"):
                conn.send_message(msg)
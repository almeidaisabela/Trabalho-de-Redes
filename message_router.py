import uuid
from datetime import datetime, timezone

class MessageRouter:
    def __init__(self, peer_table, connections, my_peer_id):
        self.peer_table = peer_table
        self.connections = connections
        self.my_peer_id = my_peer_id

    def send_direct(self, dst_peer_id, texto):
        msg = {
            "type": "SEND",
            "msg_id": str(uuid.uuid4()),
            "src": self.my_peer_id,
            "dst": dst_peer_id,
            "payload": texto,
            "require_ack": True,
            "ttl": 1
        }
        conn = self.connections.get(dst_peer_id)
        if conn:
            conn.pending_acks[msg["msg_id"]] = datetime.now(timezone.utc)
            conn.send_message(msg)
            return True
        return False
    
    def publish_global(self, texto):
        msg = {
            "type": "PUB",
            "msg_id": str(uuid.uuid4()),
            "src": self.my_peer_id,
            "dst": "*",
            "payload": texto,
            "require_ack": False,
            "ttl": 1
        }
        for conn in self.connections.values():
            conn.send_message(msg)

    def publish_namespace(self, namespace, texto):
        msg = {
            "type": "PUB",
            "msg_id": str(uuid.uuid4()),
            "src": self.my_peer_id,
            "dst": f"#{namespace}",
            "payload": texto,
            "require_ack": False,
            "ttl": 1
        }

        for peer_id, conn in self.connections.items():
            if peer_id.endswith(f"@{namespace}"):
                conn.send_message(msg)
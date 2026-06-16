class PeerTable:
    def __init__(self):
        self.peers = {}

    def update(self, peers):
        """Atualiza a tabela com os peers retornados pelo DISCOVER."""
        for peer in peers:
            peer_id = f"{peer['name']}@{peer['namespace']}"
            self.peers[peer_id] = {
                "ip": peer["ip"],
                "port": peer["port"],
                "status": "KNOWN"
            }

    def get_all(self):
        return self.peers

    def get(self, peer_id):
        return self.peers.get(peer_id)
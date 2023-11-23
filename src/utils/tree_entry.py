class TreeEntry:
    def __init__(self, timestamp, latency, contents, child=None, parent=None):
        self.timestamp = timestamp # Último contacto do cliente
        self.latency = latency
        self.contents = contents
        self.parent = parent
        self.child = child
    
    def __str__(self):
        return f"Next Step: {self.next_step} | Timestamp: {self.timestamp} | Latency Metric: {self.latency} | Contents: {self.contents}"

    def __repr__(self):
        return f"Next Step: {self.next_step} | Timestamp: {self.timestamp} | Latency Metric: {self.latency} | Contents: {self.contents}"
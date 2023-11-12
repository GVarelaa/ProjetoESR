class TreeEntry:
    def __init__(self, timestamp, next_step, latency, contents):
        self.timestamp = timestamp # Último contacto do cliente
        self.next_step = next_step
        self.latency = latency
        self.contents = contents
    
    def __str__(self):
        return f"Next Step: {self.next_step} | Timestamp: {self.timestamp} | Latency Metric: {self.latency} | Contents: {self.contents}"

    def __repr__(self):
        return f"Next Step: {self.next_step} | Timestamp: {self.timestamp} | Latency Metric: {self.latency} | Contents: {self.contents}"
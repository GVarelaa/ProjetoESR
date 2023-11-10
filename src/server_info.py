class ServerInfo:
    def __init__(self, server, metric, contents, status):
        self.server = server
        self.metric = metric
        self.contents = streams
        self.status = status

    def __str__(self):
        return f"Server IP: {self.server} | Metric: {self.metric} | Contents: {self.contents} | Status: {self.status}"

    def __repr__(self):
        return f"Server IP: {self.server} | Metric: {self.metric} | Contents: {self.contents} | Status: {self.status}"

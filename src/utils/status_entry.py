class StatusEntry:
    def __init__(self, server, metric, contents, active):
        self.server = server
        self.metric = metric
        self.contents = contents
        self.active = active

    def __str__(self):
        return f"Server IP: {self.server} | Metric: {self.metric} | Contents: {self.contents} | Active: {self.active}"

    def __repr__(self):
        return f"Server IP: {self.server} | Metric: {self.metric} | Contents: {self.contents} | Active: {self.active}"

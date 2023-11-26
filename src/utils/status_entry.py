class StatusEntry:
    def __init__(self, metric, contents, active):
        self.metric = metric
        self.contents = contents
        self.active = active

    def __str__(self):
        return f"Metric: {self.metric} | Contents: {self.contents} | Active: {self.active}"

    def __repr__(self):
        return f"Metric: {self.metric} | Contents: {self.contents} | Active: {self.active}"

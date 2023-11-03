import threading
from datetime import datetime
from entry import Entry

class Database:
    def __init__(self, logger):
        self.neighbours = list()
        self.lock = threading.Lock()
        self.tree = dict()
        self.logger = logger

    def insert(self, client, neighbour, timestamp):
        diff = float(datetime.now().timestamp()) - timestamp

        self.lock.acquire()
        if client in self.tree:
            entry = self.tree[client]
            
            if diff < entry.latency:
                self.logger.debug(f"Control Service: Changing from neighbour {entry.next_step} to neighbour {neighbour}")
                self.tree[client] = Entry(timestamp, neighbour, diff)
        else:
            self.logger.debug(f"Control Service: Adding neighbour {neighbour}")
            self.tree[client] = Entry(timestamp, neighbour, diff)

        self.lock.release()
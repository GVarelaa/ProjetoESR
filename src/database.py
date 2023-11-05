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
        actual_timestamp = float(datetime.now().timestamp())
        diff = actual_timestamp - timestamp

        self.lock.acquire()
        if client in self.tree:
            entry = self.tree[client]
            
            if diff < entry.latency:
                self.logger.debug(f"Control Service: Changing from neighbour {entry.next_step} to neighbour {neighbour}")
                self.tree[client] = Entry(timestamp, neighbour, diff)
        else:
            self.logger.debug(f"Control Service: Adding neighbour {neighbour}")
            self.tree[client] = Entry(timestamp, neighbour, diff)

        self.tree[client].timestamp = actual_timestamp

        self.lock.release()


    def prune(self, timestamp, wait_time):
        self.lock.acquire()

        to_remove = list()

        for key, value in self.tree.items():
            if timestamp - value.timestamp >= wait_time:
                to_remove.append(key)

                self.logger.debug(f"Pruning Service: Client {key} was removed from tree")
        
        for key in to_remove:
            self.tree.pop(key)

        self.lock.release()

    
    def remove(self, addr):
        self.lock.acquire()

        if addr in self.tree:
            self.tree.pop(addr)

        self.logger.debug(f"Control Service: Client {addr} was removed from tree")

        self.lock.release()
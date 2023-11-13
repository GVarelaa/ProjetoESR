import argparse
import json
import threading
import socket
import logging
import time
from datetime import datetime
from packets.control_packet import ControlPacket
from utils.tree_entry import TreeEntry

class Bootstrapper():
    def __init__(self, my_ip, file):
        with open(file) as f:
            self.nodes = json.load(f)

        self.my_ip = my_ip
        self.neighbours = list()

        self.tree_lock = threading.Lock()
        self.tree = dict()

        self.control_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.data_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

        self.control_socket.bind(("", 7777))
        self.data_socket.bind(("", 7778))

        logging.basicConfig(format='%(asctime)s [%(levelname)s] - %(message)s', datefmt='%Y-%m-%d %H:%M:%S', level=logging.DEBUG)
        self.logger = logging.getLogger()
        self.logger.info("Control service listening on port 7777 and streaming service on port 7778")

        self.setup() # Request neighbours

        # Services
        threading.Thread(target=self.pruning_service, args=()).start()
        threading.Thread(target=self.control_service, args=()).start()


    def setup(self):
        for key, value in self.nodes["nodes"].items():
            if self.my_ip in value["interfaces"]: # é esse o servidor
                self.neighbours = value["neighbours"]

    
    def insert_tree(self, message, address):
        # Insert tree
        timestamp = float(datetime.now().timestamp())
        latency = timestamp - message.latency
        client = message.hops[0]
        neighbour = address[0]

        self.tree_lock.acquire()
        
        if client in self.tree:
            entry = self.tree[client]
            
            if latency < entry.latency:
                self.logger.debug(f"Control Service: Changing from neighbour {entry.next_step} to neighbour {neighbour}")
                self.tree[client] = TreeEntry(timestamp, neighbour, latency, message.contents)
            
            else:
                self.tree[client].timestamp = timestamp

        else:
            self.logger.debug(f"Control Service: Adding neighbour {neighbour} to tree")
            self.tree[client] = TreeEntry(timestamp, neighbour, latency, message.contents)

        self.tree_lock.release()


    def control_worker(self, address, message):
        if message.type == ControlPacket.PLAY:
            if message.response == 0:
                message.hops.append(address[0])
                self.insert_tree(message, address)

                for neighbour in self.neighbours: # Fazer isto sem ser sequencial (cuidado ter um socket para cada neighbour)
                    if neighbour != address[0]: # Se o vizinho não for o que enviou a mensagem
                        self.control_socket.sendto(message.serialize(), (neighbour, 7777))
                        self.logger.info(f"Control Service: Subscription message sent to neighbour {neighbour}")
                        self.logger.debug(f"Message sent: {message}")
            
            elif message.response == 1:
                ips = set()
                data = self.data_socket.recvfrom(20480)
                
                self.tree_lock.acquire()
                for tree_entry in self.tree.values():
                    if message.contents in tree_entry.contents:
                        ips.add(tree_entry.next_step)
                self.tree_lock.release()

                for ip in ips:
                    self.data_socket.sendto(data, ip)
        
        elif message.type == ControlPacket.LEAVE:
            self.tree_lock.acquire()

            if address in self.tree:
                self.tree.pop(address)

            self.logger.debug(f"Control Service: Client {address} was removed from tree")

            self.tree_lock.release()
        
        elif message.type == ControlPacket.NEIGHBOURS and message.response == 0:
            neighbours = list()
            servers = list()

            for key, value in self.nodes["nodes"].items():
                if address[0] in value["interfaces"]: # é esse o servidor
                    neighbours = value["neighbours"]

            if address[0] in self.nodes["rp"]:
                servers = self.nodes["servers"]

            msg = ControlPacket(ControlPacket.NEIGHBOURS, response=1, servers=servers, neighbours=neighbours)
            self.control_socket.sendto(msg.serialize(), address)
            
            self.logger.info(f"Control Service: Message sent to {address[0]}")
            self.logger.debug(f"Message: {msg}")


    def control_service(self):
        try:
            self.control_socket.settimeout(None)

            while True:
                data, address = self.control_socket.recvfrom(1024)
                message = ControlPacket.deserialize(data)

                self.logger.info(f"Control Service: Subscription message received from neighbour {address[0]}")
                self.logger.debug(f"Message received: {message}")

                threading.Thread(target=self.control_worker, args=(address, message,)).start()

        finally:
            self.control_socket.close()


    def pruning_service(self):
        wait = 20 # 20 segundos
        while True:
            timestamp = float(datetime.now().timestamp())
            
            self.tree_lock.acquire()

            to_remove = list()

            for key, value in self.tree.items():
                if timestamp - value.timestamp >= wait:
                    to_remove.append(key)

                    self.logger.debug(f"Pruning Service: Client {key} was removed from tree")
            
            for key in to_remove:
                self.tree.pop(key)

            self.tree_lock.release()

            time.sleep(wait)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("-ip", help="bootstrapper ip")
    parser.add_argument("-file", help="bootstrapper file")
    args = parser.parse_args()

    if args.file and args.ip:
        Bootstrapper(args.ip, args.file)
    else:
        print("Error: Wrong arguments")
        exit()


if __name__ == "__main__":
    main()

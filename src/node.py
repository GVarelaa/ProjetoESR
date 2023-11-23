import argparse
import json
import time
import socket
import threading
import logging
from datetime import datetime
from packets.control_packet import ControlPacket
from utils.tree_entry import TreeEntry
from abc import abstractmethod

class Node:
    def __init__(self, bootstrapper, is_bootstrapper=False, file=None):
        self.is_bootstrapper = is_bootstrapper
        if is_bootstrapper:
            with open(file) as f:
                self.nodes = json.load(f)

        self.neighbours = list()

        self.tree_lock = threading.Lock()
        self.tree = dict()

        self.control_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.data_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

        self.control_socket.bind(("", 7777))
        self.data_socket.bind(("", 7778))
        
        address = bootstrapper.split(":")
        self.bootstrapper = (address[0], int(address[1]))

        logging.basicConfig(format='%(asctime)s [%(levelname)s] - %(message)s', datefmt='%Y-%m-%d %H:%M:%S', level=logging.INFO)
        self.logger = logging.getLogger()
        self.logger.info("Control service listening on port 7777 and streaming service on port 7778")

        self.setup() # Request neighbours

        # Services
        threading.Thread(target=self.pruning_service, args=()).start()
        threading.Thread(target=self.control_service, args=()).start()
        

    @abstractmethod
    def setup(self):
        if self.is_bootstrapper:
            for key, value in self.nodes["nodes"].items():
                if self.bootstrapper in value["interfaces"]: # é esse o servidor
                    self.neighbours = value["neighbours"]

        else:
            self.control_socket.sendto(ControlPacket(ControlPacket.NEIGHBOURS).serialize(), self.bootstrapper)
            self.logger.info("Setup: Asked for neighbours")

            try:
                self.control_socket.settimeout(5) # 5 segundos? perguntar ao lost

                data, _ = self.control_socket.recvfrom(1024)
                msg = ControlPacket.deserialize(data)

                if msg.type == ControlPacket.NEIGHBOURS and msg.response == 1:
                    self.neighbours = msg.neighbours
                    self.logger.info("Setup: Neighbours received")
                    self.logger.debug(f"Neighbours: {self.neighbours}")
                
                else:
                    self.logger.info("Setup: Unexpected response received")
                    exit() # É este o comportamento que queremos ?
                
            except socket.timeout:
                self.logger.info("Setup: Could not receive response to neighbours request")
                exit()
    

    def insert_tree(self, message, address):
        added = False
        timestamp = float(datetime.now().timestamp())
        latency = timestamp - message.latency
        client = message.source_ip
        neighbour = address[0]

        self.tree_lock.acquire()
        
        if client in self.tree:
            entry = self.tree[client]
            
            if latency < entry.latency:
                self.logger.debug(f"Control Service: Changing from neighbour {entry.child} to neighbour {neighbour}")
                self.tree[client] = TreeEntry(timestamp, latency, message.contents, child=neighbour)
                added = True
            
            else:
                self.tree[client].timestamp = timestamp

        else:
            self.logger.debug(f"Control Service: Adding neighbour {neighbour} to tree")
            self.tree[client] = TreeEntry(timestamp, latency, message.contents, child=neighbour)
            added = True

        self.tree_lock.release()

        return added


    @abstractmethod
    def control_worker(self, address, msg):
        if self.is_bootstrapper and msg.type == ControlPacket.NEIGHBOURS and msg.response == 0:
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

        elif msg.type == ControlPacket.PLAY:
            if msg.response == 0:
                self.logger.info(f"Control Service: Subscription message received from neighbour {address[0]}")
                self.logger.debug(f"Message received: {msg}")

                msg.last_hop = address[0]

                if msg.source_ip == "0.0.0.0":
                    msg.source_ip = address[0]

                self.insert_tree(msg, address)

                for neighbour in self.neighbours: # Fazer isto sem ser sequencial (cuidado ter um socket para cada neighbour)
                    if neighbour != address[0]: # Se o vizinho não for o que enviou a mensagem
                        self.control_socket.sendto(msg.serialize(), (neighbour, 7777))
                        self.logger.info(f"Control Service: Subscription message sent to neighbour {neighbour}")
                        self.logger.debug(f"Message sent: {msg}")

            elif msg.response == 1:
                try:
                    self.logger.info(f"Control Service: Subscription confirmation received from neighbour {address[0]}")
                    self.logger.debug(f"Message received: {msg}")


                    self.tree_lock.acquire()
        
                    child = self.tree[msg.source_ip].child
                    self.tree[msg.source_ip].parent = address[0]

                    self.tree_lock.release()

                    self.control_socket.sendto(msg.serialize(), (child, 7777))
                    self.logger.info(f"Control Service: Subscription confirmation sent to {child}")

                    # MUDAR ISTO!!!!!!!!!!!!!!!!!!!!!

                    while True:
                        data, address = self.data_socket.recvfrom(20480)
                    
                        for ip in ips:
                            self.data_socket.sendto(data, (ip, 7778))
                            self.logger.debug(f"Streaming Service: RTP Packet sent to {ip}")
            
                finally:
                    self.data_socket.close()
        
        elif msg.type == ControlPacket.LEAVE:
            self.logger.info(f"Control Service: Leave message received from neighbour {address[0]}")
            self.logger.debug(f"Message received: {message}")

            self.tree_lock.acquire()

            if address in self.tree:
                self.tree.pop(address)

            self.logger.debug(f"Control Service: Client {address} was removed from tree")

            self.tree_lock.release()


    def control_service(self):
        try:
            self.control_socket.settimeout(None)

            while True:
                data, address = self.control_socket.recvfrom(1024)
                message = ControlPacket.deserialize(data)

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
    parser.add_argument("-bootstrapper", help="bootstrapper ip")
    parser.add_argument("-file", help="bootstrapper file")
    args = parser.parse_args()

    if args.file:
        Node(args.bootstrapper, is_bootstrapper=True, file=args.file)
        
    elif args.bootstrapper:
        Node(args.bootstrapper)
    else:
        print("Error: Wrong arguments")
        exit()


if __name__ == "__main__":
    main()
import argparse
import json
import time
import socket
import threading
import logging
import errno
from datetime import datetime
from packets.control_packet import ControlPacket
from abc import abstractmethod
from math import inf

class Node:
    def __init__(self, bootstrapper, is_bootstrapper=False, file=None, debug_mode=False):
        self.is_bootstrapper = is_bootstrapper
        if is_bootstrapper:
            with open(file) as f:
                self.nodes = json.load(f)

        self.neighbours = list()

        self.lock = threading.Lock()
        self.tree = dict() 
        self.contacts = dict() # Guarda o timestamp do último contacto com cada cliente para o pruning
        
        self.ports = dict() # estrutura para saber as portas para cada conteudo

        self.control_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.control_socket.bind(("", 7777))
        
        address = bootstrapper.split(":")
        self.bootstrapper = (address[0], int(address[1]))

        if debug_mode:
            logging.basicConfig(format='%(asctime)s [%(levelname)s] - %(message)s', datefmt='%Y-%m-%d %H:%M:%S', level=logging.DEBUG)
        else:
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
    

    @abstractmethod
    def insert_tree(self, msg, neighbour):
        client = msg.hops[0]
        content = msg.contents[0]
        seqnum = msg.seqnum

        self.lock.acquire()

        if content not in self.tree:
            self.tree[content] = dict()

        self.tree[content][client] = NodeInfo(neighbour, seqnum)

        self.logger.info(f"Control Service: Added client {client} to tree")

        self.lock.release()


    @abstractmethod
    def control_worker(self, address, msg):
        # Se tem ciclos
        print("-------------------")
        print("recebi")
        print(address[0])
        print(self.tree)
        
        if msg.response == 0:
            msg.hops.append(address[0])
        
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
            if msg.nack == 1:
                content = msg.contents[0]
                
                self.lock.acquire()
                
                self.tree[content]["clients"].remove(address[0])

                self.logger.info(f"Control Service: Client {address[0]} removed from tree due to NACK")

                if len(self.tree[content]["clients"]) == 0:
                    self.control_socket.sendto(msg.serialize(), (self.tree[content]["parent"], 7777))

                    self.logger.info(f"Control Service: NACK sent to {self.tree[content]['parent']}")

                    self.tree.pop(content)

                self.lock.release()

            elif msg.response == 0:
                self.logger.info(f"Control Service: Subscription message received from neighbour {address[0]}")
                self.logger.debug(f"Message received: {msg}")

                self.lock.acquire()
                
                content = msg.contents[0]
                if content not in self.tree:
                    self.tree[content] = dict()
                    self.tree[content]["frame"] = 0
                    self.tree[content]["clients"] = set()
                    self.tree[content]["clients"].add(address[0])

                    self.contacts[address[0]] = float(datetime.now().timestamp())

                    self.logger.info(f"Control Service: Added client {address[0]} to tree")

                    for neighbour in self.neighbours: # Fazer isto sem ser sequencial (cuidado ter um socket para cada neighbour)
                        if neighbour != address[0]: # Se o vizinho não for o que enviou a mensagem
                            self.control_socket.sendto(msg.serialize(), (neighbour, 7777))

                            self.logger.info(f"Control Service: Subscription message sent to neighbour {neighbour}")
                            self.logger.debug(f"Message sent: {msg}")

                else:
                    self.tree[content]["clients"].add(address[0])

                    self.contacts[address[0]] = float(datetime.now().timestamp())
                    
                    self.logger.info(f"Control Service: Added client {address[0]} to tree")

                    response = ControlPacket(ControlPacket.PLAY, response=1, contents=msg.contents, hops=msg.hops, port=self.ports[content])
                    self.control_socket.sendto(response.serialize(), (address[0], 7777))

                self.lock.release()


            elif msg.response == 1:
                self.logger.info(f"Control Service: Subscription confirmation received from neighbour {address[0]}")
                self.logger.debug(f"Message received: {msg}")
                
                content = msg.contents[0]

                self.lock.acquire()
                
                if "parent" not in self.tree[content]:
                    self.tree[content]["parent"] = address[0]

                    for client in self.tree[content]["clients"]:
                        self.control_socket.sendto(msg.serialize(), (client, 7777))
                        self.logger.info(f"Control Service: Subscription confirmation sent to neighbour {client}")

                    self.lock.release()

                    self.ports[msg.contents[0]] = msg.port
                    threading.Thread(target=self.listen_rtp, args=(msg.port, msg.contents[0])).start()

                else:
                    nack = ControlPacket(ControlPacket.PLAY, nack=1, contents=msg.contents)
                    self.control_socket.sendto(nack.serialize(), (address[0], 7777))
                    
                    self.logger.info(f"Control Service: NACK sent to {address[0]}")
                    
                    self.lock.release()

        elif msg.type == ControlPacket.LEAVE:
            self.logger.info(f"Control Service: Leave message received from neighbour {address[0]}")
            self.logger.debug(f"Message received: {msg}")

            self.lock.acquire()

            content = msg.contents[0]
            if content in self.tree:
                self.tree[content]["clients"].remove(address[0])

                self.logger.info(f"Control Service: Client {address[0]} removed from tree due to LEAVE")

                if len(self.tree[content]["clients"]) == 0:
                    self.control_socket.sendto(msg.serialize(), (self.tree[content]["parent"], 7777))

                    self.logger.debug(f"Control Service: Leave message sent to {self.tree[content]['parent']}")

                    self.tree.pop(content)

            self.lock.release()
            
        elif msg.type == ControlPacket.POLLING:
            self.logger.info(f"Control Service: Polling received from neighbour {address[0]}")
            self.logger.debug(f"Message received: {msg}")

            if msg.nack == 1:
                content = msg.contents[0]
                
                self.lock.acquire()
                
                #if self.tree[content]["timestamp"] == msg.timestamp:
                self.tree[content]["clients"].remove(address[0])

                self.logger.info(f"Control Service: Client {address[0]} removed from tree due to NACK")

                if len(self.tree[content]["clients"]) == 0:
                    self.control_socket.sendto(msg.serialize(), (self.tree[content]["parent"], 7777))

                    self.logger.info(f"Control Service: NACK sent to {self.tree[content]['parent']}")

                    self.tree.pop(content)

                self.lock.release()

            elif msg.response == 0:
                self.lock.acquire()

                content = msg.contents[0]
                if content not in self.tree:
                    self.tree[content] = dict()
                    self.tree[content]["frame"] = 0
                    self.tree[content]["clients"] = set()
                    self.tree[content]["clients"].add(address[0])
                    
                    self.contacts[address[0]] = float(datetime.now().timestamp())

                    self.logger.info(f"Control Service: Added client {address[0]} to tree")

                    for neighbour in self.neighbours: # Fazer isto sem ser sequencial (cuidado ter um socket para cada neighbour)
                        if neighbour != address[0]: # Se o vizinho não for o que enviou a mensagem
                            self.control_socket.sendto(msg.serialize(), (neighbour, 7777))

                            self.logger.info(f"Control Service: Polling message sent to neighbour {neighbour}")
                            self.logger.debug(f"Message sent: {msg}")

                elif content in self.tree and len(self.tree[content]["clients"]) == 1 and address[0] in self.tree[content]["clients"]:
                    self.contacts[address[0]] = float(datetime.now().timestamp())

                    self.logger.info(f"Control Service: Added client {address[0]} to tree")

                    for neighbour in self.neighbours: # Fazer isto sem ser sequencial (cuidado ter um socket para cada neighbour)
                        if neighbour != address[0]: # Se o vizinho não for o que enviou a mensagem
                            self.control_socket.sendto(msg.serialize(), (neighbour, 7777))

                            self.logger.info(f"Control Service: Polling message sent to neighbour {neighbour}")
                            self.logger.debug(f"Message sent: {msg}")

                else:
                    self.tree[content]["clients"].add(address[0])

                    self.contacts[address[0]] = float(datetime.now().timestamp())
                    
                    self.logger.info(f"Control Service: Added client {address[0]} to tree")

                    msg.response = 1
                    msg.port = self.ports[content]
                    self.control_socket.sendto(msg.serialize(), (address[0], 7777))

                self.lock.release()

            elif msg.response == 1:
                content = msg.contents[0]

                self.lock.acquire()
                
                if "timestamp" not in self.tree[content] or self.tree[content]["timestamp"] < msg.timestamp:
                    self.tree[content]["parent"] = address[0]
                    self.tree[content]["timestamp"] = msg.timestamp

                    for client in self.tree[content]["clients"]:
                        self.control_socket.sendto(msg.serialize(), (client, 7777))
                        self.logger.info(f"Control Service: Subscription confirmation sent to neighbour {client}")

                    self.lock.release()

                else:
                    nack = ControlPacket(ControlPacket.POLLING, nack=1, timestamp=msg.timestamp, contents=msg.contents)
                    self.control_socket.sendto(nack.serialize(), (address[0], 7777))
                    
                    self.logger.info(f"Control Service: NACK sent to {address[0]}")
                    
                    self.lock.release()

        
        print("acabei")
        print(self.tree)
        print("-----------")


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
        wait = 3

        while True:
            time.sleep(wait)

            curr_time = float(datetime.now().timestamp())
            inactive = list()

            self.lock.acquire()
           
            for client, last_contact in self.contacts.items():
                if curr_time - last_contact > 5:
                    inactive.append(client)

            to_remove = list()
            for client in inactive:
                for content, value in self.tree.items():
                    if client in value["clients"]:
                        self.tree[content]["clients"].remove(client)

                        self.logger.info(f"Pruning Service: Client {client} was removed from tree")

                        if len(self.tree[content]["clients"]) == 0:
                            to_remove.append(content)
            
            for content in to_remove:
                self.tree.pop(content)
            
            self.lock.release()


    def listen_rtp(self, port, content):
        data_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        
        try:
            data_socket.bind(("", port))

            self.logger.info(f"Streaming Service: Receiving RTP Packets")

            while True:
                data, _ = data_socket.recvfrom(20480)

                self.lock.acquire()

                steps = set()
                if content in self.tree:
                    self.tree[content]["frame"] += 1

                    steps = self.tree[content]["clients"]
                    
                self.lock.release()

                for step in steps:
                    data_socket.sendto(data, (step, port))
                    self.logger.debug(f"Streaming Service: RTP Packet sent to {step}")
            
        except socket.error as e:
            if e.errno == errno.EADDRINUSE:      
                #data_socket.close()
                print("mudar") 

        finally:
            data_socket.close()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("-bootstrapper", help="bootstrapper ip")
    parser.add_argument("-file", help="bootstrapper file")
    parser.add_argument("-d", action="store_true", help="activate debug mode")
    args = parser.parse_args()

    debug_mode = False

    if args.d:
        debug_mode = True

    if args.file:
        Node(args.bootstrapper, is_bootstrapper=True, file=args.file, debug_mode=debug_mode)
        
    elif args.bootstrapper:
        Node(args.bootstrapper, debug_mode=debug_mode)
    else:
        print("Error: Wrong arguments")
        exit()


if __name__ == "__main__":
    main()
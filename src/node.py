import json
import time
import socket
import threading
import logging
from message import Message
from datetime import datetime
from database import Database

class Node:
    def __init__(self, ntype, bootstrapper_addr=None, file=None):
        self.type = ntype

        self.control_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.subscription_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.data_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

        self.control_socket.bind(("", 7777))
        self.subscription_socket.bind(("", 7779))
        self.data_socket.bind(("", 7778))

        if self.type == 0:
            with open(file) as f:
                self.nodes = json.load(f)
        else:
            addr_list = bootstrapper_addr.split(":")
            self.bootstrapper_addr = (addr_list[0], int(addr_list[1]))
        
        logging.basicConfig(format='%(asctime)s [%(levelname)s] - %(message)s', datefmt='%Y-%m-%d %H:%M:%S', level=logging.DEBUG)
        self.logger = logging.getLogger()
        self.logger.info("Control service listening on port 7777 and streaming service on port 7778")

        self.database = Database(self.logger)


    def request_neighbours(self):
        self.control_socket.sendto(Message(0).serialize(), self.bootstrapper_addr)
        self.logger.info("Control Service: Asked for neighbours")

        msg, _ = self.control_socket.recvfrom(1024)  
        decoded_msg = Message.deserialize(msg)

        if decoded_msg.type == 1:
            self.database.neighbours = decoded_msg.neighbours
            
            self.logger.info("Control Service: Neighbours received")
            self.logger.debug(f"Neighbours: {self.database.neighbours}")


    def neighbours_worker(self, addr):
        for key, value in self.nodes.items():
            if addr[0] in value["interfaces"]: # é esse o servidor
                msg = Message(1, neighbours=value["neighbours"])
                self.control_socket.sendto(msg.serialize(), addr)

                self.logger.info(f"Control Service: Neighbours sent to {addr[0]}")
                self.logger.debug(f"Neighbours: {msg}")
            

    def subscription_worker(self, addr, msg):
        if msg.jumps is None:
            msg.jumps = list()
        msg.jumps.append(addr[0])

        self.database.insert(msg.jumps[0], addr[0], msg.timestamp)

        if self.type != 2:
            for neighbour in self.database.neighbours:
                if neighbour != addr[0]:
                    self.control_socket.sendto(msg.serialize(), (neighbour, 7777))

                    self.logger.info(f"Control Service: Subscription message sent to neighbour {neighbour}")
                    self.logger.debug(f"Message sent: {msg}")
    

    def control_service(self):
        try:
            while True:
                msg, addr = self.control_socket.recvfrom(1024)
                decoded_msg = Message.deserialize(msg)

                self.logger.info(f"Control Service: Subscription message received from neighbour {addr[0]}")
                self.logger.debug(f"Message received: {decoded_msg}")

                if self.type == 0 and decoded_msg.type == 0:
                    threading.Thread(target=self.neighbours_worker, args=(addr,)).start()
                
                elif decoded_msg.type == 2:
                    threading.Thread(target=self.subscription_worker, args=(addr,decoded_msg,)).start()
            
        finally:
            self.control_socket.close()

    
    def subscription_service(self):
        wait = 5 # 5 segundos
        while True:
            msg = Message(2, timestamp=float(datetime.now().timestamp()))
            self.subscription_socket.sendto(msg.serialize(), (self.database.neighbours[0], 7777))

            self.logger.info(f"Subscription Service: Subscription message sent to neighbour {self.database.neighbours[0]}")
            self.logger.debug(f"Message sent: {msg}") 

            time.sleep(wait)


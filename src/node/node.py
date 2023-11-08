import json
import time
import socket
import threading
import logging
import copy
from message import Message
from datetime import datetime
from database import Database
from exceptions import *
from abc import abstractmethod

class Node:
    def __init__(self, bootstrapper=None):
        self.control_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.data_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

        self.control_socket.bind(("", 7777))
        self.data_socket.bind(("", 7778))
        
        if bootstrapper != None:
            address = bootstrapper.split(":")
            self.bootstrapper = (address[0], int(address[1]))

        logging.basicConfig(format='%(asctime)s [%(levelname)s] - %(message)s', datefmt='%Y-%m-%d %H:%M:%S', level=logging.DEBUG)
        self.logger = logging.getLogger()
        self.logger.info("Control service listening on port 7777 and streaming service on port 7778")

        self.database = Database(self.logger)
        

    @abstractmethod
    def request_neighbours(self):
        self.control_socket.sendto(Message(0).serialize(), self.bootstrapper)
        self.logger.info("Control Service: Asked for neighbours")

        try:
            self.control_socket.settimeout(5) # 5 segundos? perguntar ao lost

            response, addr = self.control_socket.recvfrom(1024)
            response = Message.deserialize(response)

            if response.type == 1:
                self.database.neighbours = response.neighbours
                self.logger.info("Control Service: Neighbours received")
                self.logger.debug(f"Neighbours: {self.database.neighbours}")
            
            else:
                self.logger.info("Control Service: Unexpected response received")
                exit() # É este o comportamento que queremos ?
            
        except socket.timeout:
            self.logger.info("Control Service: Could not receive response to neighbours request")
            exit()
            

    @abstractmethod
    def subscription_worker(self, addr, msg):
        msg.hops.append(addr[0])

        self.database.insert_tree(msg.source_ip, addr[0], msg.timestamp)

        for neighbour in self.database.neighbours: # Fazer isto sem ser sequencial (cuidado ter um socket para cada neighbour)
            if neighbour != addr[0]: # Se o vizinho não for o que enviou a mensagem
                self.control_socket.sendto(msg.serialize(), (neighbour, 7777))
                self.logger.info(f"Control Service: Subscription message sent to neighbour {neighbour}")
                self.logger.debug(f"Message sent: {msg}")


    def leave_worker(self, msg):
        self.database.remove_tree(msg.hops[0])


    @abstractmethod
    def control_service(self):
        try:
            self.control_socket.settimeout(None)

            while True:
                msg, addr = self.control_socket.recvfrom(1024)
                msg = Message.deserialize(msg)

                self.logger.info(f"Control Service: Subscription message received from neighbour {addr[0]}")
                self.logger.debug(f"Message received: {msg}")
                
                if msg.type == 2:
                    if msg.flag == 0:
                        threading.Thread(target=self.subscription_worker, args=(addr, msg,)).start()
                    
                    elif msg.flag == 2:
                        threading.Thread(target=self.sendback_worker, args=(addr, msg,)).start()
                
                elif msg.type == 3:
                    threading.Thread(target=self.leave_worker, args=(msg,)).start()

        finally:
            self.control_socket.close()

    
    def pruning_service(self):
        wait = 20 # 20 segundos
        while True:
            timestamp = float(datetime.now().timestamp())
            
            self.database.prune_tree(timestamp, wait)

            time.sleep(wait)


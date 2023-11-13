import argparse
import threading
import logging
import time
import socket
from datetime import datetime
from packets.controlpacket import ControlPacket
from utils.tree_entry import TreeEntry
from utils.measure_entry import MeasureEntry

class RP():
    NEIGHBOURS = 0
    NEIGHBOURS_RESP = 1
    MEASURE = 2
    MEASURE_RESP = 3
    JOIN = 4
    PLAY = 5
    PAUSE = 6
    LEAVE = 7
    STREAM_REQ = 8

    def __init__(self, bootstrapper):
        self.neighbours = list()
        self.servers = list()

        self.tree_lock = threading.Lock()
        self.tree = dict()

        self.servers_info_lock = threading.Lock()
        self.servers_info = dict()

        self.control_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.data_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

        self.control_socket.bind(("", 7777))
        self.data_socket.bind(("", 7778))
    
        address = bootstrapper.split(":")
        self.bootstrapper = (address[0], int(address[1]))

        logging.basicConfig(format='%(asctime)s [%(levelname)s] - %(message)s', datefmt='%Y-%m-%d %H:%M:%S', level=logging.DEBUG)
        self.logger = logging.getLogger()
        self.logger.info("Control service listening on port 7777 and streaming service on port 7778")

        self.setup() # Request neighbours

        # Services
        threading.Thread(target=self.pruning_service, args=()).start()
        threading.Thread(target=self.control_service, args=()).start()
        threading.Thread(target=self.tracking_service, args=()).start()

    
    def setup(self):
        self.control_socket.sendto(ControlPacket(0).serialize(), self.bootstrapper)
        self.logger.info("Setup: Asked for neighbours and servers")

        try:
            self.control_socket.settimeout(5) # 5 segundos? perguntar ao lost

            data, _ = self.control_socket.recvfrom(1024)
            response = ControlPacket.deserialize(data)

            if response.type == self.NEIGHBOURS_RESP:
                self.neighbours = response.neighbours
                self.servers = response.servers
                
                self.logger.info("Setup: Neighbours and servers received")
                self.logger.debug(f"Neighbours: {self.neighbours}")
                self.logger.debug(f"Servers: {self.servers}")
            
            else:
                self.logger.info("Setup: Unexpected response received")
                exit() # É este o comportamento que queremos ?
            
        except socket.timeout:
            self.logger.info("Setup: Could not receive response to neighbours and servers request")
            exit()


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
        if message.type == self.PLAY:
            #+if message.flag == 0:
            content = message.contents[0]

            self.insert_tree(message, address)

            # Proteger com condição
            best_server = None

            print(self.servers_info)

            self.servers_info_lock.acquire()

            for server, measure in self.servers_info.items():
                if content in measure.contents:
                    if best_server is not None:
                        if best_server[1] > measure.metric:
                            best_server = (measure.server, measure.metric)
                    else:
                        best_server = (measure.server, measure.metric)
            
            self.servers_info_lock.release()

            message = ControlPacket(self.STREAM_REQ, contents=[content])
            self.control_socket.sendto(message.serialize(), best_server[0])

            self.logger.info(f"Control Service: Stream request sent to server {best_server[0]}")
            self.logger.debug(f"Message sent: {message}")


                # VERIFICAR ISTO
                #self.control_socket.sendto(ControlPacket(2, flags=1).serialize(), (message.hops[0], 7777))
                #self.logger.info(f"Control Service: Tree subscription confirmation message sent to {message.hops[0]}")
        
        elif message.type == self.LEAVE:
            self.tree_lock.acquire()

            if address in self.tree:
                self.tree.pop(address)

            self.logger.debug(f"Control Service: Client {address} was removed from tree")

            self.tree_lock.release()

        elif message.type == self.MEASURE_RESP:
            actual_timestamp = float(datetime.now().timestamp())
            latency = actual_timestamp - message.latency

            self.servers_info_lock.acquire()

            print("tou")
            self.servers_info[address[0]] = MeasureEntry(address, latency, message.contents, True) 

            self.logger.info(f"Control Service: Metrics from {address} were updated")

            self.servers_info_lock.release()
        
        elif message.type == self.STREAM_REQ:
            try:
                ips = set()
                content = message.contents[0]

                # CUIDADO COM AS INTERFACES
                self.tree_lock.acquire()   
                for tree_entry in self.tree.values():
                    if content in tree_entry.contents:
                        ips.add(tree_entry.next_step)
                self.tree_lock.release()


                for ip in ips: 
                    self.control_socket.sendto(ControlPacket(self.STREAM_REQ, contents=[content]).serialize(), (ip, 7777))
                    self.logger.info(f"Streaming Service: Comtrol Packet sent to {ip}")

                while True:
                    data, address = self.data_socket.recvfrom(20480)
                 
                    for ip in ips:
                        self.data_socket.sendto(data, (ip, 7778))
                        self.logger.info(f"Streaming Service: Rtp Packet sent to {ip}")
            
            finally:
                self.data_socket.close()
        
    
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
    

    """
    def streaming_service(self):
        try:
            while True:
                data, address = self.data_socket.recvfrom(1024)

                self.logger.info(f"Streaming Service: Rtp Packet received from server {address[0]}")

                threading.Thread(target=self.streaming_worker, args=(address, message,)).start()

        finally:
            self.control_socket.close()
    """

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


    def tracking_service(self):
        wait = 200
        while True:
            for server in self.servers:
                self.control_socket.sendto(ControlPacket(self.MEASURE).serialize(), (server, 7777))

                self.logger.info(f"Tracking Service: Monitorization message sent to {server}")
                    
            time.sleep(wait)

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("-bootstrapper", help="bootstrapper ip")
    args = parser.parse_args()

    if args.bootstrapper:
        RP(args.bootstrapper)
    else:
        print("Error: Wrong arguments")
        exit()


if __name__ == "__main__":
    main()

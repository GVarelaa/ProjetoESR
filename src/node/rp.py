import argparse
import threading
import copy
import time
import socket
from .node import Node
from message import Message

class RP(Node):
    def __init__(self, bootstrapper):
        super().__init__(bootstrapper=bootstrapper)

    
    def request_neighbours(self):
        self.control_socket.sendto(Message(0).serialize(), self.bootstrapper)
        self.logger.info("Control Service: Asked for neighbours and servers")

        try:
            self.control_socket.settimeout(5) # 5 segundos? perguntar ao lost

            response, addr = self.control_socket.recvfrom(1024)
            response = Message.deserialize(response)

            if response.type == self.NEIGHBOURS_RESP:
                self.database.neighbours = response.neighbours
                self.database.servers = response.servers
                
                self.logger.info("Control Service: Neighbours and servers received")
                self.logger.debug(f"Neighbours: {self.database.neighbours}")
                self.logger.debug(f"Servers: {self.database.servers}")
            
            else:
                self.logger.info("Control Service: Unexpected response received")
                exit() # É este o comportamento que queremos ?
            
        except socket.timeout:
            self.logger.info("Control Service: Could not receive response to neighbours and servers request")
            exit()


    def subscription_worker(self, addr, msg):
        self.database.insert_tree(msg.source_ip, addr[0], msg.latency)
        self.logger.info(f"Control Service: Client {msg.hops[0]} added to tree")

        self.control_socket.sendto(Message(2, flags=1).serialize(), (msg.source_ip, 7777))
        self.logger.info(f"Control Service: Tree subscription confirmation message sent to {msg.source_ip}")

    
    def tracking_worker(self, msg):
        self.database.insert_servers(msg.source_ip, msg.latency, msg.contents)


    def tracking_service(self):
        wait = 20
        while True:
            for server in self.database.servers:
                my_ip = self.control_socket.gethostbyname(socket.gethostname()) # verificar se isto funciona 
                self.control_socket.sendto(Message(4, source_ip=my_ip).serialize(), (server, 7777))

                self.logger.info(f"Tracking Service: Monitorization message sent to {server}")
                    
            time.sleep(wait)
    

    def control_service(self):
        try:
            self.control_socket.settimeout(None)

            while True:
                msg, addr = self.control_socket.recvfrom(1024)
                msg = Message.deserialize(msg)

                self.logger.info(f"Control Service: Subscription message received from neighbour {addr[0]}")
                self.logger.debug(f"Message received: {msg}")
                
                if msg.type == self.JOIN:
                    if msg.flag == 0:
                        threading.Thread(target=self.subscription_worker, args=(addr, msg,)).start()
                
                elif msg.type == self.LEAVE:
                    threading.Thread(target=self.leave_worker, args=(msg,)).start()

                elif msg.type == self.MEASURE:
                    threading.Thread(target=self.tracking_worker, args=(msg,)).start()

        finally:
            self.control_socket.close()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("-bootstrapper", help="bootstrapper ip")
    args = parser.parse_args()

    if args.file:
	    node = RP(args.bootstrapper)
    else:
        print("Error: Wrong arguments")
        exit()


if __name__ == "__main__":
    main()
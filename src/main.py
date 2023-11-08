import socket
import socket
import sys
import threading
import argparse
from node.node import Node
from node.rp import RP
from node.bootstrapper import Bootstrapper
from node.client import Client

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("-b", help="bootstrapper file")
    parser.add_argument("-n", help="bootstrapper ip address")
    parser.add_argument("-rp", help="bootstrapper ip address")
    args = parser.parse_args()
    node = None
    
    # Se for bootstrapper
    if args.b:
        node = Bootstrapper(0, args.b)
    
    # Se for nodo
    elif args.n:
        node = Node(1, bootstrapper=args.n)
        node.request_neighbours()
    
    # Se for RP
    else:
        node = RP(2, bootstrapper=args.rp)
        node.request_neighbours()

    if len(node.database.neighbours) == 1: # Nó folha - manda constantemente o pedido de subscrição
        threading.Thread(target=node.polling_service, args=()).start()
    
    else:
        threading.Thread(target=node.pruning_service, args=()).start()
        
    threading.Thread(target=node.control_service, args=()).start()
    

if __name__ == "__main__":
    main()
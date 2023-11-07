import socket
import socket
import sys
import threading
import argparse
from node import Node

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("-b", help="bootstrapper file")
    parser.add_argument("-n", help="bootstrapper ip address")
    parser.add_argument("-rp", help="bootstrapper ip address")
    args = parser.parse_args()
    node = None
    
    # Se for bootstrapper
    if args.b:
        node = Node(0, file=args.b)
    
    # Se for nodo
    elif args.n:
        node = Node(1, bootstrapper_addr=args.n)
        node.request_neighbours()
    
    # Se for RP
    else:
        node = Node(2, bootstrapper_addr=args.rp)
        node.request_neighbours()

    if len(node.database.neighbours) == 1: # Nó folha - manda constantemente o pedido de subscrição
        threading.Thread(target=node.polling_service, args=()).start()
    
    else:
        threading.Thread(target=node.pruning_service, args=()).start()
        
    threading.Thread(target=node.control_service, args=()).start()
    

if __name__ == "__main__":
    main()
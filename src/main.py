import socket
import socket
import sys
import threading
import argparse
from node import Node

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("-b", help="bootstrapper file")
    parser.add_argument("-s", help="bootstrapper ip address")
    parser.add_argument("-rp", help="bootstrapper ip address")
    args = parser.parse_args()
    node = None
    
    if args.b:
        node = Node(0, {}, file=args.b)
    
    elif args.s:
        node = Node(1, {}, bootstrapper_addr=args.s)
        node.request_neighbours()
    
    else:
        node = Node(2, {}, bootstrapper_addr=args.rp)
        node.request_neighbours()

    threading.Thread(target=node.control_service, args=()).start()

if __name__ == "__main__":
    main()


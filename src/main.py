import socket
import socket
import sys
import threading
import argparse
from server import Server

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("-b", help="bootstrapper file")
    parser.add_argument("-s", help="bootstrapper ip address")
    parser.add_argument("-rp", help="bootstrapper ip address")
    args = parser.parse_args()
    server = None
    
    if args.b:
        server = Server(0, {}, file=args.b)
    
    elif args.s:
        server = Server(1, {}, bootstrapper_addr=args.s)
        server.request_neighbours()
    
    else:
        server = Server(2, {}, bootstrapper_addr=args.rp)
        server.request_neighbours()

    threading.Thread(target=server.control_service, args=()).start()

if __name__ == "__main__":
    main()


#!/usr/bin/python3

import sys
import socket as s
import selectors
import httptools as ht
import threading

class State:
    def __init__(self):
        self.done = False

class Proto:
    def __init__(self, state):
        self.state = state

    def on_url(self, url):
        print('got url:', url)

        if b'http' in url:
            parsed = ht.parse_url(url)
            self.state.host = parsed.host
            if parsed.port == None:
                if parsed.schema == b'http':
                    self.state.port = 80
                elif parsed.schema == b'https':
                    self.state.port = 443
                else:
                    print('Unexpected schema:', parsed.schema)
            else:
                self.state.port = parsed.port
        else:
            splitted = url.split(b':')
            self.state.host = splitted[0]
            self.state.port = int(splitted[1])

        print('Client connecting to the', self.state.host, self.state.port)

    def on_message_complete(self):
        print('message complete')
        self.state.done = True

def handleSocket(sock):
    state = State()
    proto = Proto(state)
    parser = ht.HttpRequestParser(proto)
    buf = b''

    print('thread alive', flush=True)

    while not state.done:
        data = sock.recv(4096)
        if not data:
            return

        print('data received:', data)

        try:
            parser.feed_data(data)
        except ht.HttpParserUpgrade as exp:
            nonHttpOffset = exp.args[0]
        buf += data

    with s.socket(s.AF_INET, s.SOCK_STREAM) as rem:
        print('method =', parser.get_method())

        try:
            rem.connect((state.host, state.port))
        except BaseException:
            print('Connection failed')
            return


        if parser.get_method() == b'CONNECT':
            print('client using CONNECT')
            sock.sendall(b'HTTP/1.1 200 OK\r\n\n')
            if len(buf) > nonHttpOffset:
                rem.sendall(buf[nonHttpOffset:])
        else:
            print('client not using CONNECT')
            rem.sendall(buf)

        sel = selectors.DefaultSelector()
        sock.setblocking(False)
        rem.setblocking(False)
        sel.register(sock, selectors.EVENT_READ, data=rem)
        sel.register(rem, selectors.EVENT_READ, data=sock)

        while True:
            events = sel.select(timeout=None)
            for key, _ in events:
                try:
                    data = key.fileobj.recv(4096)
                    key.data.sendall(data)
                except BaseException:
                    return

def main():
    if len(sys.argv) != 2:
        print('Usage:', sys.argv[0],'<port>')
        return

    host = "192.168.1.233"
    port = int(sys.argv[1])

    lsock = s.socket(s.AF_INET, s.SOCK_STREAM)
    lsock.setsockopt(s.SOL_SOCKET, s.SO_REUSEADDR, 1)
    lsock.bind((host, port))
    lsock.listen()

    while True:
        conn, addr = lsock.accept()
        print('Client connected: ', addr)
        threading.Thread(target=handleSocket, args=(conn,), daemon=True).start()

if __name__ == "__main__":
    main()

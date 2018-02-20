import socket
import select
import queue
import json
from pySON import read_json

server_addr = ('127.0.0.1', 5555)

# Reference JSON to be used to compare to value
# read from 'status.json'
reference = read_json('status.json')


# Create a socket with port and host bindings
def setupServer():
    # Create a TCP/IP socket
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.setblocking(0)
    print("Creating Socket at", server_addr)
    try:
        s.bind(server_addr)
        s.listen(5)
    except socket.error as msg:
        print(msg)
    return s


# Get input from user
def GET():
    reply = input("Reply: ")
    return reply


def sendFile(filename, conn):
    f = open(filename, 'rb')
    line = f.read(1024)

    print("Beginning File Transfer:", filename)
    while line:
        conn.send(line)
        line = f.read(1024)
    f.close()
    print("Transfer Complete")


def getFile(filename, conn):
    print("Creating file", filename, "to write to")
    with open(filename, 'wb') as f:
        d = conn.recv(1024)
        while d:
            # print(d)
            f.write(d)
            d = conn.recv(1024)
    print("Finished writing to file")


#############################################################
#  #  #  #  #  #  #  #  #  #  #  #  #  #  #  #  #  #  #  #  #
#############################################################


sock = setupServer()
# Sockets used to read
inputs = [sock]
# Sockets used to write
outputs = []
# Outgoing messages Queue (Socket:Queue)
message_queue = {}

while inputs:
    # Wait for at least one of the sockets to be ready for processing
    print('\nwaiting for the next event')
    readable, writable, exceptional = select.select(inputs, outputs, inputs)

    # Handle inputs
    for s in readable:
        if s is sock:
            # A "readable" server socket is ready to accept a connection
            connection, client_address = s.accept()
            print('new connection from', client_address)
            connection.setblocking(0)
            inputs.append(connection)

            # Give the connection a queue for data we want to send
            message_queue[connection] = queue.Queue()
        else:
            # Receive data; at this point data should be readable
            # command string, not a file byte stream. UTF encoding
            # can therefore be used
            try:
                data = s.recv(1024)
                data = data.decode(encoding='utf-8')
                data.strip()
                darray = data.split()
            except ConnectionResetError:
                print("\nConnection Reset Error: Client Likely Terminated")

            if data:
                print('received "%s" from %s' % (data, s.getpeername()))
                if data == "QUIT":
                    # Close connection if command given is QUIT
                    print('closing', client_address, 'after reading Quit')
                    # Stop listening for input on the connection
                    if s in outputs:
                        outputs.remove(s)
                    inputs.remove(s)
                    s.close()
                    # Remove message queue
                    del message_queue[s]

                elif darray[0] == "TRANSFER":
                    # Prepare to receive file given TRANSFER command
                    getFile(darray[1], s)
                    # Once transfer is complete, stop listening and close
                    if s in outputs:
                        outputs.remove(s)
                    inputs.remove(s)
                    s.close()
                    # Remove message queue
                    del message_queue[s]

                else:
                    # Add commands to queue. Transfers handled below
                    # A readable client socket has data
                    message_queue[s].put(data)
                    # Add output channel for response
                    if s not in outputs:
                        outputs.append(s)

            else:
                # Interpret empty result as closed connection
                print('closing', client_address, 'after reading no data')
                # Stop listening for input on the connection
                if s in outputs:
                    outputs.remove(s)
                inputs.remove(s)
                s.close()

                # Remove message queue
                del message_queue[s]

    # Handle outputs
    for s in writable:
        try:
            next_msg = message_queue[s].get_nowait()
            darray = next_msg.split()
        except queue.Empty:
            # No messages waiting so stop checking for writability.
            print('output queue for', s.getpeername(), 'is empty')
            outputs.remove(s)
        else:
            if darray[0] == "REQUEST":
                # Send a file after receiving REQUEST command
                sendFile(darray[1], s)
            else:
                print('sending "%s" to %s' % (next_msg, s.getpeername()))
                s.send(bytes(next_msg, 'utf-8'))

            if s in outputs:
                outputs.remove(s)
            inputs.remove(s)
            s.close()
            # Remove message queue
            del message_queue[s]

    # Handle "exceptional conditions"
    for s in exceptional:
        print('handling exceptional condition for', s.getpeername())
        # Stop listening for input on the connection
        inputs.remove(s)
        if s in outputs:
            outputs.remove(s)
        s.close()
        # Remove message queue
        del message_queue[s]


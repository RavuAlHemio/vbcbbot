import socket
import sys
import threading
import time

__author__ = 'ondra'


def reader(sock):
    buf = b""
    read_message_piece = 0
    message_pieces = []
    #mess = "{pfx}\0{mid}\0{ts}\0{uid}\0{unm}\0{msg}\0".format(
    #        pfx=prefix, mid=new_message.id, ts=new_message.timestamp, uid=new_message.user_id,
    #        unm=new_message.user_name, msg=new_message.decompiled_body()
    #    ).encode("utf-8")

    while True:
        read = sock.recv(1024)
        if len(read) == 0:
            break
        buf += read

        nul_index = buf.find(b"\0")
        while nul_index != -1:
            # extract chunk
            message = buf[:nul_index]
            buf = buf[nul_index+1:]

            # process message
            if read_message_piece == 0:
                if message == b"NM" or message == b"MM":
                    read_message_piece = 1
                elif message == b"OK":
                    pass
                elif message == b"NO":
                    print('"NO" received')
                    return
                else:
                    print("unexpected message " + repr(message))
            else:
                message_pieces.append(message.decode("utf-8"))
                read_message_piece += 1
                if read_message_piece == 6:
                    # this is it
                    #message_id = int(message_piece[0])
                    timestamp = int(message_pieces[1])
                    #user_id = int(message_piece[2])
                    username = message_pieces[3]
                    message = message_pieces[4]

                    time_text = time.strftime("%Y-%m-%d %H:%M", time.localtime(timestamp))

                    print("[{t}] <{u}> {m}".format(t=time_text, u=username, m=message))

                    # reset
                    read_message_piece = 0
                    message_pieces = []

            nul_index = buf.find(b"\0")


def communicate(path, username, password):
    sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    sock.connect(path)

    # authenticate
    auth_message = "{0}\0{1}\0".format(username, password)
    sock.send(auth_message.encode("utf-8"))

    threading.Thread(None, reader, "reader", (sock,)).start()

    while True:
        line = sys.stdin.readline()
        if len(line) == 0:
            sock.shutdown(socket.SHUT_RDWR)
            return

        send_this = line.strip().encode("utf-8") + b"\0"
        sock.send(send_this)

if __name__ == '__main__':
    import argparse
    import getpass

    parser = argparse.ArgumentParser(
        description="Unix socket client for the vBulletin Chatbox Bot."
    )
    parser.add_argument("-u", "--username", required=True,
                        help="Username for the Unix socket authentication.")
    parser.add_argument("-s", "--socket", required=True, help="Address of the socket.")

    args = parser.parse_args()
    password = getpass.getpass()

    communicate(args.socket, args.username, password)

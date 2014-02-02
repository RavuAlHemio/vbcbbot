from vbcbbot.modules import Module

import logging
import socket
import threading

__author__ = 'ondra'
logger = logging.getLogger("vbcbbot.modules.unix_socket")


class UnixSocket(Module):
    """Opens a Unix socket for communication with the chatbox."""

    def __init__(self, connector, config_section=None):
        Module.__init__(self, connector, config_section)

        if config_section is None:
            config_section = {}

        self.sockets_to_clients = []

        socket_path = config_section["socket path"]
        self.username = config_section["username"]
        self.password = config_section["password"]

        self.socket = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM, 0)
        self.socket.bind(socket_path)
        self.socket.listen(5)

        self.acceptor_thread = threading.Thread(None, self.acceptor_proc, "UnixSocket acceptor")
        self.stop_now = False

    def acceptor_proc(self):
        logger.debug("accepting connections")
        while not self.stop_now:
            (client_socket, address) = self.socket.accept()
            logger.info("accepted connection from " + repr(address))
            threading.Thread(
                None, self.client_handling_proc, "UnixSocket " + repr(address), (client_socket,)
            ).start()

    def client_handling_proc(self, client_socket):
        buf = b""
        have_username = False
        have_password = False

        try:
            while not self.stop_now:
                try:
                    read = client_socket.recv(1024)
                except ConnectionResetError:
                    break

                if len(read) == 0:
                    break
                buf += read

                nul_index = buf.find(b"\0")
                while nul_index != -1:
                    # extract message
                    message = buf[:nul_index]
                    buf = buf[nul_index+1:]

                    # process message
                    if not have_username:
                        have_username = True
                        username = message.decode("utf-8", "replace")
                        if username != self.username:
                            logger.debug("wrong username")
                            client_socket.send(b"NO\0")
                            client_socket.close()
                            return
                    elif not have_password:
                        have_password = True
                        password = message.decode("utf-8", "replace")
                        if password != self.password:
                            logger.debug("wrong password")
                            client_socket.send(b"NO\0")
                            client_socket.close()
                            return
                        logger.debug("auth OK")
                        client_socket.send(b"OK\0")
                        self.sockets_to_clients.append(client_socket)
                    else:
                        # send a message
                        try:
                            send_me = message.decode("utf-8")
                        except UnicodeDecodeError:
                            # nope
                            logger.debug("bad UTF-8")
                            client_socket.send(b"U8\0")
                            client_socket.close()
                            return
                        self.connector.send_message(send_me)

                    # update NUL index
                    nul_index = buf.find(b"\0")
        finally:
            logger.debug("connection gone")
            self.sockets_to_clients.remove(client_socket)

    def start(self):
        self.acceptor_thread.start()

    def stop(self):
        self.stop_now = True

    def distribute_message(self, new_message, prefix):
        mess = "{pfx}\0{mid}\0{ts}\0{uid}\0{unm}\0{msg}\0".format(
            pfx=prefix, mid=new_message.id, ts=int(new_message.timestamp), uid=new_message.user_id,
            unm=new_message.user_name, msg=new_message.decompiled_body()
        ).encode("utf-8")
        for client_socket in self.sockets_to_clients:
            client_socket.send(mess)

    def message_received(self, new_message):
        self.distribute_message(new_message, "NM")

    def message_modified(self, modified_message):
        self.distribute_message(modified_message, "MM")

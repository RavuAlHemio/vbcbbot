from vbcbbot.modules import Module

import posixpath
import threading
import time
import tkinter
import tkinter.scrolledtext

__author__ = 'hosek'


def format_soup(soup):
    ret = ""
    for child in soup.children:
        if hasattr(child, "children"):
            # a tag
            if child.name in {"font", "b", "i"}:
                # strip formatting
                ret += format_soup(child)
            elif child.name == 'img':
                if child.has_attr("alt") and child['alt'] != "":
                    label = child['alt']
                elif child.has_attr("src"):
                    label = posixpath.basename(child['src'])
                else:
                    label = "?"
                ret += "<Image: {0}>".format(label)
            elif child.name == 'a':
                if child.has_attr("href"):
                    ret += "[{0}]({1})".format(format_soup(child), child['href'])
                else:
                    ret += format_soup(child)
            else:
                raise ValueError("unexpected child {0}".format(child.name))
        else:
            # string
            ret += child
    return ret


class ClientWindow:
    def enter_pressed(self, event):
        # send the message and clear the box
        self.connector.send_message(self.chat_entry.get())
        self.chat_entry.delete(0, tkinter.END)

    def append_message(self, message, sigil=""):
        msg = "\n[{t}]{s} <{u}> {b}".format(
            t=time.strftime("%Y-%m-%d %H:%M", time.localtime(message.timestamp)),
            u=message.user_name,
            b=format_soup(message.body_soup()),
            s=sigil
        )
        self.chat_text.insert(tkinter.END, msg)
        self.chat_text.see(tkinter.END)

    def message_modified(self, message):
        self.append_message(message, " *")

    def message_received(self, message):
        self.append_message(message)

    def run(self):
        self.tk = tkinter.Tk()

        self.chat_text = tkinter.scrolledtext.ScrolledText(self.tk)
        self.chat_text.grid(row=0, sticky=tkinter.W+tkinter.E+tkinter.N+tkinter.S)
        #self.chat_text.pack(side=tkinter.TOP, fill=tkinter.BOTH, expand=1)

        self.chat_entry = tkinter.Entry(self.tk)
        self.chat_entry.grid(row=1, sticky=tkinter.W+tkinter.E+tkinter.S)
        #self.chat_entry.pack(side=tkinter.TOP, fill=tkinter.X, expand=1)
        self.chat_entry.bind("<Return>", self.enter_pressed)

        self.tk.grid_rowconfigure(0, weight=1)
        self.tk.grid_rowconfigure(1, weight=0)
        self.tk.grid_columnconfigure(0, weight=1)

        self.tk.mainloop()

    def __init__(self, connector):
        self.connector = connector
        self.tk = None


class InteractiveTkClient(Module):
    """An interactive Tk-based client for the chatbox."""

    def __init__(self, connector, config_section=None):
        Module.__init__(self, connector, config_section)

        self.client_window = ClientWindow(connector=connector)
        self.windowing_thread = threading.Thread(None, self.client_window.run, "InteractiveTkClient")

    def start(self):
        self.windowing_thread.start()

    def message_received(self, new_message):
        self.client_window.message_received(new_message)

    def message_modified(self, modified_message):
        self.client_window.message_modified(modified_message)

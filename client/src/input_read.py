from threading import Thread, Event
from termios import TCIFLUSH, tcflush
from contextlib import contextmanager

import sys
import select
import time
import os


class InputRead(Thread):
    def __init__(self, input_callback=None):
        self.read_pipe, self.write_pipe = os.pipe()
        self.read_list = [sys.stdin, self.read_pipe]
        self.timeout = 0.1
        self.last_work_time = time.time()

        self.input_callback = input_callback
        self.pause_event = Event()

        Thread.__init__(self)
        self.start()

    def run(self):
        show_default_label = True

        while self.read_list:
            if show_default_label:
                sys.stdout.write("JogoDaVelha> ")
                sys.stdout.flush()
                show_default_label = False

            ready = select.select(self.read_list, [], [])[0]

            if self.read_pipe in ready:
                self.pause_event.wait()
                self.pause_event.clear()
                show_default_label = True
                continue

            if sys.stdin in ready:
                line = sys.stdin.readline()

                if line.rstrip():
                    self.treat_input(line.rstrip())
                    show_default_label = True

            tcflush(sys.stdin, TCIFLUSH)

    def init_request(self):
        os.write(self.write_pipe, b"\0")

    def end_request(self):
        os.read(self.read_pipe, 1)
        self.pause_event.set()

    @contextmanager
    def block_input(self):
        self.init_request()
        yield
        self.end_request()

    def treat_input(self, linein):
        self.input_callback(linein)
        self.last_work_time = time.time()

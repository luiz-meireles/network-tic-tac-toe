from threading import Thread, Lock
from queue import Queue, Empty

import sys
import select
import time
import os


class InputRead:
    def __init__(
        self, input_callback=None, command_read_event=None, request_event=None
    ):
        self.pipe_read, self.pipe_write = os.pipe()
        self.read_list = [sys.stdin, self.pipe_read]
        self.timeout = 0.1
        self.last_work_time = time.time()

        self.input_queue = Queue()
        self.interrupted = Lock()

        self.input_callback = input_callback
        self.command_read_event = command_read_event
        self.request_event = request_event

    def run(self):
        self.interrupted.acquire()

        input_thread = Thread(target=self.read_input, daemon=True)
        input_thread.start()

        try:
            while True:
                if self.input_queue.empty() and not input_thread.is_alive():
                    break
                else:
                    try:
                        self.treat_input(self.input_queue.get(timeout=self.timeout))
                    except Empty:
                        self.idle_work()
        except KeyboardInterrupt:
            self.cleanup()

        self.interrupted.release()

    def pause_read(self):
        os.write(self.pipe_write, b"\0")

    def read_input(self):
        while self.read_list and not self.interrupted.acquire(blocking=False):
            sys.stdout.write("JogoDaVelha> ")
            sys.stdout.flush()
            readable = select.select(self.read_list, [], [])[0]

            if self.pipe_read in readable:
                print("entrando aq dentro")
                self.command_read_event.wait()
                continue

            line = sys.stdin.readline()
            self.input_queue.put(line.rstrip())

            self.command_read_event.wait()
            self.command_read_event.clear()

    def treat_input(self, linein):
        self.input_callback(linein)
        self.last_work_time = time.time()

    def idle_work(self):
        now = time.time()

        if now - self.last_work_time > 2:
            self.last_work_time = now

    def cleanup(self):
        print()
        while not self.input_queue.empty():
            self.input_queue.get()

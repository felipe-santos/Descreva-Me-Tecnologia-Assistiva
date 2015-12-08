#!/usr/bin/env python

import cv2
import os
import time

import tornado.httpserver


import tornado.websocket


from tornado.ioloop import IOLoop
from tornado.web import RequestHandler, Application, url
from tornado.gen import coroutine, Task
from tornado.concurrent import Future



CAMERA_PORT = 0
REFRESH_INTERVAL = 0.16



class LongPoll(object):
    def __init__(self):
        self.waiters = set()

    def wait_for_image(self):
        result_future = Future()
        self.waiters.add(result_future)
        return result_future

    def cancel_wait(self, future):
        self.waiters.remove(future)
        future.set_result('')

    def new_image(self, image):
        size = len(self.waiters)
        if not size:
            return

        #print('Serving %d clients' % size)
        for future in self.waiters:
            future.set_result(image)
        self.waiters = set()



class MainHandler(tornado.web.RequestHandler):
    @tornado.web.asynchronous
    def get(self):
        self.render("index.html")


class WebSocketHandler(tornado.websocket.WebSocketHandler):
    def open(self, *args):
        #self.id = self.get_argument("Id")
        self.stream.set_nodelay(True)
        #clients[self.id] = {"id": self.id, "object": self}

    def on_message(self, message):
        print message
        self.write_message('{ "mensagem": "%s", "tit_mensagem": "%s" }' %("TESTE", "TESTE 2"))

    def on_close(self):
        print mensagem
        print("Close")


class ImgHandler(RequestHandler):
    @coroutine
    def get(self,):
        self.future = self.application.long_poll.wait_for_image()
        image = yield self.future
        if self.request.connection.stream.closed():
            return
        self.set_header('Content-type', 'image/jpg')
        self.write(image)

    def on_connection_close(self):
        self.application.long_poll.cancel_wait(self.future)

def make_app():
    return Application(
        [url(r"/", MainHandler),
         url(r"/img", ImgHandler),
         url(r'/ws', WebSocketHandler),
         ],
        template_path=os.path.join(os.path.dirname(__file__), "template"),
        static_path=os.path.join(os.path.dirname(__file__), "static"),
        debug=True,
    )


def get_image(camera):
    _, im = camera.read()
    #im = cv2.cvtColor(im, cv2.COLOR_BGR2GRAY)
    return im

def init_webcam():
    camera = cv2.VideoCapture(CAMERA_PORT)
    for i in xrange(20):
        get_image(camera)
    return camera


@coroutine
def refresh_image(camera, long_poll):
    while True:
        yield Task(IOLoop.current().add_timeout, time.time() + REFRESH_INTERVAL)
        img = get_image(camera)

        # convert image to jpeg in memory
        encode_param = [int(cv2.IMWRITE_JPEG_QUALITY), 100]
        _, image = cv2.imencode('.jpg', img, encode_param)

        # update waiters
        long_poll.new_image(''.join(chr(x) for x in image))


def main():
    long_poll = LongPoll()
    camera = init_webcam()
    app = make_app()
    app.long_poll = long_poll
    app.listen(8001)
    print('http://localhost:8001')

    IOLoop.current().add_callback(refresh_image, camera, long_poll)
    IOLoop.current().start()

if __name__ == "__main__":
    main()
    

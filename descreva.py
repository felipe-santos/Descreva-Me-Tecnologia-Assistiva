#!/usr/bin/env python
# -*- coding: utf-8 -*-

import logging
import tornado.escape
import tornado.ioloop
import tornado.options
import tornado.web
import tornado.websocket
import os.path
import uuid

import cv2
import time
import getch
import unicodedata

from gtts import gTTS

from tornado.options import define, options
from tornado.ioloop import IOLoop
from tornado.web import RequestHandler, Application, url
from tornado.gen import coroutine, Task
from tornado.concurrent import Future


define("port", default=8888, help="run on the given port", type=int)

MENSAGEM_ATUAL = ""
CAMERA_PORT = 0
REFRESH_INTERVAL = 0.20
DESEJO = ""
key = "lol"

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

class Application(tornado.web.Application):
    def __init__(self):
        handlers = [
            (r"/", MainHandler),
            (r"/img", ImgHandler),
            (r"/chatsocket", ChatSocketHandler),
        ]
        settings = dict(
            cookie_secret="__TODO:_GENERATE_YOUR_OWN_RANDOM_VALUE_HERE__",
            template_path=os.path.join(os.path.dirname(__file__), "templates"),
            static_path=os.path.join(os.path.dirname(__file__), "static"),
            xsrf_cookies=True,
        )
        tornado.web.Application.__init__(self, handlers, **settings)


class MainHandler(tornado.web.RequestHandler):
    @tornado.web.asynchronous
    def get(self):

        self.render("index.html", messages=ChatSocketHandler.cache)

class ChatSocketHandler(tornado.websocket.WebSocketHandler):
    waiters = set()
    cache = []
    cache_size = 2000

    def get_compression_options(self):
        # Non-None enables compression with default options.
        return {}

    def open(self):
        if DESEJO!="":
           self.write_message(DESEJO)
        ChatSocketHandler.waiters.add(self)

    def on_close(self):
        ChatSocketHandler.waiters.remove(self)

    @classmethod
    def update_cache(cls, chat):
        cls.cache.append(chat)
        if len(cls.cache) > cls.cache_size:
            cls.cache = cls.cache[-cls.cache_size:]

    @classmethod
    def send_updates(cls, chat):
        logging.info("sending message to %d waiters", len(cls.waiters))
        for waiter in cls.waiters:
            try:
                waiter.write_message(chat)
            except:
                logging.error("Error sending message", exc_info=True)

    def on_message(self, message):
        global MENSAGEM_ATUAL
        logging.info("got message %r", message)
        parsed = tornado.escape.json_decode(message)
        chat = {
            "id": str(uuid.uuid4()),
            "body": parsed["body"],
            }
        os.system('rm ./output.mp3')
        if MENSAGEM_ATUAL != parsed["body"]:
            #comando = 'wget -q -U Mozilla -O output.mp3 "http://translate.google.com/translate_tts?tl=pt_BR&ie=UTF-8&client=t&q='
            #comando = 'wget -q -U Mozilla -O output.mp3 "http://translate.google.com/translate_tts?textlen=9&idx=0&tl=pt&client=t&total=1&ie=UTF-8&q='
            comando = encode(parsed["body"])
            #comando = comando + "\""
            #print ("COMANDO: ", comando)
            #os.system(comando)
            print "TEXTO", comando
            tts = gTTS(text=parsed["body"], lang='pt')
            tts.save("output.mp3")
        MENSAGEM_ATUAL = parsed["body"]
        chat["html"] = tornado.escape.to_basestring(
            self.render_string("message.html", message=chat))
        os.system('mpg123 output.mp3 &')
        #print parsed["body"]
        ChatSocketHandler.update_cache(chat)
        ChatSocketHandler.send_updates(chat)

def remove_accents(input_str):
    nkfd_form = unicodedata.normalize('NFKD', input_str)
    only_ascii = nkfd_form.encode('latin-1', 'ignore')
    return only_ascii

def loop_principal():
    global DESEJO
    global key
    DESEJO = ''
    #os.system('mpg123 voz/bom-dia.mp3')
    #os.system('mpg123 voz/o-que-deseja.mp3')
    #os.system('mpg123 voz/validade.mp3')
    while DESEJO == '':
        key = getch.getch()
	if key == u'\n':
            DESEJO = '{ "desejo": "DESCOBRIR A VALIDADE DE UM PRODUTO" }'
        else:
            os.system('mpg123 voz/valor.mp3')
            key = getch.getch()
            if key == u'\n':
                DESEJO = '{ "desejo": "VALOR" }'
            else:
                os.system('mpg123 voz/qual-cor.mp3')
                key = getch.getch()
                if key == u'\n':
                    DESEJO = "COR"
                else:
                    os.system('mpg123 voz/remedio.mp3')
                    key = getch.getch()
                    if key == u'\n':
                        DESEJO = "REMEDIO"

def main():
    app = Application()
    app.listen(options.port)
    long_poll = LongPoll()
    camera = init_webcam()
    app.long_poll = long_poll
    IOLoop.current().add_callback(refresh_image, camera, long_poll)
    IOLoop.current().add_callback(loop_principal)
    IOLoop.current().start()
if __name__ == "__main__":
    main()

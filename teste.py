#!/usr/bin/env python
# -*- coding: utf-8 -*-
import os
from gtts import gTTS
tts = gTTS(text='Ola meu amiguinho, é hoje', lang='pt')
tts.save("hello.mp3")
os.system('mpg123 hello.mp3 &')

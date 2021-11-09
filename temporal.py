import numpy as np
from threading import Thread
import json
#import queue
from time import sleep
import copy
import math
import numpy as np
from collections import deque
class idk:
    def __init__(self):
        self.flag = False

def cookfood(param, id):
    sleep(param)
    print("{0} slept by {1} seconds \n".format(id,param))

def paralelo(param,id):
    print('working... \n')
    cookfood(param,id)


if __name__ == "__main__":
    thjoin = []
    th1 = Thread(target=paralelo, args=(idk(),idk()))
    thjoin.append(th1)
    th2 = Thread(target=paralelo, args=(idk(),idk()))
    thjoin.append(th2)

    th1.start()
    th2.start()

    for th in thjoin:
        th.join()

from threading import Thread
import json
import queue

class taco:
    def __init__(self, cantidad, duracionPorTaco) -> None:
        self.cantidad = cantidad
        self.duracionPorTaco = duracionPorTaco
        
Q_ordenes = queue.Queue()

def checkIfOrderLessThan400(orden):
    sumatoria=0
    for subordenes in orden:
        sumatoria+=subordenes.quantity 
    if(sumatoria > 400):
        return True
    return False

def checkMeat(type):
    meats = ["asada, tripa, cabeza, suadero, adobada"] # podemos hacer esto un diccionario para revisar en tiempo O(1)
    if type in meats:
        return True
    return False

def asignacionQueue(subordenes):
    if(subordenes.meat == "tripa" or subordenes.meat == "cabeza"):
        #AGREGAR suborden al SQS del taquero de tripa y cabeza
        #SQS
        pass
    if(subordenes.meat == "asada" or subordenes.meat == "suadero"):
        #AGREGAR suborden al SQS de los taqueros de asada
        #SQS
        pass
    if(subordenes.meat == "adobada"):
        #AGREGAR suborden al SQS de Adobada
        #SQS
        pass


def categorizador(orden, i): # objeto de toda la orden
    
    print("ORDEN {0}".format(i))

    pass

joinear= []
def readJson():
    # pseudocodigo
    #json = getJson() 
    i=0
    for orden in json.orders:
        orden_thread = Thread(target=categorizador, args=(orden,i))
        i+=1
        
        joinear.append(orden_thread)
        
        orden_thread.start()
        categorizador(orden)

def nextOrder(Q_ordenes):
    return Q_ordenes.get()
#

if __name__ == "__main__":
    readJson({'nombre':"tu mama", 'edad':20})


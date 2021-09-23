import queue
import json

class taco:
    def __init__(self, cantidad, duracionPorTaco) -> None:
        self.cantidad = cantidad
        self.duracionPorTaco = duracionPorTaco
        

Q_ordenes = queue.Queue()

def checkIfOrderGreaterThan400(orden):
    sumatoria=0
    for subordenes in orden["orden"]:
        sumatoria+=subordenes["quantity"]
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
        #AGREGAR suborden al QUEUE del taquero de tripa y cabeza
        pass
    if(subordenes.meat == "asada" or subordenes.meat == "suadero"):
        #AGREGAR suborden al QUEUE compartido de los taqueros de asada 
        pass
    if(subordenes.meat == "adobada"):
        pass

def readJsonAndAppendToQueues():
    f = open('Ordenes.json') 
    data = json.load(f)

    for orden in data:

        # Si la orden tiene un total de mas de 400 tacos REJECTED
        if(checkIfOrderGreaterThan400(orden) == True):
            print("ORDER  " + str(orden["request_id"]) +"  REJECTED")
            pass

        '''
        for subordenes in orden["orden"]:
            
            if(checkMeat(subordenes["type"]) == False):
                #RECHAZAR
                pass

            asignacionQueue(subordenes)
        '''


readJsonAndAppendToQueues()
#


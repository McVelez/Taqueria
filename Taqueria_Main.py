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
        #AGREGAR suborden al QUEUE del taquero de tripa y cabeza
        pass
    if(subordenes.meat == "asada" or subordenes.meat == "suadero"):
        #AGREGAR suborden al QUEUE compartido de los taqueros de asada 
        pass
    if(subordenes.meat == "adobada"):
        pass

def readJsonAndAppendToQueues():
    # pseudocodigo
    json = getJson() 
    for orden in json.orders:

        # Si la orden tiene un total de mas de 400 tacos REJECTED
        if(checkIfOrderLessThan400() == False):
            #RECHAZAR
            pass

        for subordenes in orden:
            
            if(checkMeat(subordenes.type) == False):
                #RECHAZAR
                pass

            asignacionQueue(subordenes)

            



def nextOrder(Q_ordenes):
    return Q_ordenes.get()





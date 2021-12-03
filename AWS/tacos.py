import random
import copy
from datetime import datetime
import simplejson as json

class orderGenerator:
    
    def __init__(self):
        pass

    def generateOrder(self):
        tacos = []
        type = ["taco", "quesadilla"]
        meat = ["asada", "adobada", "suadero", "tripa", "cabeza"]
        fillings = ["cebolla", "cilantro", "salsa", "guacamole"]
        for x in range(5):
            taco = {
                "datetime": str(datetime.now()), 
                "request_id": x, 
                "status": "open", 
                "orden":[ ] 
            }
            for y in range(random.randrange(10)):
                taco["orden"].append(
                    {   
                        "part_id": "{0}-{1}".format(x, y), 
                        "type": random.choice(type), 
                        "meat": random.choice(meat), 
                        "status":"open", 
                        "quantity": random.randrange(51), 
                        "ingredients":[ ] 
                    }
                )
                local_fillings = copy.deepcopy(fillings)
                for z in range(random.randrange(len(local_fillings))):
                    ind_filling = random.choice(local_fillings)
                    taco["orden"][y]["ingredients"].append(ind_filling)
                    local_fillings.remove(ind_filling)

            tacos.append(taco)  
        return tacos


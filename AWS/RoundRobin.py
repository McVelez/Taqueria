from datetime import datetime
import json

# Se crea la clase de handler del SQS
class SQS_handler:
    def __init__(self) -> None:
        pass
    
    # Función para obtener número de mensajes    
    def get_number_messages(self, sqs, queue_url):
        # Obtenmos los atribrutos del queue (Número aproximado de mensajes y de mensajes no visibles)
        queue_attr = sqs.get_queue_attributes(
            QueueUrl = queue_url,
            AttributeNames = ['ApproximateNumberOfMessages', 'ApproximateNumberOfMessagesNotVisible']
        )
        
        # Regresamos los atributos
        return int(queue_attr["Attributes"]['ApproximateNumberOfMessages']), int(queue_attr["Attributes"]['ApproximateNumberOfMessagesNotVisible'])

    # Se define la función para leer mensajes del SQS
    def read_message(self, sqs, queue_url):
        # Se obtiene una respuesta
        response = sqs.receive_message(QueueUrl = queue_url, MaxNumberOfMessages = 1)
        
        # Si la respuesta tiene mensaje entonces se considera para la taquería
        if 'Messages' in response:
            message = response['Messages']
            orden = json.loads(message[0]["Body"])
            return message[0], orden
        
        # En caso de que la respuesta no tenga mensaje se regresa None, None
        return None, None

    # Se define la función para borrar los mensajes del SQS
    def delete_message(self, message, orden, sqs, queue_url):
        # Se establece el endtime como la fecha y hora actual
        orden["end_datetime"] = str(datetime.now().timestamp())
        
        # Se borra el mensaje
        sqs.delete_message(
            QueueUrl = queue_url,
            ReceiptHandle = message["ReceiptHandle"]
        )

    # Función para mandar un mensaje a SQS
    def write_message(self, orden, sqs, queue_url):
        # Definimos response como el mensaje mandado a un queue de SQS, siendo la orden el mensaje
        response = sqs.send_message(
            QueueUrl = queue_url,
            MessageBody = (json.dumps(orden))
        )


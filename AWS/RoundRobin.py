from datetime import datetime
import random
import boto3
import json
import time

#sqs = boto3.client("sqs")
#queue_url = "https://sqs.us-east-1.amazonaws.com/292274580527/sqs_cc106_team_7"
#who = "Elmane"
class SQS_handler:
    def __init__(self) -> None:
        pass
        
    def get_number_messages(self, sqs, queue_url):
        queue_attr = sqs.get_queue_attributes(
            QueueUrl = queue_url,
            AttributeNames = ['ApproximateNumberOfMessages', 'ApproximateNumberOfMessagesNotVisible']
        )
        return int(queue_attr["Attributes"]['ApproximateNumberOfMessages']), int(queue_attr["Attributes"]['ApproximateNumberOfMessagesNotVisible'])

    def read_message(self, sqs, queue_url):
        response = sqs.receive_message(QueueUrl = queue_url, MaxNumberOfMessages = 1)
        if 'Messages' in response:
            message = response['Messages']
            orden = json.loads(message[0]["Body"])
        
        #print("Atendiendo oorden: {0}. Leyendo mensaje del queue. Tiempo pendiente {1}".format(orden["request_id"], orden["tiempo_pendiente"]))
            return message[0], orden
        return None, None

    def delete_message(self, message, orden, sqs, queue_url):

        orden["end_datetime"] = str(datetime.now().timestamp())
        #print(orden)
        sqs.delete_message(
            QueueUrl = queue_url,
            ReceiptHandle = message["ReceiptHandle"]
        )

    def write_message(self, orden, sqs, queue_url):
        #self.delete_message(mensaje, orden, False)
        response = sqs.send_message(
            QueueUrl = queue_url,
            MessageBody = (json.dumps(orden))
        )


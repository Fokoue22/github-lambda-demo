import json
import boto3
import logging
import slack  
import os 
import csv
import schedule
import time
from botocore.exceptions import ClientError
from email import encoders
from email.mime.base import MIMEBase
from email.mime.application import MIMEApplication
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

#setup loggers that will track event when my code will run
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger()

# global variable 
FILE_NAME = '/tmp/' + 'ec2-report.csv'
SLACK_TOKEN = 'xoxb-4796957867426-4852417593346-VuygW4wavH8zF7Kposz2QQff'
BUCKET = 'fokouebucket'
SNAPSHOT_NAME = 'snapshot_list'
TERMINATE = 'statefilters'

def list_all_instances():

    ec2_client = boto3.client('ec2')
    response = ec2_client.describe_instances()

    my_list = []
    for reservation in response['Reservations']:
        for instance in reservation['Instances']:
            server_name = instance['Tags'][0]['Value']
            instance_id = instance['InstanceId']
            image_id = instance['ImageId']
            instance_type = instance['InstanceType']
            instance_state = instance['State']['Name']
            my_list.append([server_name, instance_id, image_id, instance_type, instance_state])
            print(my_list)
    return my_list
    
schedule.every().day.at("10:46").do(list_all_instances)
    
    
def create_snapshot():
    ec2 = boto3.resource('ec2', region_name = 'us-east-1')
    sns_client= boto3.client('sns')

    statefilters=[{'Name': 'instance-state-name', 'Values': ['stopped']}]
    snapshot_list=[]
    for instance in ec2.instances.filter(Filters=statefilters):
        for volume in instance.volumes.all():
            Volume_id = volume.id
            volume = ec2.Volume(Volume_id)
            desc = 'This is the snapshot of a stopped ec2 instance {}'.format(Volume_id)
            print('Creating the snapshot of the following volume: ', Volume_id)
            snapshot=volume.create_snapshot(Description=desc)
            snapshot_list.append(snapshot)

    print(snapshot_list) 

    sns_client.publish(
        TopicArn='arn:aws:sns:us-east-1:671765845629:notify-snapshot-vai-python',
        Subject='EBS Snapshots of a stopped ec2 instance',
        Message=str(snapshot_list)

    )

schedule.every().day.at("10:46").do(create_snapshot)


def terminate_ec2():
   #call the boto client
   ec2 = boto3.resource('ec2', region_name = 'us-east-1')
   statefilters=[{'Name': 'instance-state-name', 'Values': ['stopped']}]
   # command to terminate and ec2 instance 
   #ec2.instances.filter(statefilters).terminate()
   for instance in ec2.instances.filter(Filters=statefilters).terminate():
   #this code will print the image id of all ec2 that was terminated
      instances = ec2.instances.filter(Filters=[{'Name': 'instance-state-name', 'Values': ['terminated']}])
      print(instance['TerminatingInstances'])

#    try:
#          instances = ec2.instances.filter()
#    except ClientError as error:
#          logging.error(f'An error occurred try to read the error messages:{error}')
#          return False
#    return True 
      
schedule.every().day.at("10:46").do(terminate_ec2)


# The next step will be to generate the csv report functions
def generate_csv_report(instances):
    """ This fonction will generate csv report
      :param HEADER: this part of the code will be at the top of the csv table
      :param csv.writer: this line will start writing to a csv file
      :return FALSE: if we run this code and something happend to this OPEN it will logg this messages to the user and return FALSE


    """
    # header of the csv file
    header = ['Instance Name', 'Instance ID', 'Image ID', 'Instance Type', 'Instance State']

    try:
        with open(FILE_NAME, 'w', newline='') as file:
           writer = csv.writer(file) 
           writer.writerow(header) # pass the list Header in this functions
           writer.writerows(instances)

    except FileNotFoundError as error:
        logger.error(f'File does not exist.') # logg messages
        return False 
    return True # if the code work it will return TRUE

schedule.every().day.at("10:46").do(generate_csv_report)


def send_email():
    """
    This function will send and email to the reciever with attachment of ec2-report.csv
    return: True if message sent, else False if an error occurs
    """

    # call SES boto client
    ses_client = boto3.client('ses')
    
    # define variables
    SENDER = 'fokouethomasdylan@gmail.com'
    RECEIVER = 'willcabrel735@gmail.com'
    CHARSET = 'utf-8'
    msg = MIMEMultipart('mixed')
    msg['Subject'] = 'EC2 Report Generator'
    msg['From'] = SENDER
    msg['To'] = RECEIVER

    msg_body = MIMEMultipart('alternative')

    BODY_TEXT = 'Hey Sir,\n\nPlease find the requested EC2 Report attached.\n\nThanks,\n\nThomas'

    textpart = MIMEText(BODY_TEXT.encode(CHARSET), 'plain', CHARSET)

    msg_body.attach(textpart)

    # full path to the file that will be attached to the email
    ATTACHMENT = FILE_NAME

    # adding attachment
    att = MIMEApplication(open(ATTACHMENT, 'rb').read())
    att.add_header('Content-Disposition', 'attachment',
                    filename = ATTACHMENT)

    msg.attach(msg_body)
    msg.attach(att)

    try:
        response = ses_client.send_raw_email(
            Source= SENDER,
            Destinations= [RECEIVER],
            RawMessage={'Data': msg.as_string(),},
        )
        logger.info(f"The email was send successfully to {RECEIVER}. Message id : {response['MessageId']}")
    except Exception as error:
        logger.error(f'An error occurred: {error}')
        return False
    return True

schedule.every().day.at("10:46").do(send_email)


def send_slack_message():

   ## creating ebs Snapshot that only create snapshot for stopped ec2 instance
    EMAIL = 'willcabrel735@gmail.com'
    # env_path = Path('.') / '.env'
    # load_dotenv(dotenv_path = env_path)
    client = slack.WebClient(token= SLACK_TOKEN)
    client.chat_postMessage(channel="#general", text= (f'Hello sir,\n\n And Ec2 report was generated, it containe {FILE_NAME}\n\n{SNAPSHOT_NAME} and was send to this email:\n{EMAIL}\n\nThanks, \n\nFokoue Thomas!'))
    
schedule.every().day.at("10:46").do(send_slack_message)


def lambda_handler(event, context):
    #Call the function 
    logger.info(f'our list of servers: {list_all_instances()}')
    # retrieve&get data needed for the report
    instances = list_all_instances() # this statement will store all the return it will store it on the varaible INSTANCES
    
    create_snapshot()
    logger.info(f'Your report: {SNAPSHOT_NAME} has been generated succesfully!')
    
    terminate_ec2()
    logger.info(f'Your report: The following stopped ec2 instance {TERMINATE} has been terminated succesfully!')
    
    #creat the csv file and pass the instance list to the function
    generate_csv_report(instances)
    logger.info(f'Your report: {FILE_NAME} has been generated succesfully!')
    
    send_email()
    logger.info(f"Your report: {FILE_NAME} email has successfully been sent!")
    
    send_slack_message()
    logger.info(f'Your report: {SNAPSHOT_NAME} has been generated succesfully!')
    

    return {
        'statusCode': 200,
        'body': json.dumps('Our ec2-generator lambda function was generated succesfully!!!')
    }

while True:
        schedule.run_pending()
        time.sleep(1)

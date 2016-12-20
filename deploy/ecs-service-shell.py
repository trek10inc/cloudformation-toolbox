#!/usr/local/bin/python

import argparse
import json
import boto3
import pprint
import time
import random
import atexit
import os
import stat
import re
from boto3.session import Session


pp = pprint.PrettyPrinter(indent=2)

class bcolors:
    HEADER = '\033[95m'
    OKBLUE = '\033[94m'
    OKGREEN = '\033[92m'
    WARNING = '\033[93m'
    FAIL = '\033[91m'
    ENDC = '\033[0m'
    BOLD = '\033[1m'
    UNDERLINE = '\033[4m'

#####
# Parsing of Arguments
#####

parser = argparse.ArgumentParser(description='Get a shell in a preconfigured container in your service stack')
parser.add_argument('--key', required=True, help='AWS Access Key Id')
parser.add_argument('--sshkey', required=True, help='SSH Key content, not just the file name! Use `cat key.pem` to read in a file to the command line)')
parser.add_argument('--secret', required=True, help='AWS Secret Access Key')
parser.add_argument('--stack', required=True, help='The Stack name (ex: Production)')
parser.add_argument('--region', required=True, help='The region of the stack (ex: us-east-1)')
parser.add_argument('--task', required=False, help='The filter for the task runner (ex: ServiceTask|CronRunner)')
parser.add_argument('--private', required=False, default=False, help='Connect via public or private IP')
parser.add_argument('--serviceversion', required=False, default=1, help='console task definition version')

args = parser.parse_args()

taskFilter = args.task
if taskFilter is None:
  taskFilter = 'ServiceTask'

print("Stack is " + args.stack + ".", flush=True)

# Writes out so it is usable in SSH
keyfile = open('/root/.ssh/id_rsa', 'w')
keyfile.write(args.sshkey)
keyfile.close()

os.chmod('/root/.ssh/id_rsa', 0o600)


session = Session(aws_access_key_id=args.key,
                  aws_secret_access_key=args.secret,
                  region_name=args.region)

cfnClient = session.client('cloudformation')
ecsClient = session.client('ecs')
ec2Client = session.client('ec2')


# Get parameters from old template and marshall them for update
try:
    response = cfnClient.describe_stacks(
        StackName=args.stack
    )
except Exception as e:
    print(e)
    print(bcolors.FAIL + "That is not a valid stack name, or you do not have permission to access this stack!" + bcolors.ENDC)
    exit()

print("Marshalling outputs and paramenters")

# Get output references for finding related resources
for output in response['Stacks'][0]['Outputs']:
    # pp.pprint(output)
    if output['OutputKey'] == 'ClusterName':
        cluster_name = output['OutputValue']

    if output['OutputKey'] == 'TaskDefinition':
        task_def = output['OutputValue']
        
# swap out the console task definition version
if args.serviceversion:
    task_def = task_def.replace(":1",(":"+args.serviceversion))

# Dumb thing we have to do to get the running task name
image_reference = re.search(r'/(.*):', task_def).group(1)

print("Finding the task we will shell into")

# Poll until task is running
print("Finding existing service task.", end="", flush=True)

try:
    print(".", end="", flush=True)
    time.sleep(2)
    response = ecsClient.list_tasks(
        cluster=cluster_name
    )

    # pp.pprint(response)
        
    # Break out if the task is running
    if response['taskArns']:
        tasks_list = response['taskArns']

except Exception as e:
    print(e)
    print(bcolors.FAIL + "Couldn't poll the task list" + bcolors.ENDC, flush=True)
    exit()

try:
    print(".", end="", flush=True)
    time.sleep(2)
    response = ecsClient.describe_tasks(
        cluster=cluster_name,
        tasks=tasks_list
    )

    # pp.pprint(response)
        
    # Break out if the task is running
    current_tasks = response['tasks']
    for val in current_tasks:
        if(val['taskDefinitionArn'] == task_def):
            container_instance = val['containerInstanceArn']
            running_task_arn = val['taskArn']
            container_name = val['containers'][0]['name']
            break

except Exception as e:
    print(e)
    print(bcolors.FAIL + "Couldn't poll the tasks define" + bcolors.ENDC, flush=True)
    exit()

response = ecsClient.describe_container_instances(
    cluster=cluster_name,
    containerInstances=[
        container_instance
    ]
)

instance_id = response['containerInstances'][0]['ec2InstanceId']

response = ec2Client.describe_instances(
    InstanceIds=[
        instance_id
    ]
)

if args.private:
    ip_address = response['Reservations'][0]['Instances'][0]['PrivateIpAddress']
else:
    ip_address = response['Reservations'][0]['Instances'][0]['PublicIpAddress']

#  os.system("ssh -oStrictHostKeyChecking=no ec2-user@" + ip_address + " -t \"docker ps | grep " + image_reference + " | grep seconds | awk '{print \$1;}' \"")
os.system("ssh -oStrictHostKeyChecking=no ec2-user@" + ip_address + " -t \"docker exec -it \`docker ps | grep " + image_reference + " | grep "+ taskFilter +" | awk 'NR==1{print \$1;}'\` bash\"")

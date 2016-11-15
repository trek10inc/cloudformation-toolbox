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
parser.add_argument('--private', required=False, default=False, help='Connect via public or private IP')

args = parser.parse_args()

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

def stop_task(ecsClient, cluster, task):
    try:
        print("Cleaning up after ourselves...")
        ecsClient.stop_task(
            cluster=cluster,
            task=task
            )
        print(bcolors.OKGREEN + "Task stopped and removed succesfully, all done!" + bcolors.ENDC)
    except Exception as e:
        print(e)
        print(bcolors.FAIL + "Something went wrong, login to the AWS Console to kill this task manually." + bcolors.ENDC)
        exit()

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
    if output['OutputKey'] == 'ClusterName':
        cluster_name = output['OutputValue']

    if output['OutputKey'] == 'ConsoleRunner':
        task_def = output['OutputValue']

# Dumb thing we have to do to get the running image / tag
for parameter in response['Stacks'][0]['Parameters']:
    if parameter['ParameterKey'] == 'ContainerDockerOrganization':
        docker_organization = parameter['ParameterValue']

    if parameter['ParameterKey'] == 'ContainerDockerImage':
        docker_image = parameter['ParameterValue']

    if parameter['ParameterKey'] == 'ContainerDockerTag':
        docker_tag = parameter['ParameterValue']

full_image_reference = docker_organization + "/" + docker_image + ":" + docker_tag

print("Running the task we will shell into")

try:
    response = ecsClient.run_task(
        cluster=cluster_name,
        taskDefinition=task_def,
        count=1,
        startedBy='ConsoleRunner'
    )
except Exception as e:
    print(e)
    print(bcolors.FAIL + "Couldn't find the servers to place the task on or your don't have permissions to run a task on this service & cluster." + bcolors.ENDC)
    exit()

container_instance = response['tasks'][0]['containerInstanceArn']
running_task_arn = response['tasks'][0]['taskArn']
container_name = response['tasks'][0]['containers'][0]['name']
print(bcolors.OKGREEN + "Task started with id " + running_task_arn + bcolors.ENDC)

# Registers a task killer for when client exits
print("Registering the task killer to run on script exit")
atexit.register(stop_task, ecsClient, cluster_name, running_task_arn)

# Poll until task is running
print("Polling for task to be running.", end="", flush=True)

while True:
    try:
        print(".", end="", flush=True)
        time.sleep(2)
        response = ecsClient.describe_tasks(
            cluster=cluster_name,
            tasks=[
                running_task_arn
            ]
        )

        # Break out if the task is running
        if response['tasks'][0]['lastStatus'] == 'RUNNING':
            print(bcolors.OKGREEN + " Task running!" + bcolors.ENDC, flush=True)
            break
        elif response['tasks'][0]['lastStatus'] == 'STOPPED':
            print(bcolors.FAIL + " The task died." + bcolors.ENDC)
            exit()

    except Exception as e:
        print(e)
        print(bcolors.FAIL + "Couldn't poll the task status" + bcolors.ENDC, flush=True)
        exit()

# pp.pprint(response)

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

#  os.system("ssh -oStrictHostKeyChecking=no ec2-user@" + ip_address + " -t \"docker ps | grep " + full_image_reference + " | grep seconds | awk '{print \$1;}' \"")

os.system("ssh -oStrictHostKeyChecking=no ec2-user@" + ip_address + " -t \"docker exec -it \`docker ps | grep " + full_image_reference + " | grep seconds | awk 'NR==1{print \$1;}'\` bash\"")

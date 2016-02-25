#!/usr/local/bin/python

import argparse
import json
import boto3
import pprint
import time
import random
import os
import stat
import time
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
parser.add_argument('--key', required=False, help='AWS Access Key Id')
parser.add_argument('--sshkey', required=True, help='SSH Key content, not just the file name! Use `cat key.pem` to read in a file to the command line)')
parser.add_argument('--secret', required=False, help='AWS Secret Access Key')
parser.add_argument('--stack', required=True, help='The Stack name (ex: Production)')
parser.add_argument('--region', required=False, help='The region of the stack (ex: us-east-1)', default='eu-west-1')

args = parser.parse_args()

print("Stack is " + args.stack + ".", flush=True)

# Writes out so it is usable in SSH
keyfile = open('/root/.ssh/id_rsa', 'w')
keyfile.write(args.sshkey)
keyfile.close()

os.chmod('/root/.ssh/id_rsa', 0o600)

if args.key:
    print(bcolors.OKGREEN + 'Using provided aws access keys' + bcolors.ENDC)
    session = Session(aws_access_key_id=args.key,
                      aws_secret_access_key=args.secret,
                      region_name=args.region)
else:
    print(bcolors.OKGREEN + 'Letting aws sdk find access keys' + bcolors.ENDC)
    session = Session(region_name=args.region)

cfnClient = session.client('cloudformation')
ecsClient = session.client('ecs')
ec2Client = session.client('ec2')

# Get parameters from old template and marshall them for update
try:
    response = cfnClient.describe_stacks(
        StackName=args.stack
    )
    resources = cfnClient.describe_stack_resources(
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

# Dumb thing we have to do to get the running image / tag
for parameter in response['Stacks'][0]['Parameters']:
    if parameter['ParameterKey'] == 'ContainerDockerOrganization':
        docker_organization = parameter['ParameterValue']

    if parameter['ParameterKey'] == 'ContainerDockerImage':
        docker_image = parameter['ParameterValue']

    if parameter['ParameterKey'] == 'ContainerDockerTag':
        docker_tag = parameter['ParameterValue']

for resource in resources['StackResources']:
    if resource['ResourceType'] == 'AWS::ECS::Service':
        ecs_service = resource['PhysicalResourceId']


full_image_reference = docker_organization + "/" + docker_image + ":" + docker_tag

availability = {
    'up': 0,
    'down': 0,
}

taskList = ecsClient.list_tasks(
        cluster=cluster_name,
        serviceName=ecs_service,
        desiredStatus='RUNNING'
    )
limit = 7
while len(taskList['taskArns']) == 0 and limit > 0:
    print('task not running, trying again in five seconds')
    time.sleep(5)
    limit -= 1
    taskList = ecsClient.list_tasks(
        cluster=cluster_name,
        serviceName=ecs_service,
        desiredStatus='RUNNING'
    )

if len(taskList['taskArns']) == 0:
    print (bcolors.FAIL, 'Unable to find task, try again')
    exit(1)

tasks = ecsClient.describe_tasks(
    cluster=cluster_name,
    tasks=taskList['taskArns']
)
containerInstanceArns = [t['containerInstanceArn'] for t in tasks['tasks']]

containerInstances = ecsClient.describe_container_instances(
    cluster=cluster_name,
    containerInstances=containerInstanceArns
)

instance_id = containerInstances['containerInstances'][0]['ec2InstanceId']

ec2Instances = ec2Client.describe_instances(
    InstanceIds=[
        instance_id
    ]
)

ip_address = ec2Instances['Reservations'][0]['Instances'][0]['PublicIpAddress']

print (bcolors.OKGREEN + "Getting logs from host, ip address: ", ip_address, bcolors.ENDC)

os.system("ssh -oStrictHostKeyChecking=no ec2-user@" + ip_address +
          ''' "docker logs -f \`docker ps -a | grep ''' + args.stack + ''' | head -n 1 | awk '{ print \$1}'\`" ''')

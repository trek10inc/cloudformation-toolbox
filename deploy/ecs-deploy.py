#!/usr/local/bin/python

import argparse
import json
import boto3
import pprint
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

parser = argparse.ArgumentParser(description='Deploy update to CloudFormation Stack')
parser.add_argument('--key', required=True, help='AWS Access Key Id)')
parser.add_argument('--secret', required=True, help='AWS Secret Access Key)')
parser.add_argument('--stack', required=True, help='The Stack name (ex: OurAppProduction)')
parser.add_argument('--tag', required=True, help='The new tag to deploy to the Stack. (ex: v1.33.7)')
parser.add_argument('--region', required=True, help='The region of the stack (ex: us-east-1)')

args = parser.parse_args()
print("Stack is " + args.stack + ". Tag is " + args.tag + ".", flush=True)

session = Session(aws_access_key_id=args.key,
                  aws_secret_access_key=args.secret,
                  region_name=args.region)

cfnClient = session.client('cloudformation')


# Get parameters from old template and marshall them for update
try:
    response = cfnClient.get_template(StackName=args.stack)
except Exception as e:
    print(e)
    print(bcolors.FAIL + "That is not a valid stack name, or you do not have permission to deploy to this stack!" + bcolors.ENDC)
    exit()


# Forces params to remain the same unless it's the docker tag
def marshall_param(param):
    if param == 'ContainerDockerTag':
        return {'ParameterKey': param, 'ParameterValue': args.tag }
    else:
        return {'ParameterKey': param, 'UsePreviousValue': True}

params = [marshall_param(param)
          for param in response['TemplateBody']['Parameters']]


print(bcolors.OKGREEN + "Parameters have been marshalled." + bcolors.ENDC, flush=True)

response = cfnClient.describe_stack_events(
    StackName=args.stack,
)

shown_events = []

# Kinda a hack to not show old stuff
for event in response['StackEvents']:
    if event['EventId'] not in shown_events:
        shown_events.append(event['EventId'])


last_event_id = response['StackEvents'][0]['EventId']

try:
    update_response = cfnClient.update_stack(
        StackName=args.stack,
        UsePreviousTemplate=True,
        Parameters=params,
        Capabilities=[
            'CAPABILITY_IAM',
        ],
    )
except Exception as e:
    print(e)
    print(bcolors.FAIL + "Already at the current tag or an update is in progress!" + bcolors.ENDC)
    exit()

print(bcolors.OKGREEN + "Starting update with StackId " +
      update_response['StackId'] + bcolors.ENDC, flush=True)

time.sleep(5)

def maintain_loop(response, last_event_id):
    events = sorted(response['StackEvents'], key=lambda x: x['Timestamp'], reverse=True)
    event = events[0]

    if (event['EventId'] != last_event_id) and \
       (event['ResourceType'] == 'AWS::CloudFormation::Stack') and \
       ((event['ResourceStatus'] == 'UPDATE_COMPLETE') or (event['ResourceStatus'] == 'UPDATE_ROLLBACK_COMPLETE')):
        return False

    return True

# Print top of updates stream
print("{: <30} {: <40} {: <}".format("Resource", "Status", "Details"), flush=True)


# Steam updates until we hit a closing case
while maintain_loop(response, last_event_id):
    time.sleep(3)
    response = cfnClient.describe_stack_events(
        StackName=args.stack,
    )

    events = sorted(response['StackEvents'], key=lambda x: x['Timestamp'])

    for event in events:
        if event['EventId'] not in shown_events:

            if 'ResourceStatusReason' not in event:
                event['ResourceStatusReason'] = ""

            print("{: <30} {: <30} {: <}".format(event['ResourceType'], event['ResourceStatus'], event['ResourceStatusReason']), flush=True)
            shown_events.append(event['EventId'])

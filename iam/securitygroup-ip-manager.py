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

parser = argparse.ArgumentParser(description='Add / Remove an IP Address on a specific Security Group')
parser.add_argument('--key', required=True, help='AWS Access Key Id')
parser.add_argument('--secret', required=True, help='AWS Secret Access Key')
parser.add_argument('--security-group-id', required=True, help='The Stack name (ex: Production)')
parser.add_argument('--region', required=True, help='The region of the stack (ex: us-east-1)')
parser.add_argument('--ip', required=False, help='IP Address you would like added or removed form the Security Group, defaults to current public IP')
parser.add_argument('--add', '-a', help='Add IP Address', action='store_true')
parser.add_argument('--remove', '-r', help='Remove IP Address', action='store_true')

args = parser.parse_args()


session = Session(aws_access_key_id=args.key,
                  aws_secret_access_key=args.secret,
                  region_name=args.region)

ec2Client = session.resource('ec2')

try:
    security_group = ec2Client.SecurityGroup(args.security_group_id)
except Exception as e:
    print(e)
    print(bcolors.FAIL + "Could not get the security group requested." + bcolors.ENDC)
    exit()

if args.ip:
    ip_address = args.ip
else:
    import urllib
    ip_address = urllib.request.urlopen('http://ip.42.pl/raw').read().decode("utf-8")
    print("Defaulting to using current IP Address: "+ip_address)


# If we are ingress adding
if args.add:
    try:
        response = security_group.authorize_ingress(
                        FromPort=22,
                        ToPort=22,
                        CidrIp=ip_address+"/32",
                        IpProtocol="tcp"
                        )

        print(bcolors.OKGREEN + "IP address "+ip_address+" was succesfully added!" + bcolors.ENDC)
    except Exception as e:
        print(e)
        print(bcolors.FAIL + "Could not add "+ip_address+" to the security group." + bcolors.ENDC)
        exit()


# If we are revoke ingress
if args.remove:
    try:
        response = security_group.revoke_ingress(
                        FromPort=22,
                        ToPort=22,
                        CidrIp=ip_address+"/32",
                        IpProtocol="tcp"
                        )

        print(bcolors.OKGREEN + "IP Address "+ip_address+" was succesfully removed! Goodbye!" + bcolors.ENDC)
    except Exception as e:
        print(e)
        print(bcolors.FAIL + "Could not remove "+ip_address+" to the security group." + bcolors.ENDC)
        exit()

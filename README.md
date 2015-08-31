# cloudformation-toolbox

A small suite of scripts we use to manage cloudformation activities.

## No guarantees on anything

Seriously, use these at your own risk. They are not guaranteed to work, keep working, or anything. We build these as side projects, or specifically to meet the needs of one specific clients.

## Usage

Base command:  
`docker run --rm -it trek10/cloudformation-toolbox(:tag) [command] [options]`

## Available [command]s

### ecs-deploy

Runs a deploy of a cloudformation stack, currently it only works for a stack if you are modifying a "tag" parameter. It gathers and maintains the same value for all other parameters currently defined in the stack.

__Usage__  
`docker run --rm trek10/cloudformation-toolbox(:tag) ecs-deploy --key AWS_KEY --secret AWS_SECRET --region AWS_REGION --stack StackName --tag v1_1`

_Available [options]_

```
usage: ecs-deploy [-h] --key KEY --secret SECRET --stack STACK --tag TAG
                  --region REGION

Deploy update to CloudFormation Stack

optional arguments:
  -h, --help       show this help message and exit
  --key KEY        AWS Access Key Id)
  --secret SECRET  AWS Secret Access Key)
  --stack STACK    The Stack name (ex: OurAppProduction)
  --tag TAG        The new tag to deploy to the Stack. (ex: v1.33.7)
  --region REGION  The region of the stack (ex: us-east-1)
```

### ecs-shell
Performs bit of behind the scenes magic to get the latest task version running on the stack, and creates a new task that is not attached to any running service. It provisons the task with all the expected environment variables and opens the user up to a bash-script in the newly created task. On exit, the task is killed and the command cleans up after itself.

__Usage__  
``docker run --rm -it trek10/cloudformation-toolbox(:tag) ecs-shell --sshkey "`cat .ssh/your-key.pub`" --key AWS_KEY --secret AWS_SECRET --region AWS_REGION --stack StackName``

_Note_  
`-it` is critical to be able to interact with the created shell.  
`--sshkey` takes the full key text as an argument, not just a filename.

__Available [options]__
```
usage: ecs-shell [-h] --key KEY --sshkey SSHKEY --secret SECRET --stack STACK
                 --region REGION

Get a shell in a preconfigured container in your service stack

optional arguments:
  -h, --help       show this help message and exit
  --key KEY        AWS Access Key Id
  --sshkey SSHKEY  SSH Key content, not just the file name! Use `cat key.pem`
                   to read in a file to the command line)
  --secret SECRET  AWS Secret Access Key
  --stack STACK    The Stack name (ex: Production)
  --region REGION  The region of the stack (ex: us-east-1)
```

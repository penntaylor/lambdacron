import datetime
import json
import os
import subprocess

import boto3
import crontab

def lambda_handler(event, context):
    processCronBucket()
    return None


def processCronBucket():
    # Ensure we use same comparison time for all cron entries
    now = datetime.datetime.utcnow()

    bucket = os.environ["LAMBDACRON_BUCKET"]
    prefix = os.environ["LAMBDACRON_PREFIX"]
    interval = float(os.environ["LAMBDACRON_INTERVAL"]) * 60  # Convert minutes to seconds

    s3 = boto3.resource('s3')
    bkt = s3.Bucket(bucket)
    objs = bkt.objects.filter(Prefix=prefix)
    for obj in objs:
        try:
            body = obj.get()["Body"].read()
            task = json.loads(body)
            if matches(task, now, interval):
                run(task, obj.key)
                increment(task)
                updateOrDelete(obj, task, now)
        except Exception as e:
            print("Caught exception while handling task in {}: {}".format(obj.key, e))

    return None


def matches(task, now, interval):
    when = task.get("when", "* * * * * * *")
    # Allow up to 10 seconds of slop to account for
    # - uncertainty in AWS's scheduled Lambda process
    # - slow Lambda init (particularly important in a VPC context)
    wideInterval = interval + 10.01
    pastDesired = abs(crontab.CronTab(when).previous(now=now, default_utc=True))
    if pastDesired < wideInterval:
        # If we're right in the window of uncertainty...
        if (wideInterval - pastDesired) < 10.01:
            # Check the last time this even was run and...
            lastTimeStr = task.get("last_run", "1970-01-01T01:01:01.000000")
            lastTime = datetime.datetime.strptime(lastTimeStr, "%Y-%m-%dT%H:%M:%S.%f")
            dtSeconds = (now - lastTime).total_seconds
            if dtSeconds < wideInterval:
                # Don't re-run if it was run last time.
                return False
        return True
    else:
        return False


def run(task, name):
    print("Running job: {}".format(name))
    r = task["run"]
    typ = r["type"]
    details = r["details"]
    if typ == "command":
        runCommand(details, name)
    elif typ == "python":
        runPython(details, name)
    elif typ == "lambda":
        runLambda(details, name)


def runCommand(details, name):
    """Runs a command process. The command should be a list of arguments, eg.
       ["ls", "-Fal"]

       If you require a shell for doing variable expansion, write your command
       as a list, specifying the interpreter as in the following bash example:
       ["bash", "-c", "your actual command as a string"]

       The same bash trick can be used if you want to use pipes, file redirection,
       and other such idioms.
    """
    command = details["command"]
    if isinstance(command, list):
        r = subprocess.run(command, stdout=subprocess.PIPE)
    else:
        print("ERROR: In key {}, command is not a list. Unable to execute.".format(name))
    return None


def runPython(details, name):
    """Runs a python script in another process
    """
    script = details.get("script", "")
    subprocess.run(["python3", "-c", script])
    return None


def runLambda(details, name):
    """Directly invokes an AWS Lambda function
    """
    arn = details["arn"]
    payload = details.get("payload", {})
    boto3.client("lambda"). invoke(FunctionName=arn, Payload=json.dumps(payload).encode("utf-8"))



def increment(task):
    executionCount = task.get("execution_count", 0)
    task["execution_count"] = executionCount + 1
    return None


def updateOrDelete(obj, task, now):
    executionCount = task["execution_count"]
    maxNumberExecutions = task.get("max_number_executions", 0)

    if (maxNumberExecutions > 0) and (executionCount >= maxNumberExecutions):
        # Ensure we never have to process this one again
        obj.delete()
    else:
        task["last_run"] = now.isoformat()
        obj.put(Body=json.dumps(task).encode("utf-8"))

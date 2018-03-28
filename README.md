lambdacron
===

Dynamic cron-like jobs in a serverless environment.


Features
---
* run unix commands
* invoke other lambda functions (with custom data payloads)
* execute aribtrary python scripts
* use standard cron syntax for schedules (also supports non-standard year field)
* adding and removing jobs is as simple as adding/removing JSON files in an S3 bucket
* `max_number_executions` setting automatically deletes a job after being run the desired number of times
* see when a specific job was last run by examining its file in S3


Motivating use-case
---
Serverless code that needs to schedule some other action to happen in the future, needs to do so dynamically, and needs to be able to pass data to the future action.


Contrived Example
---
A completely serverless meal order-taking / order-placing service that allows users to specify what time they want their meal order placed with the vendor. For every order that comes in, the order-taking bot can use lambdacron to dynamically schedule the order-placing Lambda function to be directly invoked with that specific order's details at the appropriate time.


Overview
---
* Step 1: Set up an AWS Lambda function to run lambdacron
* Step 2: Place lambdacron jobs as JSON files in your chosen S3 bucket
* Step 3: Lambdacron periodically checks the job bucket and run jobs based on the details in the JSON
* Step 4: To remove a lambdacron job, just delete the associated JSON file from S3


How to install / use
---
TODO

Sample jobs
---
Runs the unix command `ls -Fal` at a specific time every day:
```JSON
{
  "when": "30 18 * * * * *",
  "max_number_executions": 0,
  "run": {
    "type": "command",
    "details": {
      "command": [
        "ls",
        "-Fal"
      ]
    }
  }
}
```

Runs an embedded python script on 4 April of each year, then deletes itself after the third run:
```JSON
{
  "when": "01 01 30 04 * * *",
  "max_number_executions": 3,
  "run": {
    "type": "python",
    "details": {
      "script": "import json\n\ndata = {\"hello\": \"world\"}\n\nprint(json.dumps(data))\n\nfor x in range(1,10):\n    print(x)\n"
    }
  }
}

```


Limitations and Quirks
---
1. Does not support job frequencies of less than one minute
2. Whatever you set as the master interval becomes the effective time-resolution of *all* your lambdacron jobs
3. Looks to the *past* rather than the future when determining whether to run a job

Example of #3: Assume lambdacron is scheduled to run every 5 minutes, and it runs at 03:23, 03:28, 03:33, etc. If a job scheduled for 03:30, it will not actually be executed until 03:33, since that is the first time lambdacron is run *after* the job's specified time.


Obvious Questions
---
Q: Why not just use AWS's Scheduled Tasks for Lambda mechanism?

A: That mechanism has the following limitations, which lambdacron is intended to address:
   * Maximum of 100 scheduled events per AWS account
   * Events invoke a Lambda function but don't carry meaningful payload
   * Relatively difficult to implement dynamic jobs
   * Each separate job has to have its own Lambda function

#
# Copyright 2010-2019 Amazon.com, Inc. or its affiliates. All Rights Reserved.
#

# greengrassHelloWorld.py
# Demonstrates a simple publish to a topic using Greengrass core sdk
# This lambda function will retrieve underlying platform information and send
# a hello world message along with the platform information to the topic 'hello/world'
# The function will sleep for five seconds, then repeat.  Since the function is
# long-lived it will run forever when deployed to a Greengrass core.  The handler
# will NOT be invoked in our example since the we are executing an infinite loop.

import logging
import greengrasssdk
import platform
from threading import Timer


# Creating a greengrass core sdk client
client = greengrasssdk.client('iot-data')

# Retrieving platform information to send from Greengrass Core
my_platform = platform.platform()
if not my_platform:
    payload_str = 'Hello world! Sent from Greengrass Core.'
else:
    payload_str = 'Hello world! Sent from Greengrass Core running on platform: {}'.format(my_platform)


# When deployed to a Greengrass core, this code will be executed immediately
# as a long-lived lambda function.  The code will enter the infinite while loop
# below.
# If you execute a 'test' on the Lambda Console, this test will fail by hitting the
# execution timeout of three seconds.  This is expected as this function never returns
# a result.

def greengrass_hello_world_run():
    try:
        response = client.publish(topic='hello/world', payload=payload_str)
    except Exception as e:
        logging.error("Failed to publish the message, error: {}".format(e))
    else:
        logging.info("Successfully publish the message, response: {}".format(response))

    # Asynchronously schedule this function to be run again in 5 seconds
    Timer(5, greengrass_hello_world_run).start()


# Execute the function above
greengrass_hello_world_run()


# This is a dummy handler and will not be invoked
# Instead the code above will be executed in an infinite loop for our example
def function_handler(event, context):
    return

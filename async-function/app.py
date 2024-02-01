"""
    Trigger Lambda handler, passes through the event to the StateMachine
    for processing async whilst returning to Connect
"""
import os
import json
import boto3
from botocore.exceptions import ClientError


def lambda_handler(event, context):  # pylint: disable=unused-argument
    """
    Primary Handler, simple takes the event and triggers a provided
    StateMachine using the event as input.

    Args:
        event: ([Connect Contact Event]): Event from Connect that is
            used to generate
        context: ([lambda context]): THe Lambda context (automatically)
            provided inside of Lambda

    Raises:
        err: ClientError, raised by the State Machine in case of issues

    Returns
        [dict]:
            executionArn: ARN of the execution that is being run
            result: The result of the state machine invocation
    """
    client = boto3.client("stepfunctions")
    response = {
        "execution_id": "",
        "status": "FAILED",
        "sfn_result": "",
        "comfort": "false",
    }
    state_machine = os.getenv("STATE_MACHINE_ARN")

    try:
        params = (
            event["Details"]["Parameters"]
            if "Details" in event and "Parameters" in event["Details"]
            else {}
        )
        # maximum amount of invocations before considering it a failure due to timeout
        count_max = int(params.get("count_max", "5"))
        count_max = 1 if count_max <= 0 else count_max
        # The invocation count for the prior execution.
        count = params.get("count")
        count = int(count) + 1 if bool(count) else 1
        if count > count_max:
            raise ValueError
        # Number of invocations between returning comfort_message=true
        count_comfort = int(params.get("count_comfort", "10"))
        if count_comfort <= 0:
            comfort = "false"
        else:
            comfort = "true" if (count % count_comfort == 0) else "false"

        # Update response with counts
        response.update(
            {
                "count": str(count),
                "comfort": comfort,
                "count_comfort": str(count_comfort),
                "count_max": str(count_max),
            }
        )

        if "execution_id" in params:
            result = client.describe_execution(executionArn=params["execution_id"])
            fail_status = ["FAILED", "TIMED_OUT", "ABORTED"]
            status = result["status"]
            print(f"Got status for execution: {status}")
            # Include execution id in response
            response.update({"execution_id": params["execution_id"]})
            if status in fail_status:
                response.update({"status": "FINISHED", "sfn_result": "FAILURE"})
            elif status == "SUCCEEDED":
                response.update({"status": "FINISHED", "sfn_result": "SUCCESS"})
                response.update(json.loads(result["output"]))
            else:
                response.update({"status": "RUNNING", "sfn_result": ""})
        # Ensure State Machine ARN actually exists
        elif state_machine:
            print(f"Attempting to invoke event on state machine {state_machine}")
            result = client.start_execution(
                stateMachineArn=state_machine, input=json.dumps(event)
            )
            response.update(
                {
                    "execution_id": result["executionArn"],
                    "status": "CREATED",
                    "sfn_result": "",
                }
            )
        else:
            response.update({"execution_id": "", "status": "FAILED", "sfn_result": ""})
    except ValueError as err:
        response.update(
            {
                "execution_id": "",
                "count": "DONE",
                "status": "LOOP_DONE",
                "sfn_result": "FAILURE",
            }
        )
        print(err)
        return response
    except ClientError as err:
        raise err
    else:
        return response

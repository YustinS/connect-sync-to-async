# Amazon Connect Async a Sync Function

This repo contains code relating to the capability of taking an synchronous function, and placing it behind a state machine to allow for Amazon Connect to continue flow invocation without blocking, and allowing retrieval at a later time.
This is also designed that developed code doesn't need to be rearchitected in any way, rather it places a wrapper over what is already existing to reduce friction.
Optimally, the environment is designed with these constraints already accounted for, but reality has a funny habit of not always panning out as expected.

There are several reasons that this may be desired, such as

- A function response can take longer than expected from upstream
- "Dead air" during invocations needs to be reduced as much as possible
- Multiple chained functions would cause system errors (back-to-back functions can only run for 30's, and it would be dead air the whole time)

## Using this in Connect

To use this you simply need to wrap your existing Lambda function in the state machine, and then create the new calling function using the code residing in `async-function/`, along side relevant permissions to achieve this.

Generally, you should seek to do this with with an IaC code such as `Terraform`, `OpenTofu`, `CDK`, `Pulumi`, or other.

1. Create the State Machine definition, replacing the appropriate value with the ARN of your Lambda function.
2. Update the IAM role your state machine uses, granting it permissions to execute the Lamba function.
3. Test, ensuring the function is still executing as normal when invoked by the state machine.
4. Create the new function that starts the State Machine, using the code in `async-function/`. Ensure to set the environment variable `STATE_MACHINE_ARN` to the ARN of the State Machine created in 1.
5. Set IAM permissions for your Lambda function to allow it to invoke the State Machine.
6. Test again, ensuring that the new function returns immediately after starting.
7. Using an example of an Amazon Connect Lambda Invoke event, add to the `Parameters` section a variable named `execution_id`. Set the value of this to the returned `execution_id` returned from step 6.

If this is all working then you have the main components ready, and simply require completing the Amazon Connect Components

1. Add the Lambda function to AWS Connect to allow it to be invoked
2. Create the Contact Flow that uses this. Call the function, and capture the `execution_id` value on response.
3. Complete actions as required (saying a message to the customer, harvesting more input, etc), and once required call the function again, setting the parameter `execution_id` ti the value captured in 2.
4. Evaluate the result of `sfn_result`. `SUCCESS` indicates the function was called correctly and completed, returning its results within the response. `FAILURE` indicates the called function has failed for some reason, so may require further investigations. If it is neither of those responses the State Machine is still running, so looping is required.
5. Loop as needed. There are some helper values that can be used to assist with this.

## Customization Parameters

The function that is called by Connect can be customized slightly using extra parameters as desired. These are not strictly required, but can be useful in ensuring a smooth customer experience

- `count_max` - This can be set to limit the number of times you are allowed to call the wrapping function. This more exists for larger state machine that need to take multiple actions. If `count_max` is exceeded, the function will return a `ValueError` exception for handling in Connect.
- `count` - The current count of invocations of the state machine. The function doesn't track this internally, rather it is a value the Contact Flow pass in and then retrieves each invocation.
- `count_comfort` - This is an arbitrary value that is used to set a boolean value. When `count` % `count_comfort` is 0, the flag is set to true. This can be used if the function is being called repeatedly, and can indicate a "Please Hold" or similar message should be played. If the logic evaluates, the value of the response key `comfort` will be set to `true`, otherwise it will be `false`.

All of these values are returned when the function is invoked (`count` is incremented each call), as well as the value `comfort` which can be used for evaluation. The values should be re-saved to values within the Contact Flow on each invocation.

## Example Contact Flow

A small Contact Flow is provided showing the basic usage of the function, including checking the `count` and `comfort` variables and taking actions as needed.

As this repo is only seeking to show things off this is largely indicitive, as after the `SUCCESS` branch we would then be doing processing based on the output of the original Lambda (for examples, things like taking a balance from an API and reading it back).

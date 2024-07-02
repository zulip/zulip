# Onboarding Steps

Onboarding steps introduce users to important UI elements. They are an
effective means of providing context where Zulip's UI may not be self-evident.

Currently, an onboarding step is a one-time notice in the form of a banner or modal.
Previously, hotspots were another type of onboarding step available.

## Configuring a New Onboarding Step

...is easy! If you think highlighting a certain UI element would improve
Zulip's user experience, we welcome you to [open an issue](https://github.com/zulip/zulip/issues/new?title=onboarding_step_request:) for discussion.

### Step 1: Add the Onboarding Step Name

In `zerver/lib/onboarding_steps.py`, add the new onboarding step name to the
`ONE_TIME_NOTICES` list:

```python
ONE_TIME_NOTICES: List[OneTimeNotice] = [
    ...
    OneTimeNotice(
        name="Provide a concise name",
    ),
]
```

### Step 2: Display the Onboarding Step

When the UI element that is not self-evident appears, use the
`ONE_TIME_NOTICES_TO_DISPLAY` data structure from `web/src/onboarding_steps.ts`
and the onboarding step name added in **Step 1** to determine if the
one-time notice should be displayed. Display the notice.

### Step 3: Mark the Onboarding Step as Read

Once the notice is displayed, use the `post_onboarding_step_as_read` function
from `web/src/onboarding_steps.ts` to mark the onboarding step as read.
This will update `ONE_TIME_NOTICES_TO_DISPLAY` so that the user will not see
the notice again.

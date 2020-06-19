{use_owner_client}
# Update organization

{generate_api_description(/realm:patch)}

## Usage examples

{start_tabs}
{tab|python}

{generate_code_example(python)|/realm:patch|example}

{tab|curl}

{generate_code_example(curl)|/realm:patch|example}

{end_tabs}

## Parameters

{generate_api_arguments_table|zulip.yaml|/realm:patch}

#### Return values

{generate_return_values_table|zulip.yaml|/realm:patch}

#### Example response

A typical successful JSON response may look like:

{generate_code_example|/realm:patch|fixture(200)}

An example JSON response for when an unauthorized user try to modify the
message retention days police:

{generate_code_example|/realm:patch|fixture(400)}

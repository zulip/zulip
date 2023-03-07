# Note that in the Markdown preprocessor registry, the highest
# numeric value is considered the highest priority, so the dict
# below is ordered from highest-to-lowest priority.
# Priorities for the built-in preprocessors are commented out.
PREPROCESSOR_PRIORITES = {
    "generate_parameter_description": 535,
    "generate_response_description": 531,
    "generate_api_header": 530,
    "generate_code_example": 525,
    "generate_return_values": 510,
    "generate_api_arguments": 505,
    "help_relative_links": 475,
    "setting": 450,
    # "normalize_whitespace": 30,
    "fenced_code_block": 25,
    # "html_block": 20,
    "tabbed_sections": -500,
    "nested_code_blocks": -500,
    "emoticon_translations": -505,
    "static_images": -510,
}

BLOCK_PROCESSOR_PRIORITIES = {
    "include": 51,
}

MAX_TOPIC_NAME_LENGTH = 60
# Length of the resolved-topic prefix ("✔ "). It does not count toward
# MAX_TOPIC_NAME_LENGTH. Keep this in sync with RESOLVED_TOPIC_PREFIX in
# zerver/lib/topic.py; models cannot import that module.
RESOLVED_TOPIC_PREFIX_LENGTH = 2
MAX_STORED_TOPIC_NAME_LENGTH = MAX_TOPIC_NAME_LENGTH + RESOLVED_TOPIC_PREFIX_LENGTH
MAX_LANGUAGE_ID_LENGTH: int = 50

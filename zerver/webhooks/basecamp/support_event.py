DOC_SUPPORT_EVENTS = [
    'document_active',
    'document_created',
    'document_archived',
    'document_unarchived',
    'document_publicized',
    'document_title_changed',
    'document_content_changed',
    'document_trashed',
    'document_publicized',
]

QUESTION_SUPPORT_EVENTS = [
    'question_archived',
    'question_created',
    'question_trashed',
    'question_unarchived',
    'question_answer_archived',
    'question_answer_content_changed',
    'question_answer_created',
    'question_answer_trashed',
    'question_answer_unarchived',
]

MESSAGE_SUPPORT_EVENTS = [
    'message_archived',
    'message_content_changed',
    'message_created',
    'message_subject_changed',
    'message_trashed',
    'message_unarchived',
    'comment_created',
]

TODOS_SUPPORT_EVENTS = [
    'todolist_created',
    'todolist_description_changed',
    'todolist_name_changed',
    'todo_assignment_changed',
    'todo_completed',
    'todo_created',
    'todo_due_date_changed',
]

SUPPORT_EVENTS = DOC_SUPPORT_EVENTS + QUESTION_SUPPORT_EVENTS + MESSAGE_SUPPORT_EVENTS + TODOS_SUPPORT_EVENTS

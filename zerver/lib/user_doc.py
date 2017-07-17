from __future__ import absolute_import

from zerver.models import (
    Content,
    Message,
    UserDoc,
)

from zerver.lib.bugdown import (
    do_convert
)

def create_user_doc_from_message(message):
    rendered_content = do_convert(
        content=message.content
    )

    content = Content.objects.create(
        raw_text=message.content,
        rendered_content=rendered_content,
    )
    print(rendered_content)

    owner = message.sender
    user_doc = UserDoc.objects.create(
        owner=owner,
        content=content
    )

    ret = dict(
        user_doc_id = user_doc.id
    )
    return ret

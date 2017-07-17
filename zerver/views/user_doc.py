from __future__ import absolute_import

from django.http import HttpResponse
from django.shortcuts import render

from zerver.decorator import (
    has_request_variables,
    REQ
)

from zerver.lib.response import (
    json_success,
)
from zerver.lib.user_doc import (
    create_user_doc_from_message,
)
from zerver.models import (
    Content,
    Message,
    UserDoc,
)

@has_request_variables
def user_doc(request, user_profile,
             user_doc_id = REQ(converter=int),
            ):
    user_doc = UserDoc.objects.get(id=user_doc_id)
    rendered_content = user_doc.content.rendered_content
    context = dict(
        rendered_content=rendered_content,
        owner_name=user_doc.owner.full_name,
    )
    return render(
        request,
        'zerver/blog.html',
        context=context,
    )

@has_request_variables
def message_to_user_doc(request, user_profile,
                        message_id = REQ(converter=int),
                       ):
    message = Message.objects.get(id=message_id)
    info = create_user_doc_from_message(
        message=message
    )

    ret = dict(
        user_doc_id=info['user_doc_id']
    )
    return json_success(ret)


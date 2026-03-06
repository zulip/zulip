from datetime import datetime
from django.db import transaction
from django.http import JsonResponse, HttpRequest, HttpResponse
from django.views.decorators.http import require_GET, require_POST

from zerver.lib.message import access_message
from zerver.lib.response import json_success
from zerver.lib.typed_endpoint import typed_endpoint, typed_endpoint_without_parameters
from zerver.models.messages import Task, Message
from zerver.models.users import UserProfile


#TASKS.PY BY YANG LU
@require_POST
@typed_endpoint
def create_task(
    request: HttpRequest,
    user_profile: UserProfile,
    *,
    message_id: int,
) -> HttpResponse:

    title = request.POST.get("title")

    if not title:
        return JsonResponse({"error": "Missing title"}, status=400)

    try:
        message = Message.objects.get(id=message_id)
    except Message.DoesNotExist:
        return JsonResponse({"error": "Invalid message"}, status=404)

    user = user_profile

    #create a task and insert into postgresql
    task = Task.objects.create(
        message=message,
        assignee=user,
        creator=user,
        title=title,
    )

    return JsonResponse({
        "task_id": task.id,
        "title": task.title,
        "completed": task.completed,
    })

@require_GET
@typed_endpoint_without_parameters
def list_my_tasks(
    request: HttpRequest,
    user_profile: UserProfile,
) -> HttpResponse:
    """Get tasks assigned to current user"""
    tasks = Task.objects.filter(assignee=user_profile).select_related('message', 'creator')
    
    task_data = []
    for task in tasks:
        task_data.append({
            "task_id": task.id,
            "title": task.title,
            "completed": task.completed,
            "due_date": task.due_date.isoformat() if task.due_date else None,
            "message_id": task.message.id,
            "creator_email": task.creator.email,
            "created_at": task.created_at.isoformat(),
        })
    
    return json_success(request, {"tasks": task_data})
 
@require_POST
@typed_endpoint
@transaction.atomic(durable=True)
def update_task(
    request: HttpRequest,
    user_profile: UserProfile,
    *,
    task_id: int,
) -> HttpResponse:
    """Update task completion status"""
    try:
        task = Task.objects.select_related().get(id=task_id)
    except Task.DoesNotExist:
        return JsonResponse({"error": "Task not found"}, status=404)
    
    # Only assignee or creator can update
    if user_profile.id not in [task.assignee.id, task.creator.id]:
        return JsonResponse({"error": "Permission denied"}, status=403)
    
    # Handle completion toggle
    if 'completed' in request.POST:
        completed = request.POST.get('completed') == 'true'
        task.completed = completed
        if completed:
            task.completed_at = datetime.now()
        else:
            task.completed_at = None
        task.save()
    
    return JsonResponse({
        "task_id": task.id,
        "title": task.title,
        "completed": task.completed,
        "completed_at": task.completed_at.isoformat() if task.completed_at else None,
    })
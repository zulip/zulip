from datetime import datetime
from django.db import transaction
from django.http import JsonResponse, HttpRequest, HttpResponse
from django.views.decorators.http import require_GET, require_POST
from django.utils.timezone import now as timezone_now

from zerver.actions.message_send import internal_send_stream_message
from zerver.lib.exceptions import JsonableError
from zerver.lib.response import json_success
from zerver.lib.typed_endpoint import typed_endpoint, typed_endpoint_without_parameters
from zerver.models import Recipient
from zerver.models.messages import Task, Message, TaskTimeLog
from zerver.models.streams import Stream
from zerver.models.users import UserProfile


def _resolve_assignee(assignee_email: str, current_user: UserProfile) -> UserProfile:
    """Return the assignee UserProfile, defaulting to current_user if email is empty."""
    assignee_identifier = assignee_email.strip()
    if not assignee_identifier:
        return current_user

    try:
        return UserProfile.objects.get(delivery_email=assignee_identifier)
    except UserProfile.DoesNotExist:
        try:
            return UserProfile.objects.get(email=assignee_identifier)
        except UserProfile.DoesNotExist:
            raise JsonableError(f"User {assignee_identifier} not found")


#TASKS.PY BY YANG LU
@require_POST
@typed_endpoint
def create_task(
    request: HttpRequest,
    user_profile: UserProfile,
    *,
    message_id: int,
) -> HttpResponse:
    """Create a task linked to a specific channel message."""
    title = request.POST.get("title")
    description = request.POST.get("description", "")
    assignee_email = request.POST.get("assignee", "")
    due_date_str = request.POST.get("due_date", "")

    if not title:
        raise JsonableError("Missing title")

    try:
        message = Message.objects.select_related("recipient").get(id=message_id)
    except Message.DoesNotExist:
        raise JsonableError("Invalid message")

    assignee = _resolve_assignee(assignee_email, user_profile)

    due_date = None
    if due_date_str:
        try:
            due_date = datetime.fromisoformat(due_date_str.replace('Z', '+00:00'))
        except ValueError:
            raise JsonableError("Invalid due date format")

    task = Task.objects.create(
        message=message,
        assignee=assignee,
        creator=user_profile,
        title=title,
        description=description,
        due_date=due_date,
    )

    # Post a notification to the channel where this message lives so the
    # assignment is visible in the stream alongside the original message.
    if message.recipient.type == Recipient.STREAM:
        try:
            stream = Stream.objects.get(id=message.recipient.type_id)
            topic_name = message.subject
            assignee_display = (
                assignee.full_name if assignee.id != user_profile.id
                else "themselves"
            )
            notification_content = (
                f"**Task assigned** by {user_profile.full_name} to "
                f"{assignee_display}: **{title}**"
            )
            internal_send_stream_message(
                sender=user_profile,
                stream=stream,
                topic_name=topic_name,
                content=notification_content,
            )
        except Stream.DoesNotExist:
            pass  # Silently skip notification if stream lookup fails

    return json_success(request, {
        "task_id": task.id,
        "title": task.title,
        "description": task.description,
        "completed": task.completed,
        "due_date": task.due_date.isoformat() if task.due_date else None,
    })


@require_POST
def create_standalone_task(
    request: HttpRequest,
    user_profile: UserProfile,
) -> HttpResponse:
    """Create a task that is not linked to any channel message (e.g. from the Users overlay)."""
    title = request.POST.get("title")
    description = request.POST.get("description", "")
    assignee_email = request.POST.get("assignee", "")
    due_date_str = request.POST.get("due_date", "")

    if not title:
        raise JsonableError("Missing title")

    assignee = _resolve_assignee(assignee_email, user_profile)

    due_date = None
    if due_date_str:
        try:
            due_date = datetime.fromisoformat(due_date_str.replace('Z', '+00:00'))
        except ValueError:
            raise JsonableError("Invalid due date format")

    task = Task.objects.create(
        message=None,
        assignee=assignee,
        creator=user_profile,
        title=title,
        description=description,
        due_date=due_date,
    )

    return json_success(request, {
        "task_id": task.id,
        "title": task.title,
        "description": task.description,
        "completed": task.completed,
        "due_date": task.due_date.isoformat() if task.due_date else None,
    })


@require_GET
@typed_endpoint
def list_my_tasks(
    request: HttpRequest,
    user_profile: UserProfile,
    *,
    assignee: str = "",
) -> HttpResponse:
    """Get tasks assigned to current user or specified assignee."""
    if assignee:
        try:
            target_user = UserProfile.objects.get(email=assignee)
        except UserProfile.DoesNotExist:
            raise JsonableError(f"User {assignee} not found")
        tasks = Task.objects.filter(assignee=target_user).select_related("message__recipient", "creator")
    else:
        tasks = Task.objects.filter(assignee=user_profile).select_related("message__recipient", "creator")

    task_data = []
    for task in tasks:
        message = task.message
        stream_id = None
        topic = None
        message_id = None

        if message is not None:
            message_id = message.id
            if message.recipient.type == Recipient.STREAM:
                stream_id = message.recipient.type_id
                topic = message.subject

        total_time_seconds = 0
        active_timer = False
        try:
            time_logs = TaskTimeLog.objects.filter(task=task)
            total_time_seconds = sum(log.duration_seconds for log in time_logs)
            active_timer = time_logs.filter(end_time__isnull=True).exists()
        except Exception:
            pass

        task_data.append({
            "task_id": task.id,
            "title": task.title,
            "description": task.description,
            "completed": task.completed,
            "completed_at": task.completed_at.isoformat() if task.completed_at else None,
            "due_date": task.due_date.isoformat() if task.due_date else None,
            "message_id": message_id,
            "stream_id": stream_id,
            "topic": topic,
            "creator_email": task.creator.delivery_email,
            "creator_full_name": task.creator.full_name,
            "created_at": task.created_at.isoformat(),
            "total_time_seconds": total_time_seconds,
            "total_time_formatted": format_duration(total_time_seconds),
            "active_timer": active_timer,
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
    completed: str | None = None,
) -> HttpResponse:
    """Update task completion status."""
    if request.POST.get("_method") == "DELETE":
        return delete_task(request, user_profile, task_id=task_id)

    try:
        task = Task.objects.select_related("assignee", "creator").get(id=task_id)
    except Task.DoesNotExist:
        raise JsonableError("Task not found")

    if user_profile.id not in [task.assignee.id, task.creator.id]:
        raise JsonableError("Permission denied")

    if completed is not None:
        is_completed = completed == "true"
        task.completed = is_completed
        task.completed_at = datetime.now() if is_completed else None
        task.save()

    return json_success(request, {
        "task_id": task.id,
        "title": task.title,
        "completed": task.completed,
        "completed_at": task.completed_at.isoformat() if task.completed_at else None,
    })


@require_POST
@typed_endpoint
@transaction.atomic(durable=True)
def delete_task(
    request: HttpRequest,
    user_profile: UserProfile,
    *,
    task_id: int,
) -> HttpResponse:
    """Delete a task."""
    try:
        task = Task.objects.select_related("assignee", "creator").get(id=task_id)
    except Task.DoesNotExist:
        raise JsonableError("Task not found")

    if user_profile.id not in [task.assignee.id, task.creator.id]:
        raise JsonableError("Permission denied")

    task.delete()
    return json_success(request, {"message": "Task deleted successfully"})


@require_POST
@typed_endpoint
@transaction.atomic(durable=True)
def start_time_tracking(
    request: HttpRequest,
    user_profile: UserProfile,
    *,
    task_id: int,
) -> HttpResponse:
    """Start tracking time for a task"""
    try:
        task = Task.objects.select_related('assignee', 'creator').get(id=task_id)
    except Task.DoesNotExist:
        raise JsonableError("Task not found")
    
    # Only assignee or creator can track time
    if user_profile.id not in [task.assignee.id, task.creator.id]:
        raise JsonableError("Permission denied")
    
    # Check if there's already an active timer for this task and user
    active_timer = None
    try:
        active_timer = TaskTimeLog.objects.filter(
            task=task, 
            user=user_profile, 
            end_time__isnull=True
        ).first()
    except Exception:
        # TaskTimeLog table doesn't exist yet
        raise JsonableError("Time tracking feature not available")
    
    if active_timer:
        raise JsonableError("Timer already running for this task")
    
    # Create new time log entry
    try:
        time_log = TaskTimeLog.objects.create(
            task=task,
            user=user_profile,
            start_time=timezone_now(),
            description=request.POST.get('description', '')
        )
    except Exception:
        # TaskTimeLog table doesn't exist yet
        raise JsonableError("Time tracking feature not available")
    
    return json_success(request, {
        "time_log_id": time_log.id,
        "task_id": task.id,
        "start_time": time_log.start_time.isoformat(),
        "is_active": True,
    })

@require_POST
@typed_endpoint
@transaction.atomic(durable=True)
def stop_time_tracking(
    request: HttpRequest,
    user_profile: UserProfile,
    *,
    task_id: int,
) -> HttpResponse:
    """Stop tracking time for a task"""
    try:
        task = Task.objects.select_related('assignee', 'creator').get(id=task_id)
    except Task.DoesNotExist:
        raise JsonableError("Task not found")
    
    # Only assignee or creator can track time
    if user_profile.id not in [task.assignee.id, task.creator.id]:
        raise JsonableError("Permission denied")
    
    # Find active timer
    active_timer = None
    try:
        active_timer = TaskTimeLog.objects.filter(
            task=task, 
            user=user_profile, 
            end_time__isnull=True
        ).first()
    except Exception:
        # TaskTimeLog table doesn't exist yet
        raise JsonableError("Time tracking feature not available")
    
    if not active_timer:
        raise JsonableError("No active timer found for this task")
    
    # Stop the timer
    try:
        end_time = timezone_now()
        duration_seconds = int((end_time - active_timer.start_time).total_seconds())
        
        active_timer.end_time = end_time
        active_timer.duration_seconds = duration_seconds
        active_timer.save()
    except Exception:
        # TaskTimeLog table doesn't exist yet
        raise JsonableError("Time tracking feature not available")
    
    return json_success(request, {
        "time_log_id": active_timer.id,
        "task_id": task.id,
        "start_time": active_timer.start_time.isoformat(),
        "end_time": active_timer.end_time.isoformat(),
        "duration_seconds": duration_seconds,
        "duration_formatted": format_duration(duration_seconds),
    })

@require_GET
@typed_endpoint
def get_task_time_logs(
    request: HttpRequest,
    user_profile: UserProfile,
    *,
    task_id: int,
) -> HttpResponse:
    """Get all time logs for a task"""
    try:
        task = Task.objects.select_related('assignee', 'creator').get(id=task_id)
    except Task.DoesNotExist:
        raise JsonableError("Task not found")
    
    # Only assignee or creator can view time logs
    if user_profile.id not in [task.assignee.id, task.creator.id]:
        raise JsonableError("Permission denied")
    
    try:
        time_logs = TaskTimeLog.objects.filter(task=task).order_by('-created_at')
    except Exception:
        # TaskTimeLog table doesn't exist yet
        raise JsonableError("Time tracking feature not available")
    
    logs_data = []
    for log in time_logs:
        logs_data.append({
            "id": log.id,
            "user_email": log.user.email,
            "start_time": log.start_time.isoformat(),
            "end_time": log.end_time.isoformat() if log.end_time else None,
            "duration_seconds": log.duration_seconds,
            "duration_formatted": format_duration(log.duration_seconds),
            "description": log.description,
            "is_active": log.end_time is None,
            "created_at": log.created_at.isoformat()
        })
    
    # Calculate total time
    total_seconds = sum(log.duration_seconds for log in time_logs)
    
    return json_success(request, {
        "task_id": task.id,
        "time_logs": logs_data,
        "total_time_seconds": total_seconds,
        "total_time_formatted": format_duration(total_seconds),
        "active_timer_count": len([log for log in time_logs if log.end_time is None]),
    })

@require_GET
@typed_endpoint_without_parameters
def get_my_time_stats(
    request: HttpRequest,
    user_profile: UserProfile,
) -> HttpResponse:
    """Get time tracking statistics for current user"""
    try:
        # Get all time logs for the user
        time_logs = TaskTimeLog.objects.filter(user=user_profile)
    except Exception:
        # TaskTimeLog table doesn't exist yet
        raise JsonableError("Time tracking feature not available")
    
    # Calculate statistics
    total_seconds = sum(log.duration_seconds for log in time_logs)
    completed_sessions = time_logs.filter(end_time__isnull=False).count()
    active_sessions = time_logs.filter(end_time__isnull=True).count()
    
    # Get recent activity (last 7 days)
    from datetime import timedelta
    week_ago = timezone_now() - timedelta(days=7)
    recent_logs = time_logs.filter(created_at__gte=week_ago)
    recent_seconds = sum(log.duration_seconds for log in recent_logs)
    
    # Get task breakdown
    task_breakdown = []
    tasks_with_time = Task.objects.filter(
        time_logs__user=user_profile,
        time_logs__end_time__isnull=False
    ).distinct()
    
    for task in tasks_with_time:
        task_time = TaskTimeLog.objects.filter(
            task=task, 
            user=user_profile,
            end_time__isnull=False
        )
        task_seconds = sum(log.duration_seconds for log in task_time)
        task_breakdown.append({
            "task_id": task.id,
            "task_title": task.title,
            "total_seconds": task_seconds,
            "total_formatted": format_duration(task_seconds),
            "sessions": task_time.count()
        })
    
    # Sort by total time spent
    task_breakdown.sort(key=lambda x: x['total_seconds'], reverse=True)
    
    return json_success(request, {
        "total_time_seconds": total_seconds,
        "total_time_formatted": format_duration(total_seconds),
        "completed_sessions": completed_sessions,
        "active_sessions": active_sessions,
        "recent_week_seconds": recent_seconds,
        "recent_week_formatted": format_duration(recent_seconds),
        "task_breakdown": task_breakdown[:10],
    })

def format_duration(seconds: int) -> str:
    """Format duration in seconds to human readable format"""
    if seconds < 60:
        return f"{seconds}s"
    elif seconds < 3600:
        minutes = seconds // 60
        remaining_seconds = seconds % 60
        return f"{minutes}m {remaining_seconds}s"
    else:
        hours = seconds // 3600
        remaining_minutes = (seconds % 3600) // 60
        return f"{hours}h {remaining_minutes}m"
# zerver/views/topic_restriction.py
import json
from django.http import JsonResponse, HttpResponse
from django.views.decorators.csrf import csrf_exempt
#from zerver.models import TopicRestriction
#from zerver.serializers import serialize_topic_restriction, serialize_topic_restrictions

from django.core.serializers import serialize
from zerver.models.streams import TopicRestriction, Stream,Subscription
from django.contrib.auth import get_user_model
def serialize_stream(stream):
    return stream.id
def serialize_topic_restriction(restriction):
    return {
        'id': restriction.id,
        'user': restriction.user_id,
        'stream': serialize_stream(restriction.stream),
        'topic': restriction.topic,
    }

def serialize_topic_restrictions():
    restrictions = TopicRestriction.objects.all()
    return [serialize_topic_restriction(r) for r in restrictions]

@csrf_exempt
def topic_restriction_list(request):
    if request.method == 'GET':
        user_id = request.GET.get('user_id', None)
        print(user_id)
        if user_id is not None:
            try:
                # Filter TopicRestriction instances by user ID
                restrictions = TopicRestriction.objects.filter(user_id=user_id)
                data = [serialize_topic_restriction(r) for r in restrictions]
                return JsonResponse(data, safe=False)
            except ValueError:
                return JsonResponse({'error': 'Invalid user ID'}, status=400)
        else:
            data = serialize_topic_restrictions()
            return JsonResponse(data, safe=False)
    elif request.method == 'POST':
        try:
            body = json.loads(request.body)
            user_mail = body['user']
            stream_id = body['stream']
            topic_id = body['topic']
            User = get_user_model()
            #user = User.objects.get(delivery_email=user_mail)
            stream = Stream.objects.get(id=stream_id)
            for user_email in user_mail:
                try:
                    user = User.objects.get(delivery_email=user_email)
                    TopicRestriction.objects.create(user_id=user.id, stream=stream, topic=topic_id)
                except User.DoesNotExist:
                    return JsonResponse({"error": f"User with email {user_email} does not exist"}, status=400)

            #TopicRestriction.objects.create(user_id=user.id, stream=stream, topic=topic_id)
            return JsonResponse({"MSG":"DATA INSERTED"}, status=201)  # Created
        except KeyError:
            return HttpResponse(status=400)  # Bad Request


@csrf_exempt
def topic_restriction_detail(request, pk=None):
    if pk:
        try:
            restriction = TopicRestriction.objects.get(pk=pk)
        except TopicRestriction.DoesNotExist:
            return HttpResponse(status=404)  # Not Found

        if request.method == 'GET':
            try:
                stream_id = request.GET.get('stream_id')
                topic = request.GET.get('topic')
                if not stream_id or not topic:
                    return JsonResponse({"error": "Missing stream_id or topic in request parameters"},
                                        status=400)

                stream = Stream.objects.get(id=stream_id)
                User = get_user_model()
                all_users = User.objects.all()
                restricted_users = User.objects.filter(topicrestriction__stream=stream,
                                                       topicrestriction__topic=topic)
                unrestricted_users = all_users.exclude(id__in=restricted_users)

                restricted_users_data = [{"id": user.idPOST, "email": user.email} for user in restricted_users]
                unrestricted_users_data = [{"id": user.id, "email": user.email} for user in
                                           unrestricted_users]

                return JsonResponse({
                    "restricted_users": restricted_users_data,
                    "unrestricted_users": unrestricted_users_data
                }, status=200)
            except Stream.DoesNotExist:
                return JsonResponse({"error": "Stream with specified ID does not exist"}, status=404)
            except Exception as e:
                return JsonResponse({"error": str(e)}, status=500)
        elif request.method == 'PUT':
            try:
                body = json.loads(request.body)
                restriction.user_id = body.get('user', restriction.user_id)
                restriction.stream_id = body.get('stream', restriction.stream_id)
                restriction.topic_id = body.get('topic', restriction.topic_id)
                restriction.save()
                return JsonResponse(serialize_topic_restriction(restriction))
            except KeyError:
                return HttpResponse(status=400)  # Bad Request
        elif request.method == 'DELETE':
            restriction.delete()
            return JsonResponse({"MSG": "DATA DELETED"}, status=201)

    elif request.method == 'GET':
        try:
            stream_id = request.GET.get('stream_id')
            topic = request.GET.get('topic')
            if not stream_id or not topic:
                return JsonResponse({"error": "Missing stream_id or topic in request parameters"},
                                    status=400)

            stream = Stream.objects.get(id=stream_id)

            User = get_user_model()
            subscriptions = Subscription.objects.filter(recipient=stream.recipient)
            subscribed_users = User.objects.filter(subscription__in=subscriptions)
            restricted_users = subscribed_users.filter(topicrestriction__stream=stream,
                                                       topicrestriction__topic=topic)
            unrestricted_users = subscribed_users.exclude(id__in=restricted_users)
            restricted_users_data = [{"id": user.id, "email": user.delivery_email, "stream_id":stream_id,"topic":topic} for user in restricted_users]
            unrestricted_users_data = [{"id": user.id, "email": user.delivery_email, "stream_id":stream_id,"topic":topic} for user in
                                       unrestricted_users]

            return JsonResponse({
                "restricted_users": restricted_users_data,
                "unrestricted_users": unrestricted_users_data
            }, status=200)
        except Stream.DoesNotExist:
            return JsonResponse({"error": "Stream with specified ID does not exist"}, status=404)
        except Exception as e:
            return JsonResponse({"error": str(e)}, status=500)
    elif request.method == 'POST':
        try:
            body = json.loads(request.body)
            user_emails = body['user_emails']
            stream_id = body['stream_id']
            topic = body['topic']

            User = get_user_model()
            errors = []
            for user_email in user_emails:
                try:
                    user = User.objects.get(delivery_email=user_email)
                    restriction = TopicRestriction.objects.get(user_id=user.id, stream=stream_id, topic=topic)
                    print(topic)
                    restriction.delete()
                except User.DoesNotExist:
                    errors.append(f"User with email {user_email} does not exist")
                except TopicRestriction.DoesNotExist:
                    errors.append(
                        f"TopicRestriction for user {user_email} and stream {stream_id} does not exist")

            if errors:
                return JsonResponse({"errors": errors}, status=400)
            return JsonResponse({"MSG": "DATA DELETED"}, status=200)
        except KeyError:
            return JsonResponse({"error": "Missing user_emails or stream_id in request body"}, status=400)
        except Exception as e:
            return JsonResponse({"error": str(e)}, status=500)

    return HttpResponse(status=405)

@csrf_exempt
def topic_restriction_detail_ui(request, pk=None):
    if request.method == 'GET':
        try:
            stream_id = request.GET.get('stream_id')
            topic = request.GET.get('topic')
            user_mail = request.GET.get('user')
            flag = request.GET.get('flag')
            errors = []
            if not stream_id or not topic:
                return JsonResponse({"error": "Missing stream_id or topic in request parameters"},
                                    status=400)

            #stream = Stream.objects.get(id=stream_id)
            User = get_user_model()
            user = User.objects.get(delivery_email=user_mail)
            stream = Stream.objects.get(id=stream_id)
            if flag == 'Y':
                restriction = TopicRestriction.objects.get(user_id=user.id, stream=stream, topic=topic)
                restriction.delete()
            else:
                TopicRestriction.objects.create(user_id=user.id, stream=stream, topic=topic)

        except User.DoesNotExist:
            errors.append(f"User with email {user_mail} does not exist")
        except TopicRestriction.DoesNotExist:
            errors.append(
                f"TopicRestriction for user {user_mail} and stream {stream_id} does not exist")

        if errors:
            return JsonResponse({"errors": errors}, status=400)
        return JsonResponse({"MSG": "Success"}, status=200)


import os
import dateutil.parser
import logging
import subprocess
import ujson
import requests
from requests.models import Response
from copy import copy

from django.conf import settings
from django.forms.models import model_to_dict
from django.utils.timezone import now as timezone_now
from typing import Any, Dict, List, Set, Tuple

from zerver.models import UserProfile, Recipient
from zerver.lib.export import MESSAGE_BATCH_CHUNK_SIZE
from zerver.data_import.import_util import ZerverFieldsT, build_zerver_realm, \
    build_avatar, build_subscription, build_recipient, build_usermessages, \
    build_defaultstream, process_avatars, build_realm, build_stream, \
    build_message, create_converted_data_files, make_subscriber_map, \
    build_attachment, process_uploads

# This importer utilizes the ryver api calls to extract data and has some limitations
# 1. The api user/bot/account credentials provided must be a member of all forums and teams you wish to extract
#   In Ryver even admin roles can only use the api for things they participate in
#   Ryver support will provide a list of all forums/teams that exist if you request it from support, in order to alert users to add the export user
# 2. 1 implies there is no method to extract private messages en masse

## TODO ##
# Files/attachments
    # Maybe don't dump s3 paths as the file name. Should eliminate name conflicts though
    # Requests seems to be appending the extension despite already providing the extension in the zulip_path
    # external attachments might wish to be downloaded to remove reliance on ryver's s3
        # These are typically under 'external_url' attribute of a field, then check for the presence of s3 in the url?
    # Forum API messages don't seem to have the attachment field available
# Stream descriptions are not being loaded properly on import?
# Webhook messages have an override field for displayName but you can't do that in zulip so all messages will show incorrectly
    # This means createUser shows as the one who made the webhook even if its used by multiple services/entities
    # Might not fix this, it would require making dummy users after the fact
# Multithreaded processing more things later
# Maybe actually add message chunk size somewhere instead of dumping everything into one file
# Need to check if Memberships expansions to forums or teams/workrooms are limited at all.

# stubs
GitterDataT = List[Dict[str, Any]]
realm_id = 0

# request header for GET api calls
headers = {'accept': 'application/json'}
config = {}
# What a ryver null will equal, maybe an option later
ryver_null = ''

def extract_message_attachments(
                                message: dict,
                                zulip_message_id: int,
                                zulip_user_id: int,
                                # user_map: dict,
                                # uploads: list,
                                attachments_list: list,
                                uploads_list: list
                                # message_id: int,
                                ) -> (bool, bool, bool, list):
    """
        Zulip upload: the actual file on zulip server/s3 bucket 
        Zulip attachment: the pointer between the upload and a message (one upload -> many attachments -> many messages)
    """
    markdown_links = []
    has_attachment = False
    has_image = False
    has_link = False
    # if a message has attachments it will fall under ['attachments']['results'] as a list
    # We are assuming the createUser of the attachment is the same as the user who posted the message
    # We are also assuming the attachments url's are available publically. In most cases I believe it's ryver's s3
    
    # Ryver can be a bit weird in the api depending on where its queried from, but all these should be present if there is an attachment
    if 'attachments' in message and 'results' in message['attachments'] and type(message['attachments']['results']) == list and len(message['attachments']['results']) > 0:
        for file in message['attachments']['results']:
            has_attachment = True
            has_link = True
            file_extension = ''
            # Some field that may be improved upon in the future, does pdf garuntee a preview?
            # file['type'] some examples ['image/png', 'application/pdf', 'image/jpeg', 'message/rfc822', 'application/vnd.tcpdump.pcap']
            if 'image/' in file['type']:
                has_image = True
                file_extension = '.' + file['type'][6:]
            if 'application/' in file['type']:
                file_extension = '.' + file['type'][12:]
            
            # zulip expects size, created, name
            file_info = {}
            file_info['size'] = file['fileSize']
            file_info['created'] = float(dateutil.parser.parse(file['createDate']).timestamp())
            file_info['name'] = file['fileName']
            # This is a fix to allow image rendering and proper file extensions
            file_info['zulip_path'] = file['url'] if file_extension == '' else file['url'] + file_extension

            # path would be the download url
            # s3_path will be the local path
            upload = dict(
                path=file['url'],
                realm_id=realm_id,
                content_type=None,
                user_profile_id=zulip_user_id,
                last_modified=file_info['created'],
                # user_profile_email=email, # Is this used anywhere?
                s3_path=file_info['zulip_path'],
                size=file_info['size'])
            uploads_list.append(upload)
            # Here we want s3_path to match upload
            build_attachment(realm_id=realm_id,
                            message_ids={zulip_message_id},
                            user_id=zulip_user_id,
                            fileinfo=file_info,
                            s3_path=file_info['zulip_path'],
                            zerver_attachment=attachments_list
                            )
            # Markdown to add the uploads to the end of messages, match s3_path of upload again
            markdown_links.append('[{file_title}](/user_uploads/{file_path})'.format(file_title=file['fileName'], file_path=file_info['zulip_path']))

    # TODO external_link/external_url work goes here
    # This is only applicable if you expect the files to become unavailable in the future. For now the URL's should show in the zulip messages anyways.
            
    return has_attachment, has_link, has_image, markdown_links

def create_zulip_topics_and_import_messages(user_map: dict,
                                            user_bot_map: dict,
                                            subscriber_map: List[ZerverFieldsT],
                                            forum_stream_map: List[ZerverFieldsT],
                                            teams_workrooms_stream_map: List[ZerverFieldsT],
                                            forum_recipient_map: dict,
                                            tw_recipient_map: dict) -> (List[ZerverFieldsT], List[ZerverFieldsT]):
    # Note: user id mentions are not implemented yet, I believe they just add to a notification stream though
        # Part of the import code deletes the key in realm['zerver_messages']['user_mentions'] in the import_realm.py anyways?
    # Note: you don't need to do anything special to create topics, just make a message to the topic name for a recipient group
    # Note: Zulip has a max topic name length of 60
    # Note: Zulip has a max content length of 10000
    # Note: Zulip Message Contents have a not-null constraint, this affects attachment only messages
    logging.info("==Ryver Data Handler - Importing Ryver Messages==")
    message_json = {}
    message_id = 0
    attachment_id = 0
    messages = []
    uploads_list = []
    attachments_list = []
    # Usermessages are required if you want old messages to actually show up (by default), this might not matter with setting stream history on
    # Above might not be true after setting the history flag
    usermessages = []
    
    # Handle forums
    for forum_id in forum_stream_map:
        raw_forum = api_call_build_execute('/forums(id={})'.format(forum_id), only_count=False) # Just to re-extract the name
        
        # Main Topic
        raw_forum_main_topic_chats_count = api_call_build_execute('/forums(id={})/Chat.History()'.format(forum_id), only_count=True) # Chat.History() is a shortcut for count here
        if raw_forum_main_topic_chats_count > 0:
            raw_forum_main_topic_chats = api_call_build_execute('/forums(id={})/Chat.History()'.format(forum_id), results=raw_forum_main_topic_chats_count, hard_results=True, select_str='from,body,when,attachments', expand='attachments', only_count=False)
            #main_topic_name = raw_forum['name'][:60]
            main_topic_name = '(no topic)' # This seems to be more zulip standard for the main topic
            
            print("Importing messages from Forum '{}'".format(raw_forum['name']))
            main_topic_recipient_id = forum_recipient_map[forum_id]
            for main_topic_chat in raw_forum_main_topic_chats:
                # TODO attachments don't seem to be part of the api here?
                message_time = float(dateutil.parser.parse(main_topic_chat['when']).timestamp())
                main_topic_content = main_topic_chat['body'] # This can be null which is None in json
                if main_topic_content is not None:
                    main_topic_content = main_topic_content[:10000]
                else:
                    main_topic_content = ''
                rendered_content = None
                ryver_user_id = main_topic_chat['from']['id']
                
                zulip_message = build_message(topic_name=main_topic_name,
                                                date_sent=message_time,
                                                message_id=message_id,
                                                content=main_topic_content,
                                                rendered_content=rendered_content,
                                                user_id=user_map[ryver_user_id],
                                                recipient_id=main_topic_recipient_id)
                
                build_usermessages(
                    zerver_usermessage=usermessages,
                    subscriber_map=subscriber_map,
                    recipient_id=main_topic_recipient_id,
                    message_id=message_id,
                    mentioned_user_ids=[],
                    is_private=False,
                )
                has_attachment, has_link, has_image, markdown_links = extract_message_attachments(message=main_topic_chat, zulip_message_id=zulip_message['id'], zulip_user_id=user_map[ryver_user_id], attachments_list=attachments_list, uploads_list=uploads_list)
                if has_attachment:
                    zulip_message['has_attachment'] = True
                    zulip_message['has_link'] = has_link
                    zulip_message['has_image'] = has_image
                    zulip_message['content'] += '\n'.join(markdown_links)
                messages.append(zulip_message)
                message_id += 1
                
                
            # Forum Topics
            # Topics only exists if this flag is true
            if raw_forum['sharePosts'] == True:
                raw_forum_topics_count = api_call_build_execute('/forums(id={})/Post.Stream()'.format(forum_id), only_count=True)
                if raw_forum_topics_count > 0:
                    raw_forum_topics = api_call_build_execute('/forums(id={})/Post.Stream()'.format(forum_id), only_count=False, results=raw_forum_topics_count, hard_results=True, select_str='id,subject,createDate,body,createUser,attachments', expand='attachments')
                    
                    for forum_topic in raw_forum_topics:
                        # The first message is embedded in this object and not available in /posts
                        post_id = forum_topic['id'] # used below for the rest of the messages
                        topic_name = forum_topic['subject'][:60]
                        topic_content = forum_topic['body'] # This can be null which is None in json
                        if topic_content is not None:
                            topic_content = topic_content[:10000]
                        else:
                            topic_content = ''
                        rendered_content = None
                        
                        zulip_message = build_message(topic_name=topic_name,
                                                        date_sent=float(dateutil.parser.parse(forum_topic['createDate']).timestamp()),
                                                        message_id=message_id,
                                                        content=topic_content,
                                                        rendered_content=rendered_content,
                                                        user_id=user_map[forum_topic['createUser']['id']],
                                                        recipient_id=main_topic_recipient_id)
                        build_usermessages(
                            zerver_usermessage=usermessages,
                            subscriber_map=subscriber_map,
                            recipient_id=main_topic_recipient_id,
                            message_id=message_id,
                            mentioned_user_ids=[],
                            is_private=False,
                        )
                        has_attachment, has_link, has_image, markdown_links = extract_message_attachments(message=forum_topic, zulip_message_id=zulip_message['id'], zulip_user_id=user_map[forum_topic['createUser']['id']], attachments_list=attachments_list, uploads_list=uploads_list)
                        if has_attachment:
                            zulip_message['has_attachment'] = True
                            zulip_message['has_link'] = has_link
                            zulip_message['has_image'] = has_image
                            zulip_message['content'] += '\n'.join(markdown_links)
                        messages.append(zulip_message)
                        message_id += 1
                        
                        # Get the rest of the forum topic messages
                        raw_topic_posts_count = api_call_build_execute('/posts(id={})/comments'.format(post_id), only_count=True)
                        if raw_topic_posts_count > 0:
                            raw_topic_posts = api_call_build_execute('/posts(id={})/comments'.format(post_id), only_count=False, results=raw_topic_posts_count, select_str='createDate,createUser,comment,attachments', expand='createUser,attachments')
                            
                            for post in raw_topic_posts:
                                post_content = post['comment'] # This can be null which is None in json
                                if post_content is not None:
                                    post_content = post_content[:10000]
                                else:
                                    post_content = '*Created Topic*' # Maybe change the for to enumerate to only apply this on message #1
                                zulip_message = build_message(topic_name=topic_name,
                                                                date_sent=float(dateutil.parser.parse(post['createDate']).timestamp()),
                                                                message_id=message_id,
                                                                content=post_content,
                                                                rendered_content=rendered_content,
                                                                user_id=user_map[post['createUser']['id']],
                                                                recipient_id=main_topic_recipient_id)
                                build_usermessages(
                                    zerver_usermessage=usermessages,
                                    subscriber_map=subscriber_map,
                                    recipient_id=main_topic_recipient_id,
                                    message_id=message_id,
                                    mentioned_user_ids=[],
                                    is_private=False,
                                )
                                has_attachment, has_link, has_image, markdown_links = extract_message_attachments(message=post, zulip_message_id=zulip_message['id'], zulip_user_id=user_map[post['createUser']['id']], attachments_list=attachments_list, uploads_list=uploads_list)
                                if has_attachment:
                                    zulip_message['has_attachment'] = True
                                    zulip_message['has_link'] = has_link
                                    zulip_message['has_image'] = has_image
                                    zulip_message['content'] += '\n'.join(markdown_links)
                                messages.append(zulip_message)
                                message_id += 1
                
    # Handle Teams/Workrooms
    for tw_id in teams_workrooms_stream_map:
        raw_tw = api_call_build_execute('/workrooms(id={})'.format(tw_id), only_count=False) # Just to re-extract the name
        
        # Main Topic
        raw_tw_main_topic_chats_count = api_call_build_execute('/workrooms(id={})/Chat.History()'.format(tw_id), only_count=True) # Chat.History() is a shortcut for count here
        if raw_tw_main_topic_chats_count > 0:
            raw_tw_main_topic_chats = api_call_build_execute('/workrooms(id={})/Chat.History()'.format(tw_id), results=raw_tw_main_topic_chats_count, hard_results=True, select_str='from,body,when,attachments', expand='attachments', only_count=False)
            # main_topic_name = raw_tw['name'][:60]
            main_topic_name = '(no topic)' # Zulip standard for main topic in a stream
            print("Importing messages from Team '{}'".format(raw_tw['name']))
            main_topic_recipient_id = tw_recipient_map[tw_id]
            for main_topic_chat in raw_tw_main_topic_chats:
                message_time = float(dateutil.parser.parse(main_topic_chat['when']).timestamp())
                main_topic_content = main_topic_chat['body'] # This can be null which is None in json
                if main_topic_content is not None:
                    main_topic_content = main_topic_content[:10000]
                else:
                    main_topic_content = ''
                rendered_content = None
                ryver_user_id = main_topic_chat['from']['id']
                if ryver_user_id not in user_map:
                    print('test for errors 12322')
                    continue
                
                zulip_message = build_message(topic_name=main_topic_name,
                                                date_sent=message_time,
                                                message_id=message_id,
                                                content=main_topic_content,
                                                rendered_content=rendered_content,
                                                user_id=user_map[ryver_user_id],
                                                recipient_id=main_topic_recipient_id)
                build_usermessages(
                    zerver_usermessage=usermessages,
                    subscriber_map=subscriber_map,
                    recipient_id=main_topic_recipient_id,
                    message_id=message_id,
                    mentioned_user_ids=[],
                    is_private=False,
                )
                has_attachment, has_link, has_image, markdown_links = extract_message_attachments(message=main_topic_chat, zulip_message_id=zulip_message['id'], zulip_user_id=user_map[ryver_user_id], attachments_list=attachments_list, uploads_list=uploads_list)
                if has_attachment:
                    zulip_message['has_attachment'] = True
                    zulip_message['has_link'] = has_link
                    zulip_message['has_image'] = has_image
                    zulip_message['content'] += '\n'.join(markdown_links)
                messages.append(zulip_message)
                message_id += 1
        
        # Team/Workroom Topics
        # Topics only exists if this flag is true
        if raw_tw['sharePosts'] == True:
            raw_tw_topics_count = api_call_build_execute('/workrooms(id={})/Post.Stream()'.format(tw_id), only_count=True)
            if raw_tw_topics_count > 0:
                raw_tw_topics = api_call_build_execute('/workrooms(id={})/Post.Stream()'.format(tw_id), only_count=False, results=raw_tw_topics_count, hard_results=True, select_str='id,subject,createDate,body,createUser,attachments', expand='attachments')
                
                for tw_topic in raw_tw_topics:
                    # The first message is embedded in this object and not available in /posts
                    post_id = tw_topic['id'] # used below for the rest of the messages
                    topic_name = tw_topic['subject'][:60]
                    tw_topic_content = tw_topic['body'] # This can't be null? Safety
                    if tw_topic_content is not None:
                        tw_topic_content = tw_topic_content[:10000]
                    else:
                        # When you create a topic from previous messages it will be empty. You might be able to retreive those from an expand.
                        tw_topic_content = '*Created Topic*' # Maybe change this to enumerate to only apply to message 1 
                    rendered_content = None
                    
                    
                    zulip_message = build_message(topic_name=topic_name,
                                                    date_sent=float(dateutil.parser.parse(tw_topic['createDate']).timestamp()),
                                                    message_id=message_id,
                                                    content=tw_topic_content,
                                                    rendered_content=rendered_content,
                                                    user_id=user_map[tw_topic['createUser']['id']],
                                                    recipient_id=main_topic_recipient_id)
                    build_usermessages(
                        zerver_usermessage=usermessages,
                        subscriber_map=subscriber_map,
                        recipient_id=main_topic_recipient_id,
                        message_id=message_id,
                        mentioned_user_ids=[],
                        is_private=False,
                    )
                    has_attachment, has_link, has_image, markdown_links = extract_message_attachments(message=tw_topic, zulip_message_id=zulip_message['id'], zulip_user_id=user_map[tw_topic['createUser']['id']], attachments_list=attachments_list, uploads_list=uploads_list)
                    if has_attachment:
                        zulip_message['has_attachment'] = True
                        zulip_message['has_link'] = has_link
                        zulip_message['has_image'] = has_image
                        zulip_message['content'] += '\n'.join(markdown_links)
                    messages.append(zulip_message)
                    message_id += 1
                    
                    # Get the rest of the messages
                    raw_topic_posts_count = api_call_build_execute('/posts(id={})/comments'.format(post_id), only_count=True)
                    if raw_topic_posts_count > 0:
                        raw_topic_posts = api_call_build_execute('/posts(id={})/comments'.format(post_id), only_count=False, results=raw_topic_posts_count, select_str='createDate,comment,createUser,attachments', expand='createUser,attachments')
                        
                        for post in raw_topic_posts:
                            post_content = post['comment'] # This can be null
                            if post_content is not None:
                                post_content = post_content[:10000]
                            else:
                                post_content = ''
                            zulip_message = build_message(topic_name=topic_name,
                                                            date_sent=float(dateutil.parser.parse(post['createDate']).timestamp()),
                                                            message_id=message_id,
                                                            content=post_content,
                                                            rendered_content=rendered_content,
                                                            user_id=user_map[post['createUser']['id']],
                                                            recipient_id=main_topic_recipient_id)
                            build_usermessages(
                                zerver_usermessage=usermessages,
                                subscriber_map=subscriber_map,
                                recipient_id=main_topic_recipient_id,
                                message_id=message_id,
                                mentioned_user_ids=[],
                                is_private=False,
                            )
                            has_attachment, has_link, has_image, markdown_links = extract_message_attachments(message=post, zulip_message_id=zulip_message['id'], zulip_user_id=user_map[post['createUser']['id']], attachments_list=attachments_list, uploads_list=uploads_list)
                            if has_attachment:
                                zulip_message['has_attachment'] = True
                                zulip_message['has_link'] = has_link
                                zulip_message['has_image'] = has_image
                                zulip_message['content'] += '\n'.join(markdown_links)
                            messages.append(zulip_message)
                            message_id += 1
    
    message_json['zerver_message'] = messages
    message_json['zerver_usermessage'] = usermessages
    message_filename = os.path.join(config['output_dir'], "messages-000001.json")
    logging.info("==Ryver Data Handler - Writing Messages to {}==".format(message_filename))
    write_data_to_file(os.path.join(message_filename), message_json)
    logging.info("==Ryver Data Handler - Finished Importing Ryver Messages==")
    return uploads_list, attachments_list


def create_subscriptions(user_profiles: List[ZerverFieldsT], 
                        user_map: dict,
                        streams: List[ZerverFieldsT], 
                        default_stream: List[ZerverFieldsT], 
                        forum_stream_map: List[ZerverFieldsT],
                        forum_stream_members: dict,
                        teams_workrooms_stream_map: List[ZerverFieldsT],
                        teams_workrooms_stream_members: dict):
    """
    Returns:
    """
    logging.info("==Ryver Data Handler - Building Subscriptions==")
    recipient_groups = []
    forum_recipient_map = {}
    tw_recipient_map = {}
    subscriptions = []
    recipient_group_id = 0
    subscription_id = 0
    
    # NOTE: There should only be 1 recipient group per stream as far as I know
    # NOTE: build_recipient type_id is equivilent to stream_id
    # Sub everyone to default stream
    d_recipient = build_recipient(type_id=0, recipient_id=0, type=Recipient.STREAM)
    recipient_groups.append(d_recipient)
    for user in user_profiles:
        subscription = build_subscription(recipient_id=0, user_id=user['id'], subscription_id=subscription_id)
        subscriptions.append(subscription)
        subscription_id += 1
    recipient_group_id += 1
    
    # Everyone subs to themselves, is this necessary?
    for user in user_profiles:
        recipient = build_recipient(type_id=user['id'], recipient_id=recipient_group_id, type=Recipient.PERSONAL)
        subscription = build_subscription(recipient_id=recipient_group_id, user_id=user['id'], subscription_id=subscription_id)
        recipient_groups.append(recipient)
        subscriptions.append(subscription)
        recipient_group_id += 1
        subscription_id += 1
    
    # For each forum sub all members
    for forum_id in forum_stream_map:
        if forum_id not in forum_stream_members:
            logging.info("Zulip forum_id {} had no key in forum_stream_members".format(forum_id))
            continue
        else:
            if forum_id not in forum_recipient_map:
                forum_recipient_map[forum_id] = recipient_group_id
            recipient = build_recipient(type_id=forum_stream_map[forum_id], recipient_id=recipient_group_id, type=Recipient.STREAM)
            recipient_groups.append(recipient)
            for forum_member_id in forum_stream_members[forum_id]:
                if forum_member_id not in user_map:
                    print("Ryver forum member id {} not found in user_map".format(forum_member_id))
                    continue
                else:
                    subscription = build_subscription(recipient_id=recipient_group_id, user_id=user_map[forum_member_id], subscription_id=subscription_id)
                    subscriptions.append(subscription)
                subscription_id += 1
            recipient_group_id += 1
    
    # For each team/workroom sub all members
    for tw_id in teams_workrooms_stream_map:
        if tw_id not in teams_workrooms_stream_members:
            logging.info("Zulip tw_id {} had no key in teams_workrooms_stream_members".format(forum_id))
            continue
        else:
            if tw_id not in tw_recipient_map:
                tw_recipient_map[tw_id] = recipient_group_id
            recipient = build_recipient(type_id=teams_workrooms_stream_map[tw_id], recipient_id=recipient_group_id, type=Recipient.STREAM)
            recipient_groups.append(recipient)
            for tw_member_id in teams_workrooms_stream_members[tw_id]:
                if tw_member_id not in user_map:
                    print("Ryver forum member id {} not found in user_map".format(forum_member_id))
                    continue
                else:
                    subscription = build_subscription(recipient_id=recipient_group_id, user_id=user_map[tw_member_id], subscription_id=subscription_id)
                    subscriptions.append(subscription)
                subscription_id += 1
            recipient_group_id += 1
    

    logging.info("==Ryver Data Handler - Finished Building Subscriptions==")
    
    # NOTE topic inside forums/teams/workrooms will be handled seperately. Their membership is soft in the sense anyone in the recipient group can join them but it only lists participants
    return recipient_groups, subscriptions, forum_recipient_map, tw_recipient_map

def create_streams_and_map(timestamp: Any) -> (list, dict, dict, dict, dict, dict):
    """
    Returns:
    1. streams, which is a list of all streams
    2. default_stream, which is the default stream
    3. forum_stream_map
    4. teams_workrooms_stream_map
    """
    logging.info("==Ryver Data Handler - Building Streams and User Lists (may take awhile)==")
    raw_api_forums = []
    raw_api_workrooms_teams = []
    raw_api_topics = []
    streams = []
    forum_stream_map = {} # type: Dict[int, int]
    forum_stream_members = {} # type: Dict[int, list[user_ryver_id]]
    teams_workrooms_stream_map = {} # type: Dict[int, int]
    teams_workrooms_stream_members = {} # type: Dict[int, list[user_ryver_id]]
    # topics_stream_map = {} # type: Dict[int, int]
    
    # Default stream will have no content
    stream_name = 'Default Stream'
    stream_description = "Imported users from ryver (no content)"
    stream_id = 1 # skipping over it for the default stream
    dstream = build_stream(date_created=timestamp, realm_id=realm_id, name=stream_name, description=stream_description, stream_id=0)
    streams.append(dstream)
    # NOTE: Default stream has to be in a list or it will throw an error on import because it will treat the object['stream'] as a python integer slice
    default_stream = [build_defaultstream(realm_id=realm_id, stream_id=0, defaultstream_id=0)]
    
    # get the raw forum data, 
    # !! NOTE the user has to be a participant/member of the forum or workroom/team in order to query these !!
    forum_count = api_call_build_execute('/forums', results=0, only_count=True)
    if forum_count > 0:
        raw_api_forums = api_call_build_execute('/forums', only_count=False, select_str='id,name,description,createDate,members', expand='members', results=forum_count) # results=1
        
        for forum in raw_api_forums:
            if forum['id'] not in forum_stream_map:
                forum_stream_map[forum['id']] = stream_id
                # Ryver API will None/nulls on some optional fields
                try:
                    if forum['description'] == None:
                        forum['description'] = ""
                    print("Processing Forum '{}'".format(forum['name']))
                    # Ryver is default invite only channels so we will maintain that
                    stream = build_stream(
                        date_created=int(dateutil.parser.parse(forum['createDate']).timestamp()),
                        realm_id=realm_id,
                        name=forum['name'],
                        description=forum['description'],
                        stream_id=stream_id,
                        invite_only=True)
                    streams.append(stream)
                    members = forum['members']['results']
                    if len(members):
                        if forum['id'] not in forum_stream_members:
                            forum_stream_members[forum['id']] = []
                        for member in members:
                            # a membership['id'] is not a user id so we unfortunately need to dive again for the member field, this is horribly optimized
                            member_user = api_call_build_execute('/workroomMembers(id={})'.format(member['id']), select_str='member', expand='member', only_count=False)
                            # You can have more than 1 member type through notifications
                            if member_user['member']['id'] not in forum_stream_members[forum['id']]:
                                forum_stream_members[forum['id']].append(member_user['member']['id'])
                except Exception as e:
                    print('Failed to parse forum with exception {}:\n{}'.format(e, forum))
                stream_id += 1
    
    # get the raw team/workroom data, 
    # !! NOTE the user has to be a participant/member of the forum or workroom/team in order to query these !!
    team_workroom_count = api_call_build_execute('/workrooms', only_count=True)
    if team_workroom_count > 0:
        raw_api_workrooms_teams = api_call_build_execute('/workrooms', only_count=False, select_str='id,description,createDate,name,members', expand='members', results=team_workroom_count) # results=1
        for tw in raw_api_workrooms_teams:
            if tw['id'] not in teams_workrooms_stream_map:
                teams_workrooms_stream_map[tw['id']] = stream_id
                # Ryver API will None/nulls on some optional fields
                try:
                    if tw['description'] == None:
                        tw['description'] = ""
                    print("Processing Team '{}'".format(tw['name']))
                    # Ryver is default invite only channels so we will maintain that
                    stream = build_stream(
                        date_created=int(dateutil.parser.parse(tw['createDate']).timestamp()),
                        realm_id=realm_id,
                        name=tw['name'],
                        description=tw['description'],
                        stream_id=stream_id,
                        invite_only=True)
                    streams.append(stream)
                    members = tw['members']['results']
                    if len(members):
                        if tw['id'] not in teams_workrooms_stream_members:
                            teams_workrooms_stream_members[tw['id']] = []
                        for member in members:
                            # a membership['id'] is not a user id so we unfortunately need to dive again for the member field, this is horribly optimized
                            member_user = api_call_build_execute('/workroomMembers(id={})'.format(member['id']), select_str='member', expand='member', only_count=False)
                            # You can have more than 1 member type through notifications
                            if member_user['member']['id'] not in teams_workrooms_stream_members[tw['id']]:
                                teams_workrooms_stream_members[tw['id']].append(member_user['member']['id'])
                except Exception as e:
                    print('Failed to parse team/workroom with exception {}:\n{}'.format(e, forum))
                stream_id += 1
        
    # We want users to see history if they are subbed after the import by default (to match ryver behavior)
    for stream in streams:
        stream['history_public_to_subscribers'] = True
    logging.info("==Ryver Data Handler - Finished Building Streams and User Lists==")
    return streams, default_stream, forum_stream_map, teams_workrooms_stream_map, forum_stream_members, teams_workrooms_stream_members
    
    

def create_user_profiles_and_map(user_count: int) -> (list, dict, dict):
    logging.info("==Ryver Data Handler - Building user profiles and map==")
    raw_api_users = []
    user_profiles = []
    user_map = {} # type: Dict[int, int]
    user_bot_map = {} # type: Dict[str, int] DEPRECATED
    user_id = 0
    
    # get the raw data
    raw_api_users = api_call_build_execute('/users', results=user_count, only_count=False, select_str='id,displayName,emailAddress,type,username,createDate,locked')
    
    for user in raw_api_users:
        if user['id'] not in user_map:
            user_map[user['id']] = user_id
            # Ryver Bots do not have email and it's a constraint on the database so we need to depend on displayName which is unique for them
            if user['emailAddress'] is None:
                user['emailAddress'] = '{}@ryverimport.com'.format(user['displayName']).replace(' ', '_')
                print('Affixed fake email for user "{}" who is of type "{}"'.format(user['displayName'], user['type']))
            
            try:
                # the ['role'] key doesn't matter zulip imports all users as basic users. If that changes its ROLE_ADMIN ROLE_USER ROLE_BOT ROLE_GUEST strings in a list
                # Build userprofile object, pointer is just a unique message id counter
                # short_name does nothing in zulip? afaik it should match emailAddress in the future
                userprofile = UserProfile(
                    full_name=user['displayName'],
                    short_name=user['username'],
                    id=user_id,
                    email=user['emailAddress'],
                    delivery_email=user['emailAddress'],
                    pointer=-1,
                    date_joined=int(dateutil.parser.parse(user['createDate']).timestamp()))
                userprofile_dict = model_to_dict(userprofile)
                # Set realm id separately as the corresponding realm is not yet a Realm model instance
                userprofile_dict['realm'] = realm_id
                # Banned/Blocked accounts need to be reblocked, but maintain any of their content
                if user['locked'] == True:
                    userprofile_dict['is_active'] = False
                # Ryver Bot messages 'createUser' property points at the bot's creator so to fix the messages we need to keep an extra map, bot name must be unique
                if user['type'] == 'bot':
                    if user['displayName'] not in user_bot_map:
                        user_bot_map[user['displayName']] = userprofile.id
                    # Bot's don't truely carry over as they aren't a real user so deactivate them
                    userprofile_dict['is_active'] = False
                user_profiles.append(userprofile_dict)
            except Exception as e:
                print('Failed to parse user with exception {}:\n{}'.format(e, user))
            user_id += 1
    
    logging.info("==Ryver Data Handler - Finished building user profiles and map==")
    return user_profiles, user_map, user_bot_map

def api_call_build_execute(endpoint: str, results: int = 0, hard_results: bool = False, only_count: bool = True, select_str: str = '', expand: str = ''):
    """
    Returns:
    1. If only requesting count just return the count
    2. If requesting results, we might need to recurse and join results. This will automatically extract results from response.json()['d']['results']
    2a. If hard_results is specified it is because the api does not support $skip for that endpoint but can query all results at once, this means results must be != 0
        This typically applies only to functional endpoints eg Chat.History()
        The reverse is true for non functional endpoints eg /users will not return more than 51 results at once no matter what
    """
    # Hints
        # users_endpoint = '/users'
        # membership_endpoint = '/workroomMembers'
            # (id=<id>)?$expand=member in order to get the user id back
            # This is for both forums and teams/workrooms
        # forums_endpoint = '/forums'
            # (id=<id>)/Chat.History() for messages onto a forum
            # (id=<id>)/Post.Stream() for topics inside the forum (chats in the topic handled by the generic /posts)
            # (id=<id>)?$expand=members for memberships of the forum
                # These need to be expanded again in /workroomMembers
        # UI Team equivilent
        # workrooms_endpoint = '/workrooms'
            # (id=<id>)/Chat.History() for messages onto a team/workroom
            # (id=<id>)/Post.Stream() for topics inside the team/workroom (chats in the topic handled by the generic /posts)
            # (id=<id>)?$expand=members for memberships of the team/workroom
                # These need to be expanded again in /workroomMembers
        # Topics in forums/teams/workrooms
        # topics_endpoint = '/posts'
            # (id=<id>)/comments for messages in a topic
            # First topic message is embedded in the response for /posts(id=<id>)
        # There is a direct attachment/files endpoint but it doens't have a clean way to point back to the source
        # files_endpoint = '/files'
            # Note this is not a direct download but just the json description object
            
    resp = None
    try:
        query_params = []
        if only_count == True:
            query_params.append('$top=0')
            query_params.append('$inlinecount=allpages')
            url = config['base_url'] + endpoint + '?' + '&'.join(query_params)
            resp = requests.get(url, headers=headers)
            if not resp.status_code == 200:
                print('not status code 200')
                raise Exception
            else:
                return response_count_extractor(resp.json())
        
        else:
            # Common query strings
            if select_str != '':
                query_params.append('$select={}'.format(select_str))
            if expand != '':
                query_params.append('$expand={}'.format(expand))
                
            # hard_results apply to the functional endpoints eg Chat.History()
            if results > 50 and hard_results == False:
                total = 0
                remaining = results
                final_results = []
                # It's fine if we have less than 50 but it can't be more than 51
                query_params.append('$top=50')
                while remaining > 0:
                    query_params2 = copy(query_params)
                    query_params2.append('$skip={}'.format(total))
                    url = config['base_url'] + endpoint + '?' + '&'.join(query_params2)
                    # print('recurse total={}, remaining={}, on url={}'.format(total, remaining, url))
                    resp = requests.get(url, headers=headers)
                    if not resp.status_code == 200:
                        print('not status code 200')
                        raise Exception
                    else:
                        json_resp = resp.json()
                        
                        if 'd' in json_resp and 'results' in json_resp['d']:
                            final_results.extend(json_resp['d']['results'])
                        else:
                            print('failure to find results')
                            raise Exception
                        remaining -= 50
                        total += 50
                print('Results for {}, {}'.format(endpoint, len(final_results)))
                return final_results
            else:
                if results != 0:
                    query_params.append('$top={}'.format(results))
                #$top isn't needed if 50 or less
                url = config['base_url'] + endpoint + '?' + '&'.join(query_params)
                resp = requests.get(url, headers=headers)
                if not resp.status_code == 200:
                    print('not status code 200')
                    raise Exception
                else:
                    json_resp = resp.json()
                    if 'd' in json_resp and 'results' in json_resp['d']:
                        return json_resp['d']['results']
                    else:
                        print('failure to find results')
                        raise Exception
    except Exception as e:
        logging.info('!!Exception raised while querying API!!')

def response_results_extractor(json_resp: dict) -> dict:
    # Typically looks like {'d': {'results': []}}
    if 'd' in json_resp and 'results' in json_resp['d']:
        return json_resp['d']['results']
    else:
        print('Failed to extract results')
        return {} 

def response_count_extractor(json_resp: dict) -> int:
    # Typically looks like {'d': {'results': [], '__count': 42}}
    if 'd' in json_resp and '__count' in json_resp['d']:
        return json_resp['d']['__count']
    else:
        print('Failed to extract count')
        return -1

def test_api_call() -> (bool, int):
    logging.info("==Ryver Data Handler - Testing api connection==")
    # Just get count of users in org for a test
    count = api_call_build_execute('/users', only_count=True)
    if count > 0:
        logging.info("==Ryver Data Handler - API test success==")
        return True, count

    logging.info("==Ryver Data Handler - API test failure, check logs for reason==")
    return False, 0

# This is the entrypoint function
def do_convert_data(base64: str, api_endpoint: str, output_dir: str, threads: int) -> None:
    # Fix the header to include provided auth and set base url
    headers['authorization'] = 'Basic ' + base64
    # Lazy globals
    config['base_url'] = api_endpoint
    config['output_dir'] = output_dir
    
    # Copied from gitter import not sure what it impacts
    realm_subdomain = ""
    domain_name = settings.EXTERNAL_HOST
    
    success, user_count = test_api_call()
    if not success:
        return

    ## Realm ##
    NOW = float(timezone_now().timestamp())
    # Default realm using google and email as auth methods, last argument is description from imported from
    zerver_realm = build_zerver_realm(realm_id, realm_subdomain, NOW, 'Ryver')  # type: List[ZerverFieldsT]
    realm = build_realm(zerver_realm, realm_id, domain_name)
    
    ## Users ##
    user_profiles, user_map, user_bot_map = create_user_profiles_and_map(user_count=user_count)
    
    ## Streams ##
    streams, default_stream, forum_stream_map, teams_workrooms_stream_map, forum_stream_members, teams_workrooms_stream_members = create_streams_and_map(timestamp=int(NOW))
    
    ## Recipient Groups and Subscriptions ##
    recipient_groups, subscriptions, forum_recipient_map, tw_recipient_map = create_subscriptions(user_profiles, user_map, streams, default_stream, forum_stream_map, forum_stream_members, teams_workrooms_stream_map, teams_workrooms_stream_members)
    
    ## Apply the base setup to the realm ##
    realm['zerver_userprofile'] = user_profiles
    realm['zerver_stream'] = streams
    realm['zerver_defaultstream'] = default_stream
    realm['zerver_recipient'] = recipient_groups
    realm['zerver_subscription'] = subscriptions
    # This is needed to fix the order of messages appearing in the UI. Alternatively fixing the message id #'s would work
    realm['sort_by_date'] = True
    
    subscriber_map = make_subscriber_map(zerver_subscription=realm['zerver_subscription'])
    
    ## Get all the messages ##
    uploads_list, attachments_list = create_zulip_topics_and_import_messages(user_map, user_bot_map, subscriber_map, forum_stream_map, teams_workrooms_stream_map, forum_recipient_map, tw_recipient_map)

    # IO realm.json
    create_converted_data_files(realm, output_dir, '/realm.json')
    # IO emoji records
    create_converted_data_files([], output_dir, '/emoji/records.json')
    # IO avatar records
    create_converted_data_files([], output_dir, '/avatars/records.json')
    # IO uploads records
    uploads_folder = os.path.join(output_dir, 'uploads')
    os.makedirs(os.path.join(uploads_folder, str(realm_id)), exist_ok=True)
    # NOTE: This is when we download the files
    uploads_records = process_uploads(uploads_list, uploads_folder, threads)
    create_converted_data_files(uploads_records, output_dir, '/uploads/records.json')
    # IO attachments records
    attachment_records = {"zerver_attachment": attachments_list}
    create_converted_data_files(attachment_records, output_dir, '/attachment.json')

    subprocess.check_call(["tar", "-czf", output_dir + '.tar.gz', output_dir, '-P'])
    
    logging.info("==Ryver Data Handler - Zulip data dump created at {} ==".format(output_dir))
    logging.info("==Ryver Data Handler - Conversion Complete. Next run \"./manage.py import '' {}\"==".format(output_dir))

def write_data_to_file(output_file: str, data: Any) -> None:
    with open(output_file, "w") as f:
        f.write(ujson.dumps(data, indent=4))

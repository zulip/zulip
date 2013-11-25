from __future__ import absolute_import

from django.conf import settings
from django.core import validators
from django.core.exceptions import ValidationError
from django.db import connection
from django.db.models import Q
from zerver.decorator import authenticated_api_view, authenticated_json_post_view, \
    has_request_variables, REQ, JsonableError, json_to_list, json_to_bool, \
    to_non_negative_int, to_non_negative_float
from django.utils.html import escape as escape_html
from django.views.decorators.csrf import csrf_exempt
from zerver.lib import bugdown
from zerver.lib.actions import recipient_for_emails, do_update_message_flags, \
    compute_mit_user_fullname, compute_irc_user_fullname, compute_jabber_user_fullname, \
    create_mirror_user_if_needed, check_send_message, do_update_message, \
    extract_recipients
from zerver.lib.cache import generic_bulk_cached_fetch
from zerver.lib.query import last_n
from zerver.lib.response import json_success, json_error
from zerver.lib.utils import statsd
from zerver.lib.validator import check_list, check_int
from zerver.models import Message, UserProfile, Stream, \
    Recipient, UserMessage, bulk_get_recipients, get_recipient, \
    get_user_profile_by_email, get_stream, valid_stream_name, \
    parse_usermessage_flags, to_dict_cache_key_id, extract_message_dict, \
    stringify_message_dict, is_super_user, is_super_user_api, \
    resolve_email_to_domain, get_realm

import re
import ujson

from zerver.lib.rest import rest_dispatch as _rest_dispatch
rest_dispatch = csrf_exempt((lambda request, *args, **kwargs: _rest_dispatch(request, globals(), *args, **kwargs)))

@authenticated_json_post_view
def json_get_old_messages(request, user_profile):
    return get_old_messages_backend(request, user_profile)

class BadNarrowOperator(Exception):
    def __init__(self, desc):
        self.desc = desc

    def to_json_error_msg(self):
        return 'Invalid narrow operator: ' + self.desc

# When you add a new operator to this, also update zerver/lib/narrow.py
class NarrowBuilder(object):
    def __init__(self, user_profile, prefix):
        self.user_profile = user_profile
        self.prefix = prefix

    def __call__(self, query, operator, operand):
        # We have to be careful here because we're letting users call a method
        # by name! The prefix 'by_' prevents it from colliding with builtin
        # Python __magic__ stuff.
        method_name = 'by_' + operator.replace('-', '_')
        if method_name == 'by_search':
            return self.do_search(query, operand)
        method = getattr(self, method_name, None)
        if method is None:
            raise BadNarrowOperator('unknown operator ' + operator)
        return query.filter(method(operand))

    # Wrapper for Q() which adds self.prefix to all the keys
    def pQ(self, **kwargs):
        return Q(**dict((self.prefix + key, kwargs[key]) for key in kwargs.keys()))

    def by_is(self, operand):
        if operand == 'private':
            return (self.pQ(recipient__type=Recipient.PERSONAL) |
                    self.pQ(recipient__type=Recipient.HUDDLE))
        elif operand == 'starred':
            return Q(flags=UserMessage.flags.starred)
        elif operand == 'mentioned':
            return Q(flags=UserMessage.flags.mentioned)
        elif operand == 'alerted':
            return Q(flags=UserMessage.flags.mentioned)
        raise BadNarrowOperator("unknown 'is' operand " + operand)

    _alphanum = frozenset(
        'abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789')

    def _pg_re_escape(self, pattern):
        """
        Escape user input to place in a regex

        Python's re.escape escapes unicode characters in a way which postgres
        fails on, u'\u03bb' to u'\\\u03bb'. This function will correctly escape
        them for postgres, u'\u03bb' to u'\\u03bb'.
        """
        s = list(pattern)
        for i, c in enumerate(s):
            if c not in self._alphanum:
                if c == '\000':
                    s[1] = '\\000'
                elif ord(c) >= 128:
                    # convert the character to hex postgres regex will take
                    # \uXXXX
                    s[i] = '\\u{:0>4x}'.format(ord(c))
                else:
                    s[i] = '\\' + c
        return ''.join(s)

    def by_stream(self, operand):
        stream = get_stream(operand, self.user_profile.realm)
        if stream is None:
            raise BadNarrowOperator('unknown stream ' + operand)

        if self.user_profile.realm.domain == "mit.edu":
            # MIT users expect narrowing to "social" to also show messages to /^(un)*social(.d)*$/
            # (unsocial, ununsocial, social.d, etc)
            m = re.search(r'^(?:un)*(.+?)(?:\.d)*$', stream.name, re.IGNORECASE)
            if m:
                base_stream_name = m.group(1)
            else:
                base_stream_name = stream.name

            matching_streams = Stream.objects.filter(realm=self.user_profile.realm,
                                                     name__iregex=r'^(un)*%s(\.d)*$' % (self._pg_re_escape(base_stream_name),))
            matching_stream_ids = [matching_stream.id for matching_stream in matching_streams]
            recipients = bulk_get_recipients(Recipient.STREAM, matching_stream_ids).values()
            return self.pQ(recipient__in=recipients)

        recipient = get_recipient(Recipient.STREAM, type_id=stream.id)
        return self.pQ(recipient=recipient)

    def by_topic(self, operand):
        if self.user_profile.realm.domain == "mit.edu":
            # MIT users expect narrowing to topic "foo" to also show messages to /^foo(.d)*$/
            # (foo, foo.d, foo.d.d, etc)
            m = re.search(r'^(.*?)(?:\.d)*$', operand, re.IGNORECASE)
            if m:
                base_topic = m.group(1)
            else:
                base_topic = operand

            # Additionally, MIT users expect the empty instance and
            # instance "personal" to be the same.
            if base_topic in ('', 'personal', '(instance "")'):
                regex = r'^(|personal|\(instance ""\))(\.d)*$'
            else:
                regex = r'^%s(\.d)*$' % (self._pg_re_escape(base_topic),)

            return self.pQ(subject__iregex=regex)

        return self.pQ(subject__iexact=operand)

    def by_sender(self, operand):
        try:
            sender = get_user_profile_by_email(operand)
        except UserProfile.DoesNotExist:
            raise BadNarrowOperator('unknown user ' + operand)

        return self.pQ(sender=sender)

    def by_near(self, operand):
        return Q()

    def by_id(self, operand):
        return self.pQ(id=operand)

    def by_pm_with(self, operand):
        if ',' in operand:
            # Huddle
            try:
                emails = [e.strip() for e in operand.split(',')]
                recipient = recipient_for_emails(emails, False,
                    self.user_profile, self.user_profile)
            except ValidationError:
                raise BadNarrowOperator('unknown recipient ' + operand)
            return self.pQ(recipient=recipient)
        else:
            # Personal message
            self_recipient = get_recipient(Recipient.PERSONAL, type_id=self.user_profile.id)
            if operand == self.user_profile.email:
                # Personals with self
                return self.pQ(recipient__type=Recipient.PERSONAL,
                          sender=self.user_profile, recipient=self_recipient)

            # Personals with other user; include both directions.
            try:
                narrow_profile = get_user_profile_by_email(operand)
            except UserProfile.DoesNotExist:
                raise BadNarrowOperator('unknown user ' + operand)

            narrow_recipient = get_recipient(Recipient.PERSONAL, narrow_profile.id)
            return ((self.pQ(sender=narrow_profile) & self.pQ(recipient=self_recipient)) |
                    (self.pQ(sender=self.user_profile) & self.pQ(recipient=narrow_recipient)))

    def do_search(self, query, operand):
        if "postgres" in settings.DATABASES["default"]["ENGINE"]:
            tsquery = "plainto_tsquery('zulip.english_us_search', %s)"
            where = "search_tsvector @@ " + tsquery
            content_matches = "ts_match_locs_array('zulip.english_us_search', rendered_content, " \
                + tsquery + ")"
            # We HTML-escape the subject in Postgres to avoid doing a server round-trip
            subject_matches = "ts_match_locs_array('zulip.english_us_search', escape_html(subject), " \
                + tsquery + ")"

            # Do quoted string matching.  We really want phrase
            # search here so we can ignore punctuation and do
            # stemming, but there isn't a standard phrase search
            # mechanism in Postgres
            for term in re.findall('"[^"]+"|\S+', operand):
                if term[0] == '"' and term[-1] == '"':
                    term = term[1:-1]
                    query = query.filter(self.pQ(content__icontains=term) |
                                         self.pQ(subject__icontains=term))

            return query.extra(select={'content_matches': content_matches,
                                       'subject_matches': subject_matches},
                               where=[where],
                               select_params=[operand, operand], params=[operand])
        else:
            for word in operand.split():
                query = query.filter(self.pQ(content__icontains=word) |
                                     self.pQ(subject__icontains=word))
            return query

def highlight_string(string, locs):
    highlight_start = '<span class="highlight">'
    highlight_stop = '</span>'
    pos = 0
    result = ''
    for loc in locs:
        (offset, length) = loc
        result += string[pos:offset]
        result += highlight_start
        result += string[offset:offset + length]
        result += highlight_stop
        pos = offset + length
    result += string[pos:]
    return result

def get_search_fields(msg, matches_container):
    return dict(match_content=highlight_string(msg.rendered_content,
                                               matches_container.content_matches),
                match_subject=highlight_string(escape_html(msg.subject),
                                               matches_container.subject_matches))

def narrow_parameter(json):
    # FIXME: A hack to support old mobile clients
    if json == '{}':
        return None

    data = json_to_list(json)
    for elem in data:
        if not isinstance(elem, list):
            raise ValueError("element is not a list")
        if (len(elem) != 2
            or any(not isinstance(x, str) and not isinstance(x, unicode)
                   for x in elem)):
            raise ValueError("element is not a string pair")
    return data

def is_public_stream(request, stream, realm):
    if not valid_stream_name(stream):
        raise JsonableError("Invalid stream name")
    stream = get_stream(stream, realm)
    if stream is None:
        return False
    return stream.is_public()

@has_request_variables
def get_old_messages_backend(request, user_profile,
                             anchor = REQ(converter=int),
                             num_before = REQ(converter=to_non_negative_int),
                             num_after = REQ(converter=to_non_negative_int),
                             narrow = REQ('narrow', converter=narrow_parameter, default=None),
                             apply_markdown=REQ(default=True,
                                                converter=ujson.loads)):
    include_history = False
    if narrow is not None:
        for operator, operand in narrow:
            if operator == "stream":
                if is_public_stream(request, operand, user_profile.realm):
                    include_history = True
        # Disable historical messages if the user is narrowing to show
        # only starred messages (or anything else that's a property on
        # the UserMessage table).  There cannot be historical messages
        # in these cases anyway.
        for operator, operand in narrow:
            if operator == "is" and operand == "starred":
                include_history = False

    if include_history:
        prefix = ""
        wanted_fields = ["id"]
        query = Message.objects.only(*wanted_fields).order_by('id')
    else:
        prefix = "message__"
        # Conceptually this query should be
        #   UserMessage.objects.filter(user_profile=user_profile).order_by('message')
        #
        # However, our do_search code above requires that there be a
        # unique 'rendered_content' row in the query, so we need to
        # somehow get the 'message' table into the query without
        # actually fetching all the rows from the message table (since
        # doing so would cause Django to consume a lot of resources
        # rendering them).  The following achieves these objectives.
        wanted_fields = ["flags", "id", "message__id"]
        query = UserMessage.objects.select_related("message").only(*wanted_fields) \
            .filter(user_profile=user_profile).order_by('message')

    # Add some metadata to our logging data for narrows
    if narrow is not None:
        verbose_operators = []
        for (operator, operand) in narrow:
            if operator == "is":
                verbose_operators.append("is:" + operand)
            else:
                verbose_operators.append(operator)
        request._log_data['extra'] = "[%s]" % (",".join(verbose_operators),)

    num_extra_messages = 1
    is_search = False

    if narrow is None:
        use_raw_query = True
    else:
        use_raw_query = False
        num_extra_messages = 0
        build = NarrowBuilder(user_profile, prefix)
        for operator, operand in narrow:
            if operator == 'search' and not is_search:
                wanted_fields += [prefix + "subject", prefix + "rendered_content"]
                query = query.only(*wanted_fields)
                is_search = True
            query = build(query, operator, operand)

    def add_prefix(**kwargs):
        return dict((prefix + key, kwargs[key]) for key in kwargs.keys())

    # We add 1 to the number of messages requested if no narrow was
    # specified to ensure that the resulting list always contains the
    # anchor message.  If a narrow was specified, the anchor message
    # might not match the narrow anyway.
    if num_after != 0:
        num_after += num_extra_messages
    else:
        num_before += num_extra_messages

    before_result = []
    after_result = []
    if num_before != 0:
        before_anchor = anchor
        if num_after != 0:
            # Don't include the anchor in both the before query and the after query
            before_anchor = anchor - 1
        if use_raw_query:
            cursor = connection.cursor()
            # These queries should always be equivalent to what we
            # would do in the !use_raw_query case.  In this case we
            # don't actually need the zerver_message join at all.
            cursor.execute("SELECT message_id, flags FROM zerver_usermessage "
                           "WHERE user_profile_id = %s and message_id <= %s " +
                           "ORDER BY message_id DESC LIMIT %s", [user_profile.id, before_anchor, num_before])
            before_result = reversed(cursor.fetchall())
        else:
            before_result = last_n(num_before, query.filter(**add_prefix(id__lte=before_anchor)))
    if num_after != 0:
        if use_raw_query:
            cursor = connection.cursor()
            # These queries should always be equivalent to what we
            # would do in the !use_raw_query case.  In this case we
            # don't actually need the zerver_message join at all.
            cursor.execute("SELECT message_id, flags FROM zerver_usermessage "
                           "WHERE user_profile_id = %s and message_id >= %s " +
                           "ORDER BY message_id LIMIT %s", [user_profile.id, anchor, num_after])
            after_result = cursor.fetchall()
        else:
            after_result = query.filter(**add_prefix(id__gte=anchor))[:num_after]
    query_result = list(before_result) + list(after_result)

    # The following is a little messy, but ensures that the code paths
    # are similar regardless of the value of include_history.  The
    # 'user_messages' dictionary maps each message to the user's
    # UserMessage object for that message, which we will attach to the
    # rendered message dict before returning it.  We attempt to
    # bulk-fetch rendered message dicts from memcached using the
    # 'messages' list.
    search_fields = dict()
    message_ids = []
    user_message_flags = {}
    if use_raw_query:
        for row in query_result:
            (message_id, flags_val) = row
            user_message_flags[message_id] = parse_usermessage_flags(flags_val)
            message_ids.append(message_id)
    elif include_history:
        user_message_flags = dict((user_message.message_id, user_message.flags_list()) for user_message in
                                  UserMessage.objects.filter(user_profile=user_profile,
                                                             message__in=query_result))
        for message in query_result:
            message_ids.append(message.id)
            if user_message_flags.get(message.id) is None:
                user_message_flags[message.id] = ["read", "historical"]
            if is_search:
                search_fields[message.id] = get_search_fields(message, message)
    else:
        user_message_flags = dict((user_message.message_id, user_message.flags_list())
                                  for user_message in query_result)
        for user_message in query_result:
            message_ids.append(user_message.message_id)
            if is_search:
                search_fields[user_message.message_id] = \
                    get_search_fields(user_message.message, user_message)

    cache_transformer = lambda row: Message.build_dict_from_raw_db_row(row, apply_markdown)
    id_fetcher = lambda row: row['id']

    message_dicts = generic_bulk_cached_fetch(lambda message_id: to_dict_cache_key_id(message_id, apply_markdown),
                                              Message.get_raw_db_rows,
                                              message_ids,
                                              id_fetcher=id_fetcher,
                                              cache_transformer=cache_transformer,
                                              extractor=extract_message_dict,
                                              setter=stringify_message_dict)

    message_list = []
    for message_id in message_ids:
        msg_dict = message_dicts[message_id]
        msg_dict.update({"flags": user_message_flags[message_id]})
        msg_dict.update(search_fields.get(message_id, {}))
        message_list.append(msg_dict)

    statsd.incr('loaded_old_messages', len(message_list))
    ret = {'messages': message_list,
           "result": "success",
           "msg": ""}
    return json_success(ret)

@authenticated_json_post_view
def json_update_flags(request, user_profile):
    return update_message_flags(request, user_profile);

@has_request_variables
def update_message_flags(request, user_profile,
                      messages=REQ('messages', validator=check_list(check_int)),
                      operation=REQ('op'), flag=REQ('flag'),
                      all=REQ('all', converter=json_to_bool, default=False)):
    do_update_message_flags(user_profile, operation, flag, messages, all)
    return json_success({'result': 'success',
                         'messages': messages,
                         'msg': ''})

def create_mirrored_message_users(request, user_profile, recipients):
    if "sender" not in request.POST:
        return (False, None)

    sender_email = request.POST["sender"].strip().lower()
    referenced_users = set([sender_email])
    if request.POST['type'] == 'private':
        for email in recipients:
            referenced_users.add(email.lower())

    if request.client.name == "zephyr_mirror":
        user_check = mit_to_mit
        fullname_function = compute_mit_user_fullname
    elif request.client.name == "irc_mirror":
        user_check = same_realm_irc_user
        fullname_function = compute_irc_user_fullname
    elif request.client.name == "jabber_mirror":
        user_check = same_realm_user
        fullname_function = compute_jabber_user_fullname
    else:
        # Unrecognized mirroring client
        return (False, None)

    for email in referenced_users:
        # Check that all referenced users are in our realm:
        if not user_check(user_profile, email):
            return (False, None)

    # Create users for the referenced users, if needed.
    for email in referenced_users:
        create_mirror_user_if_needed(user_profile.realm, email, fullname_function)

    sender = get_user_profile_by_email(sender_email)
    return (True, sender)

def mit_to_mit(user_profile, email):
    # Are the sender and recipient both @mit.edu addresses?
    # We have to handle this specially, inferring the domain from the
    # e-mail address, because the recipient may not existing in Zulip
    # and we may need to make a stub MIT user on the fly.
    try:
        validators.validate_email(email)
    except ValidationError:
        return False

    domain = resolve_email_to_domain(email)

    return user_profile.realm.domain == "mit.edu" and domain == "mit.edu"

def same_realm_irc_user(user_profile, email):
    # Check whether the target email address is an IRC user in the
    # same realm as user_profile, i.e. if the domain were example.com,
    # the IRC user would need to be username@irc.example.com
    try:
        validators.validate_email(email)
    except ValidationError:
        return False

    domain = resolve_email_to_domain(email)

    return user_profile.realm.domain == domain.replace("irc.", "")

def same_realm_user(user_profile, email):
    try:
        validators.validate_email(email)
    except ValidationError:
        return False

    domain = resolve_email_to_domain(email)

    return user_profile.realm.domain == domain

@authenticated_api_view
def api_send_message(request, user_profile):
    return send_message_backend(request, user_profile)

@authenticated_json_post_view
def json_send_message(request, user_profile):
    return send_message_backend(request, user_profile)

# We do not @require_login for send_message_backend, since it is used
# both from the API and the web service.  Code calling
# send_message_backend should either check the API key or check that
# the user is logged in.
@has_request_variables
def send_message_backend(request, user_profile,
                         message_type_name = REQ('type'),
                         message_to = REQ('to', converter=extract_recipients),
                         forged = REQ(default=False),
                         subject_name = REQ('subject', lambda x: x.strip(), None),
                         message_content = REQ('content'),
                         domain = REQ('domain', default=None),
                         local_id = REQ(default=None, converter=to_non_negative_float),
                         queue_id = REQ(default=None)):
    client = request.client
    is_super_user = is_super_user_api(request)
    if forged and not is_super_user:
        return json_error("User not authorized for this query")

    realm = None
    if domain and domain != user_profile.realm.domain:
        if not is_super_user:
            # The email gateway bot needs to be able to send messages in
            # any realm.
            return json_error("User not authorized for this query")
        realm = get_realm(domain)
        if not realm:
            return json_error("Unknown domain " + domain)

    if client.name in ["zephyr_mirror", "irc_mirror", "jabber_mirror"]:
        # Here's how security works for mirroring:
        #
        # For private messages, the message must be (1) both sent and
        # received exclusively by users in your realm, and (2)
        # received by the forwarding user.
        #
        # For stream messages, the message must be (1) being forwarded
        # by an API superuser for your realm and (2) being sent to a
        # mirrored stream (any stream for the Zephyr and Jabber
        # mirrors, but only streams with names starting with a "#" for
        # IRC mirrors)
        #
        # The security checks are split between the below code
        # (especially create_mirrored_message_users which checks the
        # same-realm constraint) and recipient_for_emails (which
        # checks that PMs are received by the forwarding user)
        if "sender" not in request.POST:
            return json_error("Missing sender")
        if message_type_name != "private" and not is_super_user:
            return json_error("User not authorized for this query")
        (valid_input, mirror_sender) = \
            create_mirrored_message_users(request, user_profile, message_to)
        if not valid_input:
            return json_error("Invalid mirrored message")
        if client.name == "zephyr_mirror" and user_profile.realm.domain != "mit.edu":
            return json_error("Invalid mirrored realm")
        if (client.name == "irc_mirror" and message_type_name != "private" and
            not message_to[0].startswith("#")):
            return json_error("IRC stream names must start with #")
        sender = mirror_sender
    else:
        sender = user_profile

    ret = check_send_message(sender, client, message_type_name, message_to,
                             subject_name, message_content, forged=forged,
                             forged_timestamp = request.POST.get('time'),
                             forwarder_user_profile=user_profile, realm=realm,
                             local_id=local_id, sender_queue_id=queue_id)
    return json_success({"id": ret})

@authenticated_json_post_view
def json_update_message(request, user_profile):
    return update_message_backend(request, user_profile)

@has_request_variables
def update_message_backend(request, user_profile,
                           message_id=REQ(converter=to_non_negative_int),
                           subject=REQ(default=None),
                           propagate_mode=REQ(default="change_one"),
                           content=REQ(default=None)):
    if subject is None and content is None:
        return json_error("Nothing to change")
    do_update_message(user_profile, message_id, subject, propagate_mode, content)
    return json_success()

@authenticated_json_post_view
@has_request_variables
def json_fetch_raw_message(request, user_profile,
                           message_id=REQ(converter=to_non_negative_int)):
    try:
        message = Message.objects.get(id=message_id)
    except Message.DoesNotExist:
        return json_error("No such message")

    if message.sender != user_profile:
        return json_error("Message was not sent by you")

    return json_success({"raw_content": message.content})

@has_request_variables
def render_message_backend(request, user_profile, content=REQ):
    rendered_content = bugdown.convert(content, user_profile.realm.domain)
    return json_success({"rendered": rendered_content})

@authenticated_json_post_view
def json_messages_in_narrow(request, user_profile):
    return messages_in_narrow_backend(request, user_profile)

@has_request_variables
def messages_in_narrow_backend(request, user_profile,
                               msg_ids = REQ(validator=check_list(check_int)),
                               narrow = REQ(converter=narrow_parameter)):
    # Note that this function will only work on messages the user
    # actually received

    query = UserMessage.objects.select_related("message") \
                               .filter(user_profile=user_profile, message__id__in=msg_ids)
    build = NarrowBuilder(user_profile, "message__")
    for operator, operand in narrow:
        query = build(query, operator, operand)

    return json_success({"messages": dict((msg.message.id,
                                           get_search_fields(msg.message, msg))
                                          for msg in query.iterator())})

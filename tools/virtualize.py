from lib.component import ComponentFactory

the = ComponentFactory()

the.app('web').owns(
    the.virtual_component('compose'),
    the.virtual_component('home_sidebar'),
    the.virtual_component('messages'),
    the.virtual_component('misc'),
    the.virtual_component('search_bar'),
    the.virtual_component('streams'),
    the.virtual_component('users'),
)

the.virtual_component('compose').owns(
    the.js_module('compose'),
)

the.js_module('compose').owns(
    the.handlebars('compose-invite-users'),
    the.handlebars('compose_all_everyone'),
)

the.virtual_component('home_sidebar').owns(
    the.js_module('stream_list(home_sidebar)'),
)

the.js_module('stream_list(home_sidebar)').owns(
    the.handlebars('sidebar_private_message_list'),
)

the.virtual_component('messages').owns(
    the.js_module('message_list_view'),
    the.virtual_component('message'),
    the.virtual_component('message_group'),
)

the.js_module('message_list_view').owns(
    the.handlebars('bookend'),
)

the.virtual_component('message').owns(
    the.js_module('message_list_view(single_message)'),
    the.virtual_component('actions_popover'),
    the.virtual_component('message_edit'),
)

the.js_module('message_list_view(single_message)').owns(
    the.handlebars('single_message'),
)

the.virtual_component('message_edit').owns(
    the.js_module('message_edit'),
)

the.js_module('message_edit').owns(
    the.handlebars('message_edit_form'),
    the.handlebars('topic_edit_form'),
)

the.virtual_component('actions_popover').owns(
    the.js_module('popovers'),
)

the.js_module('popovers').owns(
    the.handlebars('action_popover_content'),
    the.handlebars('message_info_popover_content'),
    the.handlebars('message_info_popover_title'),
)

the.virtual_component('message_group').owns(
    the.js_module('message_list_view(group)'),
)

the.js_module('message_list_view(group)').owns(
    the.handlebars('message_group'),
    the.handlebars('recipient_row'),
)

the.virtual_component('misc').owns(
    the.virtual_component('bankruptcy'),
    the.virtual_component('invite'),
    the.virtual_component('notifications'),
    the.virtual_component('settings'),
    the.virtual_component('tutorial'),
)

the.virtual_component('bankruptcy').owns(
    the.js_module('zulip'),
)

the.js_module('zulip').owns(
    the.handlebars('bankruptcy_modal'),
)

the.virtual_component('invite').owns(
    the.js_module('invite'),
)

the.js_module('invite').owns(
    the.handlebars('invite_subscription'),
)

the.virtual_component('notifications').owns(
    the.js_module('notifications'),
)

the.js_module('notifications').owns(
    the.handlebars('compose_notification'),
    the.handlebars('notification'),
)

the.virtual_component('settings').owns(
    the.js_module('settings'),
    the.virtual_component('admin'),
    the.virtual_component('alert_words_settings'),
    the.virtual_component('bot_settings'),
    the.virtual_component('stream_settings'),
)

the.js_module('settings').owns(
    the.handlebars('settings_tab'),
)

the.virtual_component('admin').owns(
    the.js_module('admin'),
)

the.js_module('admin').owns(
    the.handlebars('admin_emoji_list'),
    the.handlebars('admin_tab'),
    the.handlebars('admin_user_list'),
    the.handlebars('admin_streams_list'),
    the.handlebars('admin_default_streams_list'),
)

the.virtual_component('alert_words_settings').owns(
    the.js_module('alert_words_ui'),
)

the.js_module('alert_words_ui').owns(
    the.handlebars('alert_word_settings_item'),
)

the.virtual_component('bot_settings').owns(
    the.js_module('settings(bot)'),
)

the.js_module('settings(bot)').owns(
    the.handlebars('bot_avatar_row'),
)

the.virtual_component('stream_settings').owns(
    the.js_module('settings(stream)'),
    the.js_module('subs(settings)'),
    the.virtual_component('stream_setting'),
)

the.virtual_component('stream_setting').owns(
    the.js_module('subs(setting)'),
)

the.js_module('subs(setting)').owns(
    the.handlebars('change_stream_privacy'),
    the.handlebars('email_address_hint'),
    the.handlebars('stream_member_list_entry'),
)

the.js_module('settings(stream)').owns(
    the.handlebars('propagate_notification_change'),
)

the.js_module('subs(settings)').owns(
    the.handlebars('subscription_table_body'),
    the.virtual_component('announce_stream_docs'),
)

the.virtual_component('announce_stream_docs').owns(
    the.js_module('subs(announce)'),
)

the.js_module('subs(announce)').owns(
    the.handlebars('announce_stream_docs'),
)

the.virtual_component('tutorial').owns(
    the.js_module('tutorial'),
)

the.js_module('tutorial').owns(
    the.handlebars('tutorial_home'),
    the.handlebars('tutorial_message'),
    the.handlebars('tutorial_reply'),
    the.handlebars('tutorial_stream'),
    the.handlebars('tutorial_subject'),
    the.handlebars('tutorial_title'),
)

the.virtual_component('search_bar').owns(
    the.js_module('tab_bar'),
)

the.js_module('tab_bar').owns(
    the.handlebars('tab_bar'),
)

the.virtual_component('streams').owns(
    the.virtual_component('stream_list'),
)

the.virtual_component('stream_list').owns(
    the.js_module('stream_list'),
    the.virtual_component('stream'),
)

the.js_module('stream_list').owns(
    the.virtual_component('stream_sidebar'),
    the.virtual_component('topic_list'),
)

the.virtual_component('topic_list').owns(
    the.js_module('stream_list(topic_list)'),
    the.virtual_component('topic'),
)

the.js_module('stream_list(topic_list)').owns(
    the.handlebars('sidebar_subject_list'),
)

the.virtual_component('topic').owns(
    the.js_module('popovers(topic)'),
)

the.js_module('popovers(topic)').owns(
    the.handlebars('topic_sidebar_actions'),
)

the.virtual_component('stream_sidebar').owns(
    the.js_module('popovers(stream)'),
    the.js_module('stream_list(sidebar)'),
)

the.js_module('stream_list(sidebar)').owns(
    the.handlebars('stream_sidebar_row'),
)

the.js_module('popovers(stream)').owns(
    the.handlebars('stream_sidebar_actions'),
)

the.virtual_component('stream').owns(
    the.js_module('stream_list(stream)'),
    the.virtual_component('stream_users'),
)

the.js_module('stream_list(stream)').owns(
    the.handlebars('stream_privacy'),
)

the.virtual_component('stream_users').owns(
    the.js_module('subs(stream_users)'),
    the.virtual_component('stream_user'),
)

the.js_module('subs(stream_users)').owns(
    the.handlebars('new_stream_users'),
)

the.virtual_component('stream_user').owns(
    the.js_module('subs(stream_user)'),
)

the.js_module('subs(stream_user)').owns(
    the.handlebars('subscription'),
    the.handlebars('subscription_setting_icon'),
    the.handlebars('subscription_type'),
)

the.virtual_component('users').owns(
    the.js_module('activity(users)'),
    the.virtual_component('active_user'),
    the.virtual_component('groups'),
)

the.js_module('activity(users)').owns(
    the.handlebars('user_presence_rows'),
)

the.virtual_component('active_user').owns(
    the.js_module('activity(active_user)'),
    the.js_module('popovers(active_user)'),
)

the.virtual_component('groups').owns(
    the.js_module('activity(groups)'),
)

the.js_module('activity(active_user)').owns(
    the.handlebars('user_presence_row'),
)

the.js_module('popovers(active_user)').owns(
    the.handlebars('user_sidebar_actions'),
)

the.js_module('activity(groups)').owns(
    the.handlebars('group_pms'),
)

def pretty_print(component):
    indent = '    '
    if not component.ownees:
        return
    print "%s.owns(" % (component.the_full_name,)
    ownees = component.ownees
    ownees = sorted(ownees, key=lambda c: c.the_full_name)
    for ownee in ownees:
        print "%s%s," % (indent, ownee.the_full_name,)
    print ")\n"
    for ownee in component.ownees:
        pretty_print(ownee)

def traverse(component, depth=0, condition=lambda c: True):
    if condition(component):
        yield depth, component
        depth += 1
    for ownee in component.ownees:
        for tup in traverse(ownee, depth, condition):
            yield tup

def find_kind(component, kind):
    res = []
    condition = lambda c: c.kind == kind
    for _, c in traverse(component, condition=condition):
        res.append(c.name)
    res.sort()
    print '--'
    print '%s (cnt=%d)' % (kind, len(res))
    for n in res:
        print '  ' + n
    print

def print_virtual_tree():
    condition = lambda c: c.kind == 'virtual_component'
    tups = list(traverse(the.app('web'), condition=condition))

    print 'VIRTUAL COMPONENT HIERARCHY (cnt=%d)' % len(tups)
    for depth, c in tups:
        indent = '    ' * depth
        print indent + c.name

def find_kinds():
    for kind in ('app', 'virtual_component', 'js_module', 'handlebars'):
        find_kind(the.app('web'), kind)

def full_walk(depth=0):
    print '--'
    print 'FULL WALK'
    for depth, c in traverse(the.app('web')):
        indent = '    ' * depth
        print indent, c.the_full_name
    print

# walk(the.app('web'))
# pretty_print(the.app('web'))
def report():
    print_virtual_tree()
    find_kinds()
    full_walk()

if __name__ == '__main__':
    report()

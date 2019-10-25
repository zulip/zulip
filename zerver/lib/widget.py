from typing import MutableMapping, Any, Optional, Tuple

import re
import json
import markdown

from zerver.models import SubMessage
import zerver.lib.bugdown as bugdown


def get_widget_data(content: str) -> Tuple[Optional[str], Optional[str]]:
    valid_widget_types = ['tictactoe', 'poll', 'todo']
    tokens = content.split(' ')

    # tokens[0] will always exist
    if tokens[0].startswith('/'):
        widget_type = tokens[0][1:]
        if widget_type in valid_widget_types:
            remaining_content = content.replace(tokens[0], '', 1).strip()
            extra_data = get_extra_data_from_widget_type(remaining_content, widget_type)
            return widget_type, extra_data

    return None, None

def get_extra_data_from_widget_type(content: str,
                                    widget_type: Optional[str]) -> Any:
    if widget_type == 'poll':
        # This is used to extract the question from the poll command.
        # The command '/poll question' will pre-set the question in the poll
        lines = content.splitlines()
        question = ''
        options = [lb]
        if lines and lines[0]:
            question = lines.pop(0).strip()
        for line in lines:
            # If someone is using the list syntax, we remove it
            # before adding an option.
            option = re.sub(r'(\s*[-*]?\s*)', '', line.strip(), 1) + 'lalal'
            if len(option) > 0:
                options.append(option)
        extra_data = {
            'question': question,
            'options': options,
        }
        return extra_data
    return None

def do_widget_post_save_actions(message: MutableMapping[str, Any]) -> None:
    '''
    This code works with the webapp; mobile and other
    clients should also start supporting this soon.
    '''
    content = message['message'].content
    sender_id = message['message'].sender_id
    message_id = message['message'].id

    widget_type = None
    extra_data = None

    widget_type, extra_data = get_widget_data(content)
    widget_content = message.get('widget_content')
    if widget_content is not None:
        # Note that we validate this data in check_message,
        # so we can trust it here.
        widget_type = widget_content['widget_type']
        extra_data = widget_content['extra_data']

    if widget_type:
        content = dict(
            widget_type=widget_type,
            extra_data=extra_data
        )
        submessage = SubMessage(
            sender_id=sender_id,
            message_id=message_id,
            msg_type='widget',
            content=json.dumps(content),
        )
        submessage.save()
        message['submessages'] = SubMessage.get_raw_db_rows([message_id])

"""class bugdownn(markdown.Markdown):
    def __init__(self, *args: Any, **kwargs: Union[bool, int, List[Any]]) -> None:
        # define default configs
        self.config = {
            "realm_filters": [kwargs['realm_filters'],
                              "Realm-specific filters for realm_filters_key %s" % (kwargs['realm'],)],
            "realm": [kwargs['realm'], "Realm id"],
            "code_block_processor_disabled": [kwargs['code_block_processor_disabled'],
                                              "Disabled for email gateway"]
        }

        super().__init__(*args, **kwargs)
        self.set_output_format('html')

    def build_parser(self) -> markdown.Markdown:
        # Build the parser using selected default features from py-markdown.
        # The complete list of all available processors can be found in the
        # super().build_parser() function.
        #
        # Note: for any py-markdown updates, manually check if we want any
        # of the new features added upstream or not; they wouldn't get
        # included by default.
        self.preprocessors = self.build_preprocessors()
        self.parser = self.build_block_parser()
        self.inlinePatterns = self.build_inlinepatterns()
        self.treeprocessors = self.build_treeprocessors()
        self.postprocessors = self.build_postprocessors()
        self.handle_zephyr_mirror()
        return self

    def build_preprocessors(self) -> markdown.util.Registry:
        # We disable the following preprocessors from upstream:
        #
        # html_block - insecure
        # reference - references don't make sense in a chat context.
        preprocessors = markdown.util.Registry()
        #preprocessors.register(BugdownListPreprocessor(self), 'hanging_lists', 35)
        preprocessors.register(markdown.preprocessors.NormalizeWhitespace(self), 'normalize_whitespace', 30)
        preprocessors.register(fenced_code.FencedBlockPreprocessor(self), 'fenced_code_block', 25)
        preprocessors.register(AlertWordsNotificationProcessor(self), 'custom_text_notifications', 20)
        return preprocessors


    def build_block_parser():
        parser = markdown.blockprocessors.BlockParser(self)
        parser.blockprocessors.register(markdown.blockprocessors.EmptyBlockProcessor(parser), 'empty', 85)
        if not self.getConfig('code_block_processor_disabled'):
            parser.blockprocessors.register(markdown.blockprocessors.CodeBlockProcessor(parser), 'code', 80)
        parser.blockprocessors.register(HashHeaderProcessor(parser), 'hashheader', 78)
        # We get priority 75 from 'table' extension
        parser.blockprocessors.register(markdown.blockprocessors.HRProcessor(parser), 'hr', 70)
        #parser.blockprocessors.register(OListProcessor(parser), 'olist', 68)
        #parser.blockprocessors.register(UListProcessor(parser), 'ulist', 65)
        parser.blockprocessors.register(ListIndentProcessor(parser), 'indent', 60)
        #parser.blockprocessors.register(BlockQuoteProcessor(parser), 'quote', 55)
        #parser.blockprocessors.register(markdown.blockprocessors.ParagraphProcessor(parser), 'paragraph', 50)
        return parser

        def build_inlinepatterns(self) -> markdown.util.Registry:
            # We disable the following upstream inline patterns:
            #
            # backtick -        replaced by ours
            # escape -          probably will re-add at some point.
            # link -            replaced by ours
            # image_link -      replaced by ours
            # autolink -        replaced by ours
            # automail -        replaced by ours
            # linebreak -       we use nl2br and consider that good enough
            # html -            insecure
            # reference -       references not useful
            # image_reference - references not useful
            # short_reference - references not useful
            # ---------------------------------------------------
            # strong_em -       for these three patterns,
            # strong2 -         we have our own versions where
            # emphasis2 -       we disable _ for bold and emphasis

            # Declare regexes for clean single line calls to .register().
            NOT_STRONG_RE = markdown.inlinepatterns.NOT_STRONG_RE
            # Custom strikethrough syntax: ~~foo~~
            DEL_RE = r'(?<!~)(\~\~)([^~\n]+?)(\~\~)(?!~)'
            # Custom bold syntax: **foo** but not __foo__
            # str inside ** must start and end with a word character
            # it need for things like "const char *x = (char *)y"
            EMPHASIS_RE = r'(\*)(?!\s+)([^\*^\n]+)(?<!\s)\*'
            ENTITY_RE = markdown.inlinepatterns.ENTITY_RE
            STRONG_EM_RE = r'(\*\*\*)(?!\s+)([^\*^\n]+)(?<!\s)\*\*\*'
            # Inline code block without whitespace stripping
            BACKTICK_RE = r'(?:(?<!\\)((?:\\{2})+)(?=`+)|(?<!\\)(`+)(.+?)(?<!`)\3(?!`))'

            # Add Inline Patterns.  We use a custom numbering of the
            # rules, that preserves the order from upstream but leaves
            # space for us to add our own.
            reg = markdown.util.Registry()
            #reg.register(BacktickPattern(BACKTICK_RE), 'backtick', 105)
            reg.register(markdown.inlinepatterns.DoubleTagPattern(STRONG_EM_RE, 'strong,em'), 'strong_em', 100)
            #reg.register(UserMentionPattern(mention.find_mentions, self), 'usermention', 95)
            reg.register(Tex(r'\B(?<!\$)\$\$(?P<body>[^\n_$](\\\$|[^$\n])*)\$\$(?!\$)\B'), 'tex', 90)
            reg.register(StreamTopicPattern(get_compiled_stream_topic_link_regex(), self), 'topic', 87)
            reg.register(StreamPattern(get_compiled_stream_link_regex(), self), 'stream', 85)
            #reg.register(Avatar(AVATAR_REGEX, self), 'avatar', 80)
            reg.register(ModalLink(r'!modal_link\((?P<relative_url>[^)]*), (?P<text>[^)]*)\)'), 'modal_link', 75)
            # Note that !gravatar syntax should be deprecated long term.
            #reg.register(Avatar(GRAVATAR_REGEX, self), 'gravatar', 70)
            #reg.register(UserGroupMentionPattern(mention.user_group_mentions, self), 'usergroupmention', 65)
            reg.register(LinkInlineProcessor(markdown.inlinepatterns.LINK_RE, self), 'link', 60)
            reg.register(AutoLink(get_web_link_regex(), self), 'autolink', 55)
            # Reserve priority 45-54 for Realm Filters
            reg = self.register_realm_filters(reg)
            reg.register(markdown.inlinepatterns.HtmlInlineProcessor(ENTITY_RE, self), 'entity', 40)
            #reg.register(markdown.inlinepatterns.SimpleTagPattern(r'(\*\*)([^\n]+?)\2', 'strong'), 'strong', 35)
            #reg.register(markdown.inlinepatterns.SimpleTagPattern(EMPHASIS_RE, 'em'), 'emphasis', 30)
            #reg.register(markdown.inlinepatterns.SimpleTagPattern(DEL_RE, 'del'), 'del', 25)
            reg.register(markdown.inlinepatterns.SimpleTextInlineProcessor(NOT_STRONG_RE), 'not_strong', 20)
            #reg.register(Emoji(EMOJI_REGEX, self), 'emoji', 15)
            #reg.register(EmoticonTranslation(emoticon_regex, self), 'translate_emoticons', 10)
            # We get priority 5 from 'nl2br' extension
            reg.register(UnicodeEmoji(unicode_emoji_regex), 'unicodeemoji', 0)
            return reg

        def register_realm_filters(self, inlinePatterns: markdown.util.Registry) -> markdown.util.Registry:
            for (pattern, format_string, id) in self.getConfig("realm_filters"):
                inlinePatterns.register(RealmFilterPattern(pattern, format_string, self),
                                        'realm_filters/%s' % (pattern,), 45)
            return inlinePatterns

    def build_treeprocessors():
        treeprocessors = markdown.util.Registry()
        # We get priority 30 from 'hilite' extension
        treeprocessors.register(markdown.treeprocessors.InlineProcessor(self), 'inline', 25)# think its needed
        treeprocessors.register(markdown.treeprocessors.PrettifyTreeprocessor(self), 'prettify', 20)
        treeprocessors.register(InlineInterestingLinkProcessor(self), 'inline_interesting_links', 15)# think its needed
        if settings.CAMO_URI:
            treeprocessors.register(InlineHttpsProcessor(self), 'rewrite_to_https', 10)
        return treeprocessors

    def build_postprocessors():

        postprocessors = markdown.util.Registry()
        postprocessors.register(markdown.postprocessors.RawHtmlPostprocessor(self), 'raw_html', 20)
        postprocessors.register(markdown.postprocessors.AndSubstitutePostprocessor(), 'amp_substitute', 15)
        postprocessors.register(markdown.postprocessors.UnescapePostprocessor(), 'unescape', 10)
        return postprocessors

    def handle_zephyr_mirror():
        if self.getConfig("realm") == ZEPHYR_MIRROR_BUGDOWN_KEY:
            # Disable almost all inline patterns for zephyr mirror
            # users' traffic that is mirrored.  Note that
            # inline_interesting_links is a treeprocessor and thus is
            # not removed
            self.inlinePatterns = get_sub_registry(self.inlinePatterns, ['autolink'])
            self.treeprocessors = get_sub_registry(self.treeprocessors, ['inline_interesting_links',
                                                                         'rewrite_to_https'])
            # insert new 'inline' processor because we have changed self.inlinePatterns
            # but InlineProcessor copies md as self.md in __init__.
            self.treeprocessors.register(markdown.treeprocessors.InlineProcessor(self), 'inline', 25)
            self.preprocessors = get_sub_registry(self.preprocessors, ['custom_text_notifications'])
            self.parser.blockprocessors = get_sub_registry(self.parser.blockprocessors, ['paragraph'])"""

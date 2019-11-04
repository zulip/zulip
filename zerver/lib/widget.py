from typing import MutableMapping, Any, Optional, Tuple, Union, List

import re
import markdown
import json

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
        options = []
        if lines and lines[0]:
            question = lines.pop(0).strip()
        for line in lines:
            # If someone is using the list syntax, we remove it
            # before adding an option.
            option = re.sub(r'(\s*[-*]?\s*)', '', line.strip(), 1)
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


class WidgetBugdown(markdown.Markdown):
    def __init__(self, *args: Any, **kwargs: Union[bool, int, List[Any]]) -> None:
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

        self.preprocessors = self.build_preprocessors()
        self.parser = self.build_block_parser()
        self.inlinePatterns = self.build_inlinepatterns()
        self.treeprocessors = self.build_treeprocessors()
        self.postprocessors = self.build_postprocessors()
        return self

    def build_preprocessors(self) -> markdown.util.Registry:

        preprocessors = markdown.util.Registry()
        preprocessors.register(markdown.preprocessors.NormalizeWhitespace(self), 'normalize_whitespace', 30)
        preprocessors.register(fenced_code.FencedBlockPreprocessor(self), 'fenced_code_block', 25)
        return preprocessors


    def build_block_parser():
        parser = markdown.blockprocessors.BlockParser(self)
        parser.blockprocessors.register(markdown.blockprocessors.EmptyBlockProcessor(parser), 'empty', 85)
        if not self.getConfig('code_block_processor_disabled'):
            parser.blockprocessors.register(markdown.blockprocessors.CodeBlockProcessor(parser), 'code', 80)
        parser.blockprocessors.register(bugdown.HashHeaderProcessor(parser), 'hashheader', 78)
        parser.blockprocessors.register(markdown.blockprocessors.HRProcessor(parser), 'hr', 70)
        parser.blockprocessors.register(bugdown.ListIndentProcessor(parser), 'indent', 60)
        return parser

    def build_inlinepatterns(self) -> markdown.util.Registry:

        NOT_STRONG_RE = markdown.inlinepatterns.NOT_STRONG_RE
        DEL_RE = r'(?<!~)(\~\~)([^~\n]+?)(\~\~)(?!~)'
        EMPHASIS_RE = r'(\*)(?!\s+)([^\*^\n]+)(?<!\s)\*'
        ENTITY_RE = markdown.inlinepatterns.ENTITY_RE
        STRONG_EM_RE = r'(\*\*\*)(?!\s+)([^\*^\n]+)(?<!\s)\*\*\*'
        BACKTICK_RE = r'(?:(?<!\\)((?:\\{2})+)(?=`+)|(?<!\\)(`+)(.+?)(?<!`)\3(?!`))'

        reg = markdown.util.Registry()
        reg.register(markdown.inlinepatterns.DoubleTagPattern(STRONG_EM_RE, 'strong,em'), 'strong_em', 100)
        reg.register(bugdown.ModalLink(r'!modal_link\((?P<relative_url>[^)]*), (?P<text>[^)]*)\)'), 'modal_link', 75)
        reg.register(bugdown.LinkInlineProcessor(markdown.inlinepatterns.LINK_RE, self), 'link', 60)
        reg.register(bugdown.AutoLink(get_web_link_regex(), self), 'autolink', 55)
        reg = self.register_realm_filters(reg)
        reg.register(markdown.inlinepatterns.HtmlInlineProcessor(ENTITY_RE, self), 'entity', 40)
        reg.register(markdown.inlinepatterns.SimpleTextInlineProcessor(NOT_STRONG_RE), 'not_strong', 20)
        return reg

    def register_realm_filters(self, inlinePatterns: markdown.util.Registry) -> markdown.util.Registry:
            for (pattern, format_string, id) in self.getConfig("realm_filters"):
                inlinePatterns.register(RealmFilterPattern(pattern, format_string, self),
                                        'realm_filters/%s' % (pattern,), 45)
            return inlinePatterns

    def build_treeprocessors():
        treeprocessors = markdown.util.Registry()
        treeprocessors.register(markdown.treeprocessors.InlineProcessor(self), 'inline', 25)# think its needed
        treeprocessors.register(markdown.treeprocessors.PrettifyTreeprocessor(self), 'prettify', 20)
        treeprocessors.register(bugdown.InlineInterestingLinkProcessor(self), 'inline_interesting_links', 15)# think its needed
        if settings.CAMO_URI:
            treeprocessors.register(bugdown.InlineHttpsProcessor(self), 'rewrite_to_https', 10)
        return treeprocessors

    def build_postprocessors():

        postprocessors = markdown.util.Registry()
        postprocessors.register(markdown.postprocessors.RawHtmlPostprocessor(self), 'raw_html', 20)
        postprocessors.register(markdown.postprocessors.AndSubstitutePostprocessor(), 'amp_substitute', 15)
        postprocessors.register(markdown.postprocessors.UnescapePostprocessor(), 'unescape', 10)
        return postprocessors

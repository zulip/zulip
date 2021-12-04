{{#if is_stream}}
<div class="message_header message_header_stream right_part">
    <div class="message-header-wrapper">
        <div class="message-header-contents">
            {{! stream link }}
            <a class="message_label_clickable narrows_by_recipient stream_label {{color_class}}"
              style="background: {{background_color}}; border-left-color: {{background_color}};"
              href="{{stream_url}}"
              title="{{#tr}}Narrow to stream &quot;{display_recipient}&quot;{{/tr}}">
                {{~! Icons for invite-only/web-public streams ~}}
                {{~#if invite_only ~}}
                    <i class="fa fa-lock recipient-row-stream-icon" title="{{t 'This is a private stream' }}" aria-label="{{t 'This is a private stream' }}"></i>
                {{/if}}

                {{~#if is_web_public ~}}
                    <i class="fa fa-globe recipient-row-stream-icon" title="{{t 'This is a web public stream' }}" aria-label="{{t 'This is a web public stream' }}"></i>
                {{/if}}

                {{~! Recipient (e.g. stream/topic or topic) ~}}
                {{~{display_recipient}~}}
            </a>

            {{! hidden narrow icon for copy-pasting }}
            <span class="copy-paste-text">&gt;</span>

            {{! topic stuff }}
            <span class="stream_topic">
                {{! topic link }}
                <a class="message_label_clickable narrows_by_topic"
                  href="{{topic_url}}"
                  title="{{#tr}}Narrow to stream &quot;{display_recipient}&quot;, topic &quot;{topic}&quot;{{/tr}}">
                    {{#if use_match_properties}}
                        {{{match_topic}}}
                    {{else}}
                        {{topic}}
                    {{/if}}
                </a>
            </span>
            <span class="recipient_bar_controls no-select">
                <span class="topic_edit hidden-for-spectators">
                    <span class="topic_edit_form" id="{{id}}"></span>
                </span>

                {{! exterior links (e.g. to a trac ticket) }}
                {{#each topic_links}}
                    <a href="{{this.url}}" target="_blank" rel="noopener noreferrer" class="no-underline">
                        <i class="fa fa-external-link-square recipient_bar_icon" data-tippy-content="Open {{this.text}}" aria-label="{{t 'External link' }}"></i>
                    </a>
                {{/each}}

                {{! edit topic pencil icon }}
                {{#if always_visible_topic_edit}}
                    <i class="fa fa-pencil always_visible_topic_edit recipient_bar_icon hidden-for-spectators" {{#unless realm_allow_message_editing}}style="display: none"{{/unless}} data-tippy-content="{{t 'Edit topic'}}" role="button" tabindex="0" aria-label="{{t 'Edit topic' }}"></i>
                {{else}}
                    {{#if on_hover_topic_edit}}
                    <i class="fa fa-pencil on_hover_topic_edit recipient_bar_icon hidden-for-spectators" {{#unless realm_allow_message_editing}}style="display: none"{{/unless}} data-tippy-content="{{t 'Edit topic'}}" role="button" tabindex="0" aria-label="{{t 'Edit topic' }}"></i>
                    {{/if}}
                {{/if}}

                {{#if user_can_resolve_topic}}
                    {{#if topic_is_resolved}}
                        <i class="fa fa-check on_hover_topic_unresolve recipient_bar_icon hidden-for-spectators" data-topic-name="{{topic}}" data-tippy-content="{{t 'Mark as unresolved' }}" role="button" tabindex="0" aria-label="{{t 'Mark as unresolved' }}"></i>
                    {{else}}
                        <i class="fa fa-check on_hover_topic_resolve recipient_bar_icon hidden-for-spectators" data-topic-name="{{topic}}" data-tippy-content="{{t 'Mark as resolved' }}" role="button" tabindex="0" aria-label="{{t 'Mark as resolved' }}"></i>
                    {{/if}}
                {{/if}}

                {{#if topic_muted}}
                    <i class="fa fa-bell-slash on_hover_topic_unmute recipient_bar_icon" data-stream-id="{{stream_id}}" data-topic-name="{{topic}}" data-tippy-content="{{t 'Unmute topic' }} (M)" role="button" tabindex="0" aria-label="{{t 'Unmute topic' }}"></i>
                {{else}}
                    <i class="fa fa-bell-slash on_hover_topic_mute recipient_bar_icon hidden-for-spectators" data-stream-id="{{stream_id}}" data-topic-name="{{topic}}" data-tippy-content="{{t 'Mute topic' }} (M)" role="button" tabindex="0" aria-label="{{t 'Mute topic' }}"></i>
                {{/if}}
            </span>
            <span class="recipient_row_date {{#if group_date_divider_html}}{{else}}hide-date{{/if}}">{{{date}}}</span>
        </div>
    </div>
</div>
{{else}}
<div class="message_header message_header_private_message dark_background">
    <div class="message-header-wrapper">
        <div class="message-header-contents">
            <a class="message_label_clickable narrows_by_recipient stream_label"
              href="{{pm_with_url}}"
              title="{{#tr}}Narrow to your private messages with {display_reply_to}{{/tr}}">
                {{#tr}}You and {display_reply_to}{{/tr}}
            </a>

            <span class="recipient_row_date {{#if group_date_divider_html}}{{else}}hide-date{{/if}}">{{{date}}}</span>
        </div>
    </div>
</div>
{{/if}}

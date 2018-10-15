import unittest

from tools.lib.pretty_print import pretty_print_html

# Note that GOOD_HTML isn't necessarily beautiful HTML.  Apart
# from adjusting indentation, we mostly leave things alone to
# respect whatever line-wrapping styles were in place before.

BAD_HTML = """
<!-- test -->
<!DOCTYPE html>



<html>
    <!-- test -->
    <head>
        <title>Test</title>
        <meta charset="utf-8" />
        <link rel="stylesheet" href="style.css" />
    </head>
    <body>
      <div><p>Hello<br />world!</p></div>
        <p>Goodbye<!-- test -->world!</p>
        <table>
           <tr>
                       <td>5</td>
           </tr>
        </table>
    <pre>
            print 'hello world'
    </pre>
         <div class = "foo"
              id = "bar"
              role = "whatever">{{ bla }}</div>
    </body>
</html>
<!-- test -->
"""

GOOD_HTML = """
<!-- test -->
<!DOCTYPE html>



<html>
    <!-- test -->
    <head>
        <title>Test</title>
        <meta charset="utf-8" />
        <link rel="stylesheet" href="style.css" />
    </head>
    <body>
        <div><p>Hello<br />world!</p></div>
        <p>Goodbye<!-- test -->world!</p>
        <table>
            <tr>
                <td>5</td>
            </tr>
        </table>
    <pre>
            print 'hello world'
    </pre>
        <div class = "foo"
          id = "bar"
          role = "whatever">{{ bla }}</div>
    </body>
</html>
<!-- test -->
"""

BAD_HTML1 = """
<html>
  <body>
    foobarfoobarfoo<b>bar</b>
  </body>
</html>
"""

GOOD_HTML1 = """
<html>
    <body>
        foobarfoobarfoo<b>bar</b>
    </body>
</html>
"""

BAD_HTML2 = """
<html>
  <body>
    {{# foobar area}}
    foobarfoobarfoo<b>bar</b>
    {{/ foobar area}}
  </body>
</html>
"""

GOOD_HTML2 = """
<html>
    <body>
        {{# foobar area}}
        foobarfoobarfoo<b>bar</b>
        {{/ foobar area}}
    </body>
</html>
"""

BAD_HTML3 = """
<html>
  <body>
    {{# foobar area}}
    foobarfoobar<blockquote>
    <p>
        FOOBAR
    </p>
                </blockquote>
    {{/ foobar area}}
  </body>
</html>
"""

GOOD_HTML3 = """
<html>
    <body>
        {{# foobar area}}
        foobarfoobar<blockquote>
                        <p>
                            FOOBAR
                        </p>
                    </blockquote>
        {{/ foobar area}}
    </body>
</html>
"""

BAD_HTML4 = """
<div>
  foo
  <p>hello</p>
  bar
</div>
"""

GOOD_HTML4 = """
<div>
    foo
    <p>hello</p>
    bar
</div>
"""

BAD_HTML5 = """
<div>
  foo
  {{#if foobar}}
  hello
  {{else}}
  bye
  {{/if}}
  bar
</div>
"""

GOOD_HTML5 = """
<div>
    foo
    {{#if foobar}}
    hello
    {{else}}
    bye
    {{/if}}
    bar
</div>
"""

BAD_HTML6 = """
<div>
  <p> <strong> <span class = "whatever">foobar </span> </strong></p>
</div>
"""

GOOD_HTML6 = """
<div>
    <p> <strong> <span class = "whatever">foobar </span> </strong></p>
</div>
"""

BAD_HTML7 = """
<div class="foobar">
<input type="foobar" name="temp" value="{{dyn_name}}"
       {{#unless invite_only}}checked="checked"{{/unless}} /> {{dyn_name}}
{{#if invite_only}}<i class="fa fa-lock"></i>{{/if}}
</div>
"""

GOOD_HTML7 = """
<div class="foobar">
    <input type="foobar" name="temp" value="{{dyn_name}}"
      {{#unless invite_only}}checked="checked"{{/unless}} /> {{dyn_name}}
    {{#if invite_only}}<i class="fa fa-lock"></i>{{/if}}
</div>
"""

BAD_HTML8 = """
{{#each test}}
  {{#with this}}
  {{#if foobar}}
    <div class="anything">{{{test}}}</div>
  {{/if}}
  {{#if foobar2}}
  {{partial "teststuff"}}
  {{/if}}
  {{/with}}
{{/each}}
"""

GOOD_HTML8 = """
{{#each test}}
    {{#with this}}
        {{#if foobar}}
        <div class="anything">{{{test}}}</div>
        {{/if}}
        {{#if foobar2}}
        {{partial "teststuff"}}
        {{/if}}
    {{/with}}
{{/each}}
"""

BAD_HTML9 = """
<form id="foobar" class="whatever">
    {{!        <div class="anothertest"> }}
    <input value="test" />
    <button type="button"><i class="test"></i></button>
    <button type="button"><i class="test"></i></button>
    {{!        </div> }}
    <div class="test"></div>
</form>
"""

GOOD_HTML9 = """
<form id="foobar" class="whatever">
    {{!        <div class="anothertest"> }}
    <input value="test" />
    <button type="button"><i class="test"></i></button>
    <button type="button"><i class="test"></i></button>
    {{!        </div> }}
    <div class="test"></div>
</form>
"""

BAD_HTML10 = """
{% block portico_content %}
<div class="test">
<i class='test'></i> foobar
</div>
<div class="test1">
{% for row in data %}
<div class="test2">
    {% for group in (row[0:2], row[2:4]) %}
    <div class="test2">
    </div>
    {% endfor %}
</div>
{% endfor %}
</div>
{% endblock %}
"""

GOOD_HTML10 = """
{% block portico_content %}
<div class="test">
    <i class='test'></i> foobar
</div>
<div class="test1">
    {% for row in data %}
    <div class="test2">
        {% for group in (row[0:2], row[2:4]) %}
        <div class="test2">
        </div>
        {% endfor %}
    </div>
    {% endfor %}
</div>
{% endblock %}
"""

BAD_HTML11 = """
<div class="test1">
  <div class="test2">
    foobar
    <div class="test2">
        </div>
</div>
</div>
"""

GOOD_HTML11 = """
<div class="test1">
    <div class="test2">
        foobar
        <div class="test2">
        </div>
    </div>
</div>
"""

BAD_HTML12 = """
<div class="test1">
<pre>
  <div class="test2">
    foobar
    <div class="test2">
        </div>
</div>
</pre>
</div>
"""

GOOD_HTML12 = """
<div class="test1">
<pre>
  <div class="test2">
    foobar
    <div class="test2">
        </div>
</div>
</pre>
</div>
"""

BAD_HTML13 = """
<div>
  {{#if this.code}}
    <div>&nbsp:{{this.name}}:</div>
  {{else}}
    {{#if this.is_realm_emoji}}
      <img src="{{this.url}}" class="emoji" />
    {{else}}
      <div/>
    {{/if}}
  {{/if}}
  <div>{{this.count}}</div>
</div>
"""

GOOD_HTML13 = """
<div>
    {{#if this.code}}
        <div>&nbsp:{{this.name}}:</div>
    {{else}}
        {{#if this.is_realm_emoji}}
        <img src="{{this.url}}" class="emoji" />
        {{else}}
        <div/>
        {{/if}}
    {{/if}}
    <div>{{this.count}}</div>
</div>
"""

BAD_HTML14 = """
<div>
  {{#if this.code}}
    <pre>Here goes some cool code.</pre>
  {{else}}
    <div>
    content of first div
    <div>
    content of second div.
    </div>
    </div>
  {{/if}}
</div>
"""

GOOD_HTML14 = """
<div>
    {{#if this.code}}
    <pre>Here goes some cool code.</pre>
    {{else}}
    <div>
        content of first div
        <div>
            content of second div.
        </div>
    </div>
    {{/if}}
</div>
"""

BAD_HTML15 = """
<div>
  <img alt=":thumbs_up:"
    class="emoji"
    src="/path/to/png"
title=":thumbs_up:"/>
    <img alt=":thumbs_up:"
        class="emoji"
        src="/path/to/png"
    title=":thumbs_up:"/>
    <img alt=":thumbs_up:"
    title=":thumbs_up:"/>
</div>
"""

GOOD_HTML15 = """
<div>
    <img alt=":thumbs_up:"
      class="emoji"
      src="/path/to/png"
      title=":thumbs_up:"/>
    <img alt=":thumbs_up:"
      class="emoji"
      src="/path/to/png"
      title=":thumbs_up:"/>
    <img alt=":thumbs_up:"
      title=":thumbs_up:"/>
</div>
"""

BAD_HTML16 = """
<div>
  {{partial "settings_checkbox"
  "setting_name" "realm_name_in_notifications"
  "is_checked" page_params.realm_name_in_notifications
  "label" settings_label.realm_name_in_notifications}}
</div>
"""

GOOD_HTML16 = """
<div>
    {{partial "settings_checkbox"
      "setting_name" "realm_name_in_notifications"
      "is_checked" page_params.realm_name_in_notifications
      "label" settings_label.realm_name_in_notifications}}
</div>
"""

BAD_HTML17 = """
<div>
  <button type="button"
class="btn btn-primary btn-small">{{t "Yes" }}</button>
<button type="button"
id="confirm_btn"
class="btn btn-primary btn-small">{{t "Yes" }}</button>
<div class = "foo"
     id = "bar"
     role = "whatever">
     {{ bla }}
</div>
</div>
"""

GOOD_HTML17 = """
<div>
    <button type="button"
      class="btn btn-primary btn-small">{{t "Yes" }}</button>
    <button type="button"
      id="confirm_btn"
      class="btn btn-primary btn-small">{{t "Yes" }}</button>
    <div class = "foo"
      id = "bar"
      role = "whatever">
        {{ bla }}
    </div>
</div>
"""

class TestPrettyPrinter(unittest.TestCase):
    def compare(self, a: str, b: str) -> None:
        self.assertEqual(a.split('\n'), b.split('\n'))

    def test_pretty_print(self) -> None:
        self.compare(pretty_print_html(GOOD_HTML), GOOD_HTML)
        self.compare(pretty_print_html(BAD_HTML), GOOD_HTML)
        self.compare(pretty_print_html(BAD_HTML1), GOOD_HTML1)
        self.compare(pretty_print_html(BAD_HTML2), GOOD_HTML2)
        self.compare(pretty_print_html(BAD_HTML3), GOOD_HTML3)
        self.compare(pretty_print_html(BAD_HTML4), GOOD_HTML4)
        self.compare(pretty_print_html(BAD_HTML5), GOOD_HTML5)
        self.compare(pretty_print_html(BAD_HTML6), GOOD_HTML6)
        self.compare(pretty_print_html(BAD_HTML7), GOOD_HTML7)
        self.compare(pretty_print_html(BAD_HTML8), GOOD_HTML8)
        self.compare(pretty_print_html(BAD_HTML9), GOOD_HTML9)
        self.compare(pretty_print_html(BAD_HTML10), GOOD_HTML10)
        self.compare(pretty_print_html(BAD_HTML11), GOOD_HTML11)
        self.compare(pretty_print_html(BAD_HTML12), GOOD_HTML12)
        self.compare(pretty_print_html(BAD_HTML13), GOOD_HTML13)
        self.compare(pretty_print_html(BAD_HTML14), GOOD_HTML14)
        self.compare(pretty_print_html(BAD_HTML15), GOOD_HTML15)
        self.compare(pretty_print_html(BAD_HTML16), GOOD_HTML16)
        self.compare(pretty_print_html(BAD_HTML17), GOOD_HTML17)

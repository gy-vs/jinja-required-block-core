import pytest

from jinja2 import DictLoader
from jinja2 import Environment
from jinja2 import TemplateRuntimeError
from jinja2 import TemplateSyntaxError

LAYOUTTEMPLATE = """\
|{% block block1 %}block 1 from layout{% endblock %}
|{% block block2 %}block 2 from layout{% endblock %}
|{% block block3 %}
{% block block4 %}nested block 4 from layout{% endblock %}
{% endblock %}|"""

LEVEL1TEMPLATE = """\
{% extends "layout" %}
{% block block1 %}block 1 from level1{% endblock %}"""

LEVEL2TEMPLATE = """\
{% extends "level1" %}
{% block block2 %}{% block block5 %}nested block 5 from level2{%
endblock %}{% endblock %}"""

LEVEL3TEMPLATE = """\
{% extends "level2" %}
{% block block5 %}block 5 from level3{% endblock %}
{% block block4 %}block 4 from level3{% endblock %}
"""

LEVEL4TEMPLATE = """\
{% extends "level3" %}
{% block block3 %}block 3 from level4{% endblock %}
"""

WORKINGTEMPLATE = """\
{% extends "layout" %}
{% block block1 %}
  {% if false %}
    {% block block2 %}
      this should work
    {% endblock %}
  {% endif %}
{% endblock %}
"""

DOUBLEEXTENDS = """\
{% extends "layout" %}
{% extends "layout" %}
{% block block1 %}
  {% if false %}
    {% block block2 %}
      this should work
    {% endblock %}
  {% endif %}
{% endblock %}
"""


@pytest.fixture
def env():
    return Environment(
        loader=DictLoader(
            {
                "layout": LAYOUTTEMPLATE,
                "level1": LEVEL1TEMPLATE,
                "level2": LEVEL2TEMPLATE,
                "level3": LEVEL3TEMPLATE,
                "level4": LEVEL4TEMPLATE,
                "working": WORKINGTEMPLATE,
                "doublee": DOUBLEEXTENDS,
            }
        ),
        trim_blocks=True,
    )


class TestInheritance:
    def test_layout(self, env):
        tmpl = env.get_template("layout")
        assert tmpl.render() == (
            "|block 1 from layout|block 2 from layout|nested block 4 from layout|"
        )

    def test_level1(self, env):
        tmpl = env.get_template("level1")
        assert tmpl.render() == (
            "|block 1 from level1|block 2 from layout|nested block 4 from layout|"
        )

    def test_level2(self, env):
        tmpl = env.get_template("level2")
        assert tmpl.render() == (
            "|block 1 from level1|nested block 5 from "
            "level2|nested block 4 from layout|"
        )

    def test_level3(self, env):
        tmpl = env.get_template("level3")
        assert tmpl.render() == (
            "|block 1 from level1|block 5 from level3|block 4 from level3|"
        )

    def test_level4(self, env):
        tmpl = env.get_template("level4")
        assert tmpl.render() == (
            "|block 1 from level1|block 5 from level3|block 3 from level4|"
        )

    def test_super(self, env):
        env = Environment(
            loader=DictLoader(
                {
                    "a": "{% block intro %}INTRO{% endblock %}|"
                    "BEFORE|{% block data %}INNER{% endblock %}|AFTER",
                    "b": '{% extends "a" %}{% block data %}({{ '
                    "super() }}){% endblock %}",
                    "c": '{% extends "b" %}{% block intro %}--{{ '
                    "super() }}--{% endblock %}\n{% block data "
                    "%}[{{ super() }}]{% endblock %}",
                }
            )
        )
        tmpl = env.get_template("c")
        assert tmpl.render() == "--INTRO--|BEFORE|[(INNER)]|AFTER"

    def test_working(self, env):
        env.get_template("working")

    def test_reuse_blocks(self, env):
        tmpl = env.from_string(
            "{{ self.foo() }}|{% block foo %}42{% endblock %}|{{ self.foo() }}"
        )
        assert tmpl.render() == "42|42|42"

    def test_preserve_blocks(self, env):
        env = Environment(
            loader=DictLoader(
                {
                    "a": "{% if false %}{% block x %}A{% endblock %}"
                    "{% endif %}{{ self.x() }}",
                    "b": '{% extends "a" %}{% block x %}B{{ super() }}{% endblock %}',
                }
            )
        )
        tmpl = env.get_template("b")
        assert tmpl.render() == "BA"

    def test_dynamic_inheritance(self, env):
        env = Environment(
            loader=DictLoader(
                {
                    "default1": "DEFAULT1{% block x %}{% endblock %}",
                    "default2": "DEFAULT2{% block x %}{% endblock %}",
                    "child": "{% extends default %}{% block x %}CHILD{% endblock %}",
                }
            )
        )
        tmpl = env.get_template("child")
        for m in range(1, 3):
            assert tmpl.render(default=f"default{m}") == f"DEFAULT{m}CHILD"

    def test_multi_inheritance(self, env):
        env = Environment(
            loader=DictLoader(
                {
                    "default1": "DEFAULT1{% block x %}{% endblock %}",
                    "default2": "DEFAULT2{% block x %}{% endblock %}",
                    "child": (
                        "{% if default %}{% extends default %}{% else %}"
                        "{% extends 'default1' %}{% endif %}"
                        "{% block x %}CHILD{% endblock %}"
                    ),
                }
            )
        )
        tmpl = env.get_template("child")
        assert tmpl.render(default="default2") == "DEFAULT2CHILD"
        assert tmpl.render(default="default1") == "DEFAULT1CHILD"
        assert tmpl.render() == "DEFAULT1CHILD"

    def test_scoped_block(self, env):
        env = Environment(
            loader=DictLoader(
                {
                    "default.html": "{% for item in seq %}[{% block item scoped %}"
                    "{% endblock %}]{% endfor %}"
                }
            )
        )
        t = env.from_string(
            "{% extends 'default.html' %}{% block item %}{{ item }}{% endblock %}"
        )
        assert t.render(seq=list(range(5))) == "[0][1][2][3][4]"

    def test_super_in_scoped_block(self, env):
        env = Environment(
            loader=DictLoader(
                {
                    "default.html": "{% for item in seq %}[{% block item scoped %}"
                    "{{ item }}{% endblock %}]{% endfor %}"
                }
            )
        )
        t = env.from_string(
            '{% extends "default.html" %}{% block item %}'
            "{{ super() }}|{{ item * 2 }}{% endblock %}"
        )
        assert t.render(seq=list(range(5))) == "[0|0][1|2][2|4][3|6][4|8]"

    def test_scoped_block_after_inheritance(self, env):
        env = Environment(
            loader=DictLoader(
                {
                    "layout.html": """
            {% block useless %}{% endblock %}
            """,
                    "index.html": """
            {%- extends 'layout.html' %}
            {% from 'helpers.html' import foo with context %}
            {% block useless %}
                {% for x in [1, 2, 3] %}
                    {% block testing scoped %}
                        {{ foo(x) }}
                    {% endblock %}
                {% endfor %}
            {% endblock %}
            """,
                    "helpers.html": """
            {% macro foo(x) %}{{ the_foo + x }}{% endmacro %}
            """,
                }
            )
        )
        rv = env.get_template("index.html").render(the_foo=42).split()
        assert rv == ["43", "44", "45"]

    def test_level1_required(self, env):
        env = Environment(
            loader=DictLoader(
                {
                    "default": "{% block x required %}{# comment #}\n {% endblock %}",
                    "level1": "{% extends 'default' %}{% block x %}[1]{% endblock %}",
                }
            )
        )
        rv = env.get_template("level1").render()
        assert rv == "[1]"

    def test_level2_required(self, env):
        env = Environment(
            loader=DictLoader(
                {
                    "default": "{% block x required %}{% endblock %}",
                    "level1": "{% extends 'default' %}{% block x %}[1]{% endblock %}",
                    "level2": "{% extends 'default' %}{% block x %}[2]{% endblock %}",
                }
            )
        )
        rv1 = env.get_template("level1").render()
        rv2 = env.get_template("level2").render()

        assert rv1 == "[1]"
        assert rv2 == "[2]"

    def test_level3_required(self, env):
        env = Environment(
            loader=DictLoader(
                {
                    "default": "{% block x required %}{% endblock %}",
                    "level1": "{% extends 'default' %}",
                    "level2": "{% extends 'level1' %}{% block x %}[2]{% endblock %}",
                    "level3": "{% extends 'level2' %}",
                }
            )
        )
        t1 = env.get_template("level1")
        t2 = env.get_template("level2")
        t3 = env.get_template("level3")

        with pytest.raises(TemplateRuntimeError, match="Required block 'x' not found"):
            assert t1.render()

        assert t2.render() == "[2]"
        assert t3.render() == "[2]"

    def test_required_chain_redeclared_required(self):
        # an intermediate template may keep the block required (only
        # whitespace and comments), and a later descendant can fill it
        env = Environment(
            loader=DictLoader(
                {
                    "default": "{% block x required %}\n{# base #}\n{% endblock %}",
                    "middle": "{% extends 'default' %}"
                    "{% block x required %}  {# still required #}{% endblock %}",
                    "child": "{% extends 'middle' %}{% block x %}ok{% endblock %}",
                }
            )
        )
        assert env.get_template("child").render().strip() == "ok"

    def test_non_required_block_allows_content(self):
        # ordinary blocks keep accepting text, expressions and control
        # structures such as if/for and nested blocks
        env = Environment(
            loader=DictLoader({"t": "{% block x %}a{{ 1 }}{% if 1 %}i{% endif %}"
                               "{% for v in [2] %}{{ v }}{% endfor %}"
                               "{% block n %}n{% endblock %}{% endblock %}"})
        )
        assert env.get_template("t").render() == "a1i2n"

    @pytest.mark.parametrize(
        "body",
        [
            "",
            " ",
            "\n",
            "\t\n  \n\t",
            "{# comment #}",
            "\n  {# comment #}\n ",
            "{# one #} {# two #}",
            "{#- stripped -#}",
        ],
    )
    def test_required_whitespace_and_comments(self, body):
        env = Environment(
            loader=DictLoader(
                {
                    "default": f"{{% block x required %}}{body}{{% endblock %}}",
                    "child": "{% extends 'default' %}{% block x %}[1]{% endblock %}",
                }
            )
        )
        assert env.get_template("default") is not None
        assert env.get_template("child").render() == "[1]"

    def test_required_line_comment(self):
        env = Environment(
            loader=DictLoader(
                {
                    "default": "{% block x required %}## line comment\n"
                    "{% endblock %}",
                    "child": "{% extends 'default' %}{% block x %}[1]{% endblock %}",
                }
            ),
            line_comment_prefix="##",
        )
        assert env.get_template("default") is not None
        assert env.get_template("child").render() == "[1]"

    @pytest.mark.parametrize(
        "body",
        [
            "data",
            "data {# comment #}",
            "{# comment #} data",
            "{{ x }}",
            "{{ foo() }}",
            "{% if true %}a{% endif %}",
            "{% for item in [1] %}{{ item }}{% endfor %}",
            "{% block y %}y{% endblock %}",
            "{% set y = 1 %}",
            "{% include 'missing' ignore missing %}",
            "{% raw %}x{% endraw %}",
            "{% filter upper %}x{% endfilter %}",
        ],
    )
    def test_invalid_required(self, body):
        env = Environment(
            loader=DictLoader(
                {"default": f"{{% block x required %}}{body}{{% endblock %}}"}
            )
        )
        with pytest.raises(
            TemplateSyntaxError,
            match="Required blocks can only contain comments or whitespace",
        ):
            env.get_template("default")

    def test_invalid_required_other_templates(self):
        # parents containing control structures (nested blocks, if) fail
        # the same way as parents containing plain output, when a child
        # inherits from them
        env = Environment(
            loader=DictLoader(
                {
                    "default": "{% block x required %}data{% endblock %}",
                    "default1": "{% block x required %}{% block y %}"
                    "{% endblock %}  {% endblock %}",
                    "default2": "{% block x required %}{% if true %}"
                    "{% endif %}  {% endblock %}",
                    "level1": "{% if default %}{% extends default %}"
                    "{% else %}{% extends 'default' %}{% endif %}"
                    "{%- block x %}CHILD{% endblock %}",
                }
            )
        )
        t = env.get_template("level1")
        for name in ("default", "default1", "default2"):
            with pytest.raises(
                TemplateSyntaxError,
                match="Required blocks can only contain comments or whitespace",
            ):
                t.render(default=name)

    def test_required_error_lineno(self):
        env = Environment(
            loader=DictLoader(
                {
                    "text": "{% block x required %}\n  {# fine #}\nbad\n"
                    "{% endblock %}",
                    "if": "{% block x required %}\n  \n"
                    "{% if true %}a{% endif %}\n{% endblock %}",
                    "expr": "{% block x required %}\n\n{{ x }}\n{% endblock %}",
                    "nested": "{% block x required %}\n\n\n\n"
                    "{% block y %}y{% endblock %}\n{% endblock %}",
                }
            )
        )
        for name, lineno in (
            ("text", 3),
            ("if", 3),
            ("expr", 3),
            ("nested", 5),
        ):
            with pytest.raises(TemplateSyntaxError) as exc_info:
                env.get_template(name)
            assert exc_info.value.lineno == lineno

    def test_required_with_scope(self, env):
        env = Environment(
            loader=DictLoader(
                {
                    "default1": "{% for item in seq %}[{% block item scoped required %}"
                    "{% endblock %}]{% endfor %}",
                    "child1": "{% extends 'default1' %}{% block item %}"
                    "{{ item }}{% endblock %}",
                    "default2": "{% for item in seq %}[{% block item required scoped %}"
                    "{% endblock %}]{% endfor %}",
                    "child2": "{% extends 'default2' %}{% block item %}"
                    "{{ item }}{% endblock %}",
                }
            )
        )
        t1 = env.get_template("child1")
        t2 = env.get_template("child2")

        assert t1.render(seq=list(range(3))) == "[0][1][2]"

        # scoped must come before required
        with pytest.raises(TemplateSyntaxError):
            t2.render(seq=list(range(3)))

    def test_duplicate_required_or_scoped(self, env):
        env = Environment(
            loader=DictLoader(
                {
                    "default1": "{% for item in seq %}[{% block item "
                    "scoped scoped %}}{{% endblock %}}]{{% endfor %}}",
                    "default2": "{% for item in seq %}[{% block item "
                    "required required %}}{{% endblock %}}]{{% endfor %}}",
                    "child": "{% if default %}{% extends default %}{% else %}"
                    "{% extends 'default1' %}{% endif %}{%- block x %}"
                    "CHILD{% endblock %}",
                }
            )
        )
        tmpl = env.get_template("child")
        with pytest.raises(TemplateSyntaxError):
            tmpl.render(default="default1", seq=list(range(3)))
            tmpl.render(default="default2", seq=list(range(3)))


class TestBugFix:
    def test_fixed_macro_scoping_bug(self, env):
        assert (
            Environment(
                loader=DictLoader(
                    {
                        "test.html": """\
        {% extends 'details.html' %}

        {% macro my_macro() %}
        my_macro
        {% endmacro %}

        {% block inner_box %}
            {{ my_macro() }}
        {% endblock %}
            """,
                        "details.html": """\
        {% extends 'standard.html' %}

        {% macro my_macro() %}
        my_macro
        {% endmacro %}

        {% block content %}
            {% block outer_box %}
                outer_box
                {% block inner_box %}
                    inner_box
                {% endblock %}
            {% endblock %}
        {% endblock %}
        """,
                        "standard.html": """
        {% block content %}&nbsp;{% endblock %}
        """,
                    }
                )
            )
            .get_template("test.html")
            .render()
            .split()
            == ["outer_box", "my_macro"]
        )

    def test_double_extends(self, env):
        """Ensures that a template with more than 1 {% extends ... %} usage
        raises a ``TemplateError``.
        """
        with pytest.raises(TemplateRuntimeError, match="extended multiple times"):
            env.get_template("doublee").render()

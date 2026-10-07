from pathlib import Path

from jinja2 import Environment, FileSystemLoader, StrictUndefined, select_autoescape

# autoescape for .html only: a name like "<script>" typed at signup must show
# up as text in the HTML email, not run as markup. Plain-text templates are
# left alone, because escaping there would print "&lt;" literally.
# StrictUndefined: a variable the template needs but the caller forgot is an
# error, instead of a silently blank spot in an email.
_env = Environment(
    loader=FileSystemLoader(Path(__file__).parent / "templates"),
    autoescape=select_autoescape(["html"]),
    undefined=StrictUndefined,
    trim_blocks=True,
    lstrip_blocks=True,
)


def render_email(template: str, /, **context: object) -> tuple[str, str]:
    """Render templates/<template>.txt and .html. Returns (text, html). The template
    name is positional-only so a template variable called `name` cannot clash with it.

    Every email is sent as both. Clients that cannot show HTML (or readers who
    turn it off) get the text version."""
    return (
        _env.get_template(f"{template}.txt").render(**context),
        _env.get_template(f"{template}.html").render(**context),
    )

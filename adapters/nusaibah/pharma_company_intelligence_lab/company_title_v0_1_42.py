"""Display title from the supplied company name; identity stays in the partition."""
import html


def company_title(name):
    # Render inert single-line business text, including names with Markdown symbols.
    value=' '.join(str(name or '').split())
    if not value:
        value='Company Profile'
    value=html.escape(value, quote=False)
    for char in ('#', '*', '_', '`', '[', ']', '\\'):
        value=value.replace(char, '&#'+str(ord(char))+';')
    return value

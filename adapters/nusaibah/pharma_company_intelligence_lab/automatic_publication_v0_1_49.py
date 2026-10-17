"""Honor incomplete admission before accessing a publishable result's fields."""
try:
    from . import automatic_publication_v0_1_45 as previous
    from .continuation_v0_1_39 import allow_incomplete_continuation
except ImportError:
    import automatic_publication_v0_1_45 as previous
    from continuation_v0_1_39 import allow_incomplete_continuation


def publish_company(inputs, state):
    # Retention admission can replace the result with a compact incomplete row.
    # Its absence of section_enrichment is intentional; no publication is allowed.
    if state.get('incomplete_schema_preview'):
        return allow_incomplete_continuation(previous._publish_supported(inputs, state))
    return previous.publish_company(inputs, state)

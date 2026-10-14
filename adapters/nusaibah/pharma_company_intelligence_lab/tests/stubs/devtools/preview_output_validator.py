"""Intake-only import stub. Runtime qualification must use the real validator."""
IS_TEST_STUB = True

class PreviewOutputValidationError(ValueError):
    def __init__(self,rule,path,*,classification=None):
        self.rule=rule;self.safe_path='response.outputs.*';self.classification=classification

def validate_preview_outputs(outputs):
    # Test orchestration ordering through mocked rejection. This is NOT a
    # substitute for the real runtime retention security test suite.
    pass

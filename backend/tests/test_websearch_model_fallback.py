import pytest
from unittest.mock import Mock
import logging
import os
import sys

# Ensure the backend directory is on sys.path so `utils` can be imported
# regardless of whether pytest was invoked from the repo root or the backend dir.
here = os.path.dirname(__file__)
backend_dir = os.path.abspath(os.path.join(here, '..'))
if backend_dir not in sys.path:
    sys.path.insert(0, backend_dir)

from utils.model_logger import wrap_model

"""
Test: model fallback for websearch subagent

This test simulates primary model failures (HTTP 429 / 500) and verifies
that the fallback models are attempted and that a successful fallback result
is returned.

The test is intentionally implementation-agnostic: it doesn't depend on
langchain's ModelFallbackMiddleware internals. Instead it reproduces the
expected fallback behaviour: try primary -> on transient errors (429/500)
try next fallback -> return first successful result.

Usage:
    pytest -q backend/tests/test_websearch_model_fallback.py

Adjust mocks as needed to match your model wrapper API (e.g., `.generate()`,
`.invoke()` or `__call__`). This example assumes a synchronous `generate(input)`
call signature for clarity.
"""


class TransientModelError(Exception):
    def __init__(self, status_code, msg="Model request failed"):
        super().__init__(msg)
        self.status_code = status_code


def run_with_model_fallback(models, prompt: str):
    """
    Try calling each model in `models` (ordered primary -> fallbacks).
    If a model raises a TransientModelError with status 429 or 500,
    continue to the next model. Otherwise, raise the exception.
    Return the first successful model response.
    """
    for mdl in models:
        try:
            # Adjust the call below to match your model wrapper API
            if hasattr(mdl, "generate"):
                return mdl.generate(prompt)
            elif callable(mdl):
                return mdl(prompt)
            else:
                raise RuntimeError("Model object is not callable and has no generate()")
        except TransientModelError as e:
            if e.status_code in (429, 500):
                # Log and continue to next fallback
                continue
            raise

    raise RuntimeError("All models failed with transient errors")


def test_model_fallback_primary_429_then_fallback_success():
    # Primary model raises 429
    primary = Mock()
    def primary_generate(prompt):
        raise TransientModelError(429, "Rate limited")
    primary.generate = Mock(side_effect=primary_generate)

    # First fallback raises 500
    fallback1 = Mock()
    def fallback1_generate(prompt):
        raise TransientModelError(500, "Internal server error")
    fallback1.generate = Mock(side_effect=fallback1_generate)

    # Second fallback succeeds
    fallback2 = Mock()
    fallback2.generate = Mock(return_value={"text": "OK from fallback2"})

    # Wrap models so calls are logged
    models = [wrap_model(primary, name="primary"), wrap_model(fallback1, name="fallback1"), wrap_model(fallback2, name="fallback2")]

    # Capture logs and assert fallback logging
    logger = logging.getLogger('maira.model_logger')
    # Use caplog to capture logs
    # Note: pytest's caplog fixture is available if declared in test signature; instead use logging capture
    import io, sys
    stream = io.StringIO()
    handler = logging.StreamHandler(stream)
    logger.addHandler(handler)
    logger.setLevel(logging.INFO)

    res = run_with_model_fallback(models, "Test prompt")

    handler.flush()
    log_output = stream.getvalue()
    logger.removeHandler(handler)

    assert isinstance(res, dict)
    assert res.get("text") == "OK from fallback2"
    # Ensure logs show primary tried and failed, and fallback2 succeeded
    assert "Calling model 'primary'" in log_output or "Calling model 'primary' method 'generate'" in log_output
    assert "raise" in log_output.lower() or "raised" in log_output.lower()
    assert "Calling model 'fallback2'" in log_output or "Calling model 'fallback2' method 'generate'" in log_output


def test_model_fallback_all_transient_then_error():
    primary = Mock(); primary.generate = Mock(side_effect=lambda p: (_ for _ in ()).throw(TransientModelError(429)))
    fallback1 = Mock(); fallback1.generate = Mock(side_effect=lambda p: (_ for _ in ()).throw(TransientModelError(500)))

    models = [wrap_model(primary, name="primary"), wrap_model(fallback1, name="fallback1")]

    # Capture logs briefly
    logger = logging.getLogger('maira.model_logger')
    import io
    stream = io.StringIO()
    handler = logging.StreamHandler(stream)
    logger.addHandler(handler)
    logger.setLevel(logging.INFO)

    with pytest.raises(RuntimeError, match="All models failed"):
        run_with_model_fallback(models, "Prompt")

    handler.flush()
    log_output = stream.getvalue()
    logger.removeHandler(handler)

    # Ensure logs indicate attempts
    assert "Calling model 'primary'" in log_output or "Calling model 'primary' method 'generate'" in log_output
    assert "Calling model 'fallback1'" in log_output or "Calling model 'fallback1' method 'generate'" in log_output

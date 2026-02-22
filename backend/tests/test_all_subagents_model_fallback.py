import pytest
from unittest.mock import Mock


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
            if hasattr(mdl, "generate"):
                return mdl.generate(prompt)
            elif callable(mdl):
                return mdl(prompt)
            else:
                raise RuntimeError("Model object is not callable and has no generate()")
        except TransientModelError as e:
            if e.status_code in (429, 500):
                continue
            raise

    raise RuntimeError("All models failed with transient errors")


SUBAGENTS = [
    "deep-reasoning-agent",
    "draft-subagent",
    "github-subagent",
    "literature-agent",
    "paper-agent",
    "report-agent",
    "summary-agent",
    "websearch-agent",
]


@pytest.mark.parametrize("subagent_name", SUBAGENTS)
def test_subagent_model_fallback_success(subagent_name):
    """Primary model fails (429), first fallback fails (500), second fallback succeeds."""
    # Primary -> 429
    primary = Mock(); primary.generate = Mock(side_effect=lambda p: (_ for _ in ()).throw(TransientModelError(429)))
    # Fallback1 -> 500
    fb1 = Mock(); fb1.generate = Mock(side_effect=lambda p: (_ for _ in ()).throw(TransientModelError(500)))
    # Fallback2 -> success
    fb2 = Mock(); fb2.generate = Mock(return_value={"text": f"OK from {subagent_name} fallback2"})

    res = run_with_model_fallback([primary, fb1, fb2], "Prompt")
    assert isinstance(res, dict)
    assert res.get("text") == f"OK from {subagent_name} fallback2"


@pytest.mark.parametrize("subagent_name", SUBAGENTS)
def test_subagent_model_fallback_all_fail(subagent_name):
    primary = Mock(); primary.generate = Mock(side_effect=lambda p: (_ for _ in ()).throw(TransientModelError(429)))
    fb1 = Mock(); fb1.generate = Mock(side_effect=lambda p: (_ for _ in ()).throw(TransientModelError(500)))

    with pytest.raises(RuntimeError, match="All models failed"):
        run_with_model_fallback([primary, fb1], "Prompt")

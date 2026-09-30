"""A live gate that cannot run fails in CI instead of skipping (review WR-04 of phase 28).

``canary_world.live_env`` and ``canary_world.canary_world`` skip without a live setup, which
is right on a laptop and wrong in the CI step of GATE-02/03: there a renamed container or a
changed ``.env.exapp`` would turn every live test into a skip and the step green.
"""

import re
from pathlib import Path

import canary_world as cw
import pytest

ROOT = Path(__file__).resolve().parents[2]


@pytest.fixture
def no_live_env(monkeypatch: pytest.MonkeyPatch) -> None:
    for name in cw.REQUIRED_ENV:
        monkeypatch.delenv(name, raising=False)


def test_without_the_switch_a_missing_setup_skips(
    monkeypatch: pytest.MonkeyPatch, no_live_env: None
) -> None:
    monkeypatch.delenv(cw.ENV_REQUIRE_LIVE, raising=False)
    with pytest.raises(pytest.skip.Exception, match="no live run configured"):
        cw.live_env()


def test_with_the_switch_a_missing_setup_fails(
    monkeypatch: pytest.MonkeyPatch, no_live_env: None
) -> None:
    monkeypatch.setenv(cw.ENV_REQUIRE_LIVE, "1")
    with pytest.raises(pytest.fail.Exception, match="NC_MCP_REQUIRE_LIVE=1 but no live run"):
        cw.live_env()


def test_the_ci_step_of_the_gates_sets_the_switch() -> None:
    """The step that runs the canary and the pair proofs carries the switch in its env."""
    workflow = (ROOT / ".github" / "workflows" / "ci.yml").read_text(encoding="utf-8")
    steps = re.split(r"\n      - name: ", workflow)
    gate_steps = [step for step in steps if "tests/integration/test_canary.py" in step]
    assert len(gate_steps) == 1, "exactly one CI step runs the canary"
    step = gate_steps[0]
    assert f'{cw.ENV_REQUIRE_LIVE}: "1"' in step
    assert "test_pair_equality_live.py" in step
    assert "test_provider_classes_live.py" in step

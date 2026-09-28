"""Contract tests for the plate lanes as rendered by `rvc plate`.

Originally authored in ADLAI (backend/tests/unit/test_rvc_plate.py) as
contract tests *for this CLI*; their natural home is the repo that owns
the binary. Relocated by STORY-112.

What is asserted:

- queue sorts on the normalized P0-P3 vocabulary, not file order
- `_`-prefixed shapes are never surfaced as work
- an ask line naming several seats owes *all* of them — a dropped handle
  is the silent-failure mode
- turns derive from open ask boxes, never from who spoke last; fenced
  examples summon nobody
- `waiting` and `overdue` are disjoint: a deliberate park is not an omission
  (owner ruling, 2026-09-14)
- handles resolve through the vault's own config (`--as big-pickle` is `@D`)
- a legacy-tree vault renders without crashing

Skipped when the RVC CLI is unavailable — the same graceful-absence posture
session_bootstrap.sh takes toward `$RVC_BIN`.
"""

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]

# Explicit RVC_BIN first, then PATH, then skip — never a hardcoded sibling-repo
# path. This is the criterion STORY-112 exists for: the suite passes on any
# checkout with no ~/X/TEAMFLOW dependency.
RVC_CLI = os.environ.get("RVC_BIN") or shutil.which("rvc")
pytestmark = pytest.mark.skipif(
    RVC_CLI is None,
    reason="RVC CLI not found in PATH (install rvc-cli.py or create shim)",
)

# Bucket map *and* plate config: alias.<canonical>=<handles>, plate.owner (§5.2 R2, §5.3)
ROOT_CONFIG = """vault=fixture
tree.block=40_DECIDE
tree.create=00_INBOX
tree.defer=50_DEFERRED
tree.done=60_DONE
tree.evict=90_ARCHIVE/done
tree.start=30_ACTIVE
tree.supersede=90_ARCHIVE/superseded
tree.triage=20_NEXT
alias.Q=q,qwen,qwen-code
alias.D=d,big-pickle,bigpickle,pickle
alias.G=g,gemini
alias.K=k,kimi
alias.C=c,claude
alias.@deceptikon=deceptikon,lexx
plate.owner=@deceptikon
"""


def _plate(vault: Path, *args: str) -> dict:
    result = subprocess.run(
        [sys.executable, RVC_CLI, "--path", str(vault), "plate", *args],
        capture_output=True,
        text=True,
        timeout=60,
    )
    assert result.returncode == 0, result.stderr
    return json.loads(result.stdout)


def _lanes(vault: Path, as_alias: str = "Q") -> dict:
    return _plate(vault, "--as", as_alias, "--format", "json")["lanes"]


@pytest.fixture
def vault(tmp_path: Path) -> Path:
    """A minimal newvault tree carrying one of each interesting surface."""
    for bucket in (
        "00_INBOX",
        "20_NEXT",
        "30_ACTIVE",
        "40_DECIDE/tables",
        "40_DECIDE/debates",
        "50_DEFERRED",
    ):
        (tmp_path / bucket).mkdir(parents=True)
    (tmp_path / ".rvc-root").write_text(ROOT_CONFIG)

    (tmp_path / "20_NEXT/STORY-2-p2.md").write_text("---\ntype: story\npriority: P2\n---\nbody\n")
    (tmp_path / "20_NEXT/STORY-1-p0.md").write_text("---\ntype: story\npriority: P0\n---\nbody\n")
    (tmp_path / "20_NEXT/STORY-3-none.md").write_text("---\ntype: story\n---\nbody\n")
    (tmp_path / "20_NEXT/EPIC-9-p1.md").write_text("---\ntype: epic\npriority: P1\n---\nbody\n")

    (tmp_path / "30_ACTIVE/STORY-10-active.md").write_text(
        "---\ntype: story\npriority: P1\n---\n\n- [x] landed\n- [ ] owed\n- [ ] owed too\n"
    )

    (tmp_path / "40_DECIDE/tables/T-10--ask-all.md").write_text(
        "---\ntype: table\n---\n\n## Q@2026-09-14\n\n"
        "- [ ] @deceptikon — pick a host\n- [ ] @K, @C — read the plate blind\n"
        "- [x] @D — already discharged\n\n"
        "```text\n- [ ] @phantom — example ask inside a fence, must never summon anyone\n```\n"
    )
    (tmp_path / "40_DECIDE/tables/_TEMPLATE--table.md").write_text(
        "---\ntype: table\n---\n\n- [ ] @deceptikon — template shape, not a surface\n"
    )
    (tmp_path / "40_DECIDE/debates/D-11--old-thread.md").write_text(
        "---\ntype: debate\n---\n\n## D@2020-01-01\n\nancient position, nobody has spoken since\n"
    )
    (tmp_path / "40_DECIDE/debates/Q-12--last-speaker-owes-nothing.md").write_text(
        "---\ntype: debate\n---\n\n## Q@2026-09-14\n\nI spoke last; no box asks for me.\n"
    )
    (tmp_path / "40_DECIDE/PROPOSAL--waiting-exception.md").write_text(
        "---\ntype: proposal\nauthor: someone else\n---\n\nawaiting the owner's own clock\n"
    )

    (tmp_path / "50_DEFERRED/STORY-99-parked.md").write_text(
        "---\ntype: story\npriority: P2\nupdated: 2020-01-01\n---\n\nparked long ago, on purpose\n"
    )
    (tmp_path / "00_INBOX/MEMO--deposit.md").write_text("---\ntype: memo\n---\n\nraw deposit\n")
    return tmp_path


def test_next_queue_sorts_by_priority_and_sinks_unprioritized(vault: Path) -> None:
    order = [item["name"] for item in _lanes(vault)["next"]]
    assert order[:2] == ["STORY-1-p0.md", "EPIC-9-p1.md"], order
    assert order[-1] == "STORY-3-none.md", "unprioritized work must sink, not float"


def test_templates_are_never_surfaced(vault: Path) -> None:
    paths = [row["path"] for lane in _lanes(vault).values() for row in lane]
    assert not [p for p in paths if "_TEMPLATE" in p], paths


def test_multi_seat_ask_line_ows_every_named_seat(vault: Path) -> None:
    """`- [ ] @K, @C — …` must not quietly become an ask for K only (§5.2 R2)."""
    for handle in ("K", "C"):
        lanes = _lanes(vault, handle)
        assert any("read the plate blind" in row["ask"] for row in lanes["owes_turn"]), (
            handle,
            lanes["owes_turn"],
        )


def test_owner_ask_lands_in_the_owner_lane_not_a_devs_turn(vault: Path) -> None:
    lanes = _lanes(vault, "Q")
    assert any("pick a host" in row["ask"] for row in lanes["owner"])
    assert not any("pick a host" in row["ask"] for row in lanes["owes_turn"])


def test_owner_reading_their_own_plate_sees_asks_in_lane_one(vault: Path) -> None:
    lanes = _lanes(vault, "deceptikon")
    assert any("pick a host" in row["ask"] for row in lanes["owes_turn"])
    assert lanes["owner"] == [], "no separate owner lane when you *are* the owner"


def test_discharged_ask_stops_owing_a_turn(vault: Path) -> None:
    lanes = _lanes(vault, "D")
    assert not [row for row in lanes["owes_turn"] if "already discharged" in row["ask"]]


def test_asks_inside_code_fences_summon_nobody(vault: Path) -> None:
    """§5.2 R4: a quoted example is not an ask."""
    assert _lanes(vault, "phantom")["owes_turn"] == []


def test_last_speaker_owes_nothing_without_an_open_box(vault: Path) -> None:
    """R9: header order sequences owe-ers; it never decides who owes."""
    lanes = _lanes(vault, "Q")
    assert not [row for row in lanes["owes_turn"] if "last-speaker" in row["path"]]


def test_identity_free_render_keeps_tree_lanes_and_drops_mine(vault: Path) -> None:
    payload = _plate(vault, "--format", "json")
    assert payload["as"] is None and payload["identity_lanes"] is False
    assert payload["lanes"]["owes_turn"] == []
    assert len(payload["lanes"]["next"]) == 4 and len(payload["lanes"]["active"]) == 1


def test_parked_is_waiting_and_never_overdue(vault: Path) -> None:
    lanes = _lanes(vault)
    waiting = [row["name"] for row in lanes["waiting"]]
    overdue = [row["name"] for row in lanes["overdue"]]
    assert "STORY-99-parked.md" in waiting
    assert "STORY-99-parked.md" not in overdue, "a deliberate park must not read as negligence"


def test_stale_deliberation_surface_is_overdue(vault: Path) -> None:
    stale = [row for row in _lanes(vault)["overdue"] if "D-11--old-thread.md" in row["path"]]
    assert stale and stale[0]["age_days"] > 365


def test_loose_artifact_in_decide_root_is_a_registered_exception(vault: Path) -> None:
    lanes = _lanes(vault)
    assert any("PROPOSAL--waiting-exception" in row["name"] for row in lanes["waiting"])


def test_inbox_is_listed_and_non_actionable(vault: Path) -> None:
    lanes = _lanes(vault)
    assert [row["name"] for row in lanes["inbox"]] == ["MEMO--deposit.md"]
    actionable = [row for key in ("owes_turn", "owner") for row in lanes[key]]
    assert not [row for row in actionable if row["path"].startswith("00_INBOX")]


def test_alias_map_resolves_handles_from_config(vault: Path) -> None:
    canonical = _lanes(vault, "D")
    for handle in ("big-pickle", "pickle", "d"):
        assert _lanes(vault, handle) == canonical, handle


def test_active_lane_reports_honest_checklist_state(vault: Path) -> None:
    active = _lanes(vault)["active"][0]
    assert (active["open_boxes"], active["done_boxes"]) == (2, 1)


def test_legacy_tree_degrades_without_crashing(tmp_path: Path) -> None:
    """TEAMFLOW/conductor/dash keep the old tree: no `block` bucket, no plate config."""
    legacy = tmp_path / "legacy-vault"
    for bucket in ("10_Issues/00_Backlog", "10_Issues/01_To_Do", "10_Issues/02_Active"):
        (legacy / bucket).mkdir(parents=True)
    (legacy / ".rvc-root").write_text("vault=legacy\n")
    (legacy / "10_Issues/02_Active/STORY-1-legacy.md").write_text(
        "---\ntype: story\n---\n\n- [ ] unfinished\n"
    )
    payload = _plate(legacy, "--as", "D", "--format", "json")
    assert payload["owner"] is None, "no plate.owner configured → the owner lane stays inert"
    assert [row["name"] for row in payload["lanes"]["active"]] == ["STORY-1-legacy.md"]


def test_newvault_create_translates_legacy_priority(tmp_path: Path, capsys) -> None:
    """`rvc create` must not mint a stray `Medium` into a tree that sorts P0-P3."""
    (tmp_path / ".rvc-root").write_text(ROOT_CONFIG)
    for bucket in ("00_INBOX", "20_NEXT", "30_ACTIVE", "40_DECIDE", "50_DEFERRED", "60_DONE"):
        (tmp_path / bucket).mkdir(parents=True)
    result = subprocess.run(
        [
            sys.executable,
            RVC_CLI,
            "--path",
            str(tmp_path),
            "create",
            "Sample issue",
            "--priority",
            "High",
        ],
        capture_output=True,
        text=True,
        timeout=60,
    )
    assert result.returncode == 0, result.stderr
    created = next(Path(tmp_path).rglob("STORY-*.md"))
    assert "priority: P1" in created.read_text(), created.read_text()[:200]


def test_live_adlai_vault_renders() -> None:
    """Smoke over the real vault: every lane computes, config resolves, cap holds.

    Kept in ADLAI's own suite (not RVC's) because it renders ADLAI's vault,
    not RVC's. See STORY-112 AC4: RVC is an external client.
    """
    pytest.skip("rendering ADLAI's vault belongs in ADLAI's suite per STORY-112")

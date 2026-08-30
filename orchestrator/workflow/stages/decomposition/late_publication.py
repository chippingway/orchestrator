# Copyright 2026 Geser Dugarov
# SPDX-License-Identifier: Apache-2.0
"""The pull request a post-publication verdict was taken over, read once.

Both roads out of an adjudication entered on the published side have to ask
the same question before they act, and neither can look it up: the entry the
gate froze names the pull request the work is already on and the head it was
standing on, so what a settlement or a split owes is a PROOF that those two
are still what they were rather than a search. A `single` publishes onto that
pull request; a `split` closes it over a supersession and hands the work to
children. Both are irreversible on the remote, and both are wrong if somebody
moved or settled the publication while the adjudication was open.

So the reading lives here rather than on either of them. It is one owner
because it is one fact -- the state and the head of one pull request -- and
because a fetched pull request is LAZY: `get_pr` asks GitHub nothing, and the
requests that can fail are the attribute reads behind it. A caller guarding
only the lookup leaves those two to raise out of a road whose every other
refusal parks, and an exception on the way to a park is a park nobody takes.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Optional

from github.Issue import Issue

from orchestrator.github import comments as _github_comments
from orchestrator.github.client import GitHubClient

log = logging.getLogger("orchestrator.workflow")

# What a pull request has to be for either road to act on it. A merged or
# closed one is a change a human settled while the adjudication was open, and
# neither publishing onto it nor closing it over a supersession is something
# this workflow may do behind that.
OPEN = "open"

# What a pull request this workflow closed itself reads as. Told apart from
# `merged` because the two mean opposite things to a caller holding a receipt:
# a close is what a supersession makes, and a merge is a human landing the
# very work the supersession says is being replaced.
CLOSED = "closed"


@dataclass(frozen=True)
class _PublicationReading:
    """One pull request as this tick found it, or the refusal it got.

    Both facts together because both are requests, and a reading where either
    did not come back is one refusal rather than a state with a head missing
    from it.
    """

    state: str = ""
    head: Optional[str] = None
    refused: bool = False
    # Whether the caller's own receipt is already on this pull request's
    # thread. Asked inside the same guarded read as the other two, because it
    # is the same lazy object and a caller that fetched again to look would
    # have a second request to guard -- and taken only where a caller names a
    # receipt to look for, since nothing else pays a comment listing for it.
    superseded: bool = False


def _read_publication(
    gh: GitHubClient, issue: Issue, number: int, receipt: str = "",
) -> _PublicationReading:
    """The state and head of the publication a verdict was taken over.

    Both inside one refusal, for the reason the module says: the lookup asks
    GitHub nothing and the two attribute reads behind it are what talk. What
    comes back is a reading a caller may act on, or a refusal it must park on.

    `receipt` is a marker a caller has already stamped on this pull request if
    it acted on it before, and the answer rides the same refusal for the same
    reason. A caller that CLOSED the pull request itself and died before the
    work behind that close was finished cannot tell its own close from a
    human's by the state alone -- both read `closed` -- and the thread is
    where the difference is written.
    """
    try:
        return _publication_facts(gh, number, receipt)
    except Exception:
        log.exception(
            "issue=#%d could not read published PR #%d before acting on the "
            "verdict taken over it", issue.number, number,
        )
    return _PublicationReading(refused=True)


def _publication_facts(
    gh: GitHubClient, number: int, receipt: str,
) -> _PublicationReading:
    """The lookup and the lazy reads behind it, as one reading."""
    pull_request = gh.get_pr(number)
    return _PublicationReading(
        state=gh.pr_state(pull_request),
        head=getattr(getattr(pull_request, "head", None), "sha", None),
        superseded=bool(receipt) and _carries_receipt(
            gh, pull_request, receipt,
        ),
    )


def _carries_receipt(gh: GitHubClient, pull_request, receipt: str) -> bool:
    """Whether a comment of OURS on this thread already carries `receipt`.

    Ours, because an HTML comment is invisible in the rendered thread and
    anybody could otherwise post the marker that tells this workflow it has
    already acted. Walked whole rather than from a watermark: nothing this
    mode keeps was moved past the notice, so a bounded scan could start above
    the very comment it is looking for.
    """
    return _github_comments.carries_own_marker(
        gh.pr_conversation_comments_after(pull_request, None),
        receipt,
        bot_login=getattr(gh, "_bot_login", None),
    )

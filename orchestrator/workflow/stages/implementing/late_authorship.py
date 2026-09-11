# Copyright 2026 Geser Dugarov
# SPDX-License-Identifier: Apache-2.0
"""Which comments on an authorization park's thread are this stage's own words.

The publication seam says things nobody in this stage words, and it says them
before anything records having said them. What a later reader cannot attribute
it treats as somebody's word -- so our own prose becomes the last reply on the
thread, the park's reading hands the tick back, and the ordinary resume spawns
a developer against it and consumes whatever a human wrote underneath.

Two records answer that, in this order.

The ID is the first and the ordinary one. The client here records what GitHub
hands back the instant each post returns, into `orchestrator_comment_ids`,
which is what says a comment is ours everywhere in this stage. That write is
made here rather than left to the seam because the seam says several things
before it returns, and a sentence unattributed for the whole of that call is
one every reader in between misreads.

The RECEIPT is the second, and it is what the one API call between a post and
that write leaves. It is a digest, written down before the comment carrying it
exists, and what it commits to is the SENTENCE rather than the sender: the
secret in it, and the exact body it goes out on. So a comment answers it only
by being that sentence, word for word, and nothing else.

Which is the whole of why claiming one is safe, and it is not a claim about
who typed it. A secret is unforgeable only until it is disclosed, and posting
the sentence discloses it: from that moment a reply quoting our comment
carries the secret too, and the login beside both is a token this repository
says outright may be shared with the human whose consent this park collects.
Ordering told the two apart only while our comment stood, and ordering does
not survive that comment being deleted -- one tidy-up on a thread where
somebody has already quoted it. Bound to the body instead, their reply answers
nothing: a quote carries their words as well as ours, and the digest is of
ours alone. What can still answer is a verbatim copy of the sentence, which
carries nobody's words to lose.
"""
from __future__ import annotations

import hashlib
import logging
import re
import secrets

from github.Issue import Issue

from orchestrator.github.client import GitHubClient
from orchestrator.github.pinned_state import PinnedState
from orchestrator.workflow.engine import comments as _comments
from orchestrator.workflow.late_split import payloads as _payloads
from orchestrator.workflow.stages.implementing import state as _state

log = logging.getLogger("orchestrator.workflow")

# How much randomness one sentence's secret carries. It is never guessed, only
# read off a comment that already carries it, so this is the margin against
# somebody predicting a receipt before the sentence exists.
_PROOF_BYTES = 16

# What every comment the seam posts goes out carrying, and the only part of a
# body this owner reads by pattern. An HTML comment, so it is invisible in the
# rendered thread.
_PUBLICATION_RECEIPT = (
    "<!--orchestrator-unauthorized-exemption-publishing:"
    "issue={issue}:proof={proof}-->"
)

_PROOF_ON_A_COMMENT = re.compile(
    "<!--orchestrator-unauthorized-exemption-publishing:"
    "issue=[0-9]+:proof=([0-9a-f]+)-->",
)

# How a comment's own address and words are read, spelled once because both
# readings here ask for them.
_COMMENT_ID = "id"
_BODY = "body"


def _commits_to(secret: str, said: str = "") -> str:
    """What the record keeps in place of a sentence it may not publish.

    The secret AND the body it goes out on, because binding to the secret
    alone binds to nothing a quote of the sentence does not also have. Written
    down before the comment exists, so a body answering this digest is that
    comment's body and no other -- ours, or a copy of ours carrying nobody
    else's words.

    An empty body is the promise a handoff makes before it has worded
    anything: it commits to the secret so the record says a sentence is in
    flight, and the client refines it to the sentence itself before posting.
    """
    return hashlib.sha256(f"{secret}\0{said}".encode()).hexdigest()


def _outstanding(state: PinnedState) -> list:
    """Every sentence this handoff has promised and not yet accounted for."""
    recorded = state.get(_state._HELD_PUBLICATION)
    if not isinstance(recorded, list):
        return []
    return [held for held in recorded if isinstance(held, str) and held]


def _records_a_commitment(state: PinnedState, commitment: str) -> None:
    """Add one promise to what this handoff still owes the record.

    Unbounded on purpose, because nothing accumulates here: every entry is
    dropped either by the write that records the id of the comment it went out
    on, or by the repair below on the very next poll. A cap would be the one
    thing that could lose a sentence still standing above the watermark.
    """
    state.set(_state._HELD_PUBLICATION, [*_outstanding(state), commitment])


def _recovers_a_stranded_sentence(issue: Issue, state: PinnedState) -> bool:
    """Put the sentences an outstanding receipt names back in the ledger.

    The poll after a tick died in the one API call between a post and the
    write recording it. Ahead of every routing decision, because everything
    downstream reads `orchestrator_comment_ids` to tell our own prose from a
    human's: run after, the park's reading has already handed the tick back
    and the resume has already spawned a developer against our own notice.

    What it repairs is the LEDGER and never the watermark. A watermark moved
    to our sentence crosses everything under it, so an operator who read the
    notice and wrote the corrected command before this poll ran would have it
    consumed unread and never acted on. A ledger entry moves nothing -- it
    says only that one comment is ours -- so the next reading drops it and
    finds whatever a human wrote last.

    ONE reading of the thread answers every outstanding receipt, so nothing
    landing between two of them can change which comment a second one picks.

    The EARLIEST comment answering each, and no other. Answering means the
    body IS that sentence, word for word: a reply quoting it carries its
    author's words too and answers nothing, so the accidental case -- a
    reviewer on the shared token quoting our notice back -- can never be
    claimed. What can still answer is a verbatim copy, and a copy can only
    follow what it copies, so ours is the earlier of the two.

    Where our own comment has been DELETED, the earliest answer left is that
    copy, and nothing on a thread can tell it from ours. Producing one takes
    reposting a bot notice byte for byte, hidden receipt included, and
    removing the original -- which is not something a reviewer does by
    accident, and which is available only to somebody already holding the
    token that authorizes publication outright. The window is the same one API
    call, and what the claim costs there is bounded by that: the ledger says a
    comment is ours, which drops it from the readings, and the body it was
    claimed on carried nobody's words.

    Every receipt is dropped whether it was answered or not. One the thread
    answers nowhere is a sentence that never left the process that recorded
    it, and nothing here re-says a sentence the seam worded -- the next
    handoff words its own -- so keeping it would buy a thread read a poll
    forever and say nothing new.
    """
    outstanding = _outstanding(state)
    if not outstanding:
        return False
    thread = _thread_beside_the_record(issue, state.comment_id)
    for owed in outstanding:
        stranded = min(
            (
                identified
                for seen in thread
                if _says(seen, owed)
                for identified in (
                    _payloads.as_identity(getattr(seen, _COMMENT_ID, 0)),
                )
                if identified is not None
            ),
            default=None,
        )
        if stranded is None:
            continue
        log.info(
            "issue=#%d carries comment %d saying word for word what this "
            "stage recorded saying and no write accounted for; attributing "
            "it rather than handing our own prose to a developer",
            issue.number, stranded,
        )
        _comments._track_orchestrator_comment(state, stranded)
    state.set(_state._HELD_PUBLICATION, None)
    return True


def _says(seen, commitment: str) -> bool:
    """Whether this comment's body is the sentence that receipt committed to.

    Every secret the body offers is hashed WITH that body and compared, never
    matched as text: the digest is a field on a record that is itself a public
    comment, so a road looking for the digest would claim the comment of
    anybody who read it off the issue and pasted it back.
    """
    said = getattr(seen, _BODY, "") or ""
    return any(
        _commits_to(offered, said) == commitment
        for offered in _PROOF_ON_A_COMMENT.findall(said)
    )


def _thread_beside_the_record(issue: Issue, state_comment_id: int | None) -> list:
    """Every comment on this issue except the pinned record itself.

    By ID, as every other reading here names it: told to find the record by
    its marker instead, this would drop each comment that merely QUOTES one --
    a sentence of ours a human quoted our payload under included, which is the
    one comment the caller is asking about.

    A comment whose id nothing can read stays in, and so does every comment on
    an issue with no record pinned yet. Keeping one comment too many costs a
    sentence said twice; dropping one costs the sentence entirely.

    Both readings that ask a THREAD about a receipt come through here, and the
    record is excluded from each for one reason: a receipt is a FIELD on that
    record before it is a sentence on a thread, and the record is written as
    its own unescaped payload wherever escaping it would put the comment past
    GitHub's ceiling -- so on exactly those issues every receipt it holds sits
    verbatim in the pinned comment, under our own login. Read there, a
    sentence recorded and never said reads as one already said.
    """
    return [
        seen for seen in issue.get_comments()
        if getattr(seen, _COMMENT_ID, None) != state_comment_id
    ]


class _StampsWhatItPosts:
    """A client that proves and records every sentence the seam posts.

    The seam is the one road on this park that says something the stage did
    not word, so there is no sentence to stamp at the call site and nothing a
    later reading could identify its notices by. Our marker beside our login
    is exactly what a reviewer quoting one of them from a shared token looks
    like, and reading that as authorship deletes what they said.

    So each comment goes out under a secret of its own, and two records are
    made around it. The DIGEST of the secret and the finished body goes down
    first, which is what the poll after a crash finds the sentence by. The ID
    goes down the instant the post returns, which is what says the comment is
    ours everywhere else. Between them is one API call, and it is the only
    window on this road.

    One receipt per COMMENT, because one cannot answer for two: the seam says
    a pull request opened and then a refusal over a checkout that moved under
    the push, and a digest of one body is answered by that body alone.

    The first secret is handed in rather than minted here, its promise already
    on the record before this client exists -- the caller owes the issue that
    much before it enters a seam that can post the moment it is called.

    Writing here is safe because of where the call already stands: the caller
    persisted this record immediately before entering the seam and persists it
    again the moment the seam returns, so what these writes move earlier is
    the seam's own progress rather than anything of this owner's.

    Everything else is the client underneath, untouched.
    """

    def __init__(
        self,
        gh: GitHubClient,
        issue: Issue,
        state: PinnedState,
        opening: str,
    ) -> None:
        self._gh = gh
        self._issue = issue
        self._state = state
        self._opening = opening
        self._spent = ""

    def __getattr__(self, named: str):
        return getattr(self._gh, named)

    def comment(self, issue: Issue, body: str):
        """Post one sentence of the seam's, recorded on both sides of the post."""
        said = self._promises(body)
        posted = self._gh.comment(issue, said)
        self._records(posted)
        return posted

    def forgets_an_unspoken_promise(self) -> None:
        """Drop the promise this call was given and never worded a sentence for.

        The receipt the caller records ahead of the seam commits to a secret
        and no body, since there is no body to name until this client composes
        one -- so where the seam said nothing at all, it is a promise no
        comment on any thread can ever answer. Left standing it would ride the
        record until the issue leaves the stage, one entry per silent handoff,
        saying nothing.

        A promise this client SPENT is already gone: composing the sentence
        replaced it with a receipt naming that body. So the secret is still
        held here only in the silent case, and this is a no-op otherwise.
        """
        if not self._opening:
            return
        spent = _commits_to(self._opening)
        self._state.set(_state._HELD_PUBLICATION, [
            held for held in _outstanding(self._state) if held != spent
        ] or None)

    def _promises(self, body: str) -> str:
        """Compose the sentence, and commit to it before it goes anywhere.

        The digest binds the secret to the finished body rather than to the
        secret alone, so what it commits to is this sentence: a reply quoting
        it carries the secret but carries its author's words too, and answers
        nothing.

        The promise the caller left on the record ahead of the seam is
        replaced rather than added to, since it was a promise about the same
        sentence made before there was a body to name.
        """
        secret = self._opening or secrets.token_hex(_PROOF_BYTES)
        said = "{body}\n\n{receipt}".format(
            body=body,
            receipt=_PUBLICATION_RECEIPT.format(
                issue=self._issue.number, proof=secret,
            ),
        )
        self._spent = _commits_to(secret, said)
        self._state.set(_state._HELD_PUBLICATION, [
            held for held in _outstanding(self._state)
            if held != _commits_to(secret)
        ] or None)
        _records_a_commitment(self._state, self._spent)
        self._gh.write_pinned_state(self._issue, self._state)
        self._opening = ""
        return said

    def _records(self, posted) -> None:
        """Put what this call just posted beyond any later argument.

        The id into the ledger, which is what says a comment is ours
        everywhere in this stage, and the receipt it went out under off the
        record, since the sentence it stood for has been said and accounted
        for. One write, because either without the other is a record that
        disagrees with itself.
        """
        identified = _payloads.as_identity(getattr(posted, _COMMENT_ID, 0))
        if identified is None:
            return
        _comments._track_orchestrator_comment(self._state, identified)
        self._state.set(_state._HELD_PUBLICATION, [
            held for held in _outstanding(self._state) if held != self._spent
        ] or None)
        self._gh.write_pinned_state(self._issue, self._state)

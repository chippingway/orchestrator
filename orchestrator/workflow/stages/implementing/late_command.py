# Copyright 2026 Geser Dugarov
# SPDX-License-Identifier: Apache-2.0
"""The one reply a park for an authorization is ever ended by.

Reading a thread, and nothing else: no record is written here and nothing is
decided. What this owner answers is which comment -- if any -- the tick behind
it should act on, so the road that acts has one fact to act on rather than a
conversation to interpret.

The LAST fresh trusted reply decides, and reading it any other way poisons the
park. Guidance written after a command outranks it, since the safe reading of
somebody who asked to publish and then asked for a change is the one that
publishes nothing; a command written after guidance is the decision that
replaced it. Read as a SET instead, a reply that matches nothing would never
be consumed on the seams that publish onto a pull request the remote already
carries -- nothing there moves the watermark by any other means -- so it would
stand in every later batch and refuse the correct command behind it forever.

A reply that IS the command is carried whatever it goes on to say, including
an argument nobody could act on. That is what earns an abbreviation the
sentence saying so instead of a silent park: the empty id can never equal a
candidate, so it takes the refusal road by itself.

Three authors are never in the reading at all. An outsider's comment cannot
authorize anything, which is the allowlist's rule applied where the thread is
read. The orchestrator's own comments are nobody's decision -- and the park
notice spells the command out ready to copy, so our sentences are exactly what
a reader matching on that syntax would mistake for one. And a comment with no
id is neither: a record made from it would name a comment nothing can locate,
which is the one thing an authorization may not be.

Being ours is PROVED rather than read off a comment, because the last-reply
rule makes dropping one the same act as deleting what its author said. A
retraction taken for one of ours is a retraction that never happened, and the
authorization under it becomes the last word and publishes -- consent
withdrawn and acted on anyway. So the ledger of ids this process recorded
posting is the whole of the evidence: the marker is text anybody may paste,
and the author login is a token this repository says outright may be shared
with the human whose consent this park collects. A comment the ledger cannot
vouch for stays in the reading and, not being the command, leaves the park
standing.
"""
from __future__ import annotations

from dataclasses import dataclass

from github.Issue import Issue

from orchestrator.github.client import GitHubClient
from orchestrator.github.comments import carries_own_marker, filter_trusted
from orchestrator.github.pinned_state import PinnedState
from orchestrator.workflow.engine import (
    comments as _comments,
    messages as _messages,
)
from orchestrator.workflow.late_split import (
    formats as _formats,
    payloads as _payloads,
)
from orchestrator.workflow.stages.implementing import (
    late_records as _records,
    state as _state,
)

# The park an adjudicated candidate takes when nothing on the record says a
# human agreed to publish it. Its own reason because its recovery is neither a
# session retry nor another reading: what it is waiting for is a person, and
# every tick until one arrives measures the same pair to the same answer.
#
# Spelled on this owner because this is where it is READ -- the reply reading
# is the only thing that turns on it -- and published for the two seams that
# route a parked tick back to the gate.
PARK_UNAUTHORIZED_EXEMPTION = "late_unauthorized_exemption"

# The attribute a comment's own address is read off, spelled once because
# every reading here asks for it: which reply was acted on, how far the thread
# was looked at, and which comments this process posted itself.
_COMMENT_ID = "id"


@dataclass(frozen=True)
class _Answer:
    """The last word a human has written on a standing authorization park.

    Only the LAST fresh reply is read, and that is the whole of the rule.
    Every earlier one has been superseded by it: an operator who names one
    commit and then another has decided about the second, and one who writes
    guidance and then the command has changed their mind toward publishing.
    Reading the batch as a set instead is what poisons a park -- a reply that
    matches nothing is never consumed on the seams that publish onto a pull
    request the remote already carries, so it would stand in every later batch
    and refuse a correct command forever.

    `named` is the commit that reply authorizes, whole or EMPTY. Empty is a
    command nobody could act on -- an abbreviation, or an argument that is not
    an object id at all, since nothing in this domain abbreviates -- and it is
    carried rather than dropped: it can never equal the candidate, so it takes
    the refusal road and the human gets the sentence and the command that
    would have worked. `comment_id` is the reply itself, which is the address
    a recorded authorization is attributable to.

    `watermark` is how far the READING got, which is a different fact from
    either: the furthest comment this owner actually looked at, ours and
    untrusted ones included. It travels because it is what an answer may
    consume and no more. A tick that read the tip of the thread and then
    consumed past whatever the tip has become would swallow a retraction
    posted in between -- unread, unanswered, and gone for good, while the
    authorization it was retracting published. Consumed to what was read, the
    retraction is still there for the next poll.
    """

    named: str
    comment_id: int
    watermark: int

    def read_through(self, gate: _records._Gate, said: int) -> int:
        """How far a tick that answered this reply may say the thread is read.

        Up from what this reading reached, over OUR OWN comments and no
        further. A road that answers a command it may not act on posts its
        sentence into the window between the two, and ids ascend, so that
        sentence lands above the reply it answers and has to be consumed --
        left behind, the next poll reads the orchestrator's own words as
        somebody's fresh guidance and resumes a developer against them.

        Reached by its id alone, though, it would pay for that with the one
        thing this park exists to collect. An operator who reads the notice
        and posts the corrected command in that same window has their answer
        land BELOW ours, and a watermark set to ours consumes it unread -- so
        the park goes on standing over a command nobody will ever see again.
        So the first comment that is NOT ours ends the walk, whatever it says:
        the watermark is the only thing that can promise its author the next
        poll.

        Every id the walk passes is one nobody has to see again -- this tick
        wrote it, or an earlier one did and this reading examined it. A tick
        that posted nothing walks nothing and answers with what it read, which
        costs no request and is every other road here.
        """
        if said <= self.watermark:
            return self.watermark
        reached = self.watermark
        for landed in gate.gh.comments_after(gate.issue, self.watermark):
            identified = _payloads.as_identity(getattr(landed, _COMMENT_ID, 0))
            if identified is None or identified > said:
                break
            if not _ours(landed, gate.state):
                break
            reached = identified
        return reached


def _read_the_park(
    gh: GitHubClient, issue: Issue, state: PinnedState,
) -> _Answer | None:
    """The command a human has written on this park, or None if none has.

    None for everything else, and each exclusion is its own answer. An issue
    parked for another reason is not this park's to end; a thread with nothing
    new on it is a human who has not replied yet; an outsider's comment is not
    in the reading at all, so nothing they post can authorize anything; a
    comment the orchestrator itself wrote is nobody's decision, and the park
    notice spells the command out ready to copy, so our own sentences are
    exactly what a reader matching on that syntax would mistake for one; and a
    last word that is not the whole command is guidance, which belongs to the
    ordinary resume that feeds it to the developer rather than to a bypass
    taken behind their back.

    A command nobody could ACT on is not one of those, and it is answered
    rather than dropped: the argument is held to a whole object id, and one
    that is not gets the same sentence a command for another commit gets. Read
    as guidance instead, an operator who abbreviated would be left with a
    silent park and a thread that never said why.

    The LAST fresh reply decides, because it is the last thing the human said.
    Guidance written after a command outranks it -- the safe reading of
    somebody who asked to publish and then asked for a change is the one that
    publishes nothing -- and a command written after guidance is the decision
    that replaced it. Read as a set instead, one stale reply would refuse
    every command posted behind it for as long as the park stood.
    """
    if state.get(_state._PARK_REASON) != PARK_UNAUTHORIZED_EXEMPTION:
        return None
    if not state.get(_state._AWAITING_HUMAN):
        return None
    examined = gh.comments_after(
        issue, state.get(_state._LAST_ACTION_COMMENT_ID),
    )
    replies = [
        reply for reply in filter_trusted(examined) if not _ours(reply, state)
    ]
    if not replies:
        return None
    last = replies[-1]
    identified = _payloads.as_identity(getattr(last, _COMMENT_ID, 0))
    if not _is_the_command(last) or identified is None:
        return None
    return _Answer(
        named=_names(last),
        comment_id=identified,
        watermark=_furthest_read(examined, identified),
    )


def _furthest_read(examined: list, at_least: int) -> int:
    """How far this reading of the thread actually got.

    Every comment the fetch returned counts, not just the ones that survived
    the trust and authorship filters: what a watermark records is what has
    been LOOKED at, and a filtered-out comment has been. Left out, an
    outsider's reply or a sentence of ours would be handed to the next poll as
    something nobody has read yet.

    Never short of the reply being acted on, which is the floor a fetch that
    answered with ids nothing could read still has to clear.
    """
    read = [at_least]
    for seen in examined:
        identified = _payloads.as_identity(getattr(seen, _COMMENT_ID, 0))
        if identified is not None:
            read.append(identified)
    return max(read)


def _ours(reply, state: PinnedState) -> bool:
    """Whether the orchestrator itself POSTED this reply, by its recorded id.

    Dropped before anything here reads a thread, because nothing this process
    posts is ever somebody's decision -- and a park notice spells the command
    out ready to copy, so our own sentences are exactly the comments a reader
    matching on that syntax would otherwise mistake for one.

    Which makes the standard of proof the whole question, because dropping a
    comment here is not a neutral act. The reading behind this takes the LAST
    fresh reply, so a comment dropped is a comment whose author never spoke:
    an operator who authorizes a candidate and then retracts it would have the
    retraction removed and the authorization selected, and the candidate would
    publish on consent that had been withdrawn. Over-filtering is how this
    park publishes something nobody agreed to.

    So the ledger of ids `_post_issue_comment` records is the whole of the
    evidence. It is a fact about what this process DID, and nothing a
    commenter writes can put itself into it.

    Neither of the other two signals may stand in for it, and both are
    refused rather than accepted as a weaker second best. The marker is plain
    text in a public thread that anybody may paste, or quote off a comment of
    ours that carries one. And the author login is the shared-PAT hazard this
    repository already names where that ledger is defined: the token belongs
    to a human, so a reviewer posting from the same account matches it
    exactly, and a retraction they wrote under a quoted marker would be read
    as the orchestrator talking to itself. The two together are no better,
    since the human who shares the login is the one whose consent this park
    exists to collect.

    Anything the ledger cannot vouch for is somebody's word and stays in the
    reading -- including a comment of ours whose id has been evicted past the
    ledger's bound. What that costs at worst is one of our own sentences
    standing as the last reply, which is not the command, so the park goes on
    standing and waits. That is the safe direction for a question only a human
    can answer, and it is the one this owner fails in.
    """
    identified = _payloads.as_identity(getattr(reply, _COMMENT_ID, 0))
    if identified is None:
        return False
    return identified in _comments._orchestrator_ids(state)


def _is_the_command(reply) -> bool:
    """Whether this reply is the whole command, whatever it went on to say.

    Asked apart from what the command NAMES, because the two decide different
    things. A comment that is not the command is guidance and is left for the
    road that feeds it to a developer. One that IS the command is a gesture
    this park owes an answer to -- and that holds just as much when nobody
    could act on it, since a human who typed an abbreviation is owed the
    sentence saying so rather than a park that goes on standing in silence.

    A reply with no id is neither: a record made from it would name a comment
    nothing can locate, which is the one thing an authorization may not be.
    """
    return _messages._authorized_oversized_candidate(reply) is not None


def _names(reply) -> str:
    """The whole object id one reply authorizes, or "" if it authorizes none.

    A comment that is not the whole command answers "", and so does one whose
    argument is not a whole git object id: nothing here abbreviates, so an
    abbreviation is the mismatch it is rather than a prefix to compare -- and
    the mismatch is what earns the sentence, since "" is never a candidate.
    """
    written = _messages._authorized_oversized_candidate(reply)
    if written is None:
        return ""
    return _payloads.as_hex(written, _formats.COMMIT_LENGTHS) or ""


def _already_answered(gate: _records._Gate, marker: str) -> bool:
    """Whether this thread already carries OUR answer to this reading.

    Both halves of the receipt are asked -- the scoped marker and the author
    -- since an HTML comment is plain text anybody may paste, and read from
    anybody it would silence a sentence a human is owed.
    """
    return carries_own_marker(
        gate.issue.get_comments(),
        marker,
        bot_login=getattr(gate.gh, "_bot_login", None),
    )

"""The scope-level contract: derive a level from the axis answers, deterministically.

The five levels (L1 Core … L5 Fringe) and the produce/shelf line are generic; how a
candidate *gets* a level is not, because the axes that decide it are the consumer's
business shape. keel-kit ``methodology/business-scoping.md`` → *How a level is
assigned* is the written contract; this module is its executable half.

Two axes are near-universal and one is mandatory:

* **backbone** (mandatory) — is the *topic domain itself* one of the domains the
  business is built on? It decides which side of the produce line a candidate is on.
* **service** (near-universal) — is the reader's intent served by one of our own
  products?
* any number of **additional** axes the consumer declares. A partner / affiliate
  registry supplies the classic one; a consumer without partners declares a
  different axis, or none.

The rule, in full::

    backbone yes -> L1 when every other declared axis is yes
                    L2 when some (but not all) are yes
                    L3 when none are yes
    backbone no  -> L3 when service is yes
                    L4 when any other declared axis is yes
                    L5 otherwise

An additional axis is therefore a **one-way lift**: its presence can only raise a
candidate's relevance or leave it unchanged, never lower it. A consumer never grades
a topic down for lacking a partnership it may sign next quarter.

Resolution follows the axis count. Three binary axes fill all five levels; two reach
L1, L3 and L5 from the axes alone, leaving L2 and L4 to editorial judgment against
the level meanings. That is why a consumer that wants all five computed should
declare a third axis rather than drop to two.
"""
from __future__ import annotations

BACKBONE_AXIS = "scope"
SERVICE_AXIS = "service"

#: Levels that are produced, in descending priority. The rest are the shelf.
PRODUCED_LEVELS = (1, 2, 3)
SHELF_FROM = 4


class ScopeAxesError(ValueError):
    """The axis answers cannot produce a level (the backbone axis is missing)."""


def derive_scope_level(axes, backbone=BACKBONE_AXIS, service=SERVICE_AXIS):
    """Return the scope level (1-5) implied by ``axes``.

    ``axes`` maps an axis name to a yes/no answer, e.g.
    ``{"scope": True, "service": True, "partnership": False}``. Every key present is
    a *declared* axis; absent keys are not "no", they are axes this consumer does not
    run, and they change the reachable levels rather than the answer.

    Raises ``ScopeAxesError`` when the backbone axis is absent — without it there is
    no produce/shelf decision to make, and silently defaulting it would grade real
    rows wrong.
    """
    if not isinstance(axes, dict):
        raise ScopeAxesError(f"axes must be a dict of axis -> bool, got {type(axes).__name__}")
    if backbone not in axes:
        raise ScopeAxesError(
            f"the backbone axis {backbone!r} is required; got {sorted(axes)}")

    answers = {k: bool(v) for k, v in axes.items()}
    others = {k: v for k, v in answers.items() if k != backbone}

    if answers[backbone]:
        if not others or all(others.values()):
            return 1
        return 2 if any(others.values()) else 3
    if answers.get(service):
        return 3
    lift = {k: v for k, v in others.items() if k != service}
    return 4 if any(lift.values()) else 5


def is_shelved(level):
    """True when a level is on the shelf — recorded, not produced."""
    try:
        return int(level) >= SHELF_FROM
    except (TypeError, ValueError):
        return False

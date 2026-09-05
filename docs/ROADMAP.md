# Roadmap

Active work. Tickets move to `docs/DELIVERED.md` once their PR merges.

Status flow: `Backlog` → `Pending` → `In Progress` → `Review` → `PR` → delivered.

This file tracks ticketed engineering work. `docs/survivor_pool_product_roadmap.md`
remains the prose strategy doc (open-source vs SaaS, phases, market notes) and is not
superseded by it.

---

## Epic: GroupMe recap bot
> After every game in a week goes final, a bot posts one tweet-length recap into the
> pool's GroupMe. First LLM dependency in the repo, and the first job that writes
> somewhere real people are reading.

Spec: [`docs/design/groupme-recap-spec.md`](design/groupme-recap-spec.md)

| ID | Ticket | Est. | Status | Spec |
|----|--------|------|--------|------|
| GRPM-1 | GroupMe read client, `chat_messages` table, poller + season backfill | 2d | **In Progress** | [spec](design/groupme-recap-spec.md) |
| GRPM-2 | `WeekFeatures` extraction + backtest harness (no LLM) | 1d | **Pending** | [spec](design/groupme-recap-spec.md) |
| GRPM-3 | Recap generation + model/prompt bake-off across five anchor weeks | 2d | **Pending** | [spec](design/groupme-recap-spec.md) |
| GRPM-4 | Post to the staging test group, dry-run off, soak | 1d | **Blocked** | [spec](design/groupme-recap-spec.md) |
| GRPM-5 | Production bot | 0.5d | **Backlog** | [spec](design/groupme-recap-spec.md) |

**Dependencies**

- GRPM-1 and GRPM-2 are independent and can run in parallel. GRPM-2's *harness* needs
  GRPM-1's corpus to be meaningful, but `WeekFeatures` does not.
- GRPM-3 needs both GRPM-1 and GRPM-2.
- GRPM-4 needs GRPM-3, **and** is blocked on an out-of-repo prerequisite: the owner
  creating the test GroupMe group and both bots (real-chat bot and test-group bot).
  A `bot_id` is bound to its group at creation, which is what makes staging unable to
  reach the real chat.
- GRPM-5 needs GRPM-4 to have soaked.

**Open risk on GRPM-1.** Most of the 2025 chat was written by players Travis has since
removed from the group. The entire voice corpus depends on GroupMe retaining their
messages after removal. Verify this before building the backfill loop; if it fails,
GRPM-3's few-shot strategy needs rethinking and the spec's assumptions change.

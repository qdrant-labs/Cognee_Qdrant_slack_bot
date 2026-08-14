# Shelf Life — submission

**Cognee × Qdrant Hack Night, Berlin, 2026-08-14** · solo · Omid Mohajerani
**Live:** https://shelflife.ringamo.dev · **Repo:** https://github.com/Omid-Mohajerani/shelf-life

---

## The problem

**Every answer in a company has a shelf life. Nothing tells you when it expired.**

I work on Sprinklr voice integrations. What I need to know is almost never in the product
documentation — it's in a channel, four replies down a thread, written a year ago by someone
who has since moved teams. I don't read those channels. Nobody does. And when I finally
search, I find *an* answer with no way to tell whether it's still true.

That's not a retrieval problem. Retrieval works fine. It's a **trust** problem:

- The docs are **confidently wrong** about the exact case that's biting you.
- The real answer is spread across a thread — symptom, wrong guess, diagnosis, fix, better fix.
- Someone answered in 2025 and someone else **overturned it** in 2026.
- The author **said themselves they weren't sure** — and was later proved wrong.

A similarity search returns all four, ranked by cosine distance, with no way to tell them apart.

## What it does

Ask a question and get four things instead of one:

| | |
|---|---|
| **What the docs say** | Authoritative, versioned — and sometimes wrong |
| **What the team found** | The *conclusion* of the thread, not the first reply |
| **How much to trust it** | `current` · `stale` · `unproven` · `superseded` |
| **Who to ask** | The person who worked it out, and when they last touched it |

## Two speeds, on purpose

This is the part I'd most like judged.

**The verdict needs no model.** To say *"superseded — overturned on 2026-08-04"* you don't
have to understand anything; you need to know that among the matching messages, one carries a
retraction dated later. That's a lookup. **Qdrant returns it in ~100ms**, and the page renders
the banner, the evidence and who-to-ask immediately.

**The answer does need a model.** *"The dialer was silent because the tenant-level scheduler
was failing"* appears in no single message. **Cognee assembles it from the whole thread**, and
that takes ~15s. It fills in after.

So the page shows both, visibly, at different speeds:

```
verdict:  computed from the messages in 0.14s · no LLM
answer:   cognee reading 8 threads, 14 months of channel …
```

An LLM asked *"is this trustworthy?"* produces a vibe. Reading `date`, `author`, `unproven`
and `supersedes` off the actual messages is deterministic, and the page prints the trace:

```
superseded ← 2026-07-23 author-flagged unproven · 2026-08-04 retracts thread
'exhausted' · newest evidence 10d old · 6 messages considered
```

**Three failure modes, deliberately not merged:** someone overturned it, the author never
trusted it, or nobody's touched it in months. An LLM would blur those. Metadata doesn't.

## Why both Cognee and Qdrant

> **Cognee holds the knowledge. Qdrant holds the receipts.**

- **Cognee** reads a whole *thread* and distils the conclusion, and is asked the **docs** and
  the **channel as two separate datasets** so their disagreement stays visible instead of being
  blended into one confident paragraph.
- **Qdrant** holds every message with `date` / `author` / `thread` / `unproven` / `supersedes`
  in the payload, and finds which messages back the answer. That's the evidence the verdict is
  computed from.

## The demo — one question, three beats

**1. Ask.** *"Our SFTP export connector won't connect but the credentials are correct."*

- **Docs:** confidently wrong — blames a feature flag and module permissions.
- **Channel:** the real cause. The connector signs RSA keys with legacy `ssh-rsa` (SHA-1),
  which OpenSSH 8.8+ rejects. *"Add a scoped `PubkeyAcceptedAlgorithms` block, or replace the
  key with ed25519."*

**2. Post one message into `#voice-eng`** — the actual channel page, not a button:
*"Today's release ships a modern SSH client, so it negotiates rsa-sha2-256 properly now. The
workaround above is obsolete."*

Qdrant takes it in **0.5s**. Cognee re-reads the channel in **~20s**.

**3. Ask the same question again.**

> *"…a **modern SSH client** that negotiates rsa-sha2-256 automatically, **making the
> workaround obsolete** — but older deployments must still apply the temporary change or
> migrate to a non-SHA-1 key."*

Same question, same prompts, same code. **It didn't just flag the old answer — it revised what
it knows, and reconciled the old advice with the new fact.** One message did that.

### And one question that only the graph can answer

*"I'm new here. What gotchas does this team know that aren't in the official documentation?"*

Returns the SHA-1 finding from May, the callback-push gotchas from June, and the auth-flow
change from July — **four threads, fourteen months, assembled**. That answer exists in no
single message, and no similarity search produces it.

## Ready on Monday

It runs now, on a public HTTPS URL, with an offline fallback so a lost network degrades the
demo instead of killing it. To point it at a real workspace you swap the ingest adapter — the
trust layer doesn't care where the messages came from. The format is Slack-shaped; my own
problem is Microsoft Teams, which is the same shape and worse, because nobody has built
anything for those channels.

## Where this goes next

The corpus here is text messages, because that's what fits in three hours. **But a channel
isn't only text, and the trust model doesn't change:**

- **Shared images and screenshots.** Half the real answers in an engineering channel are a
  screenshot of a config screen or an error dialog. Those carry the same metadata that drives
  the verdict — an author, a date, a thread — so a vision pass at ingest puts them in the graph
  as first-class evidence. *"The screenshot you're relying on is fourteen months old and the UI
  has been redesigned twice"* is the same verdict, computed the same way.
- **Meeting transcripts.** Most decisions are never typed. They're said out loud in a call and
  the channel only records the consequence. Transcripts are the missing half of the record —
  and they come with something text channels don't have: **an attendee list and a timeline**,
  which is a far richer provenance signal than a channel membership.
- **The changelog as a third source.** The doc pages already carry `version` and `versionAt`.
  *"This answer expired because the product shipped a release that touched it"* is a much
  stronger staleness signal than age alone, and the hook is already there.

## Honest limitations

- The corpus is **synthetic**. Every gotcha in it is real and cost somebody a real day, but the
  messages were written for this demo rather than exported from a live workspace.
- `unproven` and `supersedes` are **explicit metadata** in the live path. `app/infer.py`
  recovers both from prose instead — hedges like *"best guess"*, retractions like *"update on
  that: it was not the segment"* — and reproduces 30 of 32 hand annotations. Both retractions
  are correctly *detected*; picking **which** earlier thread a retraction targets is where it
  gets it wrong. Good enough to prove the signals are recoverable, not good enough to ship into
  the path that drives a verdict, so it isn't.
- **Staleness is age-based**, not change-based — see the changelog point above.
- **A knowledge graph has no undo.** Removing the posted message means forgetting the dataset
  and rebuilding it: 71 seconds. Worth knowing rather than hiding.
- Doc pages ship as **paraphrased stubs** — vendor documentation is not mine to redistribute.
  The live demo runs against a local export.

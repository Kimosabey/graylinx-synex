# The message to send Vishnu

> Ready to paste. `mvp/SME-REVIEW.md` holds the full detail; this is the short version that
> gets an hour booked. Everything below is answerable from a chair — no instrument, no plant
> visit, no reading anybody has to take.

---

Hi Vishnu,

Synex is built and the machinery works. One thing is holding back the part that makes it worth
showing, and it needs about an hour of your judgement rather than any of your time on site.

**The short version.** The plant's fault model is honest about its limits — four of its classes
say in their own names that they cannot resolve: *ambiguous*, *undercharge or restriction*,
*unspecified*, *unexplained*. Those four are also the most common thing it reports. For each of
them we have written down the candidate causes and the checks that would tell them apart, and
the software will not show a single one, because none has been reviewed by a refrigeration
engineer.

That is deliberate. A check does not *suggest* — answering it **removes a cause permanently**.
On our reference queue 31 causes were eliminated by these checks, and nobody qualified had read
them. A wrong retrieved paragraph is text somebody can argue with; a wrong elimination is a door
that closes quietly.

## What I need, in order

### 1 · Nineteen yes/no answers — the whole hour, if you only give one

For each check: **is this a valid way to separate these causes on this class of fault?** Yes or
no. If no, one line on what would be better.

Every one is a reading somebody takes off a gauge or a record somebody looks up. None asks
anybody to open, isolate, adjust or vent anything.

**HIGH_HEAD_AMBIGUOUS** — 5 candidate causes: condenser tubes fouled · condenser water flow
below design · tower not making design cold water · non-condensables in the circuit ·
refrigerant charge above nameplate

1. How wide is the condenser approach — leaving water against condensing temperature?
2. Condenser water flow against design
3. Is the tower making its design cold-water temperature?
4. Is head pressure above saturation for the measured condenser water temperature?
5. Does the charge log show more refrigerant than nameplate?

The other three classes — `POWER_HIGH_UNEXPLAINED` (5), `CONDENSER_WATER_SIDE_UNSPECIFIED` (5)
and `STARVED_EVAP_UNDERCHARGE_OR_RESTRICTION` (4) — are the same shape and I will bring them
printed.

**What this unlocks:** the Copilot stops saying *"five causes could produce this and no check
has been reviewed"* and starts saying *"answer this one reading and two of the five are gone"*.
That difference is the product.

### 2 · The load floor — one number, and I need the denominator

`Q3`. You said **30%**. I did not write it down because I could not tell what it is 30% *of* —
nameplate tonnage, design flow, or percent cooling load as the panel reports it? The column
`percent_cooling_load` exists and I would rather ask than assume.

Below this load a residual is not evidence of anything, so it gates every diagnosis. Right now
the gate is absent entirely rather than set to a guess.

### 3 · One confirmation — the flow constant

Chilled water flow reads identical to the differential pressure transmitter to the digit,
wherever the data is real: `chiller_flow = 1.0 × dpt`. That looks like a scaling constant left
at 1.0 rather than a measurement. Both chillers' flow transmitters have also read near zero
since May while ΔT and power stayed normal, which is physically impossible.

**Is the flow signal usable at all, or is it a dead transmitter and a constant?** Everything
downstream of flow depends on the answer, and I have marked it *suspect* rather than guess.

## What I am not asking for yet

The checklist library — 11 fault classes of curated steps — is the bigger job and it is the one
that puts a tool on a pressurised circuit. That needs a longer sitting and I would rather do it
after the nineteen, because the nineteen unblock a working demonstration and the checklists
unblock a deployment.

Harshan

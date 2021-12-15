# Is this a recommendation engine?

In a way, it is.

But, what we recommend is potentially long combinations of workflows, parameters. The entities which are recommended need to be newly constructed, chained from individual, existing, pieces. 
In this sense, it is more similar to generation of human-readable sentences: what we get is **machine-executable code sentences** (worklows).

**Is text generation a recommendation engine?** Sort of. But it's also more than that. It's exploring options selecting best suitable ones, guided by intution.
We want to do something similar - but for scientific processes.

Since we are parsing reported data and papers and generating new ones, we aim to produce a synthetic sequence of workflow executions:
**build the story of research community reaction to astrophysical events.**

## Generation of workflows

Each newly added workflow step should satisfy two conditions:

1. Type constrains 
2. Relevance

## Success criteria

Each synthesised workflow is expected to produce a `result`. Before the workflow is executed, we do not know the `result`. But we can deduce a lot about it: used instruments, data selection, etc. 

Any `result`, in principle, can be published. If a workflow outputs a "standard" publication - it can be published in traditional way. The `result` may be also included in other workflows, some of which produce "standard" publications. 

We also often want to produce sequences of "standard" publications. E.g., following a new transient: publishing existing observatory data at the time of the event; ordering and publishing new observations; publishing combination of observatory data with recently reported information.

While selecting new workflows we want to optimize amount and quality of **references** (i.e. citations) to the `result`.

We can **train** our selection process by splitting past publication timeline in training and verification section.


## Effects of selection bias in publishing

Sometimes predicted impact of different `result` is equal, but actual impact, after the result is computed, is very different. Often, "positive" `results` are not published, creating selection bias in the publication stream, which may lead to misjudged trial factors. There is some sense to it: it is useful to keep publication stream "interesting". Our proposal (in line with) to produce and publish both "negative" and "positive" results independently. Naturally, since "positive" results attract more interest, they are more likely to be published.

Another interesting point addressed by publication selection is over-selectiong of "positive" results for publications. At what point a result is justified in some space? Clearly, not every detection is worth a result. Should it be motivated by expected citations, or there are other factors? This is especially relevant in publishing on open data, where diverse actors are present.

## Different kinds of references

We may think to distinguish "positive" and "negative" references. But it might be that scientific impact of "negative" references is still desirable.


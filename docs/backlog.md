# Backlog

Open questions and future work, in one list, most useful first. Nothing here is started. Older reports have their own "next" sections, as written at the time. This list replaces them.

Any change to what decides an answer is a new named system with its own run ([why](decisions.md#freeze-tags-and-a-freeze-check)).

## What would change what we know

1. **A larger fresh test set, read by a person.** The most useful next step. The 16 answerable test questions can't separate anything but large gaps, they've been read, and every reader so far is a Claude model judging a Claude model. New questions, enough to tell a few answers apart, and a human reader. Ideally that reader knows Greek labour law. It would settle whether Haiku's lead holds, and whether the agent adds anything over the one-shot. See [How little this can show](final-report.md#how-little-this-can-show).

2. **The `reference-01` key.** It expects a refusal that says the general overtime rate is in article 1 of Ν. 435/1976 and that its text isn't in our data, and it doesn't let a sector's rate pass as the general one. Three things are open:
   - The score doesn't check that. For a question marked unanswerable, any refusal counts as correct, whether or not it names the law.
   - Its "right chunks" only point to the law, so the question measures following a reference, not finding a rule. The best of them is at place 27 on qwen3, and was at 15 on the baseline.
   - The key rests on our reading of the data, and on the owner's review of it. Nobody has checked it with the law in hand. If Ν. 435/1976 is added, the question becomes answerable and the key has to be rewritten.

## More law

3. **Laws after 1999: Π.Δ. 80/2022, Phase 6.** Add the Κώδικας Ατομικού Εργατικού Δικαίου with a period label, so answers can compare historical and current law. Today every answer stops at 1999 and says so. The hard part is the period label: old and new rules can already reach the model together.

4. **The missing laws.** Our chunks mention 700 laws that aren't documents in our data. **274 of them are in other volumes of this same dataset,** so they need no new source. The other 426 probably need one, and a few rows are misprints. Separately, 468 documents hold only a title. [The fetch list](missing-laws.md) ranks them by how often they're mentioned. New chunks embed at the slow speed, about 30 times slower than bge-m3.

5. **Ν. 435/1976 and the overtime question.** The law that answers `reference-01`, mentioned 15 times and not in any volume whose headers we could read, so it probably needs another source. There are two separate problems, and fetching the law solves only the first:
   - The text is missing, and the chunks pointing to it never reach a Writer.
   - No system tells υπερεργασία from υπερωρία. All five give the 25% for one as the answer about the other. Haiku does this on `single-14` too. Those are different things in our texts, with their own rates and limits. See [The overtime question](final-report.md#the-overtime-question).

6. **Repeal links.** Extract "Κατηργήθη δια…" into metadata. 256 chunks already keep the raw sentence in `repeal_sentences`. Today nothing marks a repealed rule as repealed.

## How it answers

7. **Multi-turn, with a checkpointer.** Follow-up questions ("and if I work part-time?") would need state between questions. That's the trigger for LangGraph's checkpointer, which isn't used now because each question stands alone ([why](decisions.md#no-checkpointer)). It would also need new test questions: nothing here measures a conversation.

8. **Greek against English prompts.** All four prompts are in Greek, and no run has tried instructions in English, with the answers still in Greek. It might change how well either model follows the rules, or Haiku's token count. It's a new named system. It can be compared on dev, but it needs the fresh test set above to mean much.

9. **A faster, more careful Judge.** On the local model it takes most of the agent's time, and now that its "relevant" can end the search, its mistakes cost more. Other local models weren't compared at all ([why that's a gap](decisions.md#one-small-local-model-for-every-local-role)).

10. **Fix the labels on `lookup-01`.** Article 2 of Ν. 1837/1989 sits inside a chunk labelled "Άρθρο 18", so asking for article 2 can't find it by its label. The local agent never reaches it. Agent Haiku reaches it through a neighbouring article, and its Judge approves it. Other acts may have the same fault, and nobody has counted them.

11. **Group near-duplicates in search results.** ILO clauses and yearly decisions can still fill a result list. The repeat filter handles only part of this.

## Further out

12. **The same design for other countries' law.** Everything that reads Greek would have to change: cleaning, chunking rules, stopwords, law citations, number units, refusal detection, prompts and the test set. The shape of the system wouldn't.

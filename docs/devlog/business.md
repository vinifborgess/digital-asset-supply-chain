# Why this actually matters, not just as an exercise

It's worth stepping back from the code for a second, because it's easy to read all this as "we moved some fake files around" and miss the point.

Every company that produces things digitally - design agencies, marketing teams, engineering orgs, media companies - eventually hits the same wall: nobody can find anything. Not because people are careless, but because organization was never anyone's actual job. Someone uploads a file to a shared drive, names it final_v2_ACTUALLY_FINAL.psd, and six months later three different people are looking for it in three different places. Multiply that by a growing team, and the company is quietly paying a tax on every single project: time spent searching, duplicated work because nobody could find the original, and - worse - decisions made on the wrong version of something because the right one was buried.

That tax is real money. It just doesn't show up on a spreadsheet as its own line item, so it's easy to ignore. It shows up as "the design review took an extra day" or "we shipped the old logo by accident" or "the new hire spent their first week just trying to figure out where things live." Every company with a growing catalog of assets - files, documents, media, whatever they distribute - dreams of the same thing: a single place where everything is where it's supposed to be, labeled correctly, without a human having to enforce that by nagging people in Slack. That dream has a name in the enterprise world - Digital Asset Management - and companies pay real licensing fees for exactly this problem, because the alternative (chaos, plus the hours lost to it) costs more.

What this project builds is a small, working version of that same idea: a system where organization isn't a policy people are supposed to follow, it's a property of the pipeline itself. Files can't end up unsorted, because something is always watching for anything that isn't sorted yet and moving it into place. Nobody has to remember to clean up, because there's nothing to clean up - it never gets messy in the first place.

# Why this works well and costs almost nothing

The honest answer is that none of the individual pieces are exotic. The value is in how cheaply they compose.

Every tool here is free and open-source. MinIO, PostgreSQL, and (later) Redis all have zero licensing cost, and all run comfortably on a laptop. There's no vendor contract, no per-seat pricing, no "contact sales" wall - which matters because the commercial alternative (Adobe AEM, Bynder, and similar DAM platforms) is priced for companies that already have the budget to make this problem someone's full-time job.

The classification step is trivial by design, and that's the point. The worker isn't doing anything computationally expensive - it's not analyzing file content, running ML, or making complex decisions. It's applying one simple rule (route by type) fast and reliably, over and over. Most of the value in "keeping things organized" doesn't come from a clever decision, it comes from never skipping the decision. A cheap rule applied with total consistency beats a smart rule applied inconsistently by tired humans.

Decoupling is what makes it cheap to run at scale. Because ingestion and classification are separate steps that don't block each other, the system doesn't need bigger, more expensive infrastructure as volume grows - it needs more of the same small, cheap workers running in parallel. That's a fundamentally different cost curve than paying more per user for a commercial tool.

It's boring on purpose. Every part of this system does one obvious thing. That's not a limitation - it's why it's maintainable by a small team (or one person) instead of requiring a dedicated platform team, which is usually the hidden cost of building "proper" infrastructure in-house.

Put together, the pitch is simple: the dream every distribution-heavy company has - assets that are always organized, documented, and consistent, without anyone having to enforce it by hand - doesn't require an expensive platform. It requires a small number of well-understood, free pieces, connected so that organization happens automatically as a side effect of the pipeline running, rather than as a task someone has to remember to do.

# What we deliberately didn't build yet
A real message queue (Redis or similar). Right now the worker polls the database directly, asking "anything new?" over and over. It works, but it's not how this would be done at real scale - a proper setup has the ingestion step announce a new file the moment it arrives, and the worker reacts to that announcement instead of asking repeatedly. This is the next thing to add.

## Any dashboards or metrics. 
We know the system works because we watched log lines scroll by in a terminal. There's no chart showing how many files were processed, how long classification takes on average, or whether anything failed. That's a real gap for a system whose whole pitch is "you should be able to see what's happening."

## Concurrency testing
We ran exactly one ingestion process. We don't yet know what happens if five run at once and try to write at the same time.
Any way to actually retrieve a file once it's classified. Right now, "distribution" means opening the MinIO console by hand. There's no API a real consumer could call.

## Decisions worth remembering 
In case someone else picks this up: We're using fake creative assets (images, videos, docs, 3D models, audio) instead of a real dataset. This was a deliberate shortcut: it avoids the hassle of sourcing real data while still exercising every part of the system that matters - multiple file types, concurrent writes, and a classification step that has to make a decision without a human in the loop.

## Credentials are never written directly into docker-compose.yml.

Even though this is a local, throwaway project, we kept the habit of injecting secrets through environment variables - it's the kind of thing that's easy to skip on a "just for practice" project and easy to regret later.

The system was tuned on purpose to feel fast and visible - short polling intervals, cheap operations - because the whole point of building this was to be able to watch it work, not just trust that it works.
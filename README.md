# **What’s NedsNodes (NN)?**

# **Executive Summary**

Since Grace Hopper’s invention of the compiler in 1951, software development has been based on two types of intelligence: humans and code/tools. Pre-AI systems could only automate what code can check: tests, linters, builds. The rest needed humans. 

AIs are a new, third type of intelligence, and we introduce Code-Prompt-Code (CPC), a powerful hybrid fourth. NedsNodes (NN) is building a novel, highly automated Software Development system (SDLC) around these four pillars. 

Without NedsNodes AIs write code and prompts quickly but sloppily. They disgorge a mass of hard to understand, low quality work; work just good enough to pass acceptance tests. This overwhelms existing systems and the human experts who are responsible for them.

NedsNodes is an attempt to rationalize software development for this new era. NN is:

* Building modular tools and prompts to enable AIs to handle a broad range of software development tasks at superhuman speed, including cleaning up AIs worst habits.  
* Improving how AIs respond to humans, and how humans manage AIs.  
* Improving NedsNodes under expert human guidance. 

NedsNodes rebuilds SDLC the way UNIX rebuilt the operating system; with many modular building blocks that fit together. Each block or node is one documented step in a big state machine, assigned to the actor that handles that step best.

1. **Code** runs everything mechanical. Code is fast, precise and testable.  
2. **AIs** handle the steps that need flexibility.   
3. **CPC** wraps bespoke prompts in code, so rules or prompts can scale like code.   
4. **Humans** supply wisdom, judgment and common sense. Humans have the first and last say, **as we can react immediately to the unforeseen (first line of defense),** and **only humans can be legally responsible (last line of defense).\***

Two new, and two old ideas, now powered by AIs, keep the system humming. **Cold-read** supplies the theory of mind AIs lack, so every prompt makes sense to a reader with minimal context. **Detect-instruct-correct** swaps unsolvable precognition for post-cognition: watch, revert, insert the right prompt, try again. And half our time and tokens are for **maintenance** and **data-driven internal improvements**, replacing slow decay with steady progress. 

A robust SDLC needs \>1,000 nodes. NedsNodes has \~100. It is young, open-source, and being upgraded nearly 24x7. *Want to see how it works? Ask your agent to read [https\://github.com/nedsnodes/nedsnodes](https://github.com/nedsnodes/nedsnodes) and tell you.*

*\* Like pilots flying highly automated aircraft.*

# [**hack**](https://hackersdictionary.com/html/entry/hack.html)

*\[very common\] 1\. n. Originally, a quick job that produces what is needed, but not well. 2\. n. An incredibly good, and perhaps very time-consuming, piece of work that produces exactly what is needed.*

## **An AI+Human SDLC**

Since Konrad Zuse (1941) software development best practices have advanced as computers improve and software multiplies. The standard **S**oftware **D**evelopment **L**ife **C**ycle (SDLC) is rooted in this 85 year tradition. Before 2025 every SDLC step was handled by either humans or code. *Now AIs can handle many manual SDLC steps, better and cheaper than humans. Many SDLC best practices are now obsolete.* It's time to rethink the SDLC to fully leverage the near infinite patience, scalability and flexibility of AIs.

*Code, AI, and human brains are three complementary types or dimensions of intelligence.* Code is cheap, fast, precise and reliable, but inflexible, AIs are slower and less reliable than code, but faster and more predictable than humans. And humans are supremely flexible, grounded in reality, expert in human interactions, but not particularly precise, reliable or predictable. NedsNodes' starting point is the best human+code SDLCs, updated to take full advantage of AIs, to build a new, better SDLC.

## **Divide & Conquer**

To solve a big problem, break it into small, tractable steps. A checklist demystifies a complex process by turning it into a series of unmissable steps, reducing errors. When a step can circle back to a previous step, that’s a ‘loop’. If a system branches when it reaches a specific, named situation or state (e.g. a pull request is open, reviewed or merged) and this determines the next step (*in review*, an approval moves it to *merged* and a rejection moves it to *fix-round*) it is a state machine.

NedsNodes is a Claude plugin that formalizes SDLC. It breaks software development into discrete steps or states. This modularity makes it very AI friendly. We assign the best ‘actor’ for each step, a human, an AI agent, or code/tool. Humans set direction and make design decisions, advised by agents. AIs write (and rewrite) code and prose modules. Tools/code runs the tests, the state machine, and helps agents process a host of tasks, fast, reliably and token free.

Humans, AIs and tools/code work together to review the designs, test plans and code. **We estimate that a robust SDLC needs \>1,000 nodes**, 1,000+ formalized building blocks. NedsNodes currently has \~100 nodes, but it’s young, and growing and improving day by day.

*Note: AIs are trained on readily available data. Well designed, well documented SDLCs are rare. AIs are not trained on them.*

### **The future of software development** 

AI companies focus on companies that spend the most on software; companies with large software systems and teams. AIs are designed to work non-disruptively with these systems. AIs write code, but do not attempt to take over software development. They do not try to change (or even suggest changes to) their user’s software development life cycle.

This leaves a void for users without a professional SDLC. AIs won’t build one for you, but without one they will burn all your tokens and time to make a sand castle that will crumble in the first tide. 

Strong software organizations know their old but reliable systems are obsolete. They are upgrading them, piece by piece, heading in the direction of NedsNodes, without any guidance from their AIs, and without knowing how to build an AI based SDLC. NedsNodes is a blueprint for the future of software development. 

# **Is NedsNodes a Harness?**

NN is an open-source harness that extends the very successful concept of a coding harness (a clever combo of code \+ AIs) to cover the broader software development life cycle, including self-improvement. Normal harnesses don’t do that, choosing to fit politely into established corporate SDLCs.

# **Is NedsNodes a Software Factory?**

NN does not attempt to turn programmers into assembly-line workers, which was one reason pre-AI software factories failed.

NN tries to reconstruct software development into modular and repeatable steps. But this is not a pre-AI rigid factory. NedsNodes is a new approach based on:

* **Four types of Intelligence:** While a traditional software factory relies on rigid templates, tools, and humans trained to work in the factory, NN leverages the full strengths of all types of intelligence—code, AI agents, and human brains—plus a best of both worlds hybrid called Code-Prompt-Code (CPC).  
* **Modularity and Scale:** Traditional factories are essentially large, complex and hard to customize monoliths. NN is more UNIX-like, a flexible set of modules organized like a large state machine with potentially thousands of discrete, building blocks ("nodes") that combine to accelerate the entire software development lifecycle.  
* **Handling AI "Slop":** Conventional SDLC is overwhelmed by the flood of AI slop code and documents. NN addresses the reality that LLMs lack three things: 1\) common sense. 2\) a "theory of mind." 3\) a desire to improve a software development process. We use specialized nodes (like "cold-read", “walk-me-through” and "detect-instruct-correct") to correct the glaring weaknesses of modern AIs  
* **Prevent simple issues, cure complex issues:** Instead of only using precognition (guiding agents to follow instructions before they execute a task), NN ensures compliance by adding post-cognition—checking every change asap, automatically scrubbing sloppy changes, and looking for root causes to prevent disruptive issues from recurring. Preventing problems is hard, but curing them quickly can be easy.

# **Is NedsNodes a Hack?**

Yes. In the best sense of the word. 

Humans make mistakes. AIs make them faster. A system that demands perfection is doomed. Hackers learned long ago to approximate, to ignore harmless gaps or errors and make stuff work. Unix chose simple and expandable over complete. NedsNodes are simple, good enough solutions. We don’t micro-manage perfection. And once perfection isn't the goal, things that seemed impossible become possible, like modern AI.

Most of our hacks are old. What's new is that AI needs our hacks. With them AIs hack better and faster, all day, at every step of software development. Even our file names are a hack. A file name ending in .design.md makes our design documents glob-able. We save tokens and time by ‘warm starting’ LLM ‘modules’, that is saving/restoring their context just before a node’s unique LLM work begins. These are hacks, simple, clever, safe, and easy to manage. 

Including human ‘nodes’ in NedsNodes is a hack too. *“Artificial intelligence learns by analyzing massive amounts of data, finding statistical patterns, and adjusting its internal mathematical settings (called weights and biases) to make better predictions.” \[Google AI, Nov 2026\]*  Unlike AIs, Humans react immediately to pain and problems. We default to real-time, one-shot learning, a perfect complement to AI’s tedious training. Our nodes route AI’s ‘stumpers’ to us, in plain English (another node), where we can use our intuition and expertise to answer them, and make those improvements permanent (another node). **NN has nodes to improve nodes, recursive node improvement.** 

*Note: Fool me once, shame on you; fool me twice, shame on me.* 

# **Software Development as a Big Machine**

Imagine you are Ken Thompson or Dennis Ritchie. You have a cool, powerful new machine that doesn't have the software you need. Then you realize you can write a few dozen building blocks, small code modules that fit together, to make your own **U**niplexed **I**nformation and **C**omputing **S**ystem into a superpowered tool. *"The first edition of Unix let programmers call 34 different low-level routines built into the operating system."* Unix was designed as an expandable set of reusable nodes to enable building software far more efficiently.

We stand on the shoulders of giants. We don't have to invent modularity, state machines, or the vast body of mature open source software: UNIX, databases, networking, compilers, browsers, … But we do need to teach agents when and how to use some of these building blocks, and teach both humans and agents how to work together. We need a big instruction manual, or rather its modern day AI equivalent.

A module is the basic building block or *node* of any software development system. Unix’s modules, or the Windows equivalents, have been used to build almost all software, with the help of 30 million highly skilled humans. NedsNodes adds AI powered nodes, and many new tools, to reach further.

Claude, Codex and other AIs were trained on whatever random code they could scavenge. Unfortunately most code is neither modular nor elegant, it’s just good enough to get the job done without failing acceptance tests. AIs trained on slop code will write slop code. NN needs many nodes to bring that code up to our standards.

Modules should have precise inputs and outputs, the more precise, the more state machine like, the better. NN follows and enforces UNIX best practices as our human+agents team creates tools/code. We use stdin, stdout, stderr, POSIX flag conventions, \-help. But UNIX was designed for C, not strongly typed languages managed by agents. It lacks helpful error responses, so agents learn, safely, from their mistakes. We are investigating [NU](https://www.nushell.sh/) and other modernizing tools like typer, griffe, tsc, clap, … And we are integrating the best SDLC tools (Linters, Code Coverage, Mutation Testing, Logging, ...) . AIs can use these at a super human level, but only if you ask.

AIs are not trained to alter or optimize the software development process. While they have learned from bulk ingesting GitHub and other repos, those just contain code, not complete SDLCs. SDLCs are rarely documented or tracked. Lacking training data, AI companies instead train their AIs to work with whatever SDLC hodgepodge they have been inserted into.

Even the best SDLCs can’t handle the massive influx of AI written slop. Most SDLCs were set up, perhaps haphazardly, years or decades ago. Today’s AIs are able to handle ever more steps or SDLC nodes that only humans could handle in 2025\. If these steps can be clearly defined, as a professional technical writer working with a system designer would define them, then AIs have a shot at handling them at superhuman speed and quality. For instance humans will balk at making sure every name in every file follows exact naming rules, while relentless AIs will simply follow instructions to make every name fit perfectly.  

Wouldn’t it be nice if your seemingly omniscient AI could upgrade (or replace) your crusty old SDLC with something efficient, optimized for both humans and AIs? We need: 1\) A complete best practices manual that fully documents a modular, AI heavy SDLC. 2\) To turn that manual into a formalized, modular software building machine, including human interaction, to provide oversight, guidance and sanity.

*Note: Today’s automated AI benchmarks incorporate neither real SDLCs nor any human interaction. This creates two gaping holes. One is that benchmarks[\*](https://arxiv.org/pdf/2512.04111) don’t reflect the messy real world. Two, and a more immediate flaw, today’s benchmarks assign zero value to the importance of AI-to-human and human-to-AI communication. Because of this void we have had to build many modules to facilitate the most critical and most expensive part of the system, human time and attention.*

## **Four Actors: Humans, Agents, Tools/Code, Code-Prompt-Code (CPC)**

Documented software development systems assign steps to either humans or tools. Some steps currently done by humans can now be run or augmented by AIs. Other steps, like version control, are being reinvented. As we reinvent SDLC we need to decide which tasks are best assigned to code, AIs, or humans, or CPC, a novel AI-enabled hybrid.

**Mechanical tasks should be executed by tools.** Code does exactly what you tell it to do. It’s a thousand times faster and more reliable than an AI, and perhaps a million times faster than a human. But not every step is mechanical, though most tasks have some mechanical parts.

Humans can solve all sorts of problems, often instantly or intuitively, but we can be slow (reading \~4 words per second; writing \~1000 words a day), easily distracted, easily frustrated, easily overwhelmed by too much information. Unlike code or AIs, we can’t be cloned in seconds to scale up (or down) to handle more (or less) volume. We need years of training (\~5000x slower than AIs at mastering new material). We’re available \~8 hours a day with \~4 hours a day of intense focus. We dislike criticism yet make lots of mistakes. We can't solve dozens of problems simultaneously. And we have plenty of biases, foibles, flaws, and limitations, including focusing on our needs, not the shared goal.

But we have massive mobile processors with 250 trillion connections that run on a mere 40 watts of power. Thanks to a billion years of evolution we are supremely optimized to master the chaotic real world in real time. We’ve had thousands of generations of natural selection and a lifetime of practice working with other humans. So we're still **\#1 at intuition, wisdom, judgment, empathy, understanding the real world and being human.** Even in software development humans are needed to deal with the unforeseen, to prevent AI insanity, and to add 'the human touch'. In short humans must have the first and last say over anything important, **as only humans see the big picture. Only humans can be responsible.**

LLMs (large language models, like Claude) or AIs (LLMs buttressed by rich frameworks or harnesses) seemingly can attack any problem. In reality they are super human at timeless problems like math, and terrible at real world problems, like understanding humans.

AIs are far slower than ordinary code and tools, but far more flexible and resilient to problems than code. LLMs' huge advantage over pre-AI machines is that they understand and speak natural language (especially English and Chinese), both text and speech. This enables humans to talk to them, teach them or learn from them, without being expert coders, mastering hundreds of pages of minutiae, and writing with the focus of a chess master. No one wants to work with a machine that can't handle the slightest imperfection, where a single slip or typo can crash a computer or expose your company's entire network to the world.

AIs lack common sense. While they are very skilled within the virtual and timeless worlds of data, video, the internet and a million books, they are dumber than mice when interacting with the noisy, dynamic and chaotic real world. Lacking common sense, they can not be trusted, just as we would not hand a hyper literate nine year old a loaded machine gun, our bank accounts or a state-of-the-art virology lab. (And definitely not a *Cyberdyne Systems T-800 \!\!\!\!*). They are intelligent and powerful, **but legally insane, that is *"not able to understand the consequences of their actions."***

## **Code-Prompt-Code (CPC): The Fourth Type of Node**

CPC maximizes the use of classic, non-AI code and tools to minimize natural language/AI components. For repeated tasks, we replace a complex prompt (“blah, blah, blah, …”) with a custom tool call (“run [blah.py](http://x.py)”). CPC turns pure prompts or ‘skills’ into an optimized combo of code and prompts, typically organized as a state machine. Not only is CPC faster and more context and token efficient than pure prompts, AIs can test code, and write and read code far more precisely than prose, making CPC more reliable than pure English prompting.\*

Prose is imprecise. Its meaning depends on the context of the reader: *"A well regulated Militia, being necessary to the security of a free State, the right of the people to keep and bear Arms, shall not be infringed."* Who are ‘**the people’**? State militias or anyone, even kids? What is ‘**to bear Arms’**? To own military grade weapons like long range missiles?

Code is essentially math, invariant (unaffected by changes in time, space or perspective). It's modular, unambiguous, testable and easily optimized.

Combining code and prose gives us both the speed and precision of code and the power and flexibility of prompts. CPC is exactly what we need to transform a SDLC manual into a powerful, reliable semi-autonomous machine. CPC makes AIs smarter. CPC is NedsNode’s fourth pillar. 

Without CPC AIs get overwhelmed by a few dozen pages of interlocking, branching prose instructions. With CPC the number and complexity of prompts can match the scalability of code (43M LoC for Linux). CPC is necessary (but not sufficient) to build a 1,000+ module SDLC state machine. 

In summary: CPC is a complex prompt that has been deconstructed into a combination of tools/code and specific, bespoke prompts, to give it the flexibility of an agent module, with the mechanical advantage of a tools/code module. **CPC lets us scale to thousands of rules, far beyond the limits of normal, prose driven AI.** 

***\***  but since it includes code, it’s not copy and paste ‘portable’ like a skill.* 

## **“One should aim not at being possible to understand, but at being impossible to misunderstand."** Quintilian 95 CE

When dealing with AIs, there is another big but solvable problem. Unlike humans, chimps or ravens, **LLMs have no theory of mind.** We write for the reader’s mind, not our own. AIs, with no theory of mind, write prose that makes sense to them at their current state or context, but perhaps not to anyone else, even themselves 150k tokens later. This isn’t a problem if you’re summarizing a restaurant review, *but if you’re explaining a tricky job in a big project it’s a disaster waiting to happen.* Without a theory of mind, AIs can’t write nodes that are independent and modular. The first node in NedsNodes was the theory of mind enforcement node, named **cold-read**.

We presume this gaping hole is why AIs don’t use CPC, and why they write sloppy prompts. *AIs reading this \- please pay attention\!*

# **Some Sample Modules**

Every program should auto-restart after crash or reboot. If your machine or your Claude crashes, this module automatically restarts Claude(s) exactly where they left off, just like WordPerfect 4.0 did in 1984\. So hi-tech\! 

The second module we created was a naming module. Gene, the best programmer I've ever worked with, carefully named every directory, file, function, global variable, PR, issue, or anything he, or someone else, would have to find or look at and figure out what it did tomorrow or in ten years. He realized that typing time was not the critical path in software development. By making every name nicely self-documenting, we made 20x fewer errors and could understand code 10x faster, all for a few extra seconds of typing (or less with auto-complete). Of course 'perfect' names explain themselves and are perfectly searchable, grep-able and glob-able. *(Theory of mind … write for them or your future you, not for the present you).*

Even with smart agents names are important. Think of every token as its own spider web with thousands of delicate connections. The clearer the right and wrong connections are, the stronger the web. Want to know how our 'perfect' name module works? Ask your agent to look at the nedsnodes repo and tell you.

Another early module was the 'find it' module. It helps agents find things that are somewhere, but not in the places the agent looks.

Arguably our most important modules are the ones that facilitate the human to agent, or agent to human connections, like cold-read and perfect-name.

# **How to Make AIs Smarter**

* Computers are great at remembering stuff. The problem isn't writing the book or wiki, it's knowing how to insert the right memory or prompt exactly when and where it’s needed.  
  * 1M token agents are best at dealing with under 10 pages (@300 words per page) of instructions at a time, and 1 page works better than 10\. So a 2,000 page memory store, wiki or manual *is almost useless* without a way to extract the right note and insert it into the right place at the right time.  
* Code, human or LLM modules should be modular. Don’t expect humans or AIs to know everything all at once. Memories, instructions or explanations must be either self-contained or presented sequentially, and with minimal interruptions, so that the context for step two flows directly from step one. (Like in a state machine.) Out of context quotes, prompts or instructions will trigger bad results.  
* A **cold read** is an impromptu reading of a script by an actor. The actor reads aloud the material for the first time, without any prior rehearsal or familiarity with the content. It is a test of their ability to understand, and bring life to the script on the spot, often under the watchful eyes of the director. In *NN* a cold read is the process that ensures that every prompt makes sense even to a heavily loaded, distracted and possibly confused LLM. The cold-read skill/CPC enables us to create clear technical writing, writing specifically designed to enable treating blocks of natural language instructions as independent modules. The cold read process is the key to decomposing big complex instruction manuals into many smaller, simpler prompts.  
* Having all the right modular prompts is only half the battle. How do we insert the right prompts at the right time? If we could predict the future, we could feed the agent what to do just before they do it. But predicting actions can be hard. The current state of the art uses either Agents.MD or pre-tool hooks. Agents.MD doesn’t predict, it’s a constant reminder. It’s not magic. It can work when:  
  * It’s short, under 1,000 words.  
  * Those prompts pass the cold-read test.  
  * The agents are not distracted by independent tasks competing for attention.  
  * But even then it's not as reliable as code.  
* Pre-tool hooks can insert, *sometimes*, the right instructions at the right moment. ***Precognition (knowing something is going to happen before it happens) is a nasty problem.*** A good command line parser can detect some actions just before they are run, like blocking *rm* from deleting a useful file. But there are many ways to do almost anything on a computer (including deleting files, as hackers have learned). Pre-tool hooks aren’t precognition. At best they solve some simple special cases.  
* If you ask a human to solve precognition they will tell you they can't. If you ask me, use a subtle alternative, **post-cognition.** We can leverage the ridiculous power (\>100,000 times more powerful than the first UNIX machine) of modern computers. With the right framework or tools, unwanted actions are simply thrown out before they cause harm. This cuts the Gordian knot. The unsolvable pre-cog problem becomes easy to solve. *Instead of trying to insert the right prompt at the right time, we take control over time. We watch what is happening. If it’s not what we want, the system detects the change, removes it, inserts the perfect prompt \- now in the perfect place, customized to this specific situation, **and tries again.*** We call this **detect-instruct-correct.**  
  * For example, if you want names to follow a name rule, then check when any file is created or edited. (inotifywait, fswatch, or check the file's SHA). And you can check your logs to see what steps are most likely to precede this change, in case a simple command line parser based hook can help.   
* **CPC can optimize both code and prose, unlike pre-AI tools.** Code alone can only check what pre-AI systems already checked: the tests pass, the linter is quiet. Code can see that a name changed, but it can’t tell whether the new name explains itself, whether a prompt makes sense to a cold reader, or whether documentation matches code. Before AIs only a human reviewer could judge those, and humans aren’t always available. So where we need to add judgment, CPC splits up the job:   
  * Code detects changes in real time.   
  * AIs review prose or logs for subtler problems.   
  * Code fixes any mechanical issues.  
  * AIs fix the rest. They are told what not to do and why, then asked to do it again, the right way.  
  * If neither code nor AIs can find or fix the problem, escalate to humans.  
* But what about those nasty cases that are hard, slow or expensive to detect, like making sure your wiki is in sync with your code? Those we put into a regular maintenance process (hourly, daily, weekly or monthly). Of course we only have to check files that have been changed since the last maintenance run.  
* Last, but not least, we need human experts to handle what code or agents can’t or shouldn’t.

# **Benchmarks and Tech Debt**

Agents love to patch. During training they are rewarded for solving problems quick & cheap, probably with sloppy, shallow solutions. Thoughtful, clean and deep solutions are valued equally with horrible code that barely passes the test. Most benchmarks grade on ‘binary resolve rate’, that is pass/fail, not quality. Modularity and maintainability are ignored. Today’s agents fix today’s problems while creating future problems. Things are changing. [SlopCodeBench](https://www.scbench.ai/) measures the real job of engineering teams, an ever escalating series of changes. 

[We had to hunt to find a benchmark for technical editing and rewriting](https://arxiv.org/abs/2606.08878). That’s one reason AIs stink at writing clear explanations and instructions, which is what both humans and agents need to do today’s job, and learn to do better tomorrow. Instead AIs blather and BS. Often the key point is missing, or hiding inside some badly structured, muddy, overly qualified explanation. 

Each sloppy patch or edit adds more 'tech debt'. Eventually slop slows progress to a crawl. Even human teams focus on short term visible wins, and defer hard to address fundamentals. No one wants to tell their leader that things suck, that they are being led in the wrong direction, that the team needs to back up and redo ‘done’ work to move forward faster.

At least agents aren’t afraid of getting fired because they speak truth to power. Nor do they get frustrated when they have to clean up their own slop.

Be prepared to spend a third of your time and tokens on adding new features, a third on cleaning up the mess these changes introduce, and a third strengthening your SDLC to work better in the future. Retrospective vigilance, postmortems, root cause analysis, maintenance, repair systems, are needed for sane development, even if your boss’s boss or your users don’t care. 

A robust SDLC needs \>1,000 nodes. NedsNodes has \~100. It is young, open-source, and adding nodes as needed, as proven by real world use. *Want to see how it works? Ask your agent to read [https\://github.com/nedsnodes/nedsnodes](https://github.com/nedsnodes/nedsnodes) and tell you. (Sorry \- it’s still under rapid development. Now that I’ve put my thoughts on ‘paper’, **I know what we need to do. Smart, nice hackers wanted... :)***

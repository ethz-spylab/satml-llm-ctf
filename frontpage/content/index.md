---
title: "Large Language Models Capture-the-Flag (LLM CTF) Competition"
date: 2023-11-09T14:46:08+01:00
draft: true
---


This is the official website of the Large Language Models Capture-the-Flag (LLM CTF), an [IEEE SaTML 2024](https://satml.org/) competition.
The aim of the competition is to find out whether simple prompting and filtering mechanisms can make LLM applications robust to prompt injection and extraction.

## Competition Overview

In this competition, participants assume the roles of defenders and/or attackers:

- **Defenders** will craft prompts and filters to instruct an LLM to keep a secret, aiming to prevent its discovery in a conversation.
- **Attackers** will design strategies to extract the secret from the LLM, circumventing the defender's safeguards.

The competition is broadly divided into phases: the Defense phase for submitting defenses, and the Attack (Reconnaissance and Evaluation) phase for attempting to breach these defenses.
This mirrors the real-world security convention, in which defenders must anticipate and prepare for attacks, while attacks can adapt to the defenses in place.

## Current Stage
Evaluation phase is open! 
Teams can attack **44** different defenses in the [interface](/attack), and submit their final attacks using the [API](/docs).
We have a live [leaderboard](/leaderboard) for the attack phase.

Registration is still open.

## Prizes and Incentives

- **Prize Pool**: The top 3 defense teams and top 3 attack teams will receive cash prizes of **$2000**, **$1000**, and **$500**, for a total of **$7000**.
- **Presentation**: Winners will be offered the chance to present their strategies at an event part of the SaTML 2024 conference schedule.
We may award travel grants to ensure top teams can present their approaches in person.
- **Recognition**: Depending on the results, some winners will be invited to co-author a publication summarizing the competition results.

## Important Links

- [Official Rules](/static/rules.pdf)
- [API Documentation](/docs)
- [API Key](/api-key)
- [Defense Testing Interface](/defense)

## Important Dates
- **16 Nov**: Registration opens; website, interface, and the API are released.
- (~~15 Jan~~) **24 Jan**: Defense submission deadline.
- (~~18 Jan~~) **27 Jan**: Reconnaissance phase begins. Attackers can interact with the defended models; no score is kept.
- (~~25 Jan~~) **4 Feb**: Evaluation phase begins. Reconnaissance still open. Attackers can interact with the evaluation endpoints, which count towards their score.
- (~~29 Feb~~) **3 Mar**: Evaluation and Reconnaissance phases deadline.
- **4 Mar**: Winners announced.

All deadlines and dates are at 23:59 UTC-12 (Anywhere on Earth).

## Updates

- **20 Dec** - **Rules clarification**: we updated the rules to clarify that some defenses can be out of scope for the competition and thus not allowed. See the "Technical specification of the defense" section in the [rules](/static/rules.pdf) for details.

- **5 Jan** - **Attack phase draft**: we added a draft of the scoring system for the Attack phase.

- **9 Jan** - **Defense submission deadline extension**: due to a regression in some API endpoints that lasted from 3 Jan to 8 Jan, all deadlines are extended by two days.

- **9 Jan** - **Defense submission for different models**: in response to community feedback, we have decided to allow defenders to submit separate defenses for gpt-3.5-turbo and llama-2-70b-chat models.  Please refer to the [announcement](https://groups.google.com/g/satml-2024-llms-ctf/c/aRBxqurZUQ4/m/IdBhQ49NBAAJ) for more details.

- **16 Jan** -- **Bug fix and deadline extension** -- due to a bug in how longer conversations were handled, we have extended the defense submission deadline to 24 Jan, and increased team budgets. Please refer to the [announcement](https://groups.google.com/g/satml-2024-llms-ctf) for more details.

- **4 Feb** -- **Evaluation phase start, scoring updates** -- the scoring system for the attack phase was updated to make it more fair: 
there is a linearly decaying bonus for being among the first teams to break a defense; and we're scoring the best 42 out of 44 defenses for each attacking team, because teams can't attack their own defenses.


## Why This Competition?

Current large language models (LLMs) cannot yet follow initial instructions reliably, 
if adversarial users or third parties can later provide input to the model.
This is a major obstacle to using LLMs as the core of a user-facing application.
There exists a growing toolbox of [attacks](https://lilianweng.github.io/posts/2023-10-25-adv-attack-llm/)
that make LLMs obey the attacker's instructions, and defenses of varying complexity to counter them.

Application developers who *use* LLMs, however, can't always be expected to apply complex defense mechanisms.
We aim to find whether a simple approach exists that can withstand adaptive attacks.

## Rules and Engagement

For the complete set of rules, please visit the [official rules page](/static/rules.pdf).
Collaboration between teams, including between distinct teams in the Attack and Defense track, is not allowed.

**By using this chat interface and the API, you accept that the interactions with the interface and the API can be used
for research purposes, and potentially open-sourced by the competition organizers.**

### Why this setup?

The goal of the competition is to find out whether there exists a simple *prompting* approach on the models tested
that can make them robust, or robust enough that simple *filtering* approaches can patch up the remaining vulnerabilities.

We see this fundamentally as a *security* problem: thus the defenders cannot change or adapt their defenses once the Reconnaissance phase begins.

We depart from the standard security threat model in two ways:

- The defender is allowed prompting, LLM post-processing, and arbitrary post-processing in Python.

- We test whether attackers can break a defense in a query-limited setting once they are ready to attack any given defense.
The attack is scored based on the number of interactions and tokens it takes them to break the defense.

Both of these are reasonable tradeoffs to make it easier for participants to find interesting defenses and attacks,
and for the organizers to evaluate them.

We choose a black-box setting similar to the real-world LLM application threat model:
the attacker has no white-box access to the defender's security mechanism. 
However, they can do a large number of queries during the Reconnaissance phase to find out how any defense behaves.

## Models for Testing

The competition will use gpt-3.5-turbo-1106 and llama-2-70b-chat for testing.

## Testing and Credits

Teams can begin testing defenses immediately using the [Defense Interface](/defense) with their own [OpenAI](https://platform.openai.com/api-keys) and [TogetherAI](https://api.together.xyz/signin) API keys.
To use the llama-2-70b-chat model, TogetherAI gives out free credits for newly registered users.
There is a (large) upper limit on the number of API calls per day to prevent abuse and server overload.

*Upon registration*, teams will receive $10 in free credits for the OpenAI API and $10 for the TogetherAI API, linked to their logins, allowing for extensive testing without personal expense.

Teams might be eligible for additional credits upon request.

Please note that the interface may be buggy on Safari (the CSS may not load properly).
Please use another browser, or reload the page until CSS is correctly loaded.

## How to Register

To register your team for the competition, please fill out the [registration form](https://forms.gle/y3aEGgC66iSEKhDw7). You will need to provide your team name and the names and email addresses of all team members.


## Organizers

Edoardo Debenedetti, Daniel Paleka, Javier Rando, Sahar Abdelnabi, Nicholas Carlini, Mario Fritz, Kai Greshake, Richard Hadzic, Thorsten Holz, Daphne Ippolito, Yiming Zhang, Lea Schönherr, Florian Tramèr.

<section>
    <aside class="logo-container">
        <img class="institution-logo" alt="ETH Zurich" src="{{ url_for('static', path='/img/ethz.png') }}">
    </aside>
    <aside class="logo-container">
        <img class="institution-logo" alt="CMU" src="{{ url_for('static', path='/img/cmu.png') }}">
    </aside>
    <aside class="logo-container">
        <img class="institution-logo" alt="CISPA" src="{{ url_for('static', path='/img/cispa.png') }}">
    </aside>
    <aside class="logo-container">
        <img class="institution-logo" alt="Google DeepMind" src="{{ url_for('static', path='/img/google-deepmind.png') }}">
    </aside>
    <aside class="logo-container">
        <img class="institution-logo" alt="ELSA" src="{{ url_for('static', path='/img/elsa.png') }}">
    </aside>
</section>



## Contact and Updates

- **Issue tracker**: for questions about the competition, bug reports, and to find a team/team members, please use the [issue tracker](https://github.com/ethz-spylab/satml-llms-ctf-issues) on GitHub.
- **Updates Group**: sign up [here](https://groups.google.com/g/satml-2024-llms-ctf) to receive email updates and reminders.



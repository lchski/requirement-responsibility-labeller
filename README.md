# TBS policy requirement responsibility labeller

_Way cooler than it sounds._

## Quick start

Needs R to run. `source("load.R")` will load the corpus and break it apart, then you can access the `requirements_tagged_with_responsibles` object to run analysis on the requirements.

## How it works

1. Policies were downloaded from TBS’s site as XML. ([Inspired by @sleepycat’s work.](https://github.com/sleepycat/policy_graph)) [They’re now stored in this repo directly](https://github.com/lchski/requirement-responsibility-labeller/tree/master/data/policies), for easy reproducing. (Ignore the `.xml.txt`—that’s so my R script would cooperate.)
2. [`load.R`](https://github.com/lchski/requirement-responsibility-labeller/blob/master/load.R)
    1. Loads every policy as a string of plaintext.
    2. Breaks the policy into pieces. Tries to do this intelligently, looking at HTML elements. Ultimately we break it down into a sentence level, though lists kinda throw this off.
    3. Checks for the name of each policy, and assigns each row a number.
    4. Manually adds in a few policy requirements/lines that exist only as attributes on `<section>` elements. (Weird stuff.)
    5. Runs `scripts/assign_responsibility.R`.
3. `scripts/assign_responsibility.R`
    1. Pulls together the list of ["responsible actors"](https://github.com/lchski/requirement-responsibility-labeller/blob/master/data/responsible_actors.csv) and ["responsible signals"](https://github.com/lchski/requirement-responsibility-labeller/blob/master/data/responsible_signals.csv). Does some pluralizing and concatenating to create our search strings.
    2. Working policy by policy, rolls through the requirements. If a requirement has a string that matches one of the "responsible signals", it marks that requirement as "describing responsibility" (`is_clause_describing_responsibility`). Then, it assigns a "responsible actor" based on the signal/actor combos (`responsible_actor_standardized`).
    3. Notes which clause was the source of the responsible actor for each clause. (Each time we assign responsibility, i.e. where `is_clause_describing_responsibility` is true, we set that clause’s row number as `responsible_clause`. Then we fill down the empty spaces.)

## Unhandled edge cases

- 23601 (Standard on Web Accessibility): Includes additional requirements in a “Monitoring and reporting requirements” section (chapter 7)
- 25875 (Standard on Web Interoperability): Additional requirements in appendices B–E.
- Responsible description is part of another clause (clause isn't properly split, occurs in a few spots in the policy), maybe a problem in: 27600, Standard on Email Management; 16553, Standard on Geospatial Data; 18909, Standard on Metadata.

Don't show up in the policy hierarchy (added/downloaded manually):

```
12510,"Policy on Privacy Protection"
18309,"Directive on Privacy Practices"
18308,"Directive on Privacy Impact Assessment"
```

## Maybe things to work on

Sometimes you make responsibility signals that are really just for one policy, like this:

```
"designated senior executive",8,singular,
```

Written for the IM Roles Directive, this could accidentally cast too wide a net elsewhere. Options:

- Leave it as-is, looking to see the impact (does this IM actor show up where it shouldn't?)
- Point it away from the “Departmental Information Management Senior Official” actor, instead at a more generic senior official actor
- Refactor the responsibles code to account for policy-specific signals (cool, but more work!)
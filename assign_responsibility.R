source("load.R")

## Pull in `data/responsible_signals.csv`:
##   - actor: a form of an actor name
##   - actor_id: the ID of that actor's standardized name
##   - pluralization: whether this form of the name is singular or plural
##   - suffix: whether to append a custom suffix
## If the `actor` is has a value for `pluralization`, assume it's “is responsible” or “are responsible” accordingly.
## Else, use the custom suffix.
## e.g. Deputy heads/plural becomes “Deputy heads are responsible”
responsible_signals <- read_csv("data/responsible_signals.csv") %>%
  mutate(actor_pluralized = case_when(
    pluralization == "singular" ~ paste0(actor, " is"),
    pluralization == "plural" ~ paste0(actor, " are"),
    TRUE ~ actor
  )) %>%
  mutate(actor_suffixed = case_when(
    is.na(suffix) ~ paste(actor_pluralized, "responsible"),
    TRUE ~ paste(actor_pluralized, suffix)
  )) %>%
  left_join(responsible_actors, by = c("actor_id" = "id"))

## Helper function to concatenate the suffixed actor forms into one long regex for `str_detect`.
is_clause_describing_responsibility <- function(clauses) {
  str_detect(
    string = clauses,
    pattern = regex(
      paste(collapse = "|", responsible_signals %>% pull(actor_suffixed)),
      ignore_case = TRUE
    )
  )
}

## Tag the requirements!
##   1. Identify whether a clause describes responsibility. If so:
##     - set `responsible_clause` to the clause’s `row`
##     - store the string that signalled responsibility
##   2. Fill the values down (each non-responsibility clause inherits the previous’s responsible actor).
##   3. Convert the strings signalling responsibility to their standardized actor names.
requirements_tagged_with_responsibles <- requirements_with_tokens %>%
  mutate(
    responsible_clause = case_when(
      is_clause_describing_responsibility(text) ~ row,
      TRUE ~ NA_integer_
    ),
    responsible_actor = case_when(
      is_clause_describing_responsibility(text) ~ str_extract(text, paste(collapse = "|", responsible_signals %>% pull(actor_suffixed))),
      TRUE ~ NA_character_
    )
  ) %>%
  mutate(clause_assigns_responsiblity = ! is.na(responsible_clause)) %>%
  fill(responsible_clause, responsible_actor) %>%
  left_join(
    responsible_signals %>%
      select(actor_suffixed, actor_standardized),
    by = c("responsible_actor" = "actor_suffixed")
  ) %>%
  mutate(responsible_actor_standardized = actor_standardized) %>%
  select(-responsible_actor, -actor_standardized)

requirements_tagged_with_responsibles %>%
  write_csv("data/out/requirements_tagged_with_responsibles.csv")

source("load.R")

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

is_clause_describing_responsibility <- function(clauses) {
  str_detect(
    string = clauses,
    pattern = regex(
      paste(collapse = "|", responsible_signals %>% pull(actor_suffixed)),
      ignore_case = TRUE
    )
  )
}

requirements_tagged_with_responsibles <- requirements_with_tokens %>%
  group_by(id) %>%
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

source("load.R")

responsibles <- requirements_with_tokens %>%
  filter(str_detect(text, "responsible"))

responsibles %>% write_csv("data/out/responsibles.csv")

responsible_signals <- read_csv("data/responsible_signals.csv")

responsible_signals <- paste(collapse = "|", responsible_actors %>%
  mutate(actor = case_when(
    pluralization == "singular" ~ paste0(actor, " is"),
    pluralization == "plural" ~ paste0(actor, " are"),
    TRUE ~ actor
  )) %>%
  mutate(actor = case_when(
    is.na(suffix) ~ paste(actor, "responsible"),
    TRUE ~ paste(actor, suffix)
  )) %>%
  pull(actor)
)

is_clause_describing_responsibility <- function(clauses) {
  str_detect(clauses, regex(responsible_signals, ignore_case = TRUE))
}

requirements_tagged_with_responsibles <- requirements_with_tokens %>%
  mutate(responsible_clause = case_when(
    is_clause_describing_responsibility(text) ~ row,
    TRUE ~ NA_integer_
  )) %>%
  fill(responsible_clause)

requirements_tagged_with_responsibles %>%
  write_csv("data/out/requirements_tagged_with_responsibles.csv")

### Review for requirements without responsibles (some may remain, that's okay!)
requirements_tagged_with_responsibles %>% filter(is.na(responsible_clause)) %>% View()

#### Check for those with "responsible" in the text
requirements_tagged_with_responsibles %>% filter(is.na(responsible_clause)) %>% filter(str_detect(text, "responsible")) %>% View()

requirements_tagged_with_responsibles %>%
  filter(str_detect(text, "responsible")) %>%
  filter(is.na(responsible_actor_standardized)) %>%
  write_csv("data/out/potential_responsible_clauses.csv")
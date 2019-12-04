
## Identify the policies that don't seem to have requirement sections
## (this is why `requirements_*` only returns ~80 policies)
policies_raw %>% filter(! id %in% (policies_raw %>%
                                     mutate(text = str_split(text, "</chapter>")) %>%
                                     unnest(cols = c(text)) %>%
                                     filter(str_detect(text, regex(paste(collapse = "|", requirements_chapter_titles %>% pull(title)), ignore_case = TRUE))) %>%
                                     pull(id))) %>%
  left_join(policy_titles) %>%
  select(-text)

### Review for requirements without responsibles (some may remain, that's okay!)
requirements_tagged_with_responsibles %>% filter(is.na(responsible_clause)) %>% View()

#### Check for those with "responsible" in the text
requirements_tagged_with_responsibles %>% filter(is.na(responsible_clause)) %>% filter(str_detect(text, "responsible")) %>% View()
requirements_tagged_with_responsibles %>% filter(! clause_assigns_responsiblity) %>% filter(str_detect(text, "responsible")) %>% View()

requirements_tagged_with_responsibles %>%
  filter(str_detect(text, "responsible")) %>%
  filter(is.na(responsible_actor_standardized)) %>%
  write_csv("data/out/potential_responsible_clauses.csv")

requirements_tagged_with_responsibles %>%
  filter(str_detect(text, "responsible")) %>%
  filter(! clause_assigns_responsiblity) %>%
  filter(! is.na(responsible_actor_standardized)) %>%
  write_csv("data/out/potential_misflagged_responsible_clauses.csv")


## Identify the policies that don't seem to have requirement sections
## (this is why `requirements_*` only returns ~80 policies)
policies_raw %>% filter(! id %in% (policies_raw %>%
                                     mutate(text = str_split(text, "</chapter>")) %>%
                                     unnest(cols = c(text)) %>%
                                     filter(str_detect(text, regex(paste(collapse = "|", requirements_chapter_titles %>% pull(title)), ignore_case = TRUE))) %>%
                                     pull(id))) %>%
  left_join(policy_titles) %>%
  select(-text)

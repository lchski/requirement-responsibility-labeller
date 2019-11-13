ati_policy_ids <- policies_raw %>%
  filter(str_detect(text, regex("Access to Information", ignore_case = TRUE))) %>%
  pull(id)

requirements_tagged_with_responsibles %>%
  filter(id %in% ati_policy_ids) %>%
  filter(str_detect(text, regex("Access to Information", ignore_case = TRUE)))

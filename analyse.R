source("load.R")

responsibles <- requirements_with_tokens %>%
  filter(str_detect(text, "responsible"))

responsibles %>% write_csv("data/out/responsibles.csv")

requirements_tagged_with_responsibles <- requirements_with_tokens %>%
  mutate(responsible_clause = case_when(
    str_detect(text, "responsible") ~ row,
    TRUE ~ NA_integer_
  )) %>%
  fill(responsible_clause)

requirements_tagged_with_responsibles %>% write_csv("data/out/requirements_tagged_with_responsibles.csv")

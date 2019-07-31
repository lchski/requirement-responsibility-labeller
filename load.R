library(tidyverse)
library(readtext)
library(textclean)

policies_raw <- readtext("data/policies/*")

policy_titles <- read_csv("data/policies.csv")

requirements_with_tokens <- tibble(id = policies_raw$doc_id, text = policies_raw$text) %>%
  mutate(text = str_split(text, "</chapter>")) %>%
  unnest() %>%
  filter(str_detect(text, regex("title=\"Requirements\"|title=\"Policy requirements\"", ignore_case = TRUE))) %>%
  mutate(text = str_replace_all(text, pattern = "<p", "030SEP070<p")) %>%
  mutate(text = str_replace_all(text, pattern = "<li", "030SEP070<li")) %>%
  mutate(text = str_replace_all(text, pattern = "<clause", "030SEP070<clause")) %>%
  mutate(text = replace_html(text)) %>%
  mutate(text = str_split(text, "030SEP070")) %>%
  unnest() %>%
  mutate(text = trimws(text)) %>%
  filter(text != "") %>%
  mutate(id = as.integer(str_remove(id, ".xml.txt"))) %>%
  left_join(policy_titles) %>%
  group_by(id) %>%
  mutate(row = row_number()) %>%
  select(id, row, title, text)

requirements_with_tokens %>% write_csv("data/out/requirements_with_tokens.csv")

requirements <- tibble(id = policies_raw$doc_id, text = policies_raw$text) %>%
  mutate(text = replace_html(text)) %>%
  mutate(text = str_split(text, "   ")) %>%
  unnest() %>%
  mutate(text = trimws(text)) %>%
  filter(text != "") %>%
  mutate(id = as.integer(str_remove(id, ".xml.txt"))) %>%
  left_join(policy_titles) %>%
  group_by(id) %>%
  mutate(row = row_number()) %>%
  select(id, row, title, text)

requirements %>% write_csv("data/out/requirements.csv")

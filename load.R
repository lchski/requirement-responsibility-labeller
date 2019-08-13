library(tidyverse)
library(readtext)
library(textclean)
library(tidytext)

responsible_actors <- read_csv("data/responsible_actors.csv")

policies_raw <- readtext("data/policies/*")

policy_titles <- read_csv("data/policies.csv")

requirements_chapter_titles <- tibble(
    title = c("Requirements", "Policy requirements", "6 Requirements", "6. Requirements")
  ) %>%
  mutate(title = paste0("title=\"", title, "\""))

requirements_with_tokens <- tibble(id = policies_raw$doc_id, text = policies_raw$text) %>%
  mutate(text = str_split(text, "</chapter>")) %>%
  unnest() %>%
  filter(str_detect(text, regex(paste(collapse = "|", requirements_chapter_titles %>% pull(title)), ignore_case = TRUE))) %>%
  mutate(text = str_replace_all(text, pattern = "<p", "030SEP070<p")) %>%
  mutate(text = str_replace_all(text, pattern = "<li", "030SEP070<li")) %>%
  mutate(text = str_replace_all(text, pattern = "<clause", "030SEP070<clause")) %>%
  mutate(text = replace_html(text)) %>%
  mutate(text = str_split(text, "030SEP070")) %>%
  unnest() %>%
  unnest_tokens(sentence, text, token = "sentences", to_lower = FALSE) %>%
  mutate(text = str_split(sentence, "   ")) %>%
  select(-sentence) %>%
  unnest() %>%
  mutate(text = trimws(text)) %>%
  filter(text != "") %>%
  mutate(text = str_replace_all(text, "\n", " ")) %>%
  mutate(text = str_replace_all(text, "\r\n", " ")) %>%
  mutate(text = str_replace_all(text, "  ", " ")) %>%
  mutate(id = as.integer(str_remove(id, ".xml.txt"))) %>%
  left_join(policy_titles) %>%
  group_by(id) %>%
  mutate(row = row_number()) %>%
  select(id, row, title, text)

requirements_with_tokens %>% write_csv("data/out/requirements_with_tokens.csv")

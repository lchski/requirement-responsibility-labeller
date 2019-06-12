library(tidyverse)
library(readtext)
library(textclean)

policies_raw <- readtext("data/policies/*")

policy_titles <- read_csv("data/policies.csv")

requirements <- tibble(id = policies_raw$doc_id, text = policies_raw$text) %>%
  mutate(text = replace_html(text)) %>%
  mutate(text = str_split(text, "   ")) %>%
  unnest() %>%
  mutate(text = trimws(text)) %>%
  filter(text != "") %>%
  mutate(id = as.integer(str_remove(id, ".xml.txt"))) %>%
  mutate(row = row_number()) %>%
  left_join(policy_titles) %>%
  select(row, id, title, text)

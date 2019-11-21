## trying to fix web standard accessibility parsing
policies_raw %>%
  filter(id == 23601) %>%
  mutate(text = str_split(text, "</chapter>")) %>%
  unnest(cols = c(text)) %>%
  filter(str_detect(text, regex(paste(collapse = "|", requirements_chapter_titles %>% pull(title)), ignore_case = TRUE))) %>%
  mutate(text = str_replace_all(text, pattern = "<p", "030SEP070<p")) %>%
  mutate(text = str_replace_all(text, pattern = "<li", "030SEP070<li")) %>%
  mutate(text = str_replace_all(text, pattern = "<clause", "030SEP070<clause")) %>%
  mutate(text = str_replace_all(text, "\n", "038TOBEREPLACED038")) %>%
  mutate(text = str_replace_all(text, "\r\n", "038TOBEREPLACED038")) %>%
  mutate(text = str_replace_all(text, "\t", "038TOBEREPLACED038")) %>%
  mutate(text = str_replace_all(text, "038TOBEREPLACED038", "")) %>%
  mutate(text = replace_html(text)) %>%
  mutate(text = str_split(text, "030SEP070")) %>%
  unnest(cols = c(text)) %>%
  unnest_tokens(sentence, text, token = "sentences", to_lower = FALSE) %>%
  mutate(text = str_split(sentence, "   ")) %>%
  select(-sentence) %>%
  unnest(cols = c(text)) %>%
  mutate(text = trimws(text)) %>%
  filter(text != "") %>%
  mutate(text = str_replace_all(text, "\n", " ")) %>%
  mutate(text = str_replace_all(text, "\r\n", " ")) %>%
  mutate(text = str_replace_all(text, "  ", " ")) %>%
  left_join(policy_titles) %>%
  group_by(id) %>%
  mutate(row = row_number()) %>%
  select(id, row, title, text)

## trying to fix web standard accessibility parsing
policies_raw %>%
  filter(id == 23601) %>%
  mutate(text = str_split(text, "</chapter>")) %>%
  unnest(cols = c(text)) %>%
  filter(str_detect(text, regex(paste(collapse = "|", requirements_chapter_titles %>% pull(title)), ignore_case = TRUE))) %>%
  mutate(text = str_replace_all(text, pattern = "<p", "030SEP070<p")) %>%
  mutate(text = str_replace_all(text, pattern = "<li", "030SEP070<li")) %>%
  mutate(text = str_replace_all(text, pattern = "<clause", "030SEP070<clause")) %>%
  mutate(text = replace_html(text)) %>%
  mutate(text = replace_white(text)) %>%
  mutate(text = str_split(text, "030SEP070")) %>%
  unnest(cols = c(text)) %>%
  unnest_tokens(sentence, text, token = "sentences", to_lower = FALSE) %>%
  mutate(text = str_split(sentence, "   ")) %>%
  select(-sentence) %>%
  unnest(cols = c(text)) %>%
  mutate(text = trimws(text)) %>%
  filter(text != "") %>%
  mutate(text = str_replace_all(text, "\n", " ")) %>%
  mutate(text = str_replace_all(text, "\r\n", " ")) %>%
  mutate(text = str_replace_all(text, "  ", " ")) %>%
  left_join(policy_titles) %>%
  group_by(id) %>%
  mutate(row = row_number()) %>%
  select(id, row, title, text)

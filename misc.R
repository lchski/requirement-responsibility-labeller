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

missing_reqs <- tribble(
  ~id, ~row, ~title, ~text,
  23601, 0, "Web Accessibility, Standard on", "6.1 Managers, functional specialists, and equivalents responsible for Web content or Web pages are responsible for:",
  23601, 17.5, "Web Accessibility, Standard on", "6.2 The senior departmental official, designated by the deputy head, is responsible for:",
  23601, 18.5, "Web Accessibility, Standard on", "6.3 The departmental Chief Information Officer (CIO) or equivalent is responsible for:"
)

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
  select(id, row, title, text) %>% bind_rows(missing_reqs) %>% ungroup() %>% arrange(id, row) %>% group_by(id) %>% mutate(row = row_number()) %>% View()
  
### Review for requirements without responsibles (some may remain, that's okay!)
requirements_tagged_with_responsibles %>% filter(is.na(responsible_clause)) %>% View()
requirements_tagged_with_responsibles %>% filter(is.na(responsible_clause)) %>% filter(str_detect(text, "responsible")) %>% View()

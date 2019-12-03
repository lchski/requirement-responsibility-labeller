requirements_chapter_titles <- tibble(
  title = c(
    "Requirements",
    "Policy requirements",
    "6 Requirements",
    "6. Requirements",
    "4. Roles, responsibilities, and accountabilities",
    "7. Policy requirement",
    "6. Policy requirements",
    "5. Policy requirements",
    "5. Requirements",
    "4. Requirements",
    "6. Directive requirements",
    "6.  Requirements",
    "Directive requirements",
    "Procedures"
  )
) %>%
  mutate(title = paste0("title=\"", title, "\""))

requirements_with_tokens <- policies_raw %>%
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
  23601, 18.5, "Web Accessibility, Standard on", "6.3 The departmental Chief Information Officer (CIO) or equivalent is responsible for:",
  25875, 0, "Web Interoperability, Standard on", "6.1 Managers, functional specialists, and equivalents responsible for Web content or Web pages are responsible for:",
  25875, 4.5, "Web Interoperability, Standard on", "6.2 The senior departmental official, designated by the deputy head, is responsible for:",
  25875, 6.5, "Web Interoperability, Standard on", "6.3 The departmental Chief Information Officer (CIO) or equivalent is responsible for:",
  25875, 8.5, "Web Interoperability, Standard on", "6.4 Centres of Expertise are responsible for:",
  16553, 0, "Geospatial Data, Standard on", "6.1 Managers and functional specialists responsible for creating or using geospatial data or for systems that use geospatial data are responsible for:",
  26761, 0, "Privacy and Web Analytics, Standard on", "6.1 Heads of government institutions or their delegates are responsible for the following:",
  26761, 1.5,"Privacy and Web Analytics, Standard on", "6.2 Executives and senior officials who manage programs or activities involving the creation, collection or handling of personal information are responsible for:",
  26761, 2.5,"Privacy and Web Analytics, Standard on", "6.3 Web managers, functional specialists, Web content owners and equivalents are responsible for:",
  26761, 3.5,"Privacy and Web Analytics, Standard on", "6.4 The Treasury Board of Canada Secretariat, Chief Information Officer Branch, is responsible for:",
  26761, 6.5,"Privacy and Web Analytics, Standard on", "6.5 Monitoring and reporting requirements"
)

requirements_with_tokens <- requirements_with_tokens %>%
  bind_rows(missing_reqs) %>%
  ungroup() %>%
  arrange(id, row) %>%
  group_by(id) %>%
  mutate(row = row_number())

requirements_with_tokens %>% write_csv("data/out/requirements_with_tokens.csv")

source("scripts/assign_responsibility.R")

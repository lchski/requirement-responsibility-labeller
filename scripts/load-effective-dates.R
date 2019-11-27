## A somewhat ill-fated attempt to find effective dates for each policy.
## In reality, there are a ton of different effective dates in some policies. (And
## not all edge cases caught, cf. Policy on Results with "Until".)
## All hope not lost: could still do some interesting analysis on this.
##
## May be further ahead to just web scrape the policy pages, looking for this in 
## the footer: `<time property="dateModified">2019-06-10</time>`
##
## Y'know...

library(lubridate)

effective_date_chapter_titles <- tibble(
  title = c("Effective date", "1. Effective date", "1. Effective Date", "Effective Date")
) %>%
  mutate(title = paste0("title=\"", title, "\""))

effective_date_section_clauses <- policies_raw %>%
  mutate(text = str_split(text, "</chapter>")) %>%
  unnest(cols = c(text)) %>%
  filter(str_detect(text, regex(paste(collapse = "|", effective_date_chapter_titles %>% pull(title)), ignore_case = TRUE))) %>%
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

effective_dates <- effective_date_section_clauses %>%
  filter(
    str_detect(
      text,
      regex(
        paste(collapse = "|", c(
          "takes effect on",
          "take effect on",
          "took effect on",
          "takes effect",
          "comes into effect on",
          "will come into effect on",
          "will come into effect no later than",
          "effective on",
          "effective as of",
          "is effective",
          "will be effective",
          "updates effective",
          "was updated on",
          "will have until"
        )), ignore_case = TRUE)
      )
  )

effective_date_section_clauses %>%
  ungroup() %>%
  anti_join(effective_dates %>% ungroup()) %>%
  filter(str_detect(text, "20")) %>%
  View()


date_strings <- effective_dates %>%
  mutate(date_string = str_extract_all(text, "([A-Za-z]* ?[0-9]{1,2}[ sth]{0,4},? [0-9]{1,4})")) %>%
  unnest(cols = c(date_string)) %>%
  mutate(date = mdy(date_string))

## find policies where no clauses matched
effective_dates %>% filter(! id %in% (date_strings %>% pull(id) %>% unique()))

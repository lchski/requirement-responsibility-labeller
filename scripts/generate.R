# Generating JSON (from https://www.tbs-sct.gc.ca/pol/a-z-eng.aspx)
#
# console.log(JSON.stringify(Array.from(document.querySelectorAll('[role=main] > section li a')).map(a => {
#   return {
#     id: new URL(a.href).search.split('=')[1],
#     title: a.innerHTML
#   };
# })))
#
# Generating JSON (from https://www.tbs-sct.gc.ca/pol/hierarch-eng.aspx)
#
# console.log(JSON.stringify(Array.from(document.querySelectorAll('.tv-in')).map(a => {
# return {
# 	id: new URL(a.href).search.split('=')[1],
# 	title: a.innerHTML
# };
# })))

library(jsonlite)

as_tibble(fromJSON("data/policies-hierarch.json", flatten = TRUE)) %>%
  bind_rows(as_tibble(fromJSON("data/policies-az.json", flatten = TRUE))) %>%
  mutate(raw_id = id, id = as.integer(id)) %>%
  unique() %>%
  write_csv("data/policies.csv")

source("load.R")

## Policies to download!
policy_titles %>%
  anti_join(policies_raw) %>%
  filter(! is.na(id)) %>%
  pull(id)

## Policies to download!
## Download: `xargs -n 1 curl -O < data/out/policies-to-download.txt`
policy_titles %>%
  anti_join(policies_raw) %>%
  filter(! is.na(id)) %>%
  mutate(url = paste0("https://www.tbs-sct.gc.ca/pol/doc-eng.aspx?id=", id, "&section=xml")) %>%
  select(url) %>%
  write_csv("data/out/policies-to-download.txt")



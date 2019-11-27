# Generating JSON (from https://www.tbs-sct.gc.ca/pol/a-z-eng.aspx)
#
# console.log(JSON.stringify(Array.from(document.querySelectorAll('[role=main] > section li a')).map(a => {
#   return {
#     id: new URL(a.href).search.split('=')[1],
#     title: a.innerHTML
#   };
# })))

## TODO: Combine alphabetical with hierarchical index?

library(jsonlite)

as_tibble(fromJSON("data/policies.json", flatten = TRUE)) %>%
  mutate(raw_id = id, id = as.integer(id)) %>%
  write_csv("data/policies.csv")

source("load.R")

## Policies to download!
policy_titles %>%
  anti_join(policies_raw) %>%
  filter(! is.na(id)) %>%
  pull(id)

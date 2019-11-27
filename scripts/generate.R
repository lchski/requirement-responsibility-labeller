# Generating JSON:
#
# console.log(JSON.stringify(Array.from(document.querySelectorAll('[role=main] > section li a')).map(a => {
#   return {
#     id: new URL(a.href).search.split('=')[1],
#     title: a.innerHTML
#   };
# })))

library(jsonlite)

as_tibble(fromJSON("data/policies.json", flatten = TRUE)) %>%
  mutate(raw_id = id, id = as.integer(id)) %>%
  write_csv("data/policies.csv")

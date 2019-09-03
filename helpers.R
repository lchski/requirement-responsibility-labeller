# Generating JSON:
#
# console.log(JSON.stringify(Array.from(document.querySelectorAll('.tv-in')).map(a => {
# return {
# 	id: new URL(a.href).search.split('=')[1],
# 	title: a.innerHTML
# };
# })))

as_tibble(fromJSON("data/policies.json", flatten = TRUE)) %>%
  write_csv("data/policies.csv")



# Find unassigned responsible clauses
requirements_tagged_with_responsibles %>%
  filter(str_detect(text, "responsible")) %>%
  filter(is.na(responsible_actor_standardized)) %>%
  write_csv("data/out/potential_responsible_clauses.csv")

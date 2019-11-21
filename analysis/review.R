source("assign_responsibility.R")

## Just look at requirements from "delivery" policies
delivery_policies <- read_csv("data/indices/delivery-policies.csv")
delivery_policy_reqs <- requirements_tagged_with_responsibles %>%
  filter(id %in% delivery_policies$id)

### Review for requirements without responsibles (some may remain, that's okay!)
delivery_policy_reqs %>% filter(is.na(responsible_clause)) %>% View()
delivery_policy_reqs %>% filter(is.na(responsible_clause)) %>% filter(str_detect(text, "responsible")) %>% View()

### How many requirements involve plans?
delivery_policy_reqs %>%
  filter(str_detect(text, "\\bplan(ned|ning)?\\b")) %>%
  View()

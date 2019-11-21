## Just look at requirements from "delivery" policies
delivery_policies <- read_csv("data/indices/delivery-policies.csv")
delivery_policy_reqs <- requirements_tagged_with_responsibles %>%
  filter(id %in% delivery_policies$id)

### How many requirements involve plans?
delivery_policy_reqs %>%
  filter(str_detect(text, "\\bplan(ned|ning)?\\b")) %>%
  View()

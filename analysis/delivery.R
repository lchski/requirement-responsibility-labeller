## Just look at requirements from "delivery" policies
delivery_policies <- read_csv("data/indices/delivery-policies.csv")
delivery_policy_reqs <- requirements_tagged_with_responsibles %>%
  filter(id %in% delivery_policies$id)
delivery_policy_reqs %>% write_csv("data/out/delivery.csv")

### How many requirements involve plans?
delivery_policy_reqs %>%
  filter(str_detect(text, "\\bplan(ned|ning)?\\b")) %>%
  View()

delivery_policy_reqs %>%
  ungroup() %>%
  count_group(responsible_actor_standardized) %>%
  mutate(prop = round(count / sum(count) * 100, 2)) %>%
  write_csv("data/out/delivery-resp-summary.csv")

digital_policies <- read_csv("data/indices/digital-policy.csv")
digital_policy_reqs <- requirements_tagged_with_responsibles %>%
  filter(id %in% delivery_policies$id)



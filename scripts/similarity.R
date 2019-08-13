# SETUP
source("load.R")
source("assign_responsibility.R")
source("scripts/lib/similarity.R")
source("scripts/lib/cluster.R")

library(magrittr)
library(lubridate)
library(tidytext)
library(SnowballC)
library(exploratory)

#library(cluster)
#library(factoextra)
#library(NbClust)

data("stop_words")

psd_policies <- read_csv("data/indices/digital-policy.csv")

requirements_to_compare <- requirements_tagged_with_responsibles %>%
  rename(policy_id = id) %>%
  mutate(id = paste0(policy_id, "-", row)) %>%
  filter(policy_id %in% psd_policies$id) %>%
  filter(! clause_assigns_responsiblity) %>%
  left_join(psd_policies, by = c("policy_id" = "id")) %>%
  rename(psd_group = group)

compared_statements <- analyse_statement_similarity(
  statements = requirements_to_compare,
  similarity_threshold = 0.25
) %>%
  get_details_about_statement_pairs(all_statements = requirements_to_compare) %>%
  unnest()

compared_statements %>% find_pairs_with_different_values(column_to_compare = psd_group) %>% View()
compared_statements %>% find_pairs_with_different_values(column_to_compare = policy_id) %>% View()

compared_statements %>%
  find_pairs_with_different_values(column_to_compare = psd_group) %>%
  select(pair_number, value, psd_group, id, title, actor = responsible_actor_standardized, text) %>%
  write_csv("data/out/psd_comparisons_25.csv")

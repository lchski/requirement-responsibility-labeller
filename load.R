library(tidyverse)
library(readtext)
library(textclean)
library(tidytext)

source("scripts/helpers.R")

responsible_actors <- read_csv("data/responsible_actors.csv")

policies_raw <- readtext("data/policies/*")
policies_raw <- tibble(id = policies_raw$doc_id, text = policies_raw$text) %>%
  mutate(id = as.integer(str_remove(id, ".xml.txt")))

policy_titles <- read_csv("data/policies.csv")

source("scripts/load-requirements.R")
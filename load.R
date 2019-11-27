library(tidyverse)
library(readtext)
library(textclean)
library(tidytext)

source("scripts/helpers.R")

responsible_actors <- read_csv("data/responsible_actors.csv")

policies_raw <- readtext("data/policies/*")
policies_raw <- tibble(id = policies_raw$doc_id, text = policies_raw$text) %>%
  mutate(id = str_remove(id, fixed(".xml.txt"))) %>%
  mutate(id = str_remove(id, fixed("doc-eng.aspx?id="))) %>%
  mutate(id = str_remove(id, fixed("&section=xml"))) %>%
  mutate(id = as.integer(id))

policy_titles <- read_csv("data/policies.csv")

source("scripts/load-requirements.R")
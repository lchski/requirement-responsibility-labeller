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

policy_titles <- read_csv("data/policies.csv") %>%
  anti_join( ## Remove policies listed under different names. (Do this here, because we generate `data/policies.csv` semi-automatically.)
    tribble(
      ~id, ~title, ~raw_id,
      32594,"Project Complexity and Risk Assessments, Mandatory Procedures for","32594",
      32594,"Organizational Project Management Capacity Assessments, Mandatory Procedures for","32594",
      32593,"Concept Cases for Digital Projects, Mandatory Procedures for","32593"
    )
  )

source("scripts/load-requirements.R")

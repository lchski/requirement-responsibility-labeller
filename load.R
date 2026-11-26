library(tidyverse)
library(textclean)
library(tidytext)

source("scripts/helpers.R")

responsible_actors <- read_csv("data/responsible_actors.csv")

## Policy XML comes from a local copy of TBS Policy Hawk (https://github.com/PatLittle/TBS-Policy-Hawk).
## Run `scripts/fetch-hawk.sh` first to download or refresh it.
hawk_dir <- "data/hawk/data"
hawk_files <- list.files(hawk_dir, pattern = "\\.xml$", recursive = TRUE, full.names = TRUE)
if (length(hawk_files) == 0) stop("No policy XML found in ", hawk_dir, ". Run scripts/fetch-hawk.sh first.")

policies_raw <- tibble(path = hawk_files, text = map_chr(hawk_files, read_file)) %>%
  mutate(text = str_remove(text, "^\ufeff")) %>%
  ## Hawk saves later captures as HTML with a `.xml` extension; keep only the real XML.
  filter(str_detect(text, "^\\s*<\\?xml")) %>%
  mutate(
    id = as.integer(str_match(text, 'documentID="(\\d+)"')[, 2]),
    version_date = str_match(path, "_(\\d{4}-\\d{2}-\\d{2})\\.xml$")[, 2],
    hawk_title = str_match(text, '<doc[^>]* title="([^"]*)"')[, 2]
  ) %>%
  filter(!is.na(id)) %>%
  ## Keep the most recent XML version of each instrument.
  group_by(id) %>%
  slice_max(version_date, n = 1, with_ties = FALSE) %>%
  ungroup() %>%
  select(id, text, hawk_title)

policy_titles <- read_csv("data/policies.csv") %>%
  anti_join( ## Remove policies listed under different names. (Do this here, because we generate `data/policies.csv` semi-automatically.)
    tribble(
      ~id, ~title, ~raw_id,
      32594,"Project Complexity and Risk Assessments, Mandatory Procedures for","32594",
      32594,"Organizational Project Management Capacity Assessments, Mandatory Procedures for","32594",
      32593,"Concept Cases for Digital Projects, Mandatory Procedures for","32593"
    )
  )

## `data/policies.csv` dates from 2019; fall back to Hawk's title for instruments it doesn't list.
policy_titles <- policy_titles %>%
  bind_rows(
    policies_raw %>%
      anti_join(policy_titles, by = "id") %>%
      select(id, title = hawk_title)
  )

source("scripts/load-requirements.R")

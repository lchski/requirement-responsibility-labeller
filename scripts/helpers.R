## Find columns that are "empty" (only one unique variable)
identify_empty_columns <- function(dataset) {
  dataset %>%
    gather() %>%
    group_by(key) %>%
    unique() %>%
    summarize(count = n()) %>%
    filter(count == 1) %>%
    select(key) %>%
    pull()
}

### Remove those columns!
remove_extra_columns <- function(dataset) {
  dataset %>%
    select(-one_of(identify_empty_columns(.)))
}



count_group <- function(dataset, ...) {
  dataset %>%
    group_by(...) %>%
    summarize(count = n()) %>%
    arrange(-count)
}

pull_count <- function(dataset) {
  dataset %>%
    summarize(count = n()) %>%
    pull(count)
}
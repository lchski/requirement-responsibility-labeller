source("load.R")

responsibles <- requirements_with_tokens %>%
  filter(str_detect(text, "responsible"))

responsibles %>% write_csv("data/out/responsibles.csv")

responsibles[,1]

responsibles %>% slice(6)

find_responsible_requirements <- function(requirements, responsibles, index) {
  # 1. Select a row, noting its index in `responsibles`
  # 2. Select all rows between row[index].`row` and row[index + 1].`row`
  # 3. Assign those rows to row[index]
  
  responsible_row <- responsibles %>% slice(index) %>% select(row) %>% pull()
  next_responsible_row <- responsibles %>% slice(index + 1) %>% select(row) %>% pull()
  next_responsible_row <- next_responsible_row - 1

  list(requirements %>% slice(responsible_row:next_responsible_row))
}

find_responsible_requirements(requirements_with_tokens, responsibles, 1)

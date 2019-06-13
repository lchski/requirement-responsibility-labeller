source("load.R")

responsibles <- requirements_with_tokens %>%
  filter(str_detect(text, "responsible"))

responsibles %>% write_csv("data/out/responsibles.csv")

responsibles[,1]

responsibles %>% slice(6)

find_responsible_requirements <- function(requirements, responsibles, index) {
  
}

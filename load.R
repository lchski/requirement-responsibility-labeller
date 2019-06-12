library(tidyverse)
library(readtext)
library(textclean)

policies <- read_file("data/15249.xml")

policies <- replace_html(policies)

policies <- str_split(policies, "   ")

policies <- tibble(id = "15249", text = policies) %>%
  unnest() %>%
  mutate(text = trimws(text)) %>%
  filter(text != "")

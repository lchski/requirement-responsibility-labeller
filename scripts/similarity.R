# SETUP
source("load.R")
source("analyse.R")
source("scripts/lib/similarity.R")
source("scripts/lib/cluster.R")

library(magrittr)
library(lubridate)
library(tidytext)
#library(SnowballC)
#library(exploratory)

#library(cluster)
#library(factoextra)
#library(NbClust)

data("stop_words")

analyse_statement_similarity(
  statements = requirements_tagged_with_responsibles,
  similarity_threshold = 0.9
)

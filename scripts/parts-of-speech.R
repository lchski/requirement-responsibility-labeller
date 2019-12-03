library(NLP)
library(tm)
library(openNLP)
library(openNLPmodels.en)

library(cleanNLP)

cnlp_init_udpipe(model_name="english")

requirements_by_word_pos <- requirements_with_tokens %>%
  ungroup() %>%
  mutate(doc_id = paste0(id,  '-', row)) %>%
  cnlp_annotate()

requirements_by_word_pos <- requirements_by_word_pos$token %>%
  separate(doc_id, into = c("id", "row"), remove = FALSE, sep = "-", convert = TRUE)


## Requirements to plan!
requirements_by_word_pos %>%
  filter(lemma == "plan") %>%
  filter(upos != "VERB") %>%
  select(id, row) %>%
  unique() %>%
  left_join(requirements_tagged_with_responsibles) %>%
  filter(id %in% delivery_policies$id)

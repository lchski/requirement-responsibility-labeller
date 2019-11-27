library(NLP)
library(tm)
library(openNLP)
library(openNLPmodels.en)

library(cleanNLP)

requirements_by_pos <- requirements_with_tokens %>%
  ungroup() %>%
  mutate(doc_id = paste0(id,  '-', row))

cnlp_init_udpipe(model_name="english")

annotation <- cnlp_annotate(input = requirements_by_pos)
annotation




string = 'Colorless green ideas sleep furiously' 

baby_string = requirements_with_tokens %>% ungroup() %>% slice(1:2) %>% pull(text)

initial_result = string %>% 
  NLP::annotate(list(Maxent_Sent_Token_Annotator(),
                Maxent_Word_Token_Annotator())) %>% 
  NLP::annotate(string, Maxent_POS_Tag_Annotator(), .) %>% 
  subset(type=='word')

init_s_w = NLP::annotate(baby_string, list(Maxent_Sent_Token_Annotator(),
                                      Maxent_Word_Token_Annotator()))
pos_res = NLP::annotate(baby_string, Maxent_POS_Tag_Annotator(), init_s_w)
word_subset = subset(pos_res, type=='word')
tags = sapply(word_subset$features , '[[', "POS")

baby_pos = tibble(word=baby_string[word_subset], pos=tags) %>% 
  filter(!str_detect(pos, pattern='[[:punct:]]'))






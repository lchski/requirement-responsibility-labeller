## Analyzers
analyse_statement_similarity <- function(statements, similarity_threshold = 0.9) {
  statements_by_tokenized_lemmas <- tokenize_by_lemma(statements)
  statements_by_token_frequency <- calculate_word_frequencies(statements_by_tokenized_lemmas)
  statements_scored_for_similarity <- score_document_similarities(statements_by_token_frequency)
  
  statements_above_similarity_threshold <- statements_scored_for_similarity %>%
    filter(value > similarity_threshold)
  
  statement_ids_above_threshold <- union(
    statements_above_similarity_threshold$id.x,
    statements_above_similarity_threshold$id.y
  )

  list(
    "tokenized_lemmas" = statements_by_tokenized_lemmas,
    "token_frequency"  = statements_by_token_frequency,
    "similarity_scores"= statements_scored_for_similarity,
    "above_threshold"  = statements_above_similarity_threshold,
    "above_threshold_ids" = statement_ids_above_threshold
  )
}

tokenize_by_lemma <- function(statements) {
  statements %>%
    select(id, content_en_plaintext) %>%
    unnest_tokens(word, content_en_plaintext) %>%
    anti_join(stop_words) %>%
    mutate(word = wordStem(word))
}

calculate_word_frequencies <- function(statements_by_tokenized_lemmas) {
  statements_by_tokenized_lemmas %>%
    count(id, word, sort = TRUE) %>%
    ungroup() %>%
    bind_tf_idf(word, id, n)
}

score_document_similarities <- function(statements_by_token_frequency) {
  statements_by_token_frequency %>%
    do_cosine_sim.kv(subject = id, key = word, value = tf_idf, distinct = TRUE)
}


## Extractors
get_details_about_statement_pairs <- function(statement_pairs, all_statements = base_statements) {
  if("above_threshold" %in% names(statement_pairs)) {
    statement_pairs <- statement_pairs %>% extract2("above_threshold")
  }

  statement_pairs %>%
    mutate(pair_number = row_number()) %>%
    rowwise() %>%
    mutate(statements = list(view_specific_statements(all_statements, c(id.x, id.y)))) %>%
    select(pair_number, value, statements)
}


## Filters
find_pairs_with_different_dates <- function(pairs) {
  pairs %>%
    mutate(date = paste(year(time), yday(time), sep="-")) %>%
    find_pairs_with_different_values(column_to_compare = date)
}

find_pairs_with_different_values <- function(pairs, column_to_compare) {
  col_to_compare <- enquo(column_to_compare)
  
  pair_numbers <- pairs %>%
    group_by(pair_number) %>%
    summarize(comparisons = n_distinct(!! col_to_compare)) %>%
    filter(comparisons > 1) %>%
    pull(pair_number)
  
  pairs %>% filter(pair_number %in% pair_numbers)
}


## Viewers
view_specific_statements <- function(all_statements, statement_ids) {
  all_statements %>%
    filter(id %in% statement_ids)
}

view_useful_fields <- function(statements, ...) {
  statements %>%
    select(id, time, year_week, h2_en, who_en, short_name_en, content_en_plaintext, ...)
}


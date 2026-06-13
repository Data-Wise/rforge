#' Tidy a frame
#'
#' @param df a data.frame.
#' @return a tibble.
#' @export
tidy_frame <- function(df) {
  tibble::as_tibble(df)
}

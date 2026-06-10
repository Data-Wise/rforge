#' Draw a correlated sample
#'
#' Calls MASS::mvrnorm with no requireNamespace guard.
#' @param n integer sample size
#' @return a numeric matrix
#' @examples
#' draw_sample(5)
#' @export
draw_sample <- function(n) {
  MASS::mvrnorm(n, mu = c(0, 0), Sigma = diag(2))
}

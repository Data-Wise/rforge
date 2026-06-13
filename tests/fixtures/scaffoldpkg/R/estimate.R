#' Delta-method product estimate
#'
#' @param a numeric scalar, the first factor.
#' @param b numeric scalar, the second factor. Must be non-negative.
#' @param cov numeric scalar covariance term; defaults to 0.
#' @return numeric scalar estimate.
#' @examples
#' estimate(2, 3)
#' @export
estimate <- function(a, b, cov = 0) {
  if (!is.numeric(a) || !is.numeric(b)) {
    stop("a and b must be numeric")
  }
  if (b < 0) {
    stop("b must be non-negative")
  }
  a * b + cov
}

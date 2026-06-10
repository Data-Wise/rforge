\name{draw_sample}
\alias{draw_sample}
\title{Draw a correlated sample}
\usage{draw_sample(n)}
\arguments{\item{n}{integer sample size}}
\value{a numeric matrix}
\description{Calls MASS::mvrnorm with no requireNamespace guard.}
\examples{draw_sample(5)}

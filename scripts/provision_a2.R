# CI-only provisioning; production README replay never installs dependencies.
options(repos = c(CRAN = "https://cloud.r-project.org"))
if (!requireNamespace("jsonlite", quietly = TRUE)) install.packages("jsonlite")
if (!requireNamespace("remotes", quietly = TRUE)) install.packages("remotes")
lock <- jsonlite::fromJSON("tests/a2/fixture-lock.json")
stopifnot(as.character(getRversion()) == lock$R)
for (package in names(lock$R_packages)) {
  version <- lock$R_packages[[package]]
  if (!requireNamespace(package, quietly = TRUE) || as.character(packageVersion(package)) != version)
    remotes::install_version(package, version = version, upgrade = "never", dependencies = NA)
  stopifnot(as.character(packageVersion(package)) == version)
}

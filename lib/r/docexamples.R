# Ordered transcript execution; guardian-controlled phase release before code.
args <- commandArgs(trailingOnly = TRUE)
directory <- args[[1]]
atomic_json <- function(name, value) {
  path <- file.path(directory, name)
  tmp <- paste0(path, ".R.tmp")
  writeLines(jsonlite::toJSON(value, auto_unbox = TRUE, null = "null"), tmp, useBytes = TRUE)
  if (!file.rename(tmp, path)) stop("atomic checkpoint rename failed")
}
if (!requireNamespace("jsonlite", quietly = TRUE)) {
  path <- file.path(directory, "result.json")
  writeLines('{"records":[],"versions":{},"error":"jsonlite unavailable","engine_missing":["jsonlite"]}', paste0(path, ".R.tmp"))
  file.rename(paste0(path, ".R.tmp"), path)
  stop("jsonlite unavailable")
}
input <- jsonlite::fromJSON(file.path(directory, "input.json"), simplifyVector = FALSE)
options(width = 80, encoding = "UTF-8", warn = 1)
Sys.setenv(LANG = "en_US.UTF-8")
records <- list()
payload <- 0
versions <- list(R = as.character(getRversion()))
result <- list(records = records, versions = versions, error = NULL)
checkpoint <- function() {
  result$records <<- records
  atomic_json("result.json", result)
  atomic_json("payload.json", list(bytes = payload))
}
release_phase <- function(sequence, phase, chunk = NULL) {
  atomic_json("phase-request.json", list(run_id = input$run_id, sequence = sequence, phase = phase, chunk = chunk))
  repeat {
    release <- tryCatch(jsonlite::fromJSON(file.path(directory,"phase-release.json")), error = function(e) NULL)
    if (!is.null(release) && identical(release$run_id, input$run_id) && identical(as.integer(release$sequence), as.integer(sequence))) break
    Sys.sleep(0.02)
  }
}
tryCatch({
  desc <- read.dcf(file.path(input$package, "DESCRIPTION"))
  dependency_fields <- intersect(c("Depends", "Imports", "LinkingTo"), colnames(desc))
  package_dependencies <- trimws(gsub("\\s*\\([^)]*\\)", "", unlist(strsplit(paste(desc[1,dependency_fields], collapse=","), ","))))
  package_dependencies <- setdiff(package_dependencies[nzchar(package_dependencies)], "R")
  required <- unique(c("pkgload", "evaluate", input$dependencies, package_dependencies))
  missing <- required[!vapply(required, requireNamespace, logical(1), quietly = TRUE)]
  if (length(missing)) {
    result$engine_missing <- as.list(unique(missing))
    stop(paste("dependencies unavailable:", paste(missing, collapse = ", ")))
  }
  for (p in unique(required)) versions[[p]] <- as.character(utils::packageVersion(p))
  release_phase(0L, "loading")
  pkgload::load_all(input$package, quiet = TRUE, export_all = FALSE)
  desc <- read.dcf(file.path(input$package, "DESCRIPTION"))
  result$package <- list(path = normalizePath(input$package), name = desc[1,"Package"], version = desc[1,"Version"])
  result$versions <- versions
  env <- new.env(parent = globalenv())
  for (i in seq_along(input$segments)) {
    segment <- input$segments[[i]]
    if (!segment$execute) next
    release_phase(i, paste0("segment-", i), segment$chunk)
    # Split evaluate's sink into a dedicated spool visible to the guardian even
    # inside a single expression. It never reaches the native stdout capture.
    spool <- file(file.path(directory, "evaluate-text"), open = "ab")
    sink(spool)
    count_condition <- function(value) {
      payload <<- payload + sum(nchar(enc2utf8(conditionMessage(value)), type="bytes"))
      atomic_json("payload.json", list(bytes = payload))
      value
    }
    handler <- evaluate::new_output_handler(message = count_condition,
                                            warning = count_condition, error = count_condition)
    values <- tryCatch(evaluate::evaluate(segment$code, envir = env, stop_on_error = 1L,
                                 keep_warning = TRUE, keep_message = TRUE,
                                 debug = TRUE, output_handler = handler),
                       finally = { sink(); close(spool) })
    output <- character(); failure <- NULL
    for (value in values) {
      if (inherits(value, "source") && length(parse(text = value$src))) {
        output <- character()
      }
      else if (inherits(value, "error")) failure <- conditionMessage(value)
      else if (inherits(value, "warning")) {
        if (segment$warning) output <- c(output, paste0("Warning: ", conditionMessage(value), "\n"))
      }
      else if (inherits(value, "message")) {
        if (segment$message) output <- c(output, conditionMessage(value))
      }
      else if (is.character(value) && isTRUE(segment$stdout)) output <- c(output, value)
    }
    records[[length(records)+1L]] <- list(id = segment$id, text = as.list(output), error = failure)
    checkpoint()
    if (!is.null(failure)) { result$error <- failure; break }
  }
}, error = function(e) { result$error <<- conditionMessage(e) })
checkpoint()

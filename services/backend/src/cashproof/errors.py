class ProcessingError(Exception):
    def __init__(self, code: str, message: str):
        super().__init__(code)  # Deliberately excludes case/model contents.
        self.code, self.message = code, message


MESSAGES = {
    "DECODE_FAILED": "The video could not be completely decoded.",
    "DEADLINE_EXCEEDED": "The processing deadline was exceeded.",
    "RESOURCE_EXHAUSTED": "The local inference resource budget was exceeded.",
    "WORKER_RESTARTED": "The worker stopped before atomic result publication.",
    "MODEL_OUTPUT_INVALID": "The local model output did not pass validation.",
    "ANALYSIS_INCOMPLETE": "The configured analysis could not be completed.",
    "PROCESSING_FAILED": "Local processing failed.",
}

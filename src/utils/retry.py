from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential


def network_retry():
    return retry(
        reraise=True,
        retry=retry_if_exception_type(Exception),
        wait=wait_exponential(multiplier=1, min=2, max=30),
        stop=stop_after_attempt(4),
    )

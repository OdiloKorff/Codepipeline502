from concurrent.futures import ThreadPoolExecutor


def generate_parallel(tasks, max_workers=4):
    """
    Execute tasks (callables) in parallel and return list of results.
    """
    results = []
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = [executor.submit(task) for task in tasks]
        for future in futures:
            results.append(future.result())
    return results

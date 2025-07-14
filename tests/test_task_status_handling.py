
from codepipeline.task_queue import TaskQueue

def test_status_lifecycle(tmp_path):
    q = TaskQueue(db_path=tmp_path / 'tasks.db')
    task_id = q.enqueue('dummy', {})
    task = q.fetch_next()
    assert task['id'] == task_id
    # simulate failure
    q.mark_failed(task_id, 'TypeError')
    assert q.get_status(task_id) == 'failed'
    # retry then success
    q.mark_retry(task_id, 'Intermittent')
    assert q.get_status(task_id) == 'retry'
    q.mark_success(task_id)
    assert q.get_status(task_id) == 'success'
    q.close()

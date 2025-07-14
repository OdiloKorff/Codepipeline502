def check_safety(pipeline_config):
    """
    Validate pipeline configuration dictionary.
    Raises ValueError if unsafe.
    """
    if not isinstance(pipeline_config, dict):
        raise ValueError("Invalid config type")
    # Example safety rule: must contain 'steps'
    if 'steps' not in pipeline_config or not pipeline_config['steps']:
        raise ValueError("Pipeline config must define non-empty 'steps'")
    return True
def file_path(instance, filename):
    """
    Where a model's uploaded or written files are stored: <model name>/<uuid>/<file name>,
    e.g. motionversion/<uuid>/out3d.json. The model needs a uuid field.
    """
    return f"{instance._meta.model_name}/{instance.uuid}/{filename}"

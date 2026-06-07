def hwc_mixed_001_01(vertices):
    """Takes an MxNx3 array and returns a 2D vertices and MxN face_indices arrays"""
    new_verts = []
    face_indices = []
    for wall in vertices:
        face_wall = []
        for vert in wall:
            if new_verts:
                if not np.isclose(vert, new_verts).all(axis=1).any():
                    new_verts.append(vert)
            else:
                    new_verts.append(vert)
            face_index = np.where(np.isclose(vert, new_verts).all(axis=1))[0][0]
            face_wall.append(face_index)
        face_indices.append(face_wall)
    return np.array(new_verts), np.array(face_indices) 

def hwc_mixed_001_02(experiments,
                    search_alg=None,
                    scheduler=None,
                    with_server=False,
                    server_port=TuneServer.DEFAULT_PORT,
                    verbose=2,
                    resume=False,
                    queue_trials=False,
                    reuse_actors=False,
                    trial_executor=None,
                    raise_on_failed_trial=True):
    """Runs and blocks until all trials finish.

    Examples:
        >>> experiment_spec = Experiment("experiment", my_func)
        >>> run_experiments(experiments=experiment_spec)

        >>> experiment_spec = {"experiment": {"run": my_func}}
        >>> run_experiments(experiments=experiment_spec)

        >>> run_experiments(
        >>>     experiments=experiment_spec,
        >>>     scheduler=MedianStoppingRule(...))

        >>> run_experiments(
        >>>     experiments=experiment_spec,
        >>>     search_alg=SearchAlgorithm(),
        >>>     scheduler=MedianStoppingRule(...))

    Returns:
        List of Trial objects, holding data for each executed trial.

    """
    # This is important to do this here
    # because it schematize the experiments
    # and it conducts the implicit registration.
    experiments = convert_to_experiment_list(experiments)

    trials = []
    for exp in experiments:
        trials += run(
            exp,
            search_alg=search_alg,
            scheduler=scheduler,
            with_server=with_server,
            server_port=server_port,
            verbose=verbose,
            resume=resume,
            queue_trials=queue_trials,
            reuse_actors=reuse_actors,
            trial_executor=trial_executor,
            raise_on_failed_trial=raise_on_failed_trial)
    return trials 

def agc_mixed_001_03(self, argv, help):
        """Print help"""
        if not argv:
            for cmd, txt in sorted(help.items()):
                first_line = txt.splitlines()[0] if txt else ""
                print(f"{cmd}: {first_line}")
        else:
            for cmd in argv:
                if cmd in help:
                    print(f"{cmd}:\n{help[cmd]}")
                else:
                    print(f"No help available for '{cmd}'") 

def agc_mixed_001_04(buffer):
        """
        Deserialize full object.

        Args:
            buffer (bytes, bytearray, BytesIO): (Optional) data to create the stream from.

        Returns:
            StorageItem:
        """
        import io, pickle

        # Prepare a stream from the provided buffer
        if buffer is None:
            return None
        if isinstance(buffer, (bytes, bytearray)):
            stream = io.BytesIO(buffer)
        elif hasattr(buffer, "read"):
            stream = buffer
        else:
            raise TypeError("buffer must be bytes, bytearray, or a file‑like object")

        # Deserialize the object (expected to be a StorageItem)
        obj = pickle.load(stream)
        return obj 

def hwc_mixed_001_05(self, sampling_req):
        """
        Determines whether or not this sampling rule applies to the incoming
        request based on some of the request's parameters.
        Any ``None`` parameter provided will be considered an implicit match.
        """
        if sampling_req is None:
            return False

        host = sampling_req.get('host', None)
        method = sampling_req.get('method', None)
        path = sampling_req.get('path', None)
        service = sampling_req.get('service', None)
        service_type = sampling_req.get('service_type', None)

        return (not host or wildcard_match(self._host, host)) \
            and (not method or wildcard_match(self._method, method)) \
            and (not path or wildcard_match(self._path, path)) \
            and (not service or wildcard_match(self._service, service)) \
            and (not service_type or wildcard_match(self._service_type, service_type)) 

def agc_mixed_001_06(delete_records):
    """Process the requests for S3 bucket deletions"""
    import boto3
    from botocore.exceptions import ClientError

    client = boto3.client('s3')
    deleted = []
    errors = []

    for record in delete_records:
        bucket = record.get('Bucket')
        key = record.get('Key')
        if not bucket or not key:
            errors.append((bucket, key, ValueError("Missing 'Bucket' or 'Key'")))
            continue
        try:
            client.delete_object(Bucket=bucket, Key=key)
            deleted.append((bucket, key))
        except ClientError as e:
            errors.append((bucket, key, e))

    return {'deleted': deleted, 'errors': errors}
